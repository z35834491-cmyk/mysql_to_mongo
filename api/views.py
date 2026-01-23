from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
import psutil
from inspection.models import InspectionConfig, InspectionReport
from tasks.models import SyncTask
from monitor.models import MonitorTask
import requests
import datetime

# Custom Permission Class
class HasRolePermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        # For user management, require Admin role or is_staff
        if 'users' in request.path or 'roles' in request.path:
            return request.user.is_staff or request.user.groups.filter(name='Admin').exists()
        return True

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_stats(request):
    # 1. Resource Stats (Real)
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # 2. Real System Health Data
    health_items = []
    
    # Monitor Tasks Status
    active_monitors = MonitorTask.objects.filter(enabled=True).count()
    health_items.append({
        "name": "Log Monitor Engine",
        "desc": f"{active_monitors} active tasks",
        "status": "online" if active_monitors > 0 else "warning"
    })
    
    # Sync Tasks Status
    error_tasks = SyncTask.objects.filter(status='error').count()
    health_items.append({
        "name": "Data Sync Pipeline",
        "desc": f"{error_tasks} tasks with errors" if error_tasks > 0 else "All tasks healthy",
        "status": "online" if error_tasks == 0 else "warning"
    })

    # Recent Inspection
    latest_report = InspectionReport.objects.order_by('-created_at').first()
    if latest_report:
        score = 100 - latest_report.content.get('risk_summary', {}).get('score', 0)
        health_items.append({
            "name": "System Inspection",
            "desc": f"Last score: {score}%",
            "status": "online" if score > 80 else "warning"
        })

    return Response({
        "resources": {
            "cpu": { "value": f"{cpu_percent}%", "percentage": cpu_percent },
            "memory": { "value": f"{round(mem.used / (1024**3), 1)} GB", "percentage": mem.percent, "total": f"{round(mem.total / (1024**3), 1)} GB" },
            "disk": { "value": f"{round(disk.used / (1024**3), 1)} GB", "percentage": disk.percent, "total": f"{round(disk.total / (1024**3), 1)} GB" },
            "load": "Optimal" if cpu_percent < 70 else "High"
        },
        "health": health_items
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
@permission_classes([HasRolePermission])
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
                "is_staff": u.is_staff,
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
                if gname == 'Admin':
                    user.is_staff = True
        user.save()
        return Response({"msg": "created"})

@api_view(['PUT', 'DELETE'])
@permission_classes([HasRolePermission])
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
            user.is_staff = False
            for gname in data['groups']:
                group, _ = Group.objects.get_or_create(name=gname)
                user.groups.add(group)
                if gname == 'Admin':
                    user.is_staff = True
        user.save()
        return Response({"msg": "updated"})
        
    elif request.method == 'DELETE':
        if user.is_superuser:
            return Response({"error": "Cannot delete superuser"}, status=400)
        user.delete()
        return Response({"msg": "deleted"})

# --- Role & Permission Management ---

@api_view(['GET', 'POST'])
@permission_classes([HasRolePermission])
def role_list(request):
    if request.method == 'GET':
        groups = Group.objects.all().prefetch_related('permissions')
        data = []
        for g in groups:
            data.append({
                "id": g.id,
                "name": g.name,
                "permissions": [p.codename for p in g.permissions.all()]
            })
        return Response({"roles": data})
    
    elif request.method == 'POST':
        data = request.data
        group, created = Group.objects.get_or_create(name=data['name'])
        if 'permissions' in data:
            perms = Permission.objects.filter(codename__in=data['permissions'])
            group.permissions.set(perms)
        return Response({"msg": "saved", "id": group.id})

@api_view(['GET'])
@permission_classes([HasRolePermission])
def permission_list(request):
    # List all available custom permissions or key app permissions
    # For now, let's return some logical permissions for our apps
    perms = [
        {"codename": "view_dashboard", "name": "View Dashboard"},
        {"codename": "manage_tasks", "name": "Manage Sync Tasks"},
        {"codename": "view_logs", "name": "View Logs"},
        {"codename": "run_inspection", "name": "Run Inspection"},
        {"codename": "manage_users", "name": "Manage Users & Roles"},
    ]
    return Response({"permissions": perms})
