
# --- Global Logs ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def log_files_list(request):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        return Response({"files": []})
        
    files = []
    try:
        for f in os.listdir(log_dir):
            if f.endswith(".log"):
                p = os.path.join(log_dir, f)
                stat = os.stat(p)
                size_mb = round(stat.st_size / (1024 * 1024), 2)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                files.append({
                    "name": f,
                    "size": f"{size_mb} MB",
                    "bytes": stat.st_size,
                    "mtime": mtime
                })
        # Sort by mtime desc
        files.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception as e:
        return Response({"detail": str(e)}, status=500)
        
    return Response({"files": files})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def log_stats(request):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        return Response({"stats": {"error": 0, "warning": 0, "info": 0}, "series": []})
        
    # Aggregate stats from all log files (last 1000 lines each for performance)
    total_error = 0
    total_warn = 0
    total_info = 0
    
    # Simple time-series distribution (mock or rough estimate based on timestamps)
    # For real accurate time-series, we'd need to parse timestamps. 
    # Let's do a simple parsing of the last few lines to generate a trend for "Today"
    
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Bucket by hour: {"10:00": 5, "11:00": 12}
    hourly_errors = {}
    
    try:
        for f in os.listdir(log_dir):
            if not f.endswith(".log"): 
                continue
                
            p = os.path.join(log_dir, f)
            try:
                # Read last 2000 lines efficiently? For now just read lines
                with open(p, "r", encoding="utf-8", errors='ignore') as fo:
                    # Reading full file might be slow if huge. 
                    # Let's assume files rotate or aren't massive for this demo.
                    # Or use a seek to tail.
                    fo.seek(0, 2)
                    size = fo.tell()
                    # Read last 1MB
                    fo.seek(max(0, size - 1024*1024), 0)
                    lines = fo.readlines()
                    
                    for line in lines:
                        if "ERROR" in line or "CRITICAL" in line or "Exception" in line:
                            total_error += 1
                            # Extract time [2026-01-23 10:00:00]
                            if line.startswith("["):
                                try:
                                    # [2026-01-23 10:00:00]
                                    ts_str = line[1:20]
                                    if ts_str.startswith(today_str):
                                        hour = ts_str[11:13] + ":00"
                                        hourly_errors[hour] = hourly_errors.get(hour, 0) + 1
                                except:
                                    pass
                        elif "WARNING" in line:
                            total_warn += 1
                        else:
                            total_info += 1
            except Exception:
                pass
                
    except Exception as e:
        pass
        
    # Fill missing hours for chart
    hours = sorted(hourly_errors.keys())
    series_data = [hourly_errors[h] for h in hours]
    
    return Response({
        "summary": {
            "error": total_error,
            "warning": total_warn,
            "info": total_info
        },
        "trend": {
            "hours": hours,
            "errors": series_data
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def log_global_search(request):
    keyword = request.GET.get('q', '').strip()
    if not keyword:
        return Response({"matches": []})
        
    log_dir = "logs"
    matches = []
    MAX_MATCHES = 100
    
    try:
        for f in os.listdir(log_dir):
            if not f.endswith(".log"): continue
            p = os.path.join(log_dir, f)
            
            try:
                with open(p, "r", encoding="utf-8", errors='ignore') as fo:
                    for i, line in enumerate(fo):
                        if keyword.lower() in line.lower():
                            matches.append({
                                "file": f,
                                "line": i + 1,
                                "content": line.strip()[:300] # Truncate long lines
                            })
                            if len(matches) >= MAX_MATCHES:
                                break
            except:
                pass
            if len(matches) >= MAX_MATCHES:
                break
    except Exception as e:
        return Response({"detail": str(e)}, status=500)
        
    return Response({"matches": matches})
