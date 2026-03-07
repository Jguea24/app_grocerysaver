from django.core.management.base import BaseCommand

from grocerysaver.models import Product, ProductCodeType
from grocerysaver.services import ensure_product_qr_code


class Command(BaseCommand):
    help = 'Crea codigos QR para productos que aun no tienen uno.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo cuenta productos sin QR.')
        parser.add_argument('--limit', type=int, default=None, help='Limita la cantidad de productos a procesar.')

    def handle(self, *args, **options):
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
