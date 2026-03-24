"""Cola de trabajos simple basada en base de datos para tareas pesadas."""

import csv
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BackgroundJob, JobStatus, JobType, Product, ProductCodeType


JOB_EXPORTS_DIR = 'job_exports'
EXPORT_HEADERS = [
    'product_id',
    'name',
    'brand',
    'category',
    'description',
    'qr_code',
    'stores_available',
    'best_price',
]


def enqueue_export_products_job(*, created_by=None, file_format='csv', category_id=None, search=''):
    """Crea un job pendiente para exportar productos en el formato solicitado."""
    payload = {
        'format': (file_format or 'csv').strip().lower(),
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
            result = export_products(job)
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


def export_products(job):
    """Genera un archivo TXT, CSV o PDF con productos filtrados por el payload del job."""
    payload = job.payload or {}
    file_format = (payload.get('format') or 'csv').strip().lower()
    if file_format not in {'txt', 'csv', 'pdf'}:
        raise ValueError(f'Formato de exportacion no soportado: {file_format}')

    rows = list(iter_export_product_rows(payload))
    if file_format == 'txt':
        return export_products_to_txt(job, rows)
    if file_format == 'pdf':
        return export_products_to_pdf(job, rows)
    return export_products_to_csv(job, rows)


def iter_export_product_rows(payload):
    """Construye filas serializadas reutilizables para cualquier formato."""
    category_id = payload.get('category_id')
    search = (payload.get('search') or '').strip()

    queryset = Product.objects.select_related('category').prefetch_related('prices__store', 'codes')
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    if search:
        queryset = queryset.filter(name__icontains=search)

    for product in queryset:
        prices = list(product.prices.all())
        best_price = str(prices[0].price) if prices else ''
        qr_row = next((code for code in product.codes.all() if code.code_type == ProductCodeType.QR), None)
        yield [
            product.id,
            product.name,
            product.brand,
            product.category.name,
            product.description,
            qr_row.code if qr_row else '',
            len(prices),
            best_price,
        ]


def is_directory_writable(directory):
    """Verifica que un directorio exista y permita escrituras reales."""
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / '.write_probe'
    try:
        probe.write_text('ok', encoding='utf-8')
    except OSError:
        return False
    finally:
        if probe.exists():
            probe.unlink()
    return True


def resolve_export_directory():
    """Obtiene una carpeta de exportacion escribible incluso si MEDIA_ROOT falla."""
    preferred_dir = Path(settings.MEDIA_ROOT) / JOB_EXPORTS_DIR
    if is_directory_writable(preferred_dir):
        return preferred_dir

    fallback_dir = Path(settings.BASE_DIR) / '.runtime_exports' / JOB_EXPORTS_DIR
    if is_directory_writable(fallback_dir):
        return fallback_dir

    raise PermissionError('No existe una carpeta escribible para exportar jobs.')


def build_export_file_paths(job, extension):
    """Resuelve la ruta absoluta y relativa del archivo exportado."""
    export_dir = resolve_export_directory()

    filename = f'products-export-{job.job_id}.{extension}'
    absolute_path = export_dir / filename
    relative_path = f'{JOB_EXPORTS_DIR}/{filename}'
    return absolute_path, relative_path, filename


def build_export_result(*, file_format, file_name, file_path, rows_exported):
    """Estructura comun del resultado persistido para exportaciones."""
    return {
        'file_format': file_format,
        'file_path': file_path,
        'file_name': file_name,
        'rows_exported': rows_exported,
    }


def export_products_to_csv(job, rows):
    """Genera un archivo CSV con los productos ya serializados."""
    absolute_path, relative_path, filename = build_export_file_paths(job, 'csv')

    with absolute_path.open('w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(EXPORT_HEADERS)
        writer.writerows(rows)

    return build_export_result(
        file_format='csv',
        file_name=filename,
        file_path=relative_path,
        rows_exported=len(rows),
    )


def export_products_to_txt(job, rows):
    """Genera un archivo TXT legible con los productos ya serializados."""
    absolute_path, relative_path, filename = build_export_file_paths(job, 'txt')

    lines = []
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                f'Producto #{index}',
                f'ID: {row[0]}',
                f'Nombre: {row[1]}',
                f'Marca: {row[2] or "-"}',
                f'Categoria: {row[3]}',
                f'Descripcion: {row[4] or "-"}',
                f'QR: {row[5] or "-"}',
                f'Tiendas disponibles: {row[6]}',
                f'Mejor precio: {row[7] or "-"}',
                '-' * 48,
            ]
        )

    if not lines:
        lines.append('No hay productos para exportar.')

    absolute_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return build_export_result(
        file_format='txt',
        file_name=filename,
        file_path=relative_path,
        rows_exported=len(rows),
    )


def export_products_to_pdf(job, rows):
    """Genera un PDF simple con el listado de productos exportados."""
    absolute_path, relative_path, filename = build_export_file_paths(job, 'pdf')

    lines = ['Exportacion de productos', '']
    if rows:
        for row in rows:
            lines.append(f'{row[0]} | {row[1]} | {row[2] or "-"} | {row[3]} | ${row[7] or "-"}')
    else:
        lines.append('No hay productos para exportar.')

    absolute_path.write_bytes(build_simple_pdf(lines))
    return build_export_result(
        file_format='pdf',
        file_name=filename,
        file_path=relative_path,
        rows_exported=len(rows),
    )


def build_simple_pdf(lines):
    """Construye un PDF minimo usando Helvetica para evitar dependencias externas."""
    page_width = 612
    page_height = 792
    margin_left = 50
    margin_top = 60
    line_height = 16
    max_lines_per_page = 42

    pages = [lines[index:index + max_lines_per_page] for index in range(0, len(lines), max_lines_per_page)] or [[]]
    objects = []

    objects.append(b'<< /Type /Catalog /Pages 2 0 R >>')
    page_refs = ' '.join(f'{4 + (index * 2)} 0 R' for index in range(len(pages)))
    objects.append(f'<< /Type /Pages /Kids [{page_refs}] /Count {len(pages)} >>'.encode('latin-1'))
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

    for page_index, page_lines in enumerate(pages):
        page_object_id = 4 + (page_index * 2)
        content_object_id = page_object_id + 1
        page_object = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] '
            f'/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object_id} 0 R >>'
        ).encode('latin-1')
        objects.append(page_object)

        content_lines = ['BT', '/F1 12 Tf']
        y = page_height - margin_top
        for line in page_lines:
            content_lines.append(f'1 0 0 1 {margin_left} {y} Tm ({pdf_escape_text(line)}) Tj')
            y -= line_height
        content_lines.append('ET')
        content_bytes = '\n'.join(content_lines).encode('cp1252', errors='replace')
        content_stream = b'<< /Length %d >>\nstream\n%b\nendstream' % (len(content_bytes), content_bytes)
        objects.append(content_stream)

    buffer = BytesIO()
    buffer.write(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f'{index} 0 obj\n'.encode('latin-1'))
        buffer.write(obj)
        buffer.write(b'\nendobj\n')

    xref_position = buffer.tell()
    buffer.write(f'xref\n0 {len(objects) + 1}\n'.encode('latin-1'))
    buffer.write(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        buffer.write(f'{offset:010d} 00000 n \n'.encode('latin-1'))
    trailer = (
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref_position}\n%%EOF'
    )
    buffer.write(trailer.encode('latin-1'))
    return buffer.getvalue()


def pdf_escape_text(value):
    """Escapa caracteres especiales para incluir texto dentro del stream PDF."""
    text = str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return text.replace('\r', ' ').replace('\n', ' ')
