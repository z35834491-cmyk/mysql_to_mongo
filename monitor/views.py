from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import FileResponse, HttpResponseNotFound
import os
from .models import MonitorTask
from .engine import monitor_engine
from django.forms.models import model_to_dict

@api_view(['GET', 'POST'])
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
def monitor_logs(request):
    # Optional task_id filter
    task_id = request.query_params.get('task_id')
    
    base_dir = monitor_engine.LOG_DIR
    if task_id:
        # Check if task log dir exists
        log_dir = os.path.join(base_dir, str(task_id))
    else:
        # If no task_id, maybe list all logs recursively? 
        # For now let's return empty or require task_id. 
        # Actually user wants "Click into task -> show logs". So task_id is expected.
        return Response([])

    if not os.path.exists(log_dir):
        return Response([])
    
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
    except Exception as e:
        return Response({"error": str(e)}, status=500)
        
    return Response(files)

@api_view(['GET'])
def monitor_log_view(request):
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
        return Response({"error": "File not found"}, status=404)
        
    try:
        # Read file content. Limit to last 100KB to prevent huge payloads
        stat = os.stat(file_path)
        size = stat.st_size
        max_read = 100 * 1024 # 100KB
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            if size > max_read:
                f.seek(size - max_read)
                content = f.read()
                # If we started in the middle of a line, skip first partial line
                first_newline = content.find('\n')
                if first_newline != -1:
                    content = content[first_newline+1:]
                content = f"... (showing last {len(content)} bytes) ...\n" + content
            else:
                content = f.read()
                
        return Response({"content": content})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
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
def monitor_log_multi_search(request):
    data = request.data
    task_id = data.get('task_id')
    filenames = data.get('filenames', [])
    keyword = data.get('keyword', '')
    
    if not task_id or not filenames or not keyword:
        return Response({"error": "Missing parameters"}, status=400)
        
    log_dir = os.path.join(monitor_engine.LOG_DIR, str(task_id))
    results = []
    
    # Simple AND logic for keywords (space separated)
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
                        # Limit results per file to avoid explosion
                        if len(results) > 5000: 
                            break
        except Exception as e:
            continue
            
        if len(results) > 5000:
            break
            
    return Response(results)

