"""
Conexión a PostgreSQL.

Railway entrega DATABASE_URL con el esquema `postgres://` o
`postgresql://`. SQLAlchemy con el driver psycopg2 necesita el esquema
`postgresql+psycopg2://`, así que se normaliza automáticamente para que
no haya que tocar nada a mano al desplegar.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _normalize_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgresql://") and "+psycopg2" not in raw_url:
        return raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw_url


DATABASE_URL = _normalize_url(settings.database_url)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # evita conexiones muertas tras inactividad en Railway
    pool_recycle=280,     # recicla antes de que Railway/Postgres cierre el socket
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
