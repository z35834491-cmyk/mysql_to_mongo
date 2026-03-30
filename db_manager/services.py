import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import requests
import sqlparse
from django.conf import settings
from django.utils import timezone

from ai_ops.models import AIConfig

from .engines import DBEngineFactory
from .models import BackupPlan, BackupRecord, DBAccessRule, DBInstance, DBInstanceSecret, RestoreJob, RollbackJob, SQLAIReview, SQLApprovalOrder, SQLApprovalPolicy, SQLAuditLog, SQLExecutionJob, SQLExecutionLog, SQLExecutionResult


JOB_THREADS = {}
JOB_LOCK = threading.Lock()
BACKUP_THREADS = {}
RESTORE_THREADS = {}
ROLLBACK_THREADS = {}


def _normalize_sql(sql: str) -> str:
    return sqlparse.format(sql or "", keyword_case="upper", strip_comments=False, reindent=True).strip()


def _hash_sql(sql: str) -> str:
    return hashlib.sha256((sql or "").encode("utf-8")).hexdigest()


def _sql_type(sql: str) -> str:
    parsed = sqlparse.parse(sql or "")
    if not parsed:
        return "UNKNOWN"
    for token in parsed[0].tokens:
        value = str(token).strip()
        if value:
            return value.split()[0].upper()
    return "UNKNOWN"


def _extract_tables(sql: str):
    return sorted(set(re.findall(r'(?:from|join|update|into|table)\s+[`"]?([a-zA-Z0-9_.-]+)', sql or "", re.IGNORECASE)))


def _backup_root():
    return Path(getattr(settings, "BASE_DIR", Path.cwd())) / "runtime" / "db_backups"


def _match_pattern(value: str, pattern: str) -> bool:
    if not pattern or pattern == "*":
        return True
    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(regex, value or "") is not None


def _user_rule_matches(rule: DBAccessRule, user) -> bool:
    if rule.user_id and rule.user_id == user.id:
        return True
    if rule.group_name and user.groups.filter(name=rule.group_name).exists():
        return True
    return False


def _rule_allows(rule: DBAccessRule, action: str, instance: DBInstance, database_name: str = "", table_names=None, sql_type: str = "") -> bool:
    if not rule.enabled:
        return False
    if rule.instance_id and rule.instance_id != instance.id:
        return False
    if action not in (rule.actions or []):
        return False
    if database_name and not _match_pattern(database_name, rule.database_pattern or "*"):
        return False
    if sql_type and rule.sql_types and sql_type not in rule.sql_types:
        return False
    for table_name in table_names or []:
        short_name = table_name.split(".")[-1]
        if not _match_pattern(short_name, rule.table_pattern or "*") and not _match_pattern(table_name, rule.table_pattern or "*"):
            return False
    return True


def filter_accessible_instances(user, queryset=None, action: str = "view"):
    queryset = queryset or DBInstance.objects.all()
    if user.is_superuser or user.is_staff:
        return queryset
    rules = list(DBAccessRule.objects.filter(enabled=True))
    allowed_ids = set()
    for rule in rules:
        if not _user_rule_matches(rule, user):
            continue
        if action not in (rule.actions or []):
            continue
        if rule.instance_id:
            allowed_ids.add(rule.instance_id)
        else:
            allowed_ids.update(queryset.values_list("id", flat=True))
    return queryset.filter(id__in=allowed_ids)


def ensure_instance_access(user, instance: DBInstance, action: str = "view", database_name: str = "", sql: str = ""):
    if user.is_superuser or user.is_staff:
        return
    sql_type = _sql_type(sql) if sql else ""
    table_names = _extract_tables(sql) if sql else []
    rules = DBAccessRule.objects.filter(enabled=True)
    for rule in rules:
        if not _user_rule_matches(rule, user):
            continue
        if _rule_allows(rule, action=action, instance=instance, database_name=database_name, table_names=table_names, sql_type=sql_type):
            return
    raise PermissionError("当前用户没有该实例或对象范围的操作权限")


def serialize_instance(instance: DBInstance):
    return {
        "id": instance.id,
        "name": instance.name,
        "db_type": instance.db_type,
        "environment": instance.environment,
        "host": instance.host,
        "port": instance.port,
        "default_database": instance.default_database,
        "read_only": instance.read_only,
        "owner_team": instance.owner_team,
        "tags": instance.tags,
        "extra_config": instance.extra_config,
        "status": instance.status,
        "last_health_check_at": instance.last_health_check_at,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
        "username": getattr(getattr(instance, "secret", None), "username", ""),
        "password_set": bool(getattr(getattr(instance, "secret", None), "password_encrypted", "")),
    }


