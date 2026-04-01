"""Seed script — crea datos de ejemplo en MedicionCabecera + MedicionLinea.

Uso:
    cd "Js construcciones Streamlit"
    python scripts/seed_mediciones.py          # ver qué datos existen
    python scripts/seed_mediciones.py --run     # crear registros de prueba
    python scripts/seed_mediciones.py --clean   # borrar TODO de MedicionCabecera + MedicionLinea

Requisitos:
    - .env con AIRTABLE_API_KEY
    - Las tablas dimensionales (obras, DimSector, DimRubro, DimTrabajador) deben tener datos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
from pyairtable import Api
from config import AIRTABLE_BASE_ID, TABLES, get_secret

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

api = Api(get_secret("AIRTABLE_API_KEY"))


def _table(key: str):
    return api.table(AIRTABLE_BASE_ID, TABLES[key]["id"])


def _fid(table_key: str, field_key: str) -> str:
    return TABLES[table_key]["fields"][field_key]


def _get_all(table_key: str) -> list[dict]:
    tbl = _table(table_key)
    return tbl.all(use_field_ids=True)


def _create(table_key: str, fields: dict) -> str:
    """Crea un registro. fields usa claves legibles."""
    fmap = TABLES[table_key]["fields"]
    data = {fmap[k]: v for k, v in fields.items() if k in fmap}
    rec = _table(table_key).create(data)
    return rec["id"]


def _delete_all(table_key: str) -> int:
    recs = _get_all(table_key)
    tbl = _table(table_key)
    n = 0
    for rec in recs:
        tbl.delete(rec["id"])
        n += 1
    return n


def _norm(val):
    if isinstance(val, list):
        return val[0] if val else ""
    return val or ""


# ---------------------------------------------------------------------------
# Discovery — show what dimension data exists
# ---------------------------------------------------------------------------

def show_dimensions():
    print("\n═══ DATOS DIMENSIONALES EXISTENTES ═══\n")

    obras = _get_all("obras")
    f_clave = _fid("obras", "Clave")
    f_nombre = _fid("obras", "Nombre")
    f_estado = _fid("obras", "EstadoObra")
    print(f"OBRAS ({len(obras)}):")
    for r in obras[:15]:
        f = r["fields"]
        print(f"  {r['id']}  |  {_norm(f.get(f_clave, ''))}  |  {_norm(f.get(f_nombre, ''))}  |  {_norm(f.get(f_estado, ''))}")

    sectores = _get_all("DimSector")
    f_sec = _fid("DimSector", "NombreSector")
    f_sec_obra = _fid("DimSector", "ObraID")
    print(f"\nSECTORES ({len(sectores)}):")
    for r in sectores[:20]:
        f = r["fields"]
        print(f"  {r['id']}  |  {_norm(f.get(f_sec, ''))}  |  ObraID: {_norm(f.get(f_sec_obra, ''))}")

    rubros = _get_all("DimRubro")
    f_rub = _fid("DimRubro", "Rubro")
    f_rub_comp = _fid("DimRubro", "NombreCompleto")
    print(f"\nRUBROS ({len(rubros)}):")
    for r in rubros[:20]:
        f = r["fields"]
        print(f"  {r['id']}  |  {_norm(f.get(f_rub, ''))}  |  {_norm(f.get(f_rub_comp, ''))}")

    trabs = _get_all("DimTrabajador")
    f_trab = _fid("DimTrabajador", "NombreCompleto")
    print(f"\nTRABAJADORES ({len(trabs)}):")
    for r in trabs[:15]:
        f = r["fields"]
        print(f"  {r['id']}  |  {_norm(f.get(f_trab, ''))}")

    cabs = _get_all("MedicionCabecera")
    print(f"\nMEDICION CABECERAS EXISTENTES: {len(cabs)}")
    lineas = _get_all("MedicionLinea")
    print(f"MEDICION LINEAS EXISTENTES: {len(lineas)}")

    return obras, sectores, rubros, trabs


# ---------------------------------------------------------------------------
# Seed — create test records
# ---------------------------------------------------------------------------

def seed(obras, sectores, rubros, trabs):
    print("\n═══ CREANDO DATOS DE PRUEBA ═══\n")

    # Pick dimension IDs
    if len(obras) < 1:
        print("ERROR: No hay obras. Creá al menos 1 obra en Airtable primero.")
        return
    if len(trabs) < 1:
        print("ERROR: No hay trabajadores. Creá al menos 1 en Airtable primero.")
        return
    if len(rubros) < 2:
        print("ERROR: Se necesitan al menos 2 rubros.")
        return

    f_sec_obra = _fid("DimSector", "ObraID")

    # Select first 2 obras (or just 1 if only 1 exists)
    obra1_id = obras[0]["id"]
    obra2_id = obras[1]["id"] if len(obras) > 1 else obra1_id

    # Sectores for each obra
    secs_obra1 = [s for s in sectores if _norm(s["fields"].get(f_sec_obra, "")) == obra1_id]
    secs_obra2 = [s for s in sectores if _norm(s["fields"].get(f_sec_obra, "")) == obra2_id]

    if not secs_obra1:
        print(f"WARN: La obra {obra1_id} no tiene sectores. Usando primer sector disponible.")
        secs_obra1 = sectores[:2] if len(sectores) >= 2 else sectores[:1]
    if not secs_obra2:
        secs_obra2 = sectores[:2] if len(sectores) >= 2 else sectores[:1]

    sec1a = secs_obra1[0]["id"]
    sec1b = secs_obra1[1]["id"] if len(secs_obra1) > 1 else sec1a

    sec2a = secs_obra2[0]["id"]

    # Rubros
    rub1 = rubros[0]["id"]
    rub2 = rubros[1]["id"]
    rub3 = rubros[2]["id"] if len(rubros) > 2 else rub1

    # Trabajadores
    trab1 = trabs[0]["id"]
    trab2 = trabs[1]["id"] if len(trabs) > 1 else trab1

    f_rub = _fid("DimRubro", "Rubro")
    rub_names = {r["id"]: _norm(r["fields"].get(f_rub, "?")) for r in rubros}
    f_trab_name = _fid("DimTrabajador", "NombreCompleto")
    trab_names = {t["id"]: _norm(t["fields"].get(f_trab_name, "?")) for t in trabs}
    f_clave = _fid("obras", "Clave")
    obra_names = {o["id"]: _norm(o["fields"].get(f_clave, "?")) for o in obras}

    print(f"  Obra 1: {obra_names.get(obra1_id)}")
    print(f"  Obra 2: {obra_names.get(obra2_id)}")
    print(f"  Trab 1: {trab_names.get(trab1)}")
    print(f"  Trab 2: {trab_names.get(trab2)}")
    print(f"  Rubros: {rub_names.get(rub1)}, {rub_names.get(rub2)}, {rub_names.get(rub3)}")
    print()

    # ── Cabecera 1: Borrador, obra1, trab1, semana actual ──────────────────
    cab1 = _create("MedicionCabecera", {
        "ObraID":        [obra1_id],
        "TrabajadorID":  [trab1],
        "Fecha":         "2026-03-23",
        "Estado":        "Borrador",
        "Observaciones": "Medición parcial semana 13 — faltan precios de pintura",
    })
    print(f"  ✓ Cabecera 1 (Borrador): {cab1}")

    # Líneas para cabecera 1 — mezcla de rubros, algunas sin precio
    lines_cab1 = [
        # Sector A, Rubro 1
        {"cab": cab1, "sec": sec1a, "rub": rub1, "desc": "Contrapiso H°P° esp. 10cm",
         "ud": "m²", "largo": 5.2, "ancho": 3.8, "alto": 0, "cant": None, "pu": 45000},
        {"cab": cab1, "sec": sec1a, "rub": rub1, "desc": "Carpeta de nivelación esp. 3cm",
         "ud": "m²", "largo": 5.2, "ancho": 3.8, "alto": 0, "cant": None, "pu": 18000},
        # Sector A, Rubro 2
        {"cab": cab1, "sec": sec1a, "rub": rub2, "desc": "Revoque grueso interior",
         "ud": "m²", "largo": 12.0, "ancho": 0, "alto": 2.8, "cant": None, "pu": 22000},
        {"cab": cab1, "sec": sec1a, "rub": rub2, "desc": "Revoque fino interior",
         "ud": "m²", "largo": 12.0, "ancho": 0, "alto": 2.8, "cant": None, "pu": 0},  # sin precio
        # Sector B, Rubro 1
        {"cab": cab1, "sec": sec1b, "rub": rub1, "desc": "Contrapiso H°P° esp. 10cm",
         "ud": "m²", "largo": 4.0, "ancho": 6.5, "alto": 0, "cant": None, "pu": 45000},
        # Sector B, Rubro 3 (mixed rubros)
        {"cab": cab1, "sec": sec1b, "rub": rub3, "desc": "Cañería PVC 110mm",
         "ud": "ml", "largo": 0, "ancho": 0, "alto": 0, "cant": 15.5, "pu": 35000},
        {"cab": cab1, "sec": sec1b, "rub": rub3, "desc": "Pileta de cocina colocación",
         "ud": "un", "largo": 0, "ancho": 0, "alto": 0, "cant": 1, "pu": 0},  # sin precio
    ]

    for l in lines_cab1:
        largo = l["largo"]
        ancho = l["ancho"]
        alto  = l["alto"]
        if largo > 0 or ancho > 0 or alto > 0:
            cant = (largo if largo > 0 else 1) * (ancho if ancho > 0 else 1) * (alto if alto > 0 else 1)
        else:
            cant = l["cant"] or 0
        _create("MedicionLinea", {
            "CabeceraID":     [l["cab"]],
            "SectorID":       [l["sec"]],
            "RubroID":        [l["rub"]],
            "Descripcion":    l["desc"],
            "Unidad":         l["ud"],
            "Largo":          largo if largo else None,
            "Ancho":          ancho if ancho else None,
            "Alto":           alto if alto else None,
            "Cantidad":       round(cant, 3),
            "PrecioUnitario": l["pu"] if l["pu"] else None,
        })
    print(f"    → {len(lines_cab1)} líneas creadas")

    # ── Cabecera 2: Confirmada, obra1, trab1, semana anterior ──────────────
    cab2 = _create("MedicionCabecera", {
        "ObraID":        [obra1_id],
        "TrabajadorID":  [trab1],
        "Fecha":         "2026-03-16",
        "Estado":        "Confirmado",
        "Observaciones": "Semana 12 — medición completa",
    })
    print(f"  ✓ Cabecera 2 (Confirmada): {cab2}")

    lines_cab2 = [
        {"cab": cab2, "sec": sec1a, "rub": rub1, "desc": "Contrapiso H°P° esp. 10cm",
         "ud": "m²", "largo": 3.0, "ancho": 4.0, "alto": 0, "cant": None, "pu": 45000},
        {"cab": cab2, "sec": sec1a, "rub": rub1, "desc": "Carpeta de nivelación esp. 3cm",
         "ud": "m²", "largo": 3.0, "ancho": 4.0, "alto": 0, "cant": None, "pu": 18000},
        {"cab": cab2, "sec": sec1a, "rub": rub2, "desc": "Revoque grueso interior",
         "ud": "m²", "largo": 8.0, "ancho": 0, "alto": 2.8, "cant": None, "pu": 20000},
        {"cab": cab2, "sec": sec1a, "rub": rub2, "desc": "Revoque fino interior",
         "ud": "m²", "largo": 8.0, "ancho": 0, "alto": 2.8, "cant": None, "pu": 15000},
    ]

    for l in lines_cab2:
        largo = l["largo"]
        ancho = l["ancho"]
        alto  = l["alto"]
        if largo > 0 or ancho > 0 or alto > 0:
            cant = (largo if largo > 0 else 1) * (ancho if ancho > 0 else 1) * (alto if alto > 0 else 1)
        else:
            cant = l["cant"] or 0
        _create("MedicionLinea", {
            "CabeceraID":     [l["cab"]],
            "SectorID":       [l["sec"]],
            "RubroID":        [l["rub"]],
            "Descripcion":    l["desc"],
            "Unidad":         l["ud"],
            "Largo":          largo if largo else None,
            "Ancho":          ancho if ancho else None,
            "Alto":           alto if alto else None,
            "Cantidad":       round(cant, 3),
            "PrecioUnitario": l["pu"] if l["pu"] else None,
        })
    print(f"    → {len(lines_cab2)} líneas creadas")

    # ── Cabecera 3: Confirmada, obra1, trab2, misma semana que cab2 ────────
    cab3 = _create("MedicionCabecera", {
        "ObraID":        [obra1_id],
        "TrabajadorID":  [trab2],
        "Fecha":         "2026-03-17",
        "Estado":        "Confirmado",
        "Observaciones": "",
    })
    print(f"  ✓ Cabecera 3 (Confirmada, otro subcontratista): {cab3}")

    lines_cab3 = [
        {"cab": cab3, "sec": sec1a, "rub": rub2, "desc": "Revoque grueso exterior",
         "ud": "m²", "largo": 15.0, "ancho": 0, "alto": 3.2, "cant": None, "pu": 28000},
        {"cab": cab3, "sec": sec1a, "rub": rub2, "desc": "Revoque fino exterior",
         "ud": "m²", "largo": 15.0, "ancho": 0, "alto": 3.2, "cant": None, "pu": 20000},
        {"cab": cab3, "sec": sec1b, "rub": rub1, "desc": "Mampostería ladrillo hueco 12cm",
         "ud": "m²", "largo": 6.0, "ancho": 0, "alto": 2.8, "cant": None, "pu": 55000},
    ]

    for l in lines_cab3:
        largo = l["largo"]
        ancho = l["ancho"]
        alto  = l["alto"]
        if largo > 0 or ancho > 0 or alto > 0:
            cant = (largo if largo > 0 else 1) * (ancho if ancho > 0 else 1) * (alto if alto > 0 else 1)
        else:
            cant = l["cant"] or 0
        _create("MedicionLinea", {
            "CabeceraID":     [l["cab"]],
            "SectorID":       [l["sec"]],
            "RubroID":        [l["rub"]],
            "Descripcion":    l["desc"],
            "Unidad":         l["ud"],
            "Largo":          largo if largo else None,
            "Ancho":          ancho if ancho else None,
            "Alto":           alto if alto else None,
            "Cantidad":       round(cant, 3),
            "PrecioUnitario": l["pu"] if l["pu"] else None,
        })
    print(f"    → {len(lines_cab3)} líneas creadas")

    # ── Cabecera 4: Borrador, obra2, trab1, fecha reciente ─────────────────
    if obra2_id != obra1_id:
        cab4 = _create("MedicionCabecera", {
            "ObraID":        [obra2_id],
            "TrabajadorID":  [trab1],
            "Fecha":         "2026-03-28",
            "Estado":        "Borrador",
            "Observaciones": "Obra 2 — primer relevamiento",
        })
        print(f"  ✓ Cabecera 4 (Borrador, obra2): {cab4}")

        lines_cab4 = [
            {"cab": cab4, "sec": sec2a, "rub": rub1, "desc": "Contrapiso H°P° esp. 12cm",
             "ud": "m²", "largo": 10.0, "ancho": 8.0, "alto": 0, "cant": None, "pu": 52000},
            {"cab": cab4, "sec": sec2a, "rub": rub1, "desc": "Vereda perimetral esp. 8cm",
             "ud": "m²", "largo": 24.0, "ancho": 1.2, "alto": 0, "cant": None, "pu": 38000},
            {"cab": cab4, "sec": sec2a, "rub": rub3, "desc": "Instalación sanitaria completa",
             "ud": "un", "largo": 0, "ancho": 0, "alto": 0, "cant": 1, "pu": 0},  # sin precio
        ]

        for l in lines_cab4:
            largo = l["largo"]
            ancho = l["ancho"]
            alto  = l["alto"]
            if largo > 0 or ancho > 0 or alto > 0:
                cant = (largo if largo > 0 else 1) * (ancho if ancho > 0 else 1) * (alto if alto > 0 else 1)
            else:
                cant = l["cant"] or 0
            _create("MedicionLinea", {
                "CabeceraID":     [l["cab"]],
                "SectorID":       [l["sec"]],
                "RubroID":        [l["rub"]],
                "Descripcion":    l["desc"],
                "Unidad":         l["ud"],
                "Largo":          largo if largo else None,
                "Ancho":          ancho if ancho else None,
                "Alto":           alto if alto else None,
                "Cantidad":       round(cant, 3),
                "PrecioUnitario": l["pu"] if l["pu"] else None,
            })
        print(f"    → {len(lines_cab4)} líneas creadas")

    # ── Cabecera 5: Confirmada semana 11 (para tener historial en Vista General)
    cab5 = _create("MedicionCabecera", {
        "ObraID":        [obra1_id],
        "TrabajadorID":  [trab1],
        "Fecha":         "2026-03-09",
        "Estado":        "Confirmado",
        "Observaciones": "Semana 11",
    })
    print(f"  ✓ Cabecera 5 (Confirmada semana 11): {cab5}")

    lines_cab5 = [
        {"cab": cab5, "sec": sec1a, "rub": rub1, "desc": "Contrapiso H°P° esp. 10cm",
         "ud": "m²", "largo": 4.5, "ancho": 3.0, "alto": 0, "cant": None, "pu": 43000},
        {"cab": cab5, "sec": sec1a, "rub": rub2, "desc": "Revoque grueso interior",
         "ud": "m²", "largo": 6.0, "ancho": 0, "alto": 2.8, "cant": None, "pu": 20000},
    ]

    for l in lines_cab5:
        largo = l["largo"]
        ancho = l["ancho"]
        alto  = l["alto"]
        if largo > 0 or ancho > 0 or alto > 0:
            cant = (largo if largo > 0 else 1) * (ancho if ancho > 0 else 1) * (alto if alto > 0 else 1)
        else:
            cant = l["cant"] or 0
        _create("MedicionLinea", {
            "CabeceraID":     [l["cab"]],
            "SectorID":       [l["sec"]],
            "RubroID":        [l["rub"]],
            "Descripcion":    l["desc"],
            "Unidad":         l["ud"],
            "Largo":          largo if largo else None,
            "Ancho":          ancho if ancho else None,
            "Alto":           alto if alto else None,
            "Cantidad":       round(cant, 3),
            "PrecioUnitario": l["pu"] if l["pu"] else None,
        })
    print(f"    → {len(lines_cab5)} líneas creadas")

    print("\n═══ SEED COMPLETADO ═══")
    print(f"Cabeceras: 5 (2 borradores + 3 confirmadas)")
    total_lines = len(lines_cab1) + len(lines_cab2) + len(lines_cab3) + len(lines_cab5)
    if obra2_id != obra1_id:
        total_lines += len(lines_cab4)
    print(f"Líneas totales: {total_lines}")
    print("\nQué probar:")
    print("  Tab ✏️ Editar:")
    print("    - Cargar borrador → editar líneas → guardar")
    print("    - Cargar confirmada → verificar que esté bloqueada → reabrir")
    print("    - Exportar PDF y Excel de cualquier medición")
    print("    - Confirmar borrador → alerta de duplicado (misma semana)")
    print("  Tab 📊 Vista General:")
    print("    - Filtrar por obra1 + trab1 → ver acumulado de 3 semanas")
    print("    - Ítems repetidos (Contrapiso, Revoque) deben sumar cantidades")
    print("    - Ítems sin precio → badge de advertencia")
    print("    - Exportar acumulado a PDF y Excel")


# ---------------------------------------------------------------------------
# Clean — delete all test data
# ---------------------------------------------------------------------------

def clean():
    print("\n═══ LIMPIANDO DATOS DE MEDICIONES ═══\n")
    n_lines = _delete_all("MedicionLinea")
    print(f"  Líneas eliminadas: {n_lines}")
    n_cabs = _delete_all("MedicionCabecera")
    print(f"  Cabeceras eliminadas: {n_cabs}")
    print("\n═══ LIMPIEZA COMPLETADA ═══")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed datos de prueba para Tool 5 - Mediciones")
    parser.add_argument("--run", action="store_true", help="Crear registros de prueba")
    parser.add_argument("--clean", action="store_true", help="Borrar TODOS los registros de MedicionCabecera + MedicionLinea")
    args = parser.parse_args()

    if args.clean:
        clean()
    elif args.run:
        obras, sectores, rubros, trabs = show_dimensions()
        seed(obras, sectores, rubros, trabs)
    else:
        show_dimensions()
        print("\n→ Usá --run para crear datos de prueba, --clean para borrar todo.")
