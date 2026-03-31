from django.core.management.base import BaseCommand

from traffic.services.rollup_buffer import flush_closed_rollups


class Command(BaseCommand):
    help = "Flush closed per-minute traffic rollups from Redis into the database (cron every minute)."

    def handle(self, *args, **options):
        n = flush_closed_rollups()
        self.stdout.write(self.style.SUCCESS(f"traffic_rollup_flush: flushed {n} bucket(s)"))