def upsert_instance(data, user):
    instance_id = data.get("id")
    instance = DBInstance.objects.filter(id=instance_id).first() if instance_id else None
    if instance is None:
        instance = DBInstance(created_by=user)

    for field in ["name", "db_type", "environment", "host", "port", "default_database", "read_only", "owner_team", "tags", "extra_config"]:
        if field in data:
            setattr(instance, field, data.get(field))
    instance.save()

    secret = getattr(instance, "secret", None)
    if secret is None:
        secret = DBInstanceSecret(instance=instance)
    if "username" in data:
        secret.username = data.get("username") or ""
    if "password" in data and data.get("password") not in (None, ""):
        secret.set_password(data.get("password") or "")
    secret.save()
    return instance


def test_instance(instance: DBInstance):
    engine = DBEngineFactory.get_engine(instance)
    ok, message = engine.test()
    instance.status = "online" if ok else "error"
    instance.last_health_check_at = timezone.now()
    instance.save(update_fields=["status", "last_health_check_at", "updated_at"])
    return ok, message


def get_schema(instance: DBInstance):
    engine = DBEngineFactory.get_engine(instance)
    return engine.get_structure()


def get_table_detail(instance: DBInstance, database_name: str, table_name: str):
    engine = DBEngineFactory.get_engine(instance)
    if instance.db_type == "mysql":
        result = engine.query(database_name, table_name, {"page": 1, "pageSize": 20})
        return {"columns": result.get("headers", []), "sample_rows": result.get("rows", []), "total": result.get("total", 0)}
    if instance.db_type == "postgresql":
        result = engine.query(database_name, table_name, {"page": 1, "pageSize": 20})
        return {"columns": result.get("headers", []), "sample_rows": result.get("rows", []), "total": result.get("total", 0)}
    return {"columns": [], "sample_rows": [], "total": 0}


def explain_sql(instance: DBInstance, database_name: str, sql: str):
    engine = DBEngineFactory.get_engine(instance)
    if hasattr(engine, "explain") and instance.db_type in ("mysql", "postgresql"):
        return engine.explain(database_name or instance.default_database, sql)
    return {"headers": [], "rows": [], "total": 0}


def _heuristic_review(instance: DBInstance, sql: str, explain_result):
    normalized = _normalize_sql(sql)
    sql_type = _sql_type(normalized)
    findings_security = []
    findings_performance = []
    findings_permission = []
    suggestions = []
    blocking = []
    decision = "allow"
    risk_level = "low"

    lowered = normalized.lower()
    if sql_type in {"UPDATE", "DELETE"} and " where " not in f" {lowered} ":
        findings_security.append("检测到无 WHERE 的更新或删除语句。")
        blocking.append("禁止执行无 WHERE 的 UPDATE/DELETE。")
        decision = "block"
        risk_level = "critical"
    if sql_type in {"DROP", "TRUNCATE"}:
        findings_security.append("检测到高危破坏性 SQL。")
        blocking.append("生产环境建议走审批并在备份后执行。")
        decision = "block"
        risk_level = "critical"
    if sql_type == "ALTER":
        findings_performance.append("DDL 可能触发表锁或长时间元数据锁。")
        suggestions.append("建议评估在线 DDL 或维护窗口执行。")
        decision = "warn" if decision == "allow" else decision
        risk_level = "high" if risk_level in ("low", "medium") else risk_level
    if "select *" in lowered:
        findings_performance.append("存在 SELECT *，建议按需选择字段。")
        suggestions.append("减少返回字段，降低网络与排序成本。")
        if decision == "allow":
            decision = "warn"
        if risk_level == "low":
            risk_level = "medium"
    if " join " in lowered and " on " not in lowered:
        findings_security.append("JOIN 缺少明确 ON 条件，可能引发笛卡尔积。")
        if decision == "allow":
            decision = "warn"
        if risk_level == "low":
            risk_level = "medium"
    if instance.read_only and sql_type not in {"SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN"}:
        findings_permission.append("当前实例标记为只读，不允许执行写入类语句。")
        blocking.append("只读实例禁止写操作。")
        decision = "block"
        risk_level = "critical"
    if explain_result.get("rows"):
        findings_performance.append("已生成执行计划，可结合索引命中情况进一步确认。")

    return {
        "sql_type": sql_type,
        "risk_level": risk_level,
        "decision": decision,
        "syntax_ok": True,
        "security_risk_level": "high" if findings_security else "low",
        "performance_risk_level": "high" if findings_performance else "low",
        "permission_risk_level": "high" if findings_permission else "low",
        "sql_summary": f"{instance.db_type.upper()} {sql_type} 语句，涉及 {', '.join(_extract_tables(normalized)) or '未识别对象'}",
        "security_findings": findings_security,
        "performance_findings": findings_performance,
        "permission_findings": findings_permission,
        "optimization_suggestions": suggestions or ["建议先执行 EXPLAIN 并确认索引命中。"],
        "blocking_reasons": blocking,
        "rewrite_sql": normalized,
        "explain_summary": f"执行计划返回 {explain_result.get('total', 0)} 行。",
        "raw_report": {"explain": explain_result},
    }


