"""
Valida data/categories.yaml y data/qna/*.json antes de subir cambios al
repositorio (evita romper la carga automática en Railway).

Uso:
    python scripts/validate_data.py
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def main() -> int:
    errores: list[str] = []

    cat_path = DATA_DIR / "categories.yaml"
    if not cat_path.exists():
        errores.append(f"Falta {cat_path}")
        slugs_validos: set[str] = set()
    else:
        with open(cat_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        categorias = data.get("categorias", [])
        slugs_validos = set()
        for i, cat in enumerate(categorias):
            for campo in ("slug", "nombre"):
                if campo not in cat:
                    errores.append(f"categories.yaml[{i}]: falta el campo '{campo}'")
            if "slug" in cat:
                slugs_validos.add(cat["slug"])

    ids_vistos: set[str] = set()
    qna_dir = DATA_DIR / "qna"
    for archivo in sorted(qna_dir.glob("*.json")) if qna_dir.exists() else []:
        try:
            with open(archivo, encoding="utf-8") as f:
                bloque = json.load(f)
        except json.JSONDecodeError as exc:
            errores.append(f"{archivo.name}: JSON inválido -> {exc}")
            continue

        categoria = bloque.get("categoria")
        if categoria not in slugs_validos:
            errores.append(
                f"{archivo.name}: categoria '{categoria}' no existe en categories.yaml"
            )

        for pregunta in bloque.get("preguntas", []):
            pid = pregunta.get("id")
            if not pid:
                errores.append(f"{archivo.name}: hay una pregunta sin 'id'")
                continue
            if pid in ids_vistos:
                errores.append(f"{archivo.name}: id duplicado '{pid}'")
            ids_vistos.add(pid)

            if not pregunta.get("pregunta"):
                errores.append(f"{archivo.name} [{pid}]: falta el texto de 'pregunta'")
            if not pregunta.get("respuestas"):
                errores.append(f"{archivo.name} [{pid}]: no tiene ninguna respuesta")
            for j, resp in enumerate(pregunta.get("respuestas", [])):
                if not resp.get("contenido"):
                    errores.append(f"{archivo.name} [{pid}] respuesta[{j}]: falta 'contenido'")

    if errores:
        print(f"❌ Se encontraron {len(errores)} problema(s):\n")
        for e in errores:
            print(f"  - {e}")
        return 1

    print(f"✅ Data válida: {len(slugs_validos)} categorías, {len(ids_vistos)} preguntas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
