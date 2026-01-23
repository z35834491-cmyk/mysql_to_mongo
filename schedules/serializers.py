from rest_framework import serializers
from .models import Schedule
import json

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'
        extra_kwargs = {
            'staff_name': {'required': False},
            'shift_date': {'required': False},
            'shift_type': {'required': False},
        }

    def to_internal_value(self, data):
        # Extract standard fields if they exist, or try to guess them from common synonyms
        internal_data = {}
        
        # Mappings for "unknown" external fields to our internal schema
        name_fields = ['staff_name', 'employee', 'user', 'name', 'person']
        date_fields = ['shift_date', 'date', 'day', 'time']
        type_fields = ['shift_type', 'shift', 'type', 'period']
        
        # Helper to find first matching key
        def find_value(candidates, source):
            for key in candidates:
                if key in source:
                    return source[key]
            return None

        # 1. Try to populate standard fields
        staff_name = find_value(name_fields, data)
        shift_date = find_value(date_fields, data)
        shift_type = find_value(type_fields, data)

        # 2. Defaults if missing (or let validation fail later if strict)
        # For this task, we want to be permissive.
        if staff_name: internal_data['staff_name'] = staff_name
        if shift_date: internal_data['shift_date'] = shift_date
        if shift_type: internal_data['shift_type'] = shift_type

        # 3. Store EVERYTHING in extra_info
        internal_data['extra_info'] = data

        # Pass through to standard DRF validation
        # We need to make sure required fields are present or have defaults in Model
        # But wait, to_internal_value returns the dictionary that validation runs against.
        
        # If we missed any required fields, we might want to provide fallbacks or handle gracefully
        # For now, let's assume the simulation script provides at least these recognizable fields
        
        return super().to_internal_value(internal_data)