def _call_llm_review(instance: DBInstance, database_name: str, sql: str, explain_result):
    cfg = AIConfig.get_active_config()
    if not cfg or not cfg.enable_ai_analysis or not cfg.api_key:
        return None
    prompt = (
        "你是数据库安全与性能专家，请输出严格 JSON。"
        "字段包括 decision,risk_level,sql_summary,security_findings,performance_findings,"
        "permission_findings,optimization_suggestions,blocking_reasons,rewrite_sql,explain_summary。"
        f"\n数据库类型: {instance.db_type}"
        f"\n环境: {instance.environment}"
        f"\n数据库: {database_name or instance.default_database}"
        f"\nSQL:\n{sql}"
        f"\n执行计划:\n{explain_result}"
    )
    payload = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg.temperature,
        "max_tokens": min(cfg.max_tokens, 1500),
    }
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    response = requests.post(f"{cfg.api_base}/chat/completions", headers=headers, json=payload, timeout=45)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM response is not valid JSON")
    report = requests.models.complexjson.loads(content[start:end + 1])
    report["raw_report"] = {"llm": report, "explain": explain_result}
    report.setdefault("syntax_ok", True)
    report.setdefault("security_risk_level", report.get("risk_level", "medium"))
    report.setdefault("performance_risk_level", report.get("risk_level", "medium"))
    report.setdefault("permission_risk_level", report.get("risk_level", "medium"))
    return report


def review_sql(instance: DBInstance, database_name: str, sql: str):
    explain_result = {"headers": [], "rows": [], "total": 0}
    sql_type = _sql_type(sql)
    if instance.db_type in ("mysql", "postgresql") and sql_type in {"SELECT", "UPDATE", "DELETE"}:
        try:
            explain_result = explain_sql(instance, database_name, sql)
        except Exception:
            explain_result = {"headers": [], "rows": [], "total": 0}
    heuristic = _heuristic_review(instance, sql, explain_result)
    try:
        llm_result = _call_llm_review(instance, database_name, sql, explain_result)
    except Exception:
        llm_result = None
    return llm_result or heuristic


def create_ai_review_job(instance: DBInstance, user, database_name: str, sql: str):
    ensure_instance_access(user, instance, action="query", database_name=database_name or instance.default_database, sql=sql)
    job = SQLExecutionJob.objects.create(
        instance=instance,
        user=user,
        database_name=database_name or instance.default_database,
        sql_text=sql,
        sql_hash=_hash_sql(sql),
        sql_type=_sql_type(sql),
        status="ai_reviewing",
    )
    report = review_sql(instance, database_name, sql)
    SQLAIReview.objects.create(
        job=job,
        model_name=AIConfig.get_active_config().model if AIConfig.get_active_config() else "",
        prompt_version="db-manager-v1",
        syntax_ok=report.get("syntax_ok", True),
        security_risk_level=report.get("security_risk_level", "low"),
        performance_risk_level=report.get("performance_risk_level", "low"),
        permission_risk_level=report.get("permission_risk_level", "low"),
        decision=report.get("decision", "allow"),
        sql_summary=report.get("sql_summary", ""),
        explain_summary=report.get("explain_summary", ""),
        rewrite_sql=report.get("rewrite_sql", ""),
        optimization_suggestions=report.get("optimization_suggestions", []),
        blocking_reasons=report.get("blocking_reasons", []),
        raw_report=report.get("raw_report", {}),
    )
    job.risk_level = report.get("risk_level", "low")
    job.status = "waiting_confirm"
    job.save(update_fields=["risk_level", "status", "updated_at"])
    return job, report


def need_approval(instance: DBInstance, sql: str, report=None):
    sql_type = _sql_type(sql)
    policies = SQLApprovalPolicy.objects.filter(enabled=True)
    for policy in policies:
        if policy.environment_scope and instance.environment not in policy.environment_scope:
            continue
        if policy.db_type_scope and instance.db_type not in policy.db_type_scope:
            continue
        if policy.sql_type_scope and sql_type not in policy.sql_type_scope:
            continue
        if policy.risk_scope and report and report.get("risk_level") not in policy.risk_scope:
            continue
        return True
    if instance.environment == "prod" and sql_type in {"ALTER", "DROP", "TRUNCATE", "UPDATE", "DELETE", "INSERT"}:
        return True
    if report and report.get("decision") == "warn":
        return True
    return False


def append_job_log(job: SQLExecutionJob, message: str, level: str = "info"):
    seq = (job.logs.order_by("-seq").first().seq + 1) if job.logs.exists() else 1
    SQLExecutionLog.objects.create(job=job, seq=seq, level=level, message=message)


