"""Cola de trabajos simple basada en base de datos para tareas pesadas."""

import csv
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BackgroundJob, JobStatus, JobType, Product, ProductCodeType


JOB_EXPORTS_DIR = 'job_exports'


def enqueue_export_products_job(*, created_by=None, category_id=None, search=''):
    """Crea un job pendiente para exportar productos a CSV."""
    payload = {
        'category_id': category_id,
        'search': (search or '').strip(),
    }
    return BackgroundJob.objects.create(
        job_type=JobType.EXPORT_PRODUCTS_CSV,
        payload=payload,
        created_by=created_by,
    )


def claim_next_job():
    """Toma el siguiente job en cola y lo marca como processing."""
    with transaction.atomic():
        job = (
            BackgroundJob.objects.select_for_update(skip_locked=True)
            .filter(status=JobStatus.QUEUED)
            .order_by('created_at')
            .first()
        )
        if job is None:
            return None

        job.status = JobStatus.PROCESSING
        job.started_at = timezone.now()
        job.attempts += 1
        job.error = ''
        job.save(update_fields=['status', 'started_at', 'attempts', 'error'])
        return job


def process_next_job():
    """Procesa el siguiente job pendiente si existe."""
    job = claim_next_job()
    if job is None:
        return None

    process_job(job)
    return job


def process_job(job):
    """Despacha el trabajo segun su tipo y persiste su resultado final."""
    try:
        if job.job_type == JobType.EXPORT_PRODUCTS_CSV:
            result = export_products_to_csv(job)
        else:
            raise ValueError(f'Tipo de job no soportado: {job.job_type}')
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error', 'finished_at'])
        return job

    job.status = JobStatus.COMPLETED
    job.result = result
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'result', 'finished_at'])
    return job


def export_products_to_csv(job):
    """Genera un archivo CSV con productos filtrados por el payload del job."""
    payload = job.payload or {}
    category_id = payload.get('category_id')
    search = (payload.get('search') or '').strip()

    queryset = Product.objects.select_related('category').prefetch_related('prices__store', 'codes')
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    if search:
        queryset = queryset.filter(name__icontains=search)

    export_dir = Path(settings.MEDIA_ROOT) / JOB_EXPORTS_DIR
    export_dir.mkdir(parents=True, exist_ok=True)

    filename = f'products-export-{job.job_id}.csv'
    absolute_path = export_dir / filename
    relative_path = f'{JOB_EXPORTS_DIR}/{filename}'

    exported_rows = 0
    with absolute_path.open('w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                'product_id',
                'name',
                'brand',
                'category',
                'description',
                'qr_code',
                'stores_available',
                'best_price',
            ]
        )

        for product in queryset:
            prices = list(product.prices.all())
            best_price = str(prices[0].price) if prices else ''
            qr_row = next((code for code in product.codes.all() if code.code_type == ProductCodeType.QR), None)
            writer.writerow(
                [
                    product.id,
                    product.name,
                    product.brand,
                    product.category.name,
                    product.description,
                    qr_row.code if qr_row else '',
                    len(prices),
                    best_price,
                ]
            )
            exported_rows += 1

    return {
        'file_path': relative_path,
        'file_name': filename,
        'rows_exported': exported_rows,
    }
