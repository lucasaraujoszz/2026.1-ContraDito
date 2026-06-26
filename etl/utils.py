from datetime import date, datetime


def para_timestamp(valor) -> int | None:
    """Converte date/datetime/str ISO para Unix timestamp inteiro."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    if isinstance(valor, datetime):
        return int(valor.timestamp())
    if isinstance(valor, date):
        return int(datetime(valor.year, valor.month, valor.day).timestamp())
    try:
        return int(datetime.fromisoformat(str(valor)).timestamp())
    except (ValueError, TypeError):
        return None