def _write_audit(job: SQLExecutionJob, request_meta=None):
    SQLAuditLog.objects.update_or_create(
        job=job,
        defaults={
            "user": job.user,
            "instance": job.instance,
            "database_name": job.database_name,
            "sql_text": job.sql_text,
            "normalized_sql": _normalize_sql(job.sql_text),
            "sql_type": job.sql_type,
            "table_names_json": _extract_tables(job.sql_text),
            "affected_rows": job.affected_rows,
            "duration_ms": job.duration_ms,
            "risk_level": job.risk_level,
            "success": job.status == "success",
            "client_ip": (request_meta or {}).get("client_ip"),
            "user_agent": (request_meta or {}).get("user_agent", ""),
            "trace_id": (request_meta or {}).get("trace_id", ""),
        },
    )


def _run_sql_job(job_id: int, request_meta=None):
    job = SQLExecutionJob.objects.select_related("instance", "user").get(id=job_id)
    started = time.time()
    engine = DBEngineFactory.get_engine(job.instance)
    job.status = "running"
    job.progress_percent = 10
    job.started_at = timezone.now()
    job.save(update_fields=["status", "progress_percent", "started_at", "updated_at"])
    append_job_log(job, "SQL 作业开始执行")
    try:
        if job.execute_mode == "dry_run":
            result = {"headers": [], "rows": [], "affected_rows": 0, "execution_context": {}}
            append_job_log(job, "Dry Run 模式未实际执行 SQL")
        else:
            result = engine.execute_sql(job.database_name or job.instance.default_database, job.sql_text)
        SQLExecutionResult.objects.update_or_create(
            job=job,
            defaults={
                "result_type": "table",
                "columns_json": result.get("headers", []),
                "rows_json": result.get("rows", [])[:200],
                "total_rows": len(result.get("rows", [])),
                "preview_rows": min(len(result.get("rows", [])), 200),
                "warnings_json": [],
                "execution_stats_json": {"engine": job.instance.db_type},
            },
        )
        job.execution_context = result.get("execution_context", {})
        job.status = "success"
        job.progress_percent = 100
        job.affected_rows = result.get("affected_rows", len(result.get("rows", [])))
        job.duration_ms = int((time.time() - started) * 1000)
        job.finished_at = timezone.now()
        job.save(update_fields=["execution_context", "status", "progress_percent", "affected_rows", "duration_ms", "finished_at", "updated_at"])
        append_job_log(job, "SQL 作业执行成功", "success")
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.duration_ms = int((time.time() - started) * 1000)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "duration_ms", "finished_at", "updated_at"])
        append_job_log(job, f"SQL 作业执行失败: {exc}", "error")
    finally:
        _write_audit(job, request_meta=request_meta)
        with JOB_LOCK:
            JOB_THREADS.pop(job.id, None)


def create_execution_job(instance: DBInstance, user, database_name: str, sql: str, execute_mode: str, request_meta=None):
    action = "query"
    sql_type = _sql_type(sql)
    if sql_type in {"INSERT", "UPDATE", "DELETE", "MERGE"}:
        action = "dml"
    if sql_type in {"ALTER", "DROP", "TRUNCATE", "CREATE", "RENAME"}:
        action = "ddl"
    ensure_instance_access(user, instance, action=action, database_name=database_name or instance.default_database, sql=sql)
    report = review_sql(instance, database_name, sql)
    job = SQLExecutionJob.objects.create(
        instance=instance,
        user=user,
        database_name=database_name or instance.default_database,
        sql_text=sql,
        sql_hash=_hash_sql(sql),
        sql_type=_sql_type(sql),
        execute_mode=execute_mode,
        status="queued",
        risk_level=report.get("risk_level", "low"),
    )
    SQLAIReview.objects.update_or_create(
        job=job,
        defaults={
            "model_name": AIConfig.get_active_config().model if AIConfig.get_active_config() else "",
            "prompt_version": "db-manager-v1",
            "syntax_ok": report.get("syntax_ok", True),
            "security_risk_level": report.get("security_risk_level", "low"),
            "performance_risk_level": report.get("performance_risk_level", "low"),
            "permission_risk_level": report.get("permission_risk_level", "low"),
            "decision": report.get("decision", "allow"),
            "sql_summary": report.get("sql_summary", ""),
            "explain_summary": report.get("explain_summary", ""),
            "rewrite_sql": report.get("rewrite_sql", ""),
            "optimization_suggestions": report.get("optimization_suggestions", []),
            "blocking_reasons": report.get("blocking_reasons", []),
            "raw_report": report.get("raw_report", {}),
        },
    )
    if report.get("decision") == "block":
        job.status = "failed"
        job.error_message = "AI 预审阻断执行"
        job.save(update_fields=["status", "error_message", "updated_at"])
        append_job_log(job, "AI 预审阻断执行", "error")
        _write_audit(job, request_meta=request_meta)
        return job, report, None
    if need_approval(instance, sql, report=report):
        order = SQLApprovalOrder.objects.create(job=job, applicant=user, reason="命中审批策略")
        job.status = "waiting_approval"
        job.save(update_fields=["status", "updated_at"])
        append_job_log(job, "SQL 作业进入审批流程")
        return job, report, order
    start_job_async(job, request_meta=request_meta)
    return job, report, None


