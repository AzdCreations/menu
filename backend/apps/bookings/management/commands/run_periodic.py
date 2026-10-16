import time

from django.core.management.base import BaseCommand

from apps.bookings.services import run_periodic


class Command(BaseCommand):
    help = "Истечение заявок, напоминания и автозавершение записей. --loop: запускать каждую минуту."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Работать бесконечно с паузой --interval секунд.")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, loop=False, interval=60, **options):
        while True:
            try:
                stats = run_periodic()
                if any(stats.values()):
                    self.stdout.write(str(stats))
            except Exception as exc:  # планировщик не должен падать из-за одной ошибки
                self.stderr.write(f"run_periodic failed: {exc!r}")
                if not loop:
                    raise
            if not loop:
                return
            time.sleep(interval)
