# Git House — Bot de Preguntas y Respuestas Inteligentes

Backend en **FastAPI + PostgreSQL**, listo para desplegar en **Railway**,
que carga automáticamente su base de conocimiento (categorías, preguntas,
variantes y respuestas) desde archivos JSON/YAML del propio repositorio,
sin intervención manual en producción.

## Estructura del repositorio

```
git-house-bot/
├── app/
│   ├── main.py          # Entrypoint FastAPI (lifespan: crea tablas + carga datos)
│   ├── config.py        # Settings vía variables de entorno
│   ├── database.py      # Engine/Session SQLAlchemy (normaliza DATABASE_URL de Railway)
│   ├── models.py        # Modelos relacionales (Category, Question, Answer, ...)
│   ├── schemas.py        # Esquemas Pydantic de entrada/salida
│   ├── loader.py         # Lee data/ y hace upsert idempotente en la DB
│   ├── matcher.py        # Motor de coincidencia difusa (rapidfuzz)
│   └── routers/
│       ├── health.py     # GET /health
│       ├── categories.py # GET /categorias, GET /categorias/{slug}/preguntas
│       ├── chat.py       # POST /chat/consultar
│       └── admin.py      # POST /admin/recargar-datos (recarga sin redeploy)
├── data/
│   ├── categories.yaml   # Catálogo de categorías
│   └── qna/*.json        # Bancos de preguntas por categoría
├── scripts/validate_data.py  # Valida data/ antes de hacer commit
├── tests/test_matcher.py
├── Dockerfile
├── railway.json
├── Procfile
├── requirements.txt
└── .env.example
```

## Cómo agregar contenido (categorías/preguntas)

1. Para una categoría nueva, agrégala en `data/categories.yaml`.
2. Crea o edita un archivo en `data/qna/<categoria>.json` con esta forma:

```json
{
  "categoria": "slug-de-la-categoria",
  "preguntas": [
    {
      "id": "identificador_unico",
      "pregunta": "Texto principal de la pregunta",
      "palabras_clave": ["palabra1", "palabra2"],
      "variantes": ["forma en que un usuario real la escribiría"],
      "respuestas": [
        { "tipo": "texto", "contenido": "La respuesta." },
        { "tipo": "link", "contenido": "Ver más", "meta": { "url": "https://..." } }
      ]
    }
  ]
}
```

3. Corre `python scripts/validate_data.py` antes de subir el cambio.
4. Al hacer deploy (o llamar `POST /admin/recargar-datos`), el backend
   sincroniza automáticamente la base de datos con lo que haya en `data/`.
   El `id` de cada pregunta es la clave de upsert: si lo repites, se
   actualiza en vez de duplicarse.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Chequeo de salud (valida conexión a Postgres) |
| GET | `/categorias` | Lista todas las categorías |
| GET | `/categorias/{slug}/preguntas` | Preguntas de una categoría |
| POST | `/chat/consultar` | `{"mensaje": "..."}` → respuesta más parecida o sugerencias |
| POST | `/admin/recargar-datos` | Header `X-Admin-Secret`; releer `data/` sin redeploy |

## Desplegar en Railway

1. Sube este repositorio a GitHub.
2. En Railway: **New Project → Deploy from GitHub repo**.
3. Agrega el plugin **PostgreSQL** al mismo proyecto — Railway inyecta
   `DATABASE_URL` automáticamente al servicio del bot (no hay que
   configurarla a mano).
4. En las variables del servicio, define al menos:
   - `ADMIN_SECRET` (usa un valor fuerte y único)
   - Opcional: `MATCH_THRESHOLD`, `MAX_SUGERENCIAS`
5. Railway detecta el `Dockerfile` y hace el build. Al primer arranque,
   el servicio crea las tablas y carga todo el contenido de `data/`
   automáticamente — no se ejecuta nada manual.
6. Verifica con `GET /health` y luego `GET /categorias`.

## Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajusta DATABASE_URL a tu Postgres local
uvicorn app.main:app --reload
```

## Notas de diseño

- **Migrations on boot**: `Base.metadata.create_all()` corre en el
  `lifespan` de FastAPI en cada arranque; si agregas un modelo nuevo,
  la tabla se crea sola en el próximo deploy. Para cambios de columnas
  en tablas ya existentes en producción con datos reales, se recomienda
  incorporar Alembic más adelante — el diseño actual ya usa SQLAlchemy
  Declarative, por lo que Alembic se integraría sin reescribir modelos.
- **Carga idempotente**: correr el loader muchas veces no duplica datos;
  usa `slug` y `external_id` como claves naturales de upsert.
- **Matching sin LLM**: `rapidfuzz` da respuestas inmediatas y sin costo
  por consulta; si más adelante quieres respuestas generativas para los
  casos sin match, `app/matcher.py` es el único módulo a extender.