def start_job_async(job: SQLExecutionJob, request_meta=None):
    with JOB_LOCK:
        if job.id in JOB_THREADS:
            return
        thread = threading.Thread(target=_run_sql_job, args=(job.id, request_meta), daemon=True)
        JOB_THREADS[job.id] = thread
        thread.start()


def approve_order(order: SQLApprovalOrder, approver, request_meta=None):
    order.status = "approved"
    order.approved_at = timezone.now()
    order.save(update_fields=["status", "approved_at"])
    job = order.job
    append_job_log(job, f"审批通过，审批人: {approver.username}", "success")
    job.status = "queued"
    job.save(update_fields=["status", "updated_at"])
    start_job_async(job, request_meta=request_meta)


def reject_order(order: SQLApprovalOrder, approver, comment=""):
    order.status = "rejected"
    order.rejected_at = timezone.now()
    order.reason = comment or order.reason
    order.save(update_fields=["status", "rejected_at", "reason"])
    job = order.job
    job.status = "cancelled"
    job.error_message = "审批拒绝"
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
    append_job_log(job, f"审批拒绝，审批人: {approver.username}", "warning")
    _write_audit(job)


def cancel_job(job: SQLExecutionJob):
    job.cancel_requested = True
    ctx = job.execution_context or {}
    engine = DBEngineFactory.get_engine(job.instance)
    if hasattr(engine, "cancel_query"):
        thread_id = ctx.get("thread_id")
        backend_pid = ctx.get("backend_pid")
        engine.cancel_query(thread_id or backend_pid)
    job.status = "cancelled"
    job.finished_at = timezone.now()
    job.save(update_fields=["cancel_requested", "status", "finished_at", "updated_at"])
    append_job_log(job, "SQL 作业已取消", "warning")
    _write_audit(job)


def pause_job(job: SQLExecutionJob):
    job.pause_requested = True
    if job.status == "queued":
        job.status = "paused"
    job.save(update_fields=["pause_requested", "status", "updated_at"])
    append_job_log(job, "已请求暂停 SQL 作业", "warning")


def resume_job(job: SQLExecutionJob, request_meta=None):
    if job.status == "paused":
        job.pause_requested = False
        job.status = "queued"
        job.save(update_fields=["pause_requested", "status", "updated_at"])
        append_job_log(job, "SQL 作业恢复排队")
        start_job_async(job, request_meta=request_meta)


def serialize_backup_plan(plan: BackupPlan):
    return {
        "id": plan.id,
        "instance": plan.instance_id,
        "instance_name": plan.instance.name,
        "name": plan.name,
        "backup_type": plan.backup_type,
        "schedule_expr": plan.schedule_expr,
        "retention_days": plan.retention_days,
        "storage_uri": plan.storage_uri,
        "enabled": plan.enabled,
        "last_run_at": plan.last_run_at,
        "next_run_at": plan.next_run_at,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def serialize_access_rule(rule: DBAccessRule):
    return {
        "id": rule.id,
        "name": rule.name,
        "user_id": rule.user_id,
        "username": rule.user.username if rule.user_id else "",
        "group_name": rule.group_name,
        "instance": rule.instance_id,
        "instance_name": rule.instance.name if rule.instance_id else "全部实例",
        "database_pattern": rule.database_pattern,
        "table_pattern": rule.table_pattern,
        "sql_types": rule.sql_types,
        "actions": rule.actions,
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def upsert_access_rule(data):
    rule_id = data.get("id")
    rule = DBAccessRule.objects.filter(id=rule_id).first() if rule_id else None
    if rule is None:
        rule = DBAccessRule()
    for field in ["name", "group_name", "database_pattern", "table_pattern", "sql_types", "actions", "enabled"]:
        if field in data:
            setattr(rule, field, data.get(field))
    if "user_id" in data:
        rule.user_id = data.get("user_id") or None
    if "instance" in data:
        instance_value = data.get("instance")
        if isinstance(instance_value, DBInstance):
            rule.instance = instance_value
        else:
            rule.instance_id = instance_value or None
    rule.save()
    return rule


def _run_command(command, env=None):
    process = subprocess.run(command, env=env, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "command failed")
    return process.stdout.strip()


def _build_db_cli_env(instance: DBInstance):
    env = os.environ.copy()
    password = getattr(getattr(instance, "secret", None), "get_password", lambda: "")() or ""
    if instance.db_type == "mysql":
        env["MYSQL_PWD"] = password
    if instance.db_type == "postgresql":
        env["PGPASSWORD"] = password
    return env


def _backup_file_path(plan: BackupPlan):
    ext_map = {
        "mysql": "sql",
        "postgresql": "sql",
        "redis": "rdb",
        "mongo": "archive",
        "rabbitmq": "json",
    }
    base_dir = _backup_root() / plan.instance.name
    base_dir.mkdir(parents=True, exist_ok=True)
    ext = ext_map.get(plan.instance.db_type, "bak")
    return base_dir / f"{plan.name}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}"


def _execute_backup(record_id: int):
    record = BackupRecord.objects.select_related("plan", "instance", "instance__secret").get(id=record_id)
    plan = record.plan
    instance = record.instance
    record.status = "running"
    record.started_at = timezone.now()
    record.save(update_fields=["status", "started_at"])
    plan.last_run_at = timezone.now()
    plan.save(update_fields=["last_run_at", "updated_at"])
    file_path = Path(record.file_uri)
    if str(record.file_uri).startswith("local://"):
        file_path = _backup_root() / record.file_uri.replace("local://", "").lstrip("/")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    env = _build_db_cli_env(instance)
    metadata = dict(record.metadata_json or {})
    try:
        if instance.db_type == "mysql":
            cmd = [
                shutil.which("mysqldump") or "mysqldump",
                "-h", instance.host,
                "-P", str(instance.port),
                "-u", getattr(instance.secret, "username", ""),
                "--single-transaction",
                instance.default_database or "mysql",
            ]
            result = subprocess.run(cmd, env=env, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode("utf-8", errors="ignore") or "mysqldump failed")
            file_path.write_bytes(result.stdout)
        elif instance.db_type == "postgresql":
            cmd = [
                shutil.which("pg_dump") or "pg_dump",
                "-h", instance.host,
                "-p", str(instance.port),
                "-U", getattr(instance.secret, "username", ""),
                "-d", instance.default_database or "postgres",
                "-f", str(file_path),
            ]
            _run_command(cmd, env=env)
        elif instance.db_type == "mongo":
            cmd = [
                shutil.which("mongodump") or "mongodump",
                f"--host={instance.host}",
                f"--port={instance.port}",
                f"--username={getattr(instance.secret, 'username', '')}",
                f"--password={getattr(instance.secret, 'get_password', lambda: '')()}",
                f"--db={instance.default_database or 'admin'}",
                f"--archive={file_path}",
            ]
            _run_command(cmd, env=env)
        elif instance.db_type == "redis":
            cmd = [
                shutil.which("redis-cli") or "redis-cli",
                "-h", instance.host,
                "-p", str(instance.port),
                "--rdb", str(file_path),
            ]
            if getattr(instance.secret, "get_password", lambda: "")():
                cmd.extend(["-a", getattr(instance.secret, "get_password", lambda: "")()])
            _run_command(cmd, env=env)
        else:
            raise RuntimeError(f"{instance.db_type} 暂未支持真实备份")
        record.file_size = file_path.stat().st_size if file_path.exists() else 0
        record.status = "success"
        record.finished_at = timezone.now()
        metadata["executor"] = "real"
        record.metadata_json = metadata
        record.save(update_fields=["file_size", "status", "finished_at", "metadata_json"])
    except Exception as exc:
        record.status = "failed"
        record.finished_at = timezone.now()
        metadata["error"] = str(exc)
        record.metadata_json = metadata
        record.save(update_fields=["status", "finished_at", "metadata_json"])
    finally:
        with JOB_LOCK:
            BACKUP_THREADS.pop(record.id, None)


def upsert_backup_plan(data, user):
    plan_id = data.get("id")
    plan = BackupPlan.objects.filter(id=plan_id).first() if plan_id else None
    if plan is None:
        plan = BackupPlan(created_by=user)
    if "instance" in data:
        instance_value = data.get("instance")
        if isinstance(instance_value, DBInstance):
            plan.instance = instance_value
        else:
            plan.instance_id = instance_value
    for field in ["name", "backup_type", "schedule_expr", "retention_days", "storage_uri", "enabled"]:
        if field in data:
            setattr(plan, field, data.get(field))
    plan.save()
    return plan


def run_backup_plan(plan: BackupPlan):
    now = timezone.now()
    file_path = _backup_file_path(plan)
    record = BackupRecord.objects.create(
        plan=plan,
        instance=plan.instance,
        backup_type=plan.backup_type,
        file_uri=str(file_path),
        file_size=0,
        snapshot_ref=f"{plan.instance.name}-{now.strftime('%Y%m%d%H%M%S')}",
        status="pending",
        metadata_json={
            "schedule_expr": plan.schedule_expr,
            "retention_days": plan.retention_days,
            "instance": plan.instance.name,
            "storage_uri": plan.storage_uri,
        },
    )
    plan.last_run_at = now
    plan.next_run_at = now
    plan.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
    with JOB_LOCK:
        if record.id not in BACKUP_THREADS:
            thread = threading.Thread(target=_execute_backup, args=(record.id,), daemon=True)
            BACKUP_THREADS[record.id] = thread
            thread.start()
    return record


def _execute_restore(job_id: int):
    job = RestoreJob.objects.select_related("instance", "instance__secret", "backup_record").get(id=job_id)
    job.status = "running"
    job.started_at = timezone.now()
    logs = list(job.log_json or [])
    logs.append({"time": timezone.now().isoformat(), "message": "开始执行恢复任务"})
    job.log_json = logs
    job.save(update_fields=["status", "started_at", "log_json"])
    instance = job.instance
    env = _build_db_cli_env(instance)
    try:
        if not job.backup_record or not job.backup_record.file_uri:
            raise RuntimeError("缺少备份文件")
        file_path = Path(job.backup_record.file_uri)
        if instance.db_type == "mysql":
            cmd = [
                shutil.which("mysql") or "mysql",
                "-h", instance.host,
                "-P", str(instance.port),
                "-u", getattr(instance.secret, "username", ""),
                instance.default_database or "mysql",
            ]
            with open(file_path, "rb") as fp:
                process = subprocess.run(cmd, env=env, stdin=fp, capture_output=True)
            if process.returncode != 0:
                raise RuntimeError(process.stderr.decode("utf-8", errors="ignore") or "mysql restore failed")
        elif instance.db_type == "postgresql":
            cmd = [
                shutil.which("psql") or "psql",
                "-h", instance.host,
                "-p", str(instance.port),
                "-U", getattr(instance.secret, "username", ""),
                "-d", instance.default_database or "postgres",
                "-f", str(file_path),
            ]
            _run_command(cmd, env=env)
        elif instance.db_type == "mongo":
            cmd = [
                shutil.which("mongorestore") or "mongorestore",
                f"--host={instance.host}",
                f"--port={instance.port}",
                f"--username={getattr(instance.secret, 'username', '')}",
                f"--password={getattr(instance.secret, 'get_password', lambda: '')()}",
                f"--archive={file_path}",
                "--drop",
            ]
            _run_command(cmd, env=env)
        elif instance.db_type == "redis":
            raise RuntimeError("Redis 恢复需替换 RDB/AOF 文件，当前版本不支持在线恢复")
        else:
            raise RuntimeError(f"{instance.db_type} 暂未支持真实恢复")
        logs.append({"time": timezone.now().isoformat(), "message": "恢复任务执行成功"})
        job.status = "success"
        job.finished_at = timezone.now()
        job.log_json = logs
        job.save(update_fields=["status", "finished_at", "log_json"])
    except Exception as exc:
        logs.append({"time": timezone.now().isoformat(), "message": f"恢复失败: {exc}"})
        job.status = "failed"
        job.finished_at = timezone.now()
        job.log_json = logs
        job.save(update_fields=["status", "finished_at", "log_json"])
    finally:
        with JOB_LOCK:
            RESTORE_THREADS.pop(job.id, None)


def create_restore_job(instance_id, backup_record_id=None, restore_mode="backup", target_time=None, target_txn_id="", user=None):
    job = RestoreJob.objects.create(
        instance_id=instance_id,
        backup_record_id=backup_record_id or None,
        restore_mode=restore_mode,
        target_time=target_time,
        target_txn_id=target_txn_id or "",
        status="pending",
        log_json=[
            {"time": timezone.now().isoformat(), "message": "已创建恢复任务"},
            {"time": timezone.now().isoformat(), "message": "已进入恢复队列"},
        ],
        created_by=user,
    )
    with JOB_LOCK:
        if job.id not in RESTORE_THREADS:
            thread = threading.Thread(target=_execute_restore, args=(job.id,), daemon=True)
            RESTORE_THREADS[job.id] = thread
            thread.start()
    return job


def _build_rollback_sql(audit: SQLAuditLog):
    sql_type = (audit.sql_type or "").upper()
    sql = audit.normalized_sql or audit.sql_text or ""
    tables = audit.table_names_json or []
    table_name = tables[0].split(".")[-1] if tables else "target_table"
    if sql_type == "INSERT":
        return f"-- 请补充主键条件\nDELETE FROM {table_name} WHERE <primary_key_condition>;"
    if sql_type == "UPDATE":
        return f"-- 请根据审计记录补充回滚前字段值\nUPDATE {table_name} SET <column>=<old_value> WHERE <primary_key_condition>;"
    if sql_type == "DELETE":
        return f"-- 请根据备份或审计快照补充被删除记录\nINSERT INTO {table_name} (<columns>) VALUES (<old_values>);"
    if sql_type in {"ALTER", "DROP", "TRUNCATE", "CREATE"}:
        return f"-- {sql_type} 属于结构变更，建议优先使用备份恢复或 PITR\n-- 原始 SQL:\n{sql}"
    return f"-- 未识别的回滚模板，请人工评估\n-- 原始 SQL:\n{sql}"


def serialize_rollback_job(job: RollbackJob):
    return {
        "id": job.id,
        "source_audit": job.source_audit_id,
        "source_txn_id": job.source_txn_id,
        "instance": job.instance_id,
        "instance_name": job.instance.name,
        "rollback_sql": job.rollback_sql,
        "status": job.status,
        "log_json": job.log_json,
        "created_by": job.created_by_id,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "created_at": job.created_at,
    }


def _execute_rollback(job_id: int):
    job = RollbackJob.objects.select_related("instance", "instance__secret").get(id=job_id)
    logs = list(job.log_json or [])
    logs.append({"time": timezone.now().isoformat(), "message": "开始执行回滚 SQL"})
    job.status = "running"
    job.started_at = timezone.now()
    job.log_json = logs
    job.save(update_fields=["status", "started_at", "log_json"])
    try:
        if not job.rollback_sql.strip():
            raise RuntimeError("回滚 SQL 为空")
        engine = DBEngineFactory.get_engine(job.instance)
        engine.execute_sql(job.instance.default_database, job.rollback_sql)
        logs.append({"time": timezone.now().isoformat(), "message": "回滚 SQL 执行成功"})
        job.status = "success"
        job.finished_at = timezone.now()
        job.log_json = logs
        job.save(update_fields=["status", "finished_at", "log_json"])
    except Exception as exc:
        logs.append({"time": timezone.now().isoformat(), "message": f"回滚失败: {exc}"})
        job.status = "failed"
        job.finished_at = timezone.now()
        job.log_json = logs
        job.save(update_fields=["status", "finished_at", "log_json"])
    finally:
        with JOB_LOCK:
            ROLLBACK_THREADS.pop(job.id, None)


def create_rollback_job(instance: DBInstance, user, audit: SQLAuditLog = None, source_txn_id: str = ""):
    rollback_sql = _build_rollback_sql(audit) if audit else "-- 请手工补充回滚 SQL"
    job = RollbackJob.objects.create(
        source_audit=audit,
        source_txn_id=source_txn_id or "",
        instance=instance,
        rollback_sql=rollback_sql,
        status="generated",
        log_json=[
            {"time": timezone.now().isoformat(), "message": "已生成回滚任务"},
            {"time": timezone.now().isoformat(), "message": "请确认回滚 SQL 后执行"},
        ],
        created_by=user,
    )
    return job


def execute_rollback_job(job: RollbackJob):
    with JOB_LOCK:
        if job.id not in ROLLBACK_THREADS:
            thread = threading.Thread(target=_execute_rollback, args=(job.id,), daemon=True)
            ROLLBACK_THREADS[job.id] = thread
            thread.start()


def export_audit_rows(queryset):
    rows = []
    for item in queryset:
        rows.append({
            "id": item.id,
            "job_id": item.job_id,
            "instance_name": item.instance.name,
            "username": item.user.username,
            "database_name": item.database_name,
            "sql_type": item.sql_type,
            "risk_level": item.risk_level,
            "affected_rows": item.affected_rows,
            "duration_ms": item.duration_ms,
            "success": item.success,
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "sql_text": item.sql_text,
        })
    return rows


def run_instance_diagnostics(instance: DBInstance):
    report = {
        "instance": serialize_instance(instance),
        "checks": [],
        "summary": {},
    }
    ok, message = test_instance(instance)
    report["checks"].append({"name": "连接测试", "status": "success" if ok else "failed", "message": message})
    try:
        structure = get_schema(instance)
        schema_count = len(structure.keys()) if isinstance(structure, dict) else 0
        table_count = sum(len(v) for v in structure.values()) if isinstance(structure, dict) else 0
        report["checks"].append({"name": "Schema 读取", "status": "success", "message": f"{schema_count} 个 schema / {table_count} 张表"})
        report["summary"]["schema_count"] = schema_count
        report["summary"]["table_count"] = table_count
    except Exception as exc:
        report["checks"].append({"name": "Schema 读取", "status": "failed", "message": str(exc)})
    report["summary"]["backup_plan_count"] = instance.backup_plans.count()
    report["summary"]["latest_backup_status"] = instance.backup_records.order_by("-created_at").values_list("status", flat=True).first() or "none"
    report["summary"]["sql_job_count"] = instance.sql_jobs.count()
    report["summary"]["failed_sql_jobs"] = instance.sql_jobs.filter(status="failed").count()
    report["checks"].append({
        "name": "备份状态",
        "status": "success" if report["summary"]["latest_backup_status"] in ("success", "none") else "warning",
        "message": f'计划 {report["summary"]["backup_plan_count"]} 条，最近备份状态 {report["summary"]["latest_backup_status"]}',
    })
    report["checks"].append({
        "name": "作业状态",
        "status": "success" if report["summary"]["failed_sql_jobs"] == 0 else "warning",
        "message": f'共 {report["summary"]["sql_job_count"]} 条 SQL 作业，失败 {report["summary"]["failed_sql_jobs"]} 条',
    })
    return report
