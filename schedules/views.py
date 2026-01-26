from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Schedule
from .serializers import ScheduleSerializer

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "code": 0,
            "data": serializer.data,
            "msg": "success"
        })

    def create(self, request, *args, **kwargs):
        # Check if input is wrapped in {code, data: [], msg}
        data = request.data
        input_data = data
        
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            input_data = data['data']
        
        is_many = isinstance(input_data, list)
        
        serializer = self.get_serializer(data=input_data, many=is_many)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response({
            "code": 0,
            "data": serializer.data,
            "msg": "success"
        }, status=status.HTTP_201_CREATED)
