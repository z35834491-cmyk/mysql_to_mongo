import base64
import hashlib
import uuid

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

DEPLOYMENT_MODES = [
    ("single", "Single"),
    ("cluster", "Cluster"),
]


def _build_cipher():
    digest = hashlib.sha256((settings.SECRET_KEY or "shark-platform").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class DatabaseConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)
    deployment_mode = models.CharField(max_length=16, choices=DEPLOYMENT_MODES, default="single")
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=3306)
    user = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    database = models.CharField(max_length=100, blank=True, null=True)
    extra_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.type})"


class DBInstance(models.Model):
    DB_TYPES = [
        ("mysql", "MySQL"),
        ("postgresql", "PostgreSQL"),
        ("redis", "Redis"),
        ("mongo", "MongoDB"),
        ("rabbitmq", "RabbitMQ"),
    ]
    ENV_TYPES = [
        ("dev", "Dev"),
        ("test", "Test"),
        ("staging", "Staging"),
        ("prod", "Prod"),
    ]

    name = models.CharField(max_length=128, unique=True)
    db_type = models.CharField(max_length=32, choices=DB_TYPES)
    deployment_mode = models.CharField(max_length=16, choices=DEPLOYMENT_MODES, default="single")
    environment = models.CharField(max_length=32, choices=ENV_TYPES, default="dev")
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    default_database = models.CharField(max_length=128, blank=True, default="")
    read_only = models.BooleanField(default=False)
    owner_team = models.CharField(max_length=128, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    extra_config = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, default="unknown")
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.db_type})"


class DBInstanceSecret(models.Model):
    instance = models.OneToOneField(DBInstance, on_delete=models.CASCADE, related_name="secret")
    auth_type = models.CharField(max_length=32, default="password")
    username = models.CharField(max_length=255, blank=True, default="")
    password_encrypted = models.TextField(blank=True, default="")
    ssl_mode = models.CharField(max_length=64, blank=True, default="")
    ssl_cert_encrypted = models.TextField(blank=True, default="")
    ssl_key_encrypted = models.TextField(blank=True, default="")
    kms_key_id = models.CharField(max_length=255, blank=True, default="")
    rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password: str):
        self.password_encrypted = _build_cipher().encrypt((raw_password or "").encode("utf-8")).decode("utf-8")

    def get_password(self) -> str:
        if not self.password_encrypted:
            return ""
        try:
            return _build_cipher().decrypt(self.password_encrypted.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError):
            return ""

    def __str__(self):
        return f"{self.instance.name} secret"


class DBAccessRule(models.Model):
    ACTION_CHOICES = [
        ("view", "View"),
        ("query", "Query"),
        ("dml", "DML"),
        ("ddl", "DDL"),
        ("approve", "Approve"),
        ("manage", "Manage"),
        ("backup", "Backup"),
    ]

    name = models.CharField(max_length=128)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="db_access_rules")
    group_name = models.CharField(max_length=150, blank=True, default="")
    instance = models.ForeignKey(DBInstance, null=True, blank=True, on_delete=models.CASCADE, related_name="access_rules")
    database_pattern = models.CharField(max_length=128, blank=True, default="*")
    table_pattern = models.CharField(max_length=128, blank=True, default="*")
    sql_types = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]


class SQLExecutionJob(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ai_reviewing", "AI Reviewing"),
        ("waiting_confirm", "Waiting Confirm"),
        ("waiting_approval", "Waiting Approval"),
        ("queued", "Queued"),
        ("running", "Running"),
        ("paused", "Paused"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    instance = models.ForeignKey(DBInstance, on_delete=models.CASCADE, related_name="sql_jobs")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="db_sql_jobs")
    database_name = models.CharField(max_length=128, blank=True, default="")
    sql_text = models.TextField()
    sql_hash = models.CharField(max_length=64, db_index=True)
    sql_type = models.CharField(max_length=32, blank=True, default="")
    execute_mode = models.CharField(max_length=32, default="auto_commit")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="draft")
    risk_level = models.CharField(max_length=32, default="low")
    trace_id = models.CharField(max_length=128, blank=True, default="")
    progress_percent = models.IntegerField(default=0)
    affected_rows = models.BigIntegerField(default=0)
    duration_ms = models.BigIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    execution_context = models.JSONField(default=dict, blank=True)
    cancel_requested = models.BooleanField(default=False)
    pause_requested = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class SQLAIReview(models.Model):
    job = models.OneToOneField(SQLExecutionJob, on_delete=models.CASCADE, related_name="ai_review")
    model_name = models.CharField(max_length=128, blank=True, default="")
    prompt_version = models.CharField(max_length=64, blank=True, default="")
    syntax_ok = models.BooleanField(default=True)
    security_risk_level = models.CharField(max_length=32, default="low")
    performance_risk_level = models.CharField(max_length=32, default="low")
    permission_risk_level = models.CharField(max_length=32, default="low")
    decision = models.CharField(max_length=32, default="allow")
    sql_summary = models.TextField(blank=True, default="")
    explain_summary = models.TextField(blank=True, default="")
    rewrite_sql = models.TextField(blank=True, default="")
    optimization_suggestions = models.JSONField(default=list, blank=True)
    blocking_reasons = models.JSONField(default=list, blank=True)
    raw_report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SQLExecutionResult(models.Model):
    job = models.OneToOneField(SQLExecutionJob, on_delete=models.CASCADE, related_name="result")
    result_type = models.CharField(max_length=32, default="table")
    columns_json = models.JSONField(default=list, blank=True)
    rows_json = models.JSONField(default=list, blank=True)
    total_rows = models.BigIntegerField(default=0)
    preview_rows = models.IntegerField(default=0)
    warnings_json = models.JSONField(default=list, blank=True)
    execution_stats_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SQLExecutionLog(models.Model):
    job = models.ForeignKey(SQLExecutionJob, on_delete=models.CASCADE, related_name="logs")
    seq = models.BigIntegerField()
    level = models.CharField(max_length=32, default="info")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seq", "created_at"]


