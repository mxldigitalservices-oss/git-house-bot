"""Utilidades pequeñas compartidas entre varios módulos."""


def normalizar_telefono(phone: str) -> str:
    """Deja solo dígitos — Green API espera el número limpio en el chatId."""
    return "".join(c for c in phone if c.isdigit())
