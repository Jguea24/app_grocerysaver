"""Comando para completar QR faltantes en productos existentes."""

from django.core.management.base import BaseCommand

from grocerysaver.models import Product, ProductCodeType
from grocerysaver.services import ensure_product_qr_code


class Command(BaseCommand):
    """Backfill operativo para corregir productos antiguos sin QR."""

    help = 'Crea codigos QR para productos que aun no tienen uno.'

    def add_arguments(self, parser):
        """Expone flags para simulacion y procesamiento parcial."""
        parser.add_argument('--dry-run', action='store_true', help='Solo cuenta productos sin QR.')
        parser.add_argument('--limit', type=int, default=None, help='Limita la cantidad de productos a procesar.')

    def handle(self, *args, **options):
        """Recorre productos y genera QR donde todavia faltan."""
        queryset = Product.objects.all().prefetch_related('codes')
        limit = options.get('limit')
        if limit:
            queryset = queryset[:limit]

        created = 0
        for product in queryset:
            if product.codes.filter(code_type=ProductCodeType.QR).exists():
                continue
            created += 1
            if not options.get('dry_run'):
                ensure_product_qr_code(product)

        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING(f'Productos sin QR: {created}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'QR creados: {created}'))