class SQLApprovalOrder(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    job = models.ForeignKey(SQLExecutionJob, on_delete=models.CASCADE, related_name="approval_orders")
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submitted_db_sql_approvals")
    current_node = models.IntegerField(default=1)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    reason = models.TextField(blank=True, default="")
    cc_users_json = models.JSONField(default=list, blank=True)
    requested_flow_json = models.JSONField(default=list, blank=True)
    request_payload_json = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)


class SQLExecutionPolicy(models.Model):
    EXECUTE_MODES = [
        ("auto_commit", "Auto Commit"),
        ("transaction", "Transaction"),
        ("dry_run", "Dry Run"),
    ]

    name = models.CharField(max_length=128, unique=True)
    priority = models.IntegerField(default=100)
    environment_scope = models.JSONField(default=list, blank=True)
    db_type_scope = models.JSONField(default=list, blank=True)
    sql_type_scope = models.JSONField(default=list, blank=True)
    risk_scope = models.JSONField(default=list, blank=True)
    database_pattern = models.CharField(max_length=128, blank=True, default="*")
    auto_execute_mode = models.CharField(max_length=32, choices=EXECUTE_MODES, default="auto_commit")
    require_approval = models.BooleanField(default=False)
    allow_direct_execute = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "-updated_at", "-created_at"]


class SQLApprovalPolicy(models.Model):
    name = models.CharField(max_length=128, unique=True)
    environment_scope = models.JSONField(default=list, blank=True)
    db_type_scope = models.JSONField(default=list, blank=True)
    sql_type_scope = models.JSONField(default=list, blank=True)
    risk_scope = models.JSONField(default=list, blank=True)
    approval_flow = models.JSONField(default=list, blank=True)
    sla_minutes = models.IntegerField(default=60)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SQLApprovalStep(models.Model):
    ACTION_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    order = models.ForeignKey(SQLApprovalOrder, on_delete=models.CASCADE, related_name="steps")
    step_no = models.IntegerField(default=1)
    approver = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="db_sql_approval_steps")
    approver_role = models.CharField(max_length=128, blank=True, default="")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default="pending")
    comment = models.TextField(blank=True, default="")
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["step_no", "id"]


class SQLAuditLog(models.Model):
    job = models.OneToOneField(SQLExecutionJob, on_delete=models.CASCADE, related_name="audit")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    instance = models.ForeignKey(DBInstance, on_delete=models.CASCADE)
    database_name = models.CharField(max_length=128, blank=True, default="")
    sql_text = models.TextField()
    normalized_sql = models.TextField(blank=True, default="")
    sql_type = models.CharField(max_length=32, blank=True, default="")
    table_names_json = models.JSONField(default=list, blank=True)
    affected_rows = models.BigIntegerField(default=0)
    duration_ms = models.BigIntegerField(default=0)
    risk_level = models.CharField(max_length=32, default="low")
    before_image_json = models.JSONField(default=list, blank=True)
    after_image_json = models.JSONField(default=list, blank=True)
    txn_snapshot_json = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class BackupPlan(models.Model):
    BACKUP_TYPES = [
        ("logical", "Logical"),
        ("physical", "Physical"),
        ("snapshot", "Snapshot"),
    ]

    instance = models.ForeignKey(DBInstance, on_delete=models.CASCADE, related_name="backup_plans")
    name = models.CharField(max_length=128)
    backup_type = models.CharField(max_length=32, choices=BACKUP_TYPES, default="logical")
    schedule_expr = models.CharField(max_length=128, blank=True, default="")
    retention_days = models.IntegerField(default=7)
    storage_uri = models.CharField(max_length=255, blank=True, default="")
    storage_config = models.JSONField(default=dict, blank=True)
    compression_enabled = models.BooleanField(default=True)
    encryption_enabled = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_backup_plans")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]


class BackupRecord(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    plan = models.ForeignKey(BackupPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="records")
    instance = models.ForeignKey(DBInstance, on_delete=models.CASCADE, related_name="backup_records")
    backup_type = models.CharField(max_length=32, default="logical")
    file_uri = models.CharField(max_length=255, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    snapshot_ref = models.CharField(max_length=255, blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="")
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    metadata_json = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RestoreJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    RESTORE_MODES = [
        ("backup", "Backup"),
        ("point_in_time", "Point In Time"),
        ("transaction", "Transaction"),
    ]

    instance = models.ForeignKey(DBInstance, on_delete=models.CASCADE, related_name="restore_jobs")
    backup_record = models.ForeignKey(BackupRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="restore_jobs")
    restore_mode = models.CharField(max_length=32, choices=RESTORE_MODES, default="backup")
    target_time = models.DateTimeField(null=True, blank=True)
    target_txn_id = models.CharField(max_length=128, blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    log_json = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_restore_jobs")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RollbackJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("generated", "Generated"),
        ("approved", "Approved"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    source_audit = models.ForeignKey(SQLAuditLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="rollback_jobs")
    source_txn_id = models.CharField(max_length=128, blank=True, default="")
    instance = models.ForeignKey(DBInstance, on_delete=models.CASCADE, related_name="rollback_jobs")
    trace_id = models.CharField(max_length=128, blank=True, default="")
    rollback_sql = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    log_json = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_rollback_jobs")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
