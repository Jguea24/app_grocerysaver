"""Backfill del historico de precios desde ProductPrice."""

from django.core.management.base import BaseCommand

from grocerysaver.models import ProductPrice
from prices.services import record_price_history


class Command(BaseCommand):
    help = 'Crea snapshots historicos a partir de los precios actuales existentes.'

    def handle(self, *args, **options):
        total = 0
        for product_price in ProductPrice.objects.select_related('product', 'store'):
            record_price_history(product_price, source='backfill')
            total += 1
        self.stdout.write(self.style.SUCCESS(f'Se procesaron {total} precio(s) vigentes.'))