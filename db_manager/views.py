from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import DatabaseConnection
from .engines import DBEngineFactory

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def connection_list(request):
    if request.method == 'GET':
        conns = DatabaseConnection.objects.all().order_by('-created_at')
        data = []
        for c in conns:
            data.append({
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "host": c.host,
                "port": c.port,
                "user": c.user,
                "database": c.database
            })
        return Response(data)
    elif request.method == 'POST':
        data = request.data
        conn = DatabaseConnection.objects.create(
            name=data.get('name'),
            type=data.get('type'),
            host=data.get('host'),
            port=data.get('port', 3306),
            user=data.get('user'),
            password=data.get('password'),
            database=data.get('database'),
            extra_config=data.get('extra_config', {})
        )
        return Response({"id": conn.id, "msg": "Created"})

@api_view(['GET', 'DELETE', 'PUT'])
@permission_classes([IsAuthenticated])
def connection_detail(request, pk):
    conn = get_object_or_404(DatabaseConnection, pk=pk)
    if request.method == 'GET':
        return Response({
            "id": conn.id,
            "name": conn.name,
            "type": conn.type,
            "host": conn.host,
            "port": conn.port,
            "user": conn.user,
            "database": conn.database,
            "extra_config": conn.extra_config
        })
    elif request.method == 'DELETE':
        conn.delete()
        return Response({"msg": "Deleted"})
    elif request.method == 'PUT':
        data = request.data
        conn.name = data.get('name', conn.name)
        conn.host = data.get('host', conn.host)
        conn.port = data.get('port', conn.port)
        conn.user = data.get('user', conn.user)
        if 'password' in data:
            conn.password = data['password']
        conn.database = data.get('database', conn.database)
        conn.extra_config = data.get('extra_config', conn.extra_config)
        conn.save()
        return Response({"msg": "Updated"})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_connection(request):
    data = request.data
    conn = DatabaseConnection(
        type=data.get('type'),
        host=data.get('host'),
        port=data.get('port'),
        user=data.get('user'),
        password=data.get('password'),
        database=data.get('database'),
        extra_config=data.get('extra_config', {})
    )
    try:
        engine = DBEngineFactory.get_engine(conn)
        ok, msg = engine.test()
        return Response({"ok": ok, "msg": msg})
    except Exception as e:
        return Response({"ok": False, "msg": str(e)})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_saved_connection(request, pk):
    conn = get_object_or_404(DatabaseConnection, pk=pk)
    try:
        engine = DBEngineFactory.get_engine(conn)
        ok, msg = engine.test()
        return Response({"ok": ok, "msg": msg})
    except Exception as e:
        return Response({"ok": False, "msg": str(e)})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_structure(request, pk):
    conn = get_object_or_404(DatabaseConnection, pk=pk)
    try:
        engine = DBEngineFactory.get_engine(conn)
        tree = engine.get_structure()
        return Response(tree)
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_query(request, pk):
    conn = get_object_or_404(DatabaseConnection, pk=pk)
    db = request.data.get('db')
    target = request.data.get('target')
    params = request.data.get('params', {})
    
    try:
        engine = DBEngineFactory.get_engine(conn)
        result = engine.query(db, target, params)
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=400)
