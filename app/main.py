"""
Entrypoint del servicio "Git House Bot".

Al arrancar (lifespan):
  1. Se conecta a PostgreSQL usando DATABASE_URL (inyectada por Railway).
  2. Crea dinámicamente todas las tablas relacionales que falten
     (Base.metadata.create_all — no requiere correr migraciones a mano).
  3. Lee data/categories.yaml + data/qna/*.json y sincroniza la base de
     datos (upsert idempotente), sin intervención manual.

Si el paso 3 falla, el servicio igual levanta (para poder diagnosticar
vía /health y /admin/recargar-datos), pero el error queda registrado en
la tabla load_logs y en los logs de Railway.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal, engine
from app.loader import DataLoadError, cargar_datos
from app.models import Base
from app.routers import admin, categories, chat, health, whatsapp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("githouse.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Conectando a PostgreSQL y creando tablas si no existen...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas listas. Cargando datos estructurados desde el repositorio...")

    db = SessionLocal()
    try:
        cargar_datos(db)
    except DataLoadError:
        logger.error(
            "La carga inicial de datos falló. El servicio sigue arriba; "
            "revisa /admin/recargar-datos y load_logs para más detalle."
        )
    finally:
        db.close()

    yield  # --- la app corre aquí ---

    logger.info("Apagando servicio Git House Bot.")


app = FastAPI(
    title="Git House — Bot Inteligente",
    description="API de preguntas y respuestas inteligentes para Git House",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS abierto por defecto: ajusta allow_origins a tu dominio real en
# cuanto tengas el frontend/n8n final apuntando aquí.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(categories.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(whatsapp.router)


@app.get("/")
def root():
    return {"servicio": "Git House Bot", "status": "activo"}
