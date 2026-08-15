"""
Configuración central del servicio.
Toma todos los valores desde variables de entorno (Railway los inyecta
automáticamente en el caso de DATABASE_URL cuando agregas el plugin de
Postgres al proyecto).
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Railway inyecta DATABASE_URL automáticamente al vincular el plugin
    # de Postgres. Se deja un default local solo para desarrollo.
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/githouse"

    # Carpeta raíz donde vive la data estructurada (categorías/preguntas)
    data_dir: str = str(Path(__file__).resolve().parent.parent / "data")

    # Secreto para poder disparar una recarga de datos sin redeploy
    # (POST /admin/recargar-datos con header X-Admin-Secret)
    admin_secret: str = "changeme"

    # Umbral mínimo (0-100) de similitud para considerar una coincidencia
    match_threshold: int = 62

    # Cuántas respuestas alternativas devolver como sugerencias cuando
    # no hay una coincidencia clara
    max_sugerencias: int = 3

    app_env: str = "production"

    # --- WhatsApp (Green API) ---
    # Host específico de tu cuenta, ej. https://7107.api.greenapi.com
    # (Green API asigna un host por instancia; no siempre es api.green-api.com)
    whatsapp_api_url: str = "https://api.green-api.com"
    # idInstance de tu instancia en Green API
    whatsapp_instance_id: str = ""
    # apiTokenInstance de tu instancia en Green API
    whatsapp_api_token: str = ""

    # Horas sin escribir que cuentan como "nueva sesión" — al pasar ese
    # tiempo, el bot vuelve a saludar por nombre en el próximo mensaje.
    saludo_sesion_horas: int = 6

    @field_validator("whatsapp_api_url")
    @classmethod
    def _limpiar_whatsapp_api_url(cls, v: str) -> str:
        """
        Blindaje contra valores mal pegados en Railway: sintaxis Markdown
        [texto](url), espacios extra, o barra final. Si alguien pega
        "[https://x.com](https://x.com)" por accidente, aquí se extrae
        la URL real en vez de dejar pasar un hostname inválido que
        revienta con 'Name or service not known'.
        """
        v = v.strip()
        if v.startswith("[") and "](" in v and v.endswith(")"):
            v = v.split("](", 1)[1].rstrip(")")
        return v.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
