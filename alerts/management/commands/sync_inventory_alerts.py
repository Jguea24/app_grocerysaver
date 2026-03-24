"""Sincroniza alertas de caducidad para el inventario."""

from django.core.management.base import BaseCommand

from alerts.services import sync_all_expiry_alerts


class Command(BaseCommand):
    help = 'Sincroniza alertas de caducidad para todos los items del inventario.'

    def add_arguments(self, parser):
        parser.add_argument('--threshold-days', type=int, default=None)

    def handle(self, *args, **options):
        threshold_days = options.get('threshold_days')
        synced = sync_all_expiry_alerts() if threshold_days is None else sync_all_expiry_alerts(threshold_days=threshold_days)
        self.stdout.write(self.style.SUCCESS(f'Se sincronizaron {synced} item(s) de inventario.'))