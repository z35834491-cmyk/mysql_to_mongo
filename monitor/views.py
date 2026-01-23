from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse, HttpResponseNotFound
import os
from .models import MonitorTask
from .engine import monitor_engine
from django.forms.models import model_to_dict

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
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
            slack_webhook_url=data.get('slack_webhook_url', ''),
            poll_interval_seconds=data.get('poll_interval_seconds', 60),
            alert_keywords=data.get('alert_keywords', []),
            ignore_keywords=data.get('ignore_keywords', []),
            record_only_keywords=data.get('record_only_keywords', [])
        )
        return Response(model_to_dict(task))

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
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
            "retention_days", "slack_webhook_url", "poll_interval_seconds",
            "alert_keywords", "ignore_keywords", "record_only_keywords"
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
@permission_classes([IsAuthenticated])
def monitor_logs(request):
    task_id = request.query_params.get('task_id')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    
    base_dir = monitor_engine.LOG_DIR
    if task_id:
        log_dir = os.path.join(base_dir, str(task_id))
    else:
        return Response({"files": [], "total": 0})

    if not os.path.exists(log_dir):
        return Response({"files": [], "total": 0})
    
    files = []
    try:
        for f in os.listdir(log_dir):
            if f.endswith(".log"):
                full_path = os.path.join(log_dir, f)
                stat = os.stat(full_path)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })
        # Sort by mtime desc
        files.sort(key=lambda x: x['mtime'], reverse=True)
        
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
@permission_classes([IsAuthenticated])
def monitor_log_view(request):
    filename = request.query_params.get('filename')
    task_id = request.query_params.get('task_id')
    keyword = request.query_params.get('keyword')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 1000))
    reverse = request.query_params.get('reverse', 'false').lower() == 'true'
    
    if not filename or not task_id:
        return Response({"error": "filename and task_id required"}, status=400)
    
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

        # Pagination logic
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
        
        content = "".join(all_lines[start:end])
        
        return Response({
            "content": content, 
            "total": total,
            "page": page,
            "page_size": page_size
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def monitor_log_download(request):
    filename = request.query_params.get('filename')
    task_id = request.query_params.get('task_id')
    
    if not filename or not task_id:
        return Response({"error": "filename and task_id required"}, status=400)
    
    # Security check
    if os.path.sep in filename or '..' in filename or os.path.sep in task_id or '..' in task_id:
         return Response({"error": "invalid parameters"}, status=400)
         
    log_dir = os.path.join(monitor_engine.LOG_DIR, str(task_id))
    file_path = os.path.join(log_dir, filename)
    
    if not os.path.exists(file_path):
        return HttpResponseNotFound("File not found")
        
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def monitor_log_batch_search(request):
    data = request.data
    task_id = data.get('task_id')
    filenames = data.get('filenames', [])
    keyword = data.get('keyword', '')
    
    if not task_id or not filenames or not keyword:
        return Response({"error": "Missing parameters"}, status=400)
        
    log_dir = os.path.join(monitor_engine.LOG_DIR, str(task_id))
    results = []
    MAX_TOTAL_RESULTS = 2000
    
    keywords = keyword.lower().split()
    
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
                        results.append({
                            "file": fname,
                            "line": i,
                            "content": line.strip()
                        })
                        if len(results) >= MAX_TOTAL_RESULTS:
                            break
        except Exception:
            pass
            
        if len(results) >= MAX_TOTAL_RESULTS:
            break
            
    return Response({"results": results})

