from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from api.views import HasRolePermission
from django.http import FileResponse, HttpResponseNotFound, StreamingHttpResponse
import os
import datetime
import codecs
from .models import MonitorTask
from .engine import monitor_engine
from django.forms.models import model_to_dict
try:
    import boto3
except ImportError:
    boto3 = None

def _get_s3_client(task):
    if not boto3:
        return None
    if not getattr(task, 's3_archive_enabled', False):
        return None
    if not getattr(task, 's3_bucket', ''):
        return None
    try:
        return boto3.client(
            's3',
            region_name=task.s3_region,
            aws_access_key_id=task.s3_access_key,
            aws_secret_access_key=task.s3_secret_key,
            endpoint_url=task.s3_endpoint or None
        )
    except Exception:
        return None

def _task_s3_prefixes(task):
    prefixes = [f"logs/monitor/{task.id}/"]
    if getattr(task, 'name', None):
        prefixes.append(f"logs/{task.name}/")
    return prefixes

def _iter_s3_lines(body_stream):
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    buf = ""
    for chunk in iter(lambda: body_stream.read(64 * 1024), b''):
        buf += decoder.decode(chunk)
        while True:
            nl = buf.find('\n')
            if nl == -1:
                break
            line = buf[:nl + 1]
            buf = buf[nl + 1:]
            yield line
    buf += decoder.decode(b'', final=True)
    if buf:
        yield buf

@api_view(['GET', 'POST'])
@permission_classes([HasRolePermission])
def monitor_tasks(request):
    if request.method == 'GET':
        tasks = MonitorTask.objects.all()
        return Response([model_to_dict(t) for t in tasks])
    elif request.method == 'POST':
        data = request.data
        task = MonitorTask.objects.create(
            name=data.get('name', 'New Monitor'),
            enabled=data.get('enabled', False),
            k8s_namespace=data.get('k8s_namespace', 'default'),
            k8s_kubeconfig=data.get('k8s_kubeconfig', ''),
            s3_archive_enabled=data.get('s3_archive_enabled', False),
            s3_bucket=data.get('s3_bucket', ''),
            s3_region=data.get('s3_region', 'us-east-1'),
            s3_access_key=data.get('s3_access_key', ''),
            s3_secret_key=data.get('s3_secret_key', ''),
            s3_endpoint=data.get('s3_endpoint', ''),
            retention_days=data.get('retention_days', 3),
            alert_enabled=data.get('alert_enabled', True),
            slack_webhook_url=data.get('slack_webhook_url', ''),
            poll_interval_seconds=data.get('poll_interval_seconds', 60),
            alert_keywords=data.get('alert_keywords', []),
            ignore_keywords=data.get('ignore_keywords', []),
            record_only_keywords=data.get('record_only_keywords', []),
            # New fields
            immediate_keywords=data.get('immediate_keywords', []),
            alert_threshold_count=data.get('alert_threshold_count', 5),
            alert_threshold_window=data.get('alert_threshold_window', 60),
            alert_silence_minutes=data.get('alert_silence_minutes', 60)
        )
        return Response(model_to_dict(task))

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([HasRolePermission])
def monitor_task_detail(request, pk):
    try:
        task = MonitorTask.objects.get(pk=pk)
    except MonitorTask.DoesNotExist:
        return Response({"error": "Task not found"}, status=404)
        
    if request.method == 'GET':
        return Response(model_to_dict(task))
        
    elif request.method == 'PUT':
        data = request.data
        for field in [
            "name", "enabled", "k8s_namespace", "k8s_kubeconfig", 
            "s3_archive_enabled", "s3_bucket", "s3_region", "s3_access_key", "s3_secret_key", "s3_endpoint",
            "retention_days", "alert_enabled", "slack_webhook_url", "poll_interval_seconds",
            "alert_keywords", "ignore_keywords", "record_only_keywords",
            "immediate_keywords", "alert_threshold_count", "alert_threshold_window", "alert_silence_minutes"
        ]:
            if field in data:
                setattr(task, field, data[field])
        task.save()
        
        # Trigger engine update if needed (engine loop should handle DB changes automatically)
        return Response(model_to_dict(task))
        
    elif request.method == 'DELETE':
        task.delete()
        return Response({"msg": "deleted"})

