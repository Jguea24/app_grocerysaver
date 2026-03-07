"""Worker de consola para procesar jobs pendientes fuera del request HTTP."""

import time

from django.core.management.base import BaseCommand

from grocerysaver.job_queue import process_next_job


class Command(BaseCommand):
    """Loop simple de consumo para la cola de trabajos basada en BD."""

    help = 'Procesa jobs encolados en la base de datos.'

    def add_arguments(self, parser):
        """Permite ejecucion continua o en modo single-shot."""
        parser.add_argument('--once', action='store_true', help='Procesa un solo job y termina.')
        parser.add_argument(
            '--poll-seconds',
            type=float,
            default=2.0,
            help='Segundos de espera entre ciclos cuando no hay jobs.',
        )

    def handle(self, *args, **options):
        """Consume jobs pendientes hasta que se detenga el proceso."""
        once = options['once']
        poll_seconds = max(options['poll_seconds'], 0.2)

        self.stdout.write(self.style.SUCCESS('Worker de jobs iniciado.'))

        while True:
            job = process_next_job()
            if job is None:
                if once:
                    self.stdout.write('No hay jobs pendientes.')
                    return
                time.sleep(poll_seconds)
                continue

            self.stdout.write(f'Job procesado: {job.job_id} estado={job.status}')
            if once:
                return
