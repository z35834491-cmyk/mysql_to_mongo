from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.models import User, Group
import psutil
from inspection.models import InspectionConfig
import requests

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_stats(request):
    # ... (existing code) ...
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    cfg = InspectionConfig.load()
    prometheus_status = "offline"
    health_items = [
        { "name": "MySQL Master", "desc": "Monitoring...", "status": "online" },
        { "name": "MongoDB rs0", "desc": "Monitoring...", "status": "online" }
    ]
    
    if cfg.prometheus_url:
        try:
            url = f"{cfg.prometheus_url.rstrip('/')}/api/v1/query"
            resp = requests.get(url, params={'query': 'up'}, timeout=2)
            if resp.ok:
                prometheus_status = "online"
        except:
            pass

    return Response({
        "resources": {
            "cpu": { "value": f"{cpu_percent}%", "percentage": cpu_percent },
            "memory": { "value": f"{round(mem.used / (1024**3), 1)} GB", "percentage": mem.percent, "total": f"{round(mem.total / (1024**3), 1)} GB" },
            "disk": { "value": f"{round(disk.used / (1024**3), 1)} GB", "percentage": disk.percent, "total": f"{round(disk.total / (1024**3), 1)} GB" },
            "load": "Optimal" if cpu_percent < 70 else "High"
        },
        "health": health_items,
        "prometheus_status": prometheus_status
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({
        "id": request.user.id,
        "username": request.user.username,
        "email": request.user.email,
        "is_staff": request.user.is_staff,
        "groups": [g.name for g in request.user.groups.all()]
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def user_list(request):
    if request.method == 'GET':
        users = User.objects.all().prefetch_related('groups')
        data = []
        for u in users:
            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "groups": [g.name for g in u.groups.all()]
            })
        return Response({"users": data})
    
    elif request.method == 'POST':
        data = request.data
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            email=data.get('email', '')
        )
        if 'groups' in data:
            for gname in data['groups']:
                group, _ = Group.objects.get_or_create(name=gname)
                user.groups.add(group)
        return Response({"msg": "created"})

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def user_detail(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
        
    if request.method == 'PUT':
        data = request.data
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'groups' in data:
            user.groups.clear()
            for gname in data['groups']:
                group, _ = Group.objects.get_or_create(name=gname)
                user.groups.add(group)
        user.save()
        return Response({"msg": "updated"})
        
    elif request.method == 'DELETE':
        if user.is_superuser:
            return Response({"error": "Cannot delete superuser"}, status=400)
        user.delete()
        return Response({"msg": "deleted"})