@api_view(['GET'])
@permission_classes([HasRolePermission])
def monitor_logs(request):
    task_id = request.query_params.get('task_id')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    search_query = request.query_params.get('search', '').lower()
    sort_by = request.query_params.get('sort_by', 'mtime') # name, size, mtime
    order = request.query_params.get('order', 'desc') # asc, desc
    log_type = (request.query_params.get('log_type') or 'all').lower()
    
    base_dir = monitor_engine.LOG_DIR
    if not task_id:
        return Response({"files": [], "total": 0})

    try:
        task = MonitorTask.objects.get(pk=task_id)
    except MonitorTask.DoesNotExist:
        return Response({"files": [], "total": 0})

    s3_client = _get_s3_client(task)
    if s3_client:
        files = []
        try:
            prefixes = _task_s3_prefixes(task)
            def is_error_key(key: str) -> bool:
                k = (key or '').lower()
                return ('/error/' in k) or k.endswith('_error.log') or ('task_errors_' in k)

            for prefix in prefixes:
                paginator = s3_client.get_paginator('list_objects_v2')
                for p in paginator.paginate(Bucket=task.s3_bucket, Prefix=prefix):
                    for obj in p.get('Contents', []) or []:
                        key = obj.get('Key') or ''
                        if not key.endswith(".log"):
                            continue
                        if log_type == 'error' and not is_error_key(key):
                            continue
                        if log_type == 'raw' and is_error_key(key):
                            continue
                        if search_query and search_query not in key.lower():
                            continue
                        lm = obj.get('LastModified')
                        mtime = lm.timestamp() if lm else 0
                        files.append({
                            "name": key,
                            "size": int(obj.get('Size') or 0),
                            "mtime": mtime
                        })
        except Exception as e:
            return Response({"error": str(e)}, status=500)

        reverse = (order == 'desc')
        if sort_by == 'name':
            files.sort(key=lambda x: x['name'], reverse=reverse)
        elif sort_by == 'size':
            files.sort(key=lambda x: x['size'], reverse=reverse)
        else:
            files.sort(key=lambda x: x['mtime'], reverse=reverse)

        total = len(files)
        start = (page - 1) * page_size
        end = start + page_size
        paged_files = files[start:end]
        return Response({"files": paged_files, "total": total, "page": page, "page_size": page_size})

    log_dir = os.path.join(base_dir, str(task_id))

    if not os.path.exists(log_dir):
        return Response({"files": [], "total": 0})
    
    files = []
    try:
        def is_error_name(name: str) -> bool:
            n = (name or '').lower()
            return n.endswith('_error.log') or ('task_errors_' in n)

        for f in os.listdir(log_dir):
            if f.endswith(".log"):
                # Filter by search query if provided
                if search_query and search_query not in f.lower():
                    continue
                if log_type == 'error' and not is_error_name(f):
                    continue
                if log_type == 'raw' and is_error_name(f):
                    continue
                    
                full_path = os.path.join(log_dir, f)
                stat = os.stat(full_path)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })
        
        # Sort logic
        reverse = (order == 'desc')
        if sort_by == 'name':
            files.sort(key=lambda x: x['name'], reverse=reverse)
        elif sort_by == 'size':
            files.sort(key=lambda x: x['size'], reverse=reverse)
        else: # mtime default
            files.sort(key=lambda x: x['mtime'], reverse=reverse)
            
        # Pagination
        total = len(files)
        start = (page - 1) * page_size
        end = start + page_size
        paged_files = files[start:end]
        
    except Exception as e:
        return Response({"error": str(e)}, status=500)
        
    return Response({
        "files": paged_files,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@api_view(['GET'])
@permission_classes([HasRolePermission])
def monitor_log_view(request):
    filename = request.query_params.get('filename')
    task_id = request.query_params.get('task_id')
    keyword = request.query_params.get('keyword')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 1000))
    reverse = request.query_params.get('reverse', 'false').lower() == 'true'
    
    if not filename or not task_id:
        return Response({"error": "filename and task_id required"}, status=400)

    try:
        task = MonitorTask.objects.get(pk=task_id)
    except MonitorTask.DoesNotExist:
        return Response({"error": "Task not found"}, status=404)

    s3_client = _get_s3_client(task)
    if s3_client:
        key = filename
        prefixes = _task_s3_prefixes(task)
        if not any(key.startswith(p) for p in prefixes):
            return Response({"error": "invalid parameters"}, status=400)

        try:
            head = s3_client.head_object(Bucket=task.s3_bucket, Key=key)
            size = int(head.get('ContentLength') or 0)
        except Exception:
            return Response({"error": "File not found"}, status=404)

        try:
            if keyword:
                results = []
                keywords = keyword.lower().split()
                obj = s3_client.get_object(Bucket=task.s3_bucket, Key=key)
                for i, line in enumerate(_iter_s3_lines(obj['Body']), 1):
                    ll = line.lower()
                    if all(k in ll for k in keywords):
                        results.append(line.rstrip('\n'))
                        if len(results) > 2000:
                            results.append("... (Matches truncated, found > 2000 lines) ...")
                            break
                return Response({"content": "\n".join(results), "is_search_result": True, "total": len(results)})

            MAX_SIZE_MB = 50
            if size > MAX_SIZE_MB * 1024 * 1024:
                if reverse and page == 1:
                    tail_bytes = min(size, 1024 * 1024)
                    start = max(0, size - tail_bytes)
                    obj = s3_client.get_object(Bucket=task.s3_bucket, Key=key, Range=f"bytes={start}-{size-1}")
                    text = obj['Body'].read().decode('utf-8', errors='replace')
                    lines = text.splitlines(True)
                    if lines and not text.endswith('\n'):
                        pass
                    lines = lines[-page_size:]
                    lines.reverse()
                    return Response({
                        "content": "".join(lines),
                        "total": page_size + 1,
                        "page": 1,
                        "page_size": page_size,
                        "warning": "File too large, showing last lines only."
                    })
                return Response({"error": "File too large"}, status=413)

            obj = s3_client.get_object(Bucket=task.s3_bucket, Key=key)
            text = obj['Body'].read().decode('utf-8', errors='replace')
            all_lines = text.splitlines(True)
            total = len(all_lines)
            if reverse:
                all_lines.reverse()
            if page == -1:
                import math
                page = max(1, math.ceil(total / page_size))
            start = (page - 1) * page_size
            end = start + page_size
            return Response({"content": "".join(all_lines[start:end]), "total": total, "page": page, "page_size": page_size})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    if os.path.sep in filename or '..' in filename or os.path.sep in task_id or '..' in task_id:
        return Response({"error": "invalid parameters"}, status=400)
         
    log_dir = os.path.join(monitor_engine.LOG_DIR, str(task_id))
    file_path = os.path.join(log_dir, filename)
    
    if not os.path.exists(file_path):
        return Response({"error": "File not found"}, status=404)
        
    try:
        # If keyword provided, we search (no pagination for search yet, or simple one)
        if keyword:
            results = []
            keywords = keyword.lower().split()
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f, 1):
                    line_lower = line.lower()
                    if all(k in line_lower for k in keywords):
                        results.append(line.rstrip())
                        if len(results) > 2000: 
                             results.append(f"... (Matches truncated, found > 2000 lines) ...")
                             break
            return Response({"content": "\n".join(results), "is_search_result": True, "total": len(results)})

        # Pagination logic - Optimized for large files
        # Instead of readlines(), we use a more memory efficient approach.
        # However, for reverse=True (show latest lines), we need to read from the end.
        
        # Simple optimization:
        # If file size is small (< 10MB), readlines() is fine.
        # If large, use 'tail' logic for reverse=True page=1.
        # Implementing full seek-based line pagination is complex due to variable line lengths.
        # We will stick to readlines for now but add a safety check for file size.
        
        file_size = os.path.getsize(file_path)
        MAX_SIZE_MB = 50
        
        if file_size > MAX_SIZE_MB * 1024 * 1024 and not keyword:
            # File too big, just read the last N bytes approx?
            # Or just fail?
            # Let's try to read only the last 20000 lines if it's too big?
            # Or just return a warning?
            # Implementing a safe "tail"
            if reverse and page == 1:
                # Read last N lines using a deque
                from collections import deque
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    # Read last page_size lines
                    all_lines = list(deque(f, page_size))
                    all_lines.reverse() # Latest first
                    total = page_size + 1 # Fake total to show there might be more
                    content = "".join(all_lines)
                    return Response({
                        "content": content,
                        "total": total, # Inaccurate but allows viewing
                        "page": 1,
                        "page_size": page_size,
                        "warning": "File too large, showing last lines only."
                    })
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            
        total = len(all_lines)
        
        # If reverse is requested (show latest logs first)
        if reverse:
            # For reverse view, page 1 means the last N lines.
            # But usually users want to scroll down to see older logs?
            # Or scroll down to see newer logs?
            # "Reverse display" usually means line N, N-1, N-2...
            # Let's implement simple reverse: just reverse the list of lines.
            all_lines.reverse()
        
        if page == -1: # Last page (useful for normal order to see tail)
            import math
            page = max(1, math.ceil(total / page_size))
            
        start = (page - 1) * page_size
        end = start + page_size
        
        # If reverse=True, we should return the *latest* N lines (first page)
        # The frontend logic for reverse is to show latest logs first.
        # So page 1 should be the *end* of the file if we were reading normally?
        # No, we already reversed `all_lines` if reverse=True.
        # So page 1 of reversed lines = the last N lines of the original file.
        # This is correct.
        
        content = "".join(all_lines[start:end])
        
        # Add warning if file is truncated (though we read all lines currently)
        # Optimization: We should probably use `seek` for huge files instead of readlines()
        # But user asked for "default 1m" display limit?
        # Actually user said "display 1m" maybe meaning file size limit or just default page size.
        # "默认分页 500" -> page_size=500 default.
        
        return Response({
            "content": content, 
            "total": total,
            "page": page,
            "page_size": page_size
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([HasRolePermission])
def monitor_log_download(request):
    filename = request.query_params.get('filename')
    task_id = request.query_params.get('task_id')
    
    if not filename or not task_id:
        return Response({"error": "filename and task_id required"}, status=400)

    try:
        task = MonitorTask.objects.get(pk=task_id)
    except MonitorTask.DoesNotExist:
        return HttpResponseNotFound("File not found")

    s3_client = _get_s3_client(task)
    if s3_client:
        key = filename
        prefixes = _task_s3_prefixes(task)
        if not any(key.startswith(p) for p in prefixes):
            return Response({"error": "invalid parameters"}, status=400)
        try:
            obj = s3_client.get_object(Bucket=task.s3_bucket, Key=key)
        except Exception:
            return HttpResponseNotFound("File not found")

        resp = StreamingHttpResponse(obj['Body'], content_type='text/plain; charset=utf-8')
        out_name = os.path.basename(key) or "log.log"
        resp['Content-Disposition'] = f'attachment; filename="{out_name}"'
        return resp

    if os.path.sep in filename or '..' in filename or os.path.sep in task_id or '..' in task_id:
        return Response({"error": "invalid parameters"}, status=400)
         
    log_dir = os.path.join(monitor_engine.LOG_DIR, str(task_id))
    file_path = os.path.join(log_dir, filename)
    
    if not os.path.exists(file_path):
        return HttpResponseNotFound("File not found")
        
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)

@api_view(['POST'])
@permission_classes([HasRolePermission])
def monitor_log_batch_search(request):
    data = request.data
    task_id = data.get('task_id')
    filenames = data.get('filenames', [])
    keyword = data.get('keyword', '')
    
    if not task_id or not filenames or not keyword:
        return Response({"error": "Missing parameters"}, status=400)

    try:
        task = MonitorTask.objects.get(pk=task_id)
    except MonitorTask.DoesNotExist:
        return Response({"results": []})

    s3_client = _get_s3_client(task)
    results = []
    MAX_TOTAL_RESULTS = 2000
    keywords = keyword.lower().split()

    if s3_client:
        prefixes = _task_s3_prefixes(task)
        for key in filenames:
            if not any(str(key).startswith(p) for p in prefixes):
                continue
            try:
                obj = s3_client.get_object(Bucket=task.s3_bucket, Key=key)
                for i, line in enumerate(_iter_s3_lines(obj['Body']), 1):
                    ll = line.lower()
                    if all(k in ll for k in keywords):
                        results.append({"file": key, "line": i, "content": line.strip()})
                        if len(results) >= MAX_TOTAL_RESULTS:
                            break
            except Exception:
                pass
            if len(results) >= MAX_TOTAL_RESULTS:
                break
        return Response({"results": results})

    log_dir = os.path.join(monitor_engine.LOG_DIR, str(task_id))
    for fname in filenames:
        if os.path.sep in fname or '..' in fname:
            continue
        fpath = os.path.join(log_dir, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f, 1):
                    line_lower = line.lower()
                    if all(k in line_lower for k in keywords):
                        results.append({"file": fname, "line": i, "content": line.strip()})
                        if len(results) >= MAX_TOTAL_RESULTS:
                            break
        except Exception:
            pass
        if len(results) >= MAX_TOTAL_RESULTS:
            break

    return Response({"results": results})
