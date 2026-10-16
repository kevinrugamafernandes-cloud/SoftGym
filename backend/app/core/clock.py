"""Reloj inyectable. Define qué es "hoy" para cada gimnasio según SU zona horaria."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


class Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today(self, tz_name: str) -> date:
        """Fecha de hoy en la zona horaria del gimnasio (en Costa Rica no coincide con UTC tras las 6 p. m.)."""
        return self.now().astimezone(ZoneInfo(tz_name)).date()


def get_clock() -> Clock:
    return Clock()
