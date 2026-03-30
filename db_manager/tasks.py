from celery import shared_task

from .services import _execute_backup, _execute_restore, _execute_rollback, _run_sql_job


@shared_task(name="db_manager.run_sql_job")
def run_sql_job(job_id, request_meta=None):
    _run_sql_job(job_id, request_meta=request_meta or {})


@shared_task(name="db_manager.run_backup_record")
def run_backup_record(record_id):
    _execute_backup(record_id)


@shared_task(name="db_manager.run_restore_job")
def run_restore_job(job_id):
    _execute_restore(job_id)


@shared_task(name="db_manager.run_rollback_job")
def run_rollback_job(job_id):
    _execute_rollback(job_id)
