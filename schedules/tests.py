from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Schedule
import datetime

class ScheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/schedules/'
        self.schedule_data = {
            'staff_name': 'John Doe',
            'shift_date': '2023-10-27',
            'shift_type': 'Morning',
            'extra_info': {'location': 'Room A'}
        }

    def test_create_schedule(self):
        response = self.client.post(self.url, self.schedule_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 1)
        self.assertEqual(Schedule.objects.get().staff_name, 'John Doe')

    def test_get_schedules(self):
        Schedule.objects.create(**self.schedule_data)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
