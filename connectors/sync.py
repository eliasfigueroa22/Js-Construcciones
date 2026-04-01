"""Motor de sincronización Airtable → Supabase para JS Tools.

Uso típico (desde app.py o un script):
    from connectors.sync import run_full_sync
    result = run_full_sync()
    # result = {"status": "success", "total": 1234, "tables": {...}, "errors": [...]}

Estrategia:
  - Upsert en Supabase usando airtable_id como clave de conflicto.
  - Los IDs "rec..." de Airtable se resuelven a BIGINT de Supabase mediante
    un id_map construido después de cada batch de dimensiones.
  - Si un FK no se puede resolver (registro dim faltante), el registro se
    saltea y se loguea el warning — nunca se inserta con FK roto.
  - Orden de sync respeta el grafo de dependencias (ver SYNC_ORDER).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from connectors.airtable import get_all_records as at_get_all
from connectors.supabase_connector import get_service_client, upsert_records, clear_cache
from config import TABLES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Orden de sync — respeta dependencias de FK
# Tuplas: (airtable_table_key, supabase_table_name)
# ---------------------------------------------------------------------------
SYNC_ORDER: list[tuple[str, str]] = [
    # Batch 1: dims hoja (sin FK a otras dims)
    ("DimClientes",    "dim_cliente"),
    ("DimRubro",       "dim_rubro"),
    ("DimProveedores", "dim_proveedor"),
    # Batch 2: dims que referencian batch 1
    ("obras",          "dim_obra"),
    ("DimTrabajador",  "dim_trabajador"),
    # Batch 3: dims que referencian batch 2
    ("DimSector",      "dim_sector"),
    # Batch 4: hechos solo con FK a dims
    ("FactPresupuestoSubcontratista", "fact_presupuesto_subcontratista"),
    ("facturas",                      "fact_compra"),
    ("FactPresupuestoCliente",        "fact_presupuesto_cliente"),
    ("FactIngreso",                   "fact_ingreso"),
    ("FactDeuda",                     "fact_deuda"),
    # Batch 5: hechos que referencian otros hechos
    ("FactPago",                      "fact_pago"),
    ("FactFacturacionSubcontratista", "fact_facturacion_subcontratista"),
    ("FactPagoDeuda",                 "fact_pago_deuda"),
    # Batch 6: operacionales (cabeceras)
    ("CertPresupuestoLinea", "op_cert_presupuesto_linea"),
    ("MedicionCabecera",     "op_medicion_cabecera"),
    # Batch 7: operacionales (líneas dependen de cabeceras)
    ("MedicionLinea", "op_medicion_linea"),
    ("CertCabecera",  "op_cert_cabecera"),
    # Batch 8: líneas de cert (dependen de CertCabecera + CertPresupuestoLinea)
    ("CertLinea", "op_cert_linea"),
    # Batch 9: auxiliares
    ("FalsosDuplicados", "aux_falsos_duplicados"),
]


# ---------------------------------------------------------------------------
# id_map: { supabase_table → { airtable_id → supabase_int_id } }
# ---------------------------------------------------------------------------
IdMap = dict[str, dict[str, int]]


def _build_id_map(sb_table: str, current_map: IdMap) -> None:
    """Consulta Supabase y puebla current_map[sb_table] con {airtable_id: id}."""
    client = get_service_client()
    # Paginar en chunks de 1000 para tablas grandes
    chunk = 1000
    offset = 0
    current_map[sb_table] = {}
    while True:
        resp = (
            client.table(sb_table)
            .select("id, airtable_id")
            .range(offset, offset + chunk - 1)
            .execute()
        )
        rows = resp.data or []
        for row in rows:
            current_map[sb_table][row["airtable_id"]] = row["id"]
        if len(rows) < chunk:
            break
        offset += chunk


def _resolve(
    value: str | list | None,
    sb_table: str,
    id_map: IdMap,
) -> int | None:
    """Convierte un rec... de Airtable al BIGINT surrogate de Supabase.

    Airtable devuelve linked fields como lista de rec IDs.
    """
    if not value:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if not value:
        return None
    return id_map.get(sb_table, {}).get(value)


# ---------------------------------------------------------------------------
# Funciones de mapeo: Airtable record → dict para Supabase
# Cada función recibe (rec: dict, id_map: IdMap) → dict | None
# Retorna None si el registro debe saltearse.
# ---------------------------------------------------------------------------

def _v(rec: dict, key: str) -> Any:
    """Atajo: obtiene el valor ya normalizado del campo (post-pyairtable)."""
    return rec.get(key)


def _map_dim_cliente(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":   rec["_id"],
        "nombre_cliente": _v(rec, "NombreCliente"),
        "cliente_nro":    _v(rec, "ClienteNro"),
        "ruc":            _v(rec, "RUC"),
        "direccion":      _v(rec, "Direccion"),
        "telefono":       _v(rec, "Telefono"),
        "email":          _v(rec, "Email"),
        "tipo_cliente":   _v(rec, "TipoCliente"),
        "fecha_registro": _v(rec, "FechaRegistro"),
    }


def _map_dim_rubro(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":    rec["_id"],
        "rubro":          _v(rec, "Rubro"),
        "nombre_completo":_v(rec, "NombreCompleto"),
    }


def _map_dim_proveedor(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":      rec["_id"],
        "nombre_proveedor": _v(rec, "NombreProveedor"),
        "proveedor_nro":    _v(rec, "ProveedorNro"),
        "ruc":              _v(rec, "RUC"),
        "telefono":         _v(rec, "Telefono"),
        "email":            _v(rec, "Email"),
    }


def _map_dim_obra(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":   rec["_id"],
        "nombre":        _v(rec, "Nombre"),
        "clave":         _v(rec, "Clave") or "",
        "obra_nro":      _v(rec, "ObraNro"),
        "estado_obra":   _v(rec, "EstadoObra"),
        "categoria_obra":_v(rec, "CategoriaObra"),
        "cliente_id":    _resolve(_v(rec, "ClienteID"), "dim_cliente", id_map),
        "ubicacion":     _v(rec, "Ubicacion"),
        "superficie":    _v(rec, "Superficie"),
    }


def _map_dim_trabajador(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":    rec["_id"],
        "nombre_completo":_v(rec, "NombreCompleto"),
        "trabajador_nro": _v(rec, "TrabajadorNro"),
        "tipo_personal":  _v(rec, "TipoPersonal"),
        "telefono":       _v(rec, "Telefono"),
        "ruc_ci":         _v(rec, "RUC_CI"),
        "rubro_id":       _resolve(_v(rec, "RubroID"), "dim_rubro", id_map),
    }


def _map_dim_sector(rec: dict, id_map: IdMap) -> dict | None:
    obra_id = _resolve(_v(rec, "ObraID"), "dim_obra", id_map)
    return {
        "airtable_id":  rec["_id"],
        "nombre_sector":_v(rec, "NombreSector"),
        "sector_nro":   _v(rec, "SectorNro"),
        "obra_id":      obra_id,
        "descripcion":  _v(rec, "Descripcion"),
    }


def _map_fact_presupuesto_subcontratista(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":          rec["_id"],
        "presupuesto_nro":      _v(rec, "PresupuestoNro"),
        "trabajador_id":        _resolve(_v(rec, "TrabajadorID"), "dim_trabajador", id_map),
        "obra_id":              _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "sector_id":            _resolve(_v(rec, "SectorID"), "dim_sector", id_map),
        "rubro_id":             _resolve(_v(rec, "RubroID"), "dim_rubro", id_map),
        "concepto":             _v(rec, "Concepto"),
        "fecha_presupuesto":    _v(rec, "FechaPresupuesto"),
        "monto_presupuestado":  _v(rec, "MontoPresupuestado"),
        "estado":               _v(rec, "Estado"),
    }


def _map_fact_compra(rec: dict, id_map: IdMap) -> dict | None:
    # Proveedor puede ser texto libre o un rec ID (linked)
    proveedor_raw = _v(rec, "Proveedor")
    proveedor_id = None
    proveedor_texto = None
    if isinstance(proveedor_raw, list) and proveedor_raw and str(proveedor_raw[0]).startswith("rec"):
        proveedor_id = _resolve(proveedor_raw, "dim_proveedor", id_map)
    else:
        proveedor_texto = proveedor_raw if isinstance(proveedor_raw, str) else (
            proveedor_raw[0] if isinstance(proveedor_raw, list) and proveedor_raw else None
        )

    return {
        "airtable_id":       rec["_id"],
        "compra_nro":        _v(rec, "CompraNro"),
        "obra_id":           _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "sector_id":         _resolve(_v(rec, "SectorID"), "dim_sector", id_map),
        "rubro_id":          _resolve(_v(rec, "RubroID"), "dim_rubro", id_map),
        "proveedor_texto":   proveedor_texto,
        "proveedor_id":      proveedor_id,
        "fecha":             _v(rec, "Fecha"),
        "nro_factura":       _v(rec, "NroFactura"),
        "descripcion":       _v(rec, "Descripcion"),
        "cantidad":          _v(rec, "Cantidad"),
        "unidad":            _v(rec, "Unidad"),
        "monto_total":       _v(rec, "MontoTotal"),
        "tipo_documento":    _v(rec, "TipoDocumento"),
        "observaciones":     _v(rec, "Observaciones"),
        "created_at_source": _v(rec, "Created"),
    }


def _map_fact_presupuesto_cliente(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":            rec["_id"],
        "presupuesto_cliente_nro":_v(rec, "PresupuestoClienteNro"),
        "obra_id":                _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "sector_id":              _resolve(_v(rec, "SectorID"), "dim_sector", id_map),
        "rubro_id":               _resolve(_v(rec, "RubroID"), "dim_rubro", id_map),
        "tipo_presupuesto":       _v(rec, "TipoPresupuesto"),
        "numero_version":         _v(rec, "NumeroVersion"),
        "fecha_presupuesto":      _v(rec, "FechaPresupuesto"),
        "fecha_aprobacion":       _v(rec, "FechaAprobacion"),
        "descripcion":            _v(rec, "Descripcion"),
        "cantidad":               _v(rec, "Cantidad"),
        "unidad":                 _v(rec, "Unidad"),
        "precio_unitario":        _v(rec, "PrecioUnitario"),
        "monto_total":            _v(rec, "MontoTotal"),
        "estado":                 _v(rec, "Estado"),
        "observaciones":          _v(rec, "Observaciones"),
    }


def _map_fact_ingreso(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":    rec["_id"],
        "ingreso_nro":    _v(rec, "IngresoNro"),
        "obra_id":        _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "fecha_ingreso":  _v(rec, "FechaIngreso"),
        "fecha_factura":  _v(rec, "FechaFactura"),
        "numero_factura": _v(rec, "NumeroFactura"),
        "tipo_ingreso":   _v(rec, "TipoIngreso"),
        "concepto":       _v(rec, "Concepto"),
        "monto_facturado":_v(rec, "MontoFacturado"),
        "monto_recibido": _v(rec, "MontoRecibido"),
        "estado_cobro":   _v(rec, "EstadoCobro"),
        "fecha_cobro":    _v(rec, "FechaCobro"),
        "metodo_pago":    _v(rec, "MetodoPago"),
        "observaciones":  _v(rec, "Observaciones"),
    }


def _map_fact_deuda(rec: dict, id_map: IdMap) -> dict | None:
    tipo_raw = _v(rec, "TipoDeuda")
    # Airtable devuelve multiSelect como lista; tomamos el primer valor
    if isinstance(tipo_raw, list):
        tipo_str = tipo_raw[0] if tipo_raw else None
    else:
        tipo_str = tipo_raw or None
    return {
        "airtable_id":   rec["_id"],
        "deuda_nro":     _v(rec, "DeudaNro"),
        "obra_id":       _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "trabajador_id": _resolve(_v(rec, "TrabajadorID"), "dim_trabajador", id_map),
        "tipo_deuda":    tipo_str,
        "fecha_solicitud":_v(rec, "FechaSolicitud"),
        "monto_deuda":   _v(rec, "MontoDeuda"),
        "estado":        _v(rec, "Estado"),
        "observaciones": _v(rec, "Observaciones"),
    }


def _map_fact_pago(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":                   rec["_id"],
        "pago_nro":                       _v(rec, "PagoNro"),
        "presupuesto_subcontratista_id":  _resolve(
            _v(rec, "PresupuestoSubcontratistaID"),
            "fact_presupuesto_subcontratista",
            id_map,
        ),
        "obra_id":      _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "trabajador_id":_resolve(_v(rec, "TrabajadorID"), "dim_trabajador", id_map),
        "sector_id":    _resolve(_v(rec, "SectorID"), "dim_sector", id_map),
        "rubro_id":     _resolve(_v(rec, "RubroID"), "dim_rubro", id_map),
        "fecha_pago":   _v(rec, "FechaPago"),
        "concepto":     _v(rec, "Concepto"),
        "tipo_pago":    _v(rec, "TipoPago"),
        "monto_pago":   _v(rec, "MontoPago"),
        "metodo_pago":  _v(rec, "MetodoPago"),
    }


def _map_fact_facturacion_subcontratista(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":                   rec["_id"],
        "facturacion_nro":               _v(rec, "FacturacionNro"),
        "presupuesto_subcontratista_id": _resolve(
            _v(rec, "PresupuestoSubcontratistaID"),
            "fact_presupuesto_subcontratista",
            id_map,
        ),
        "fecha_factura":      _v(rec, "FechaFactura"),
        "numero_factura":     _v(rec, "NumeroFactura"),
        "monto_facturado":    _v(rec, "MontoFacturado"),
        "porcentaje_aplicado":_v(rec, "PorcentajeAplicado"),
        "observaciones":      _v(rec, "Observaciones"),
    }


def _map_fact_pago_deuda(rec: dict, id_map: IdMap) -> dict | None:
    deuda_id = _resolve(_v(rec, "DeudaID"), "fact_deuda", id_map)
    if deuda_id is None:
        logger.warning("fact_pago_deuda %s: DeudaID no resuelto — salteado", rec["_id"])
        return None
    return {
        "airtable_id":  rec["_id"],
        "pago_deuda_nro":_v(rec, "PagoDeudaNro"),
        "deuda_id":     deuda_id,
        "fecha_pago":   _v(rec, "FechaPago"),
        "monto_pagado": _v(rec, "MontoPagado"),
        "metodo_pago":  _v(rec, "MetodoPago"),
        "observaciones":_v(rec, "Observaciones"),
    }


def _map_op_cert_presupuesto_linea(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":   rec["_id"],
        "rubro_texto":   _v(rec, "Rubro"),
        "rubro_id":      _resolve(_v(rec, "RubroID"), "dim_rubro", id_map) if _v(rec, "RubroID") else None,
        "obra_id":       _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "orden":         _v(rec, "Orden"),
        "item_nro":      _v(rec, "ItemNro"),
        "zona":          _v(rec, "Zona"),
        "grupo_nombre":  _v(rec, "GrupoNombre"),
        "unidad":        _v(rec, "Unidad"),
        "cantidad":      _v(rec, "Cantidad"),
        "precio_unitario":_v(rec, "PrecioUnitario"),
        "observaciones": _v(rec, "Observaciones"),
        "sin_cotizar":   bool(_v(rec, "SinCotizar")),
    }


def _map_op_medicion_cabecera(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":  rec["_id"],
        "medicion_ref": _v(rec, "MedicionRef") or rec["_id"],
        "obra_id":      _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "trabajador_id":_resolve(_v(rec, "TrabajadorID"), "dim_trabajador", id_map),
        "fecha":        _v(rec, "Fecha"),
        "estado":       _v(rec, "Estado"),
        "observaciones":_v(rec, "Observaciones"),
    }


def _map_op_medicion_linea(rec: dict, id_map: IdMap) -> dict | None:
    cabecera_id = _resolve(_v(rec, "CabeceraID"), "op_medicion_cabecera", id_map)
    if cabecera_id is None:
        logger.warning("op_medicion_linea %s: CabeceraID no resuelto — salteado", rec["_id"])
        return None
    return {
        "airtable_id":   rec["_id"],
        "cabecera_id":   cabecera_id,
        "sector_id":     _resolve(_v(rec, "SectorID"), "dim_sector", id_map),
        "rubro_id":      _resolve(_v(rec, "RubroID"), "dim_rubro", id_map),
        "descripcion":   _v(rec, "Descripcion"),
        "unidad":        _v(rec, "Unidad"),
        "largo":         _v(rec, "Largo"),
        "ancho":         _v(rec, "Ancho"),
        "alto":          _v(rec, "Alto"),
        "cantidad":      _v(rec, "Cantidad"),
        "precio_unitario":_v(rec, "PrecioUnitario"),
    }


def _map_op_cert_cabecera(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id":      rec["_id"],
        "cert_ref":         _v(rec, "CertRef") or rec["_id"],
        "obra_id":          _resolve(_v(rec, "ObraID"), "dim_obra", id_map),
        "numero":           _v(rec, "Numero"),
        "fecha_certificado":_v(rec, "FechaCertificado"),
        "estado":           _v(rec, "Estado"),
        "observaciones":    _v(rec, "Observaciones"),
    }


def _map_op_cert_linea(rec: dict, id_map: IdMap) -> dict | None:
    cabecera_id = _resolve(_v(rec, "CabeceraID"), "op_cert_cabecera", id_map)
    if cabecera_id is None:
        logger.warning("op_cert_linea %s: CabeceraID no resuelto — salteado", rec["_id"])
        return None
    return {
        "airtable_id":         rec["_id"],
        "linea_ref":           _v(rec, "LineaRef"),
        "cabecera_id":         cabecera_id,
        "presupuesto_linea_id":_resolve(
            _v(rec, "PresupuestoLineaID"), "op_cert_presupuesto_linea", id_map
        ),
        "cantidad_certificada":_v(rec, "CantidadCertificada"),
    }


def _map_aux_falsos_duplicados(rec: dict, id_map: IdMap) -> dict | None:
    return {
        "airtable_id": rec["_id"],
        "clave_grupo": _v(rec, "ClaveGrupo") or rec["_id"],
        "tipo":        _v(rec, "Tipo"),
        "nro_factura": _v(rec, "NroFactura"),
        "proveedor":   _v(rec, "Proveedor"),
    }


# Registro de mappers por tabla de Airtable
_MAPPERS: dict[str, Any] = {
    "DimClientes":                   _map_dim_cliente,
    "DimRubro":                      _map_dim_rubro,
    "DimProveedores":                _map_dim_proveedor,
    "obras":                         _map_dim_obra,
    "DimTrabajador":                 _map_dim_trabajador,
    "DimSector":                     _map_dim_sector,
    "FactPresupuestoSubcontratista": _map_fact_presupuesto_subcontratista,
    "facturas":                      _map_fact_compra,
    "FactPresupuestoCliente":        _map_fact_presupuesto_cliente,
    "FactIngreso":                   _map_fact_ingreso,
    "FactDeuda":                     _map_fact_deuda,
    "FactPago":                      _map_fact_pago,
    "FactFacturacionSubcontratista": _map_fact_facturacion_subcontratista,
    "FactPagoDeuda":                 _map_fact_pago_deuda,
    "CertPresupuestoLinea":          _map_op_cert_presupuesto_linea,
    "MedicionCabecera":              _map_op_medicion_cabecera,
    "MedicionLinea":                 _map_op_medicion_linea,
    "CertCabecera":                  _map_op_cert_cabecera,
    "CertLinea":                     _map_op_cert_linea,
    "FalsosDuplicados":              _map_aux_falsos_duplicados,
}


# ---------------------------------------------------------------------------
# Core: sincronizar una tabla
# ---------------------------------------------------------------------------

def _sync_table(
    at_key: str,
    sb_table: str,
    id_map: IdMap,
    errors: list[str],
) -> int:
    """Sincroniza una tabla de Airtable a Supabase.

    Returns:
        Cantidad de registros upsertados.
    """
    mapper = _MAPPERS.get(at_key)
    if mapper is None:
        errors.append(f"{at_key}: no hay mapper definido")
        return 0

    # Leer todos los registros de Airtable (usa el caché de airtable.py)
    try:
        at_records = at_get_all(at_key)
    except Exception as exc:
        errors.append(f"{at_key}: error leyendo Airtable — {exc}")
        return 0

    # Mapear cada registro
    rows: list[dict] = []
    for rec in at_records:
        try:
            mapped = mapper(rec, id_map)
        except Exception as exc:
            errors.append(f"{at_key} rec {rec.get('id', '?')}: error en mapper — {exc}")
            continue
        if mapped is not None:
            rows.append(mapped)

    if not rows:
        return 0

    # Upsert en Supabase
    try:
        count = upsert_records(sb_table, rows, conflict_col="airtable_id", use_service_role=True)
    except Exception as exc:
        errors.append(f"{sb_table}: error en upsert — {exc}")
        return 0

    # Actualizar id_map con los nuevos registros
    _build_id_map(sb_table, id_map)

    return count


# ---------------------------------------------------------------------------
# Sync log helpers
# ---------------------------------------------------------------------------

def _log_start(table_name: str) -> int | None:
    """Inserta una fila 'running' en aux_sync_log y devuelve su id."""
    try:
        client = get_service_client()
        resp = (
            client.table("aux_sync_log")
            .insert({"table_name": table_name, "status": "running"})
            .execute()
        )
        return resp.data[0]["id"] if resp.data else None
    except Exception:
        return None


def _log_finish(log_id: int | None, records: int, error: str | None = None) -> None:
    if log_id is None:
        return
    try:
        client = get_service_client()
        client.table("aux_sync_log").update({
            "finished_at":      datetime.now(timezone.utc).isoformat(),
            "records_upserted": records,
            "status":           "error" if error else "success",
            "error_message":    error,
        }).eq("id", log_id).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def run_full_sync() -> dict:
    """Ejecuta el sync completo Airtable → Supabase.

    Returns:
        {
            "status": "success" | "partial" | "error",
            "total":  int,          # registros totales upsertados
            "tables": {tabla: count},
            "errors": [str],
        }
    """
    id_map: IdMap = {}
    errors: list[str] = []
    table_counts: dict[str, int] = {}
    total = 0

    # Log global de sync
    global_log_id = _log_start("__full_sync__")

    for at_key, sb_table in SYNC_ORDER:
        log_id = _log_start(sb_table)
        try:
            count = _sync_table(at_key, sb_table, id_map, errors)
            table_counts[sb_table] = count
            total += count
            _log_finish(log_id, count)
        except Exception as exc:
            err_msg = f"{sb_table}: excepción inesperada — {exc}"
            errors.append(err_msg)
            _log_finish(log_id, 0, err_msg)

    # Invalidar caché de Supabase para que la app lea datos frescos
    clear_cache()

    status = "success" if not errors else ("partial" if total > 0 else "error")
    _log_finish(global_log_id, total, "\n".join(errors) if errors else None)

    return {
        "status": status,
        "total":  total,
        "tables": table_counts,
        "errors": errors,
    }
