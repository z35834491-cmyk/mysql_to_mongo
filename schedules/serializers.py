from rest_framework import serializers
from .models import Schedule

class ScheduleSerializer(serializers.ModelSerializer):
    ruleId = serializers.IntegerField(source='rule_id', required=False)
    shiftDate = serializers.DateField(source='shift_date')
    startTime = serializers.CharField(source='start_time')
    endTime = serializers.CharField(source='end_time')
    staffIds = serializers.CharField(source='staff_ids', required=False, allow_blank=True)
    staffList = serializers.JSONField(source='staff_list', required=False)
    createTime = serializers.CharField(source='create_time', required=False, allow_blank=True)

    class Meta:
        model = Schedule
        fields = ['id', 'ruleId', 'shiftDate', 'startTime', 'endTime', 'staffIds', 'staffList', 'createTime']
