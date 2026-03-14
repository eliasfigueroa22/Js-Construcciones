"""
Generate an anonymized sample DuckDB database for portfolio reproducibility.

Reads the real DuckDB (warehouse/js_construcciones.duckdb), copies all tables,
anonymizes sensitive data, and generates synthetic rows for sparse tables so
that all dbt models and notebook charts produce meaningful output.

Usage:
    python -m v2_analytics.sample.generate_sample_db
    # or
    python v2_analytics/sample/generate_sample_db.py
"""

import random
import string
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

# ── Paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DB = SCRIPT_DIR.parent / "warehouse" / "js_construcciones.duckdb"
SAMPLE_DB = SCRIPT_DIR / "js_construcciones_sample.duckdb"

# ── Fake name pools ────────────────────────────────────────────────────
FAKE_CLIENT_NAMES = [
    "CLIENTE ALPHA", "CLIENTE BETA", "CLIENTE GAMMA", "CLIENTE DELTA",
    "CLIENTE EPSILON", "CLIENTE ZETA", "CLIENTE ETA", "CLIENTE THETA",
    "CLIENTE IOTA", "CLIENTE KAPPA",
]

FAKE_PROVIDER_NAMES = [
    "FERRETERIA SOL", "MATERIALES DEL ESTE", "HIERROS GUARANI",
    "DISTRIBUIDORA CENTRAL", "MADERAS DEL SUR", "ELECTRICA ASUNCION",
    "CERAMICAS PARAGUAY", "PINTURAS NACIONAL", "SANITARIOS EXPRESS",
    "CONSTRUCCIONES ABC", "VIDRIERIA MODERNA", "ARENA Y PIEDRA SRL",
    "TECHOS UNIDOS", "HORMIGON RAPID", "TRANSPORTE ROCA",
    "FERRETERIA LA ESQUINA", "MATERIALES PREMIUM", "ACEROS DEL NORTE",
    "PISOS Y REVESTIMIENTOS SA", "ELECTRICIDAD TOTAL",
    "PLOMERIA INTEGRAL", "MADERAS FINAS", "BLOQUES GUARANI",
    "CORRALON EL PROGRESO", "PINTURAS DEL LITORAL", "ABERTURAS MODERNAS",
    "CEMENTOS PARAGUAYOS", "HIERROS Y PERFILES SRL", "SANITARIOS PLUS",
    "DEPOSITO MATERIALES OK",
]

FAKE_PERSONAL_PROVIDERS = [
    "SUPERMERCADO STOCK", "FARMACIA CATEDRAL", "ESTACION DE SERVICIO PETROBRAS",
    "RESTAURANTE EL BUEN SABOR", "TIENDA DE ROPA LA MODA",
    "LIBRERIA CERVANTES", "OPTICA VISION", "PELUQUERIA ESTILO",
    "TALLER MECANICO RAPIDO", "LAVADERO EXPRESS",
    "VETERINARIA ANIMAL", "PANADERIA SAN JOSE", "CARNICERIA LA MEJOR",
    "VERDULERIA FRESCA", "HELADERIA DOLCE",
    "ELECTRONICA DIGITAL", "MUEBLERIA HOGAR", "FERRETERIA CHICA",
    "BAZAR TODO UTIL", "KIOSKO LA ESQUINA",
]

FAKE_WORKER_NAMES = [
    "JUAN PEREZ", "MARIA GONZALEZ", "CARLOS LOPEZ", "ANA MARTINEZ",
    "PEDRO RAMIREZ", "LUCIA FERNANDEZ", "JORGE ROMERO", "ROSA BENITEZ",
    "MIGUEL ACOSTA", "CARMEN TORRES", "DIEGO VILLALBA", "LAURA GIMENEZ",
    "ROBERTO FRANCO", "SILVIA DUARTE", "ANDRES CACERES",
    "PATRICIA ROJAS", "FERNANDO ORTIZ", "GABRIELA AYALA",
    "OSCAR MORINIGO", "ELENA VERA", "MARCOS CARDOZO", "CLAUDIA RIOS",
    "RAUL ESPINOLA", "SUSANA AQUINO", "HUGO CANDIA",
    "BEATRIZ LEDESMA", "VICTOR GAUTO", "NANCY BOGADO",
    "ANGEL BARRIOS", "TERESA SAMANIEGO", "JULIO CABALLERO",
    "MONICA ARCE", "ERNESTO SANCHEZ", "GLORIA CENTURION",
    "RICARDO DOMINGUEZ", "MARTA FLEITAS", "SERGIO MAIDANA",
    "VERONICA PORTILLO", "GUSTAVO NUÑEZ", "LORENA PAREDES",
    "EMILIO SALINAS", "ADRIANA COLMAN", "HERNAN BRITEZ",
    "CAROLINA NOGUERA", "PABLO INSAURRALDE", "DELIA CHAMORRO",
    "CRISTIAN GODOY", "VIVIANA LUGO", "ARIEL MENDOZA", "LIDIA GAMARRA",
    "JOSE ESTIGARRIBIA", "RAMONA SOSA", "FRANCISCO MEDINA",
    "BLANCA RIVEROS", "ENRIQUE OVIEDO", "ESTELA CABRERA",
    "NICOLAS VAZQUEZ", "AURORA CANTERO", "DAVID AMARILLA",
    "GRACIELA RUIZ DIAZ", "ALBERTO ECHEVERRIA", "MIRTA ENCISO",
    "CESAR OJEDA", "FABIANA RIQUELME", "HORACIO JARA",
    "CELESTE TRINIDAD", "RAFAEL OTAZU", "SONIA FIGUEREDO",
    "TOMAS BAEZ", "YOLANDA PENAYO", "LUIS BOBADILLA",
    "MARGARITA SEGOVIA", "AGUSTIN MIÑO", "IRMA FALCON",
    "ESTEBAN GILL", "NORMA GAONA", "RUBEN CAÑETE",
    "ANTONIA AVALOS", "DAMIAN CUBILLA", "FELIPA ZARZA",
    "BENIGNO CORVALAN", "PETRONA CABRIZA", "ISMAEL ROLON",
    "JUANA BRIZUELA", "CLEMENTE MARECOS", "RAMONA ACUÑA",
    "OSVALDO PERALTA", "NINFA RECALDE", "BASILICIO GONZALEZ",
    "DOMINGA OVELAR", "ARNALDO FLORENTIN", "CRESCENCIA MARTINEZ",
    "LIBERATO VILLASBOA", "SATURNINA GAVILAN", "EMIGDIO GONZALEZ",
    "EUSEBIA ORTEGA", "NICANOR DELVALLE", "MAXIMINA BAREIRO",
    "FERMINA CABRAL", "PORFIRIO ZARATE", "ANASTACIA AREVALOS",
    "DIONISIO PRESENTADO", "CEFERINA RAMOS", "HIGINIO PEREIRA",
    "FELICIANA SANABRIA", "ESTANISLAO BOGARIN", "ANTOLINA OCAMPOS",
    "HERMENEGILDO AQUINO", "ESCOLASTICA BENITEZ", "BAUTISTA GONZALEZ",
    "SATURNINA ROMERO", "POLICARPO ACOSTA", "EDUVIGIS LOPEZ",
]

TIPO_INGRESO_VALUES = ["FACTURA", "ANTICIPO", "CERTIFICADO"]

CONCEPTO_INGRESO = [
    "Pago certificado de obra", "Anticipo de contrato",
    "Factura por avance de obra", "Cobro de materiales adicionales",
    "Pago parcial de contrato", "Certificado mensual",
    "Factura por trabajos extras", "Anticipo segundo tramo",
    "Cobro final de obra", "Pago por adicional aprobado",
]

CONCEPTO_PRESUPUESTO = [
    "Mano de obra albañilería", "Materiales de construcción",
    "Instalación eléctrica", "Instalación sanitaria",
    "Revoque y pintura", "Estructura metálica",
    "Carpintería de obra", "Pisos y revestimientos",
    "Impermeabilización", "Techado y cubierta",
    "Excavación y movimiento de tierra", "Hormigón armado",
    "Mampostería", "Aberturas", "Terminaciones",
]

CONCEPTO_SUBCONTRATISTA = [
    "Trabajos de albañilería", "Instalación eléctrica completa",
    "Instalación sanitaria completa", "Pintura interior y exterior",
    "Colocación de pisos", "Estructura de techo",
    "Revoque grueso y fino", "Carpintería de aberturas",
    "Trabajos de herrería", "Impermeabilización de techo",
]


def _rand_rec_id() -> str:
    """Generate a fake Airtable record ID like recXXXXXXXXXXXXXX."""
    chars = string.ascii_letters + string.digits
    return "rec" + "".join(random.choices(chars, k=14))


def _rand_date(start: date, end: date) -> date:
    """Random date between start and end (inclusive)."""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _rand_guaranies(low: int, high: int, step: int = 50_000) -> int:
    """Random guaranies amount rounded to step."""
    return random.randrange(low, high + 1, step)


def _extracted_at() -> str:
    """Fixed extraction timestamp for synthetic rows."""
    return "2025-01-15 10:00:00"


# =====================================================================
#  MAIN
# =====================================================================
def main():
    if not SOURCE_DB.exists():
        print(f"ERROR: Source DB not found at {SOURCE_DB}")
        print("Run the Airtable extraction first, or use an existing sample.")
        sys.exit(1)

    # Remove old sample if exists
    if SAMPLE_DB.exists():
        SAMPLE_DB.unlink()

    print(f"Source: {SOURCE_DB}")
    print(f"Target: {SAMPLE_DB}")

    src = duckdb.connect(str(SOURCE_DB), read_only=True)
    dst = duckdb.connect(str(SAMPLE_DB))

    # Create raw schema and copy all tables
    dst.execute("CREATE SCHEMA IF NOT EXISTS raw")
    tables = src.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'raw'"
    ).fetchall()

    for (table_name,) in tables:
        print(f"  Copying raw.{table_name}...")
        df = src.execute(f'SELECT * FROM raw."{table_name}"').fetchdf()
        dst.execute(
            f'CREATE TABLE raw."{table_name}" AS SELECT * FROM df'
        )

    src.close()
    print(f"Copied {len(tables)} tables.\n")

    # ── Fix column types for sparse tables ──────────────────────────
    # Tables with very few rows had NULL columns typed as INTEGER by DuckDB.
    # We need to cast them to the correct types before inserting synthetic data.
    print("Fixing column types for sparse tables...")

    type_fixes: dict[str, dict[str, str]] = {
        "fact_presupuesto_cliente": {
            "ObraID": "VARCHAR", "SectorID": "VARCHAR",
            "TipoPresupuesto": "VARCHAR", "NumeroVersion": "VARCHAR",
            "FechaPresupuesto": "VARCHAR", "FechaAprobacion": "VARCHAR",
            "RubroID": "VARCHAR", "Descripcion": "VARCHAR",
            "Cantidad": "DOUBLE", "Unidad": "VARCHAR",
            "PrecioUnitario": "BIGINT", "MontoTotal": "BIGINT",
            "Estado": "VARCHAR", "Observaciones": "VARCHAR",
        },
        "fact_ingreso": {
            "FechaFactura": "VARCHAR", "TipoIngreso": "VARCHAR",
            "MontoFacturado": "BIGINT", "FechaCobro": "VARCHAR",
            "MetodoPago": "VARCHAR", "Observaciones": "VARCHAR",
        },
        "fact_presupuesto_subcontratista": {
            "Concepto/Descripcion": "VARCHAR", "SectorID": "VARCHAR",
        },
        "fact_facturacion_subcontratista": {
            "Observaciones": "VARCHAR",
        },
    }

    for table, cols in type_fixes.items():
        for col, new_type in cols.items():
            try:
                dst.execute(
                    f'ALTER TABLE raw."{table}" ALTER COLUMN "{col}" '
                    f"SET DATA TYPE {new_type}"
                )
            except Exception:
                # Column might already be the correct type
                pass

    print("  Done.\n")

    # ── Gather existing FK values ───────────────────────────────────
    def get_ids(table: str) -> list[str]:
        rows = dst.execute(
            f"SELECT airtable_id FROM raw.\"{table}\""
        ).fetchall()
        return [r[0] for r in rows]

    def get_column_values(table: str, col: str) -> list:
        rows = dst.execute(
            f'SELECT DISTINCT "{col}" FROM raw."{table}" WHERE "{col}" IS NOT NULL'
        ).fetchall()
        return [r[0] for r in rows]

    obra_ids = get_ids("dim_obras")
    cliente_ids = get_ids("dim_clientes")
    trabajador_ids = get_ids("dim_trabajador")
    rubro_ids = get_ids("dim_rubro")
    sector_ids = get_ids("dim_sector")
    proveedor_ids = get_ids("dim_proveedores")

    # Workers that are subcontratistas
    subcontratista_ids = [
        r[0] for r in dst.execute(
            """SELECT airtable_id FROM raw."dim_trabajador"
               WHERE UPPER(TRIM("TipoPersonal")) = 'SUBCONTRATISTA'"""
        ).fetchall()
    ]

    # Sectors grouped by obra
    obra_sector_map: dict[str, list[str]] = {}
    for obra_id, sector_id in dst.execute(
        'SELECT "ObraID", airtable_id FROM raw."dim_sector"'
    ).fetchall():
        obra_sector_map.setdefault(obra_id, []).append(sector_id)

    # ── 1. Anonymize dimensions ────────────────────────────────────
    print("Anonymizing dimensions...")

    # dim_clientes
    client_rows = dst.execute(
        'SELECT airtable_id FROM raw."dim_clientes" ORDER BY "ClienteNro"'
    ).fetchall()
    for i, (aid,) in enumerate(client_rows):
        fake_name = FAKE_CLIENT_NAMES[i % len(FAKE_CLIENT_NAMES)]
        dst.execute(
            """UPDATE raw."dim_clientes"
               SET "NombreCliente" = ?,
                   "RUC" = NULL,
                   "Direccion" = NULL,
                   "Telefono" = NULL,
                   "Email" = NULL
               WHERE airtable_id = ?""",
            [fake_name, aid],
        )

    # dim_proveedores
    prov_rows = dst.execute(
        'SELECT airtable_id FROM raw."dim_proveedores" ORDER BY "ProveedorNro"'
    ).fetchall()
    for i, (aid,) in enumerate(prov_rows):
        fake_name = FAKE_PROVIDER_NAMES[i % len(FAKE_PROVIDER_NAMES)]
        if i >= len(FAKE_PROVIDER_NAMES):
            fake_name = f"PROVEEDOR {i + 1}"
        dst.execute(
            """UPDATE raw."dim_proveedores"
               SET "NombreProveedor" = ?,
                   "RUC" = NULL,
                   "Telefono" = NULL,
                   "Email" = NULL
               WHERE airtable_id = ?""",
            [fake_name, aid],
        )

    # dim_proveedores_personal
    pprov_rows = dst.execute(
        'SELECT airtable_id FROM raw."dim_proveedores_personal" '
        'ORDER BY "ProveedorPersonalNro"'
    ).fetchall()
    for i, (aid,) in enumerate(pprov_rows):
        fake_name = FAKE_PERSONAL_PROVIDERS[i % len(FAKE_PERSONAL_PROVIDERS)]
        if i >= len(FAKE_PERSONAL_PROVIDERS):
            fake_name = f"PROVEEDOR PERSONAL {i + 1}"
        dst.execute(
            """UPDATE raw."dim_proveedores_personal"
               SET "NombreProveedor" = ?,
                   "RUC" = NULL,
                   "Telefono" = NULL
               WHERE airtable_id = ?""",
            [fake_name, aid],
        )

    # dim_trabajador
    trab_rows = dst.execute(
        'SELECT airtable_id FROM raw."dim_trabajador" ORDER BY "TrabajadorNro"'
    ).fetchall()
    for i, (aid,) in enumerate(trab_rows):
        fake_name = FAKE_WORKER_NAMES[i % len(FAKE_WORKER_NAMES)]
        if i >= len(FAKE_WORKER_NAMES):
            fake_name = f"TRABAJADOR {i + 1}"
        dst.execute(
            """UPDATE raw."dim_trabajador"
               SET "NombreCompleto" = ?,
                   "RUC_CI" = NULL,
                   "Telefono" = NULL
               WHERE airtable_id = ?""",
            [fake_name, aid],
        )

    # dim_obras — nullify address only
    dst.execute(
        'UPDATE raw."dim_obras" SET "Ubicacion_Direccion" = NULL'
    )

    print("  Done.\n")

    # ── 2. Get current max NRO values for each table ────────────────
    def get_max_nro(table: str, col: str) -> int:
        result = dst.execute(
            f'SELECT COALESCE(MAX("{col}"), 0) FROM raw."{table}"'
        ).fetchone()
        return result[0]

    # ── 3. Generate synthetic fact_presupuesto_cliente rows ─────────
    # Use REAL (obra_id, rubro_id) combos from fact_compra so budget deviation
    # analysis matches actual spending data.
    print("Generating synthetic data: fact_presupuesto_cliente...")
    max_nro = get_max_nro("fact_presupuesto_cliente", "PresupuestoClienteNro")
    pc_count = 0

    real_obra_rubro_combos = dst.execute(
        """SELECT DISTINCT "ObraID", "RubroID"
           FROM raw."fact_compra"
           WHERE "ObraID" IS NOT NULL AND "RubroID" IS NOT NULL"""
    ).fetchall()
    # Sample ~50 combos from the real data
    selected_combos = random.sample(
        real_obra_rubro_combos,
        min(50, len(real_obra_rubro_combos)),
    )
    estados_pc = ["APROBADO"] * 7 + ["PENDIENTE"] * 2 + ["RECHAZADO"]

    for obra_id, rubro_id in selected_combos:
        max_nro += 1
        pc_count += 1
        obra_sectors = obra_sector_map.get(obra_id, [])
        sector_id = random.choice(obra_sectors) if obra_sectors else None
        estado = random.choice(estados_pc)
        fecha_pres = _rand_date(date(2024, 7, 1), date(2025, 10, 1))
        fecha_aprob = (
            fecha_pres + timedelta(days=random.randint(3, 30))
            if estado == "APROBADO" else None
        )
        monto = _rand_guaranies(500_000, 10_000_000)
        precio_unit = _rand_guaranies(50_000, 500_000)
        cantidad = round(monto / precio_unit, 2) if precio_unit else 1

        dst.execute(
            """INSERT INTO raw."fact_presupuesto_cliente"
               (airtable_id, "PresupuestoClienteNro", "ObraID", "SectorID",
                "RubroID", "TipoPresupuesto", "NumeroVersion",
                "FechaPresupuesto", "FechaAprobacion", "Descripcion",
                "Cantidad", "Unidad", "PrecioUnitario", "MontoTotal",
                "Estado", "Observaciones", "_extracted_at")
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                _rand_rec_id(), max_nro, obra_id, sector_id,
                rubro_id, "MATERIALES", "v1",
                str(fecha_pres), str(fecha_aprob) if fecha_aprob else None,
                random.choice(CONCEPTO_PRESUPUESTO),
                cantidad, "GL", precio_unit, monto,
                estado, None, _extracted_at(),
            ],
        )

    print(f"  Added {pc_count} rows (total now: {max_nro})\n")

    # ── 4. Generate synthetic fact_ingreso rows ─────────────────────
    print("Generating synthetic data: fact_ingreso...")
    max_nro = get_max_nro("fact_ingreso", "IngresoNro")
    ing_count = 0

    selected_obras_ing = random.sample(obra_ids, min(30, len(obra_ids)))
    for obra_id in selected_obras_ing:
        n_ingresos = random.randint(1, 4)
        for _ in range(n_ingresos):
            max_nro += 1
            ing_count += 1
            fecha_ing = _rand_date(date(2024, 7, 1), date(2025, 12, 1))
            tipo = random.choice(TIPO_INGRESO_VALUES)
            estado = random.choice(["COBRADO"] * 6 + ["PENDIENTE"] * 4)
            monto_fact = _rand_guaranies(1_000_000, 50_000_000)
            monto_rec = monto_fact if estado == "COBRADO" else 0
            fecha_cobro = (
                str(fecha_ing + timedelta(days=random.randint(5, 60)))
                if estado == "COBRADO" else None
            )

            dst.execute(
                """INSERT INTO raw."fact_ingreso"
                   (airtable_id, "IngresoNro", "ObraID", "FechaIngreso",
                    "FechaFactura", "NumeroFactura", "TipoIngreso",
                    "Concepto", "MontoFacturado", "MontoRecibido",
                    "EstadoCobro", "FechaCobro", "MetodoPago",
                    "Observaciones", "_extracted_at")
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    _rand_rec_id(), max_nro, obra_id,
                    str(fecha_ing), str(fecha_ing),
                    f"FAC-{max_nro:04d}", tipo,
                    random.choice(CONCEPTO_INGRESO),
                    monto_fact, monto_rec,
                    estado, fecha_cobro,
                    random.choice(["TRANSFERENCIA", "CHEQUE", "EFECTIVO"]),
                    None, _extracted_at(),
                ],
            )

    print(f"  Added {ing_count} rows\n")

    # ── 5. Generate synthetic fact_deuda rows ───────────────────────
    print("Generating synthetic data: fact_deuda...")
    max_nro = get_max_nro("fact_deuda", "DeudaNro")
    deuda_count = 0
    deuda_records: list[tuple[str, int]] = []  # (airtable_id, monto)

    selected_workers = random.sample(trabajador_ids, min(20, len(trabajador_ids)))
    tipos_deuda = (
        ["PRESTAMO"] * 4 + ["ADELANTO_PERSONAL"] * 3 + ["COMPRA_PERSONAL"] * 3
    )

    for trab_id in selected_workers:
        max_nro += 1
        deuda_count += 1
        obra_id = random.choice(obra_ids)
        tipo = random.choice(tipos_deuda)
        estado = random.choice(["ACTIVO"] * 6 + ["PAGADO"] * 4)
        monto = _rand_guaranies(100_000, 2_000_000)
        fecha = _rand_date(date(2024, 8, 1), date(2025, 11, 1))
        rec_id = _rand_rec_id()
        deuda_records.append((rec_id, monto, estado))

        dst.execute(
            """INSERT INTO raw."fact_deuda"
               (airtable_id, "DeudaNro", "TrabajadorID", "ObraID",
                "TipoDeuda", "FechaSolicitud", "MontoDeuda",
                "Estado", "Observaciones", "_extracted_at")
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                rec_id, max_nro, trab_id, obra_id,
                tipo, str(fecha), monto,
                estado, None, _extracted_at(),
            ],
        )

    print(f"  Added {deuda_count} rows\n")

    # ── 6. Generate synthetic fact_pago_deuda rows ──────────────────
    print("Generating synthetic data: fact_pago_deuda...")
    max_nro = get_max_nro("fact_pago_deuda", "PagoDeudaNro")
    pd_count = 0
    metodos_pago = (
        ["EFECTIVO"] * 5 + ["DESCUENTO_SUELDO"] * 3 + ["TRANSFERENCIA"] * 2
    )

    # Also get existing deuda records that don't have payments
    existing_deudas = dst.execute(
        """SELECT d.airtable_id, d."MontoDeuda", d."Estado"
           FROM raw."fact_deuda" d
           WHERE d.airtable_id NOT IN (
               SELECT DISTINCT "DeudaID" FROM raw."fact_pago_deuda"
               WHERE "DeudaID" IS NOT NULL
           )"""
    ).fetchall()
    all_deuda_for_payments = [
        (r[0], r[1], r[2]) for r in existing_deudas
    ] + list(deuda_records)

    for deuda_id, monto_deuda, estado in all_deuda_for_payments:
        if estado == "PAGADO":
            n_pagos = random.randint(1, 3)
        else:
            n_pagos = random.randint(0, 2)

        if n_pagos == 0:
            continue

        monto_restante = monto_deuda
        for j in range(n_pagos):
            max_nro += 1
            pd_count += 1
            if j == n_pagos - 1 and estado == "PAGADO":
                monto_pago = monto_restante
            else:
                monto_pago = _rand_guaranies(
                    50_000, max(50_000, monto_restante // 2), 50_000
                )
                monto_pago = min(monto_pago, monto_restante)
            monto_restante -= monto_pago

            fecha_pago = _rand_date(date(2024, 9, 1), date(2025, 12, 1))

            dst.execute(
                """INSERT INTO raw."fact_pago_deuda"
                   (airtable_id, "PagoDeudaNro", "DeudaID",
                    "FechaPago", "MontoPagado", "MetodoPago",
                    "Observaciones", "_extracted_at")
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    _rand_rec_id(), max_nro, deuda_id,
                    str(fecha_pago), monto_pago,
                    random.choice(metodos_pago),
                    None, _extracted_at(),
                ],
            )

    print(f"  Added {pd_count} rows\n")

    # ── 7. Generate synthetic fact_presupuesto_subcontratista rows ──
    print("Generating synthetic data: fact_presupuesto_subcontratista...")
    max_nro = get_max_nro(
        "fact_presupuesto_subcontratista", "PresupuestoSubcontratistaNro"
    )
    ps_count = 0
    presup_sub_records: list[tuple[str, int]] = []  # (airtable_id, monto)

    # Use existing subcontratistas, or pick from all workers if too few
    if len(subcontratista_ids) < 5:
        sub_pool = random.sample(trabajador_ids, min(12, len(trabajador_ids)))
    else:
        sub_pool = random.sample(
            subcontratista_ids, min(12, len(subcontratista_ids))
        )

    selected_obras_sub = random.sample(obra_ids, min(10, len(obra_ids)))

    for trab_id in sub_pool:
        n_presup = random.randint(1, 3)
        for _ in range(n_presup):
            max_nro += 1
            ps_count += 1
            obra_id = random.choice(selected_obras_sub)
            obra_sectors = obra_sector_map.get(obra_id, [])
            sector_id = random.choice(obra_sectors) if obra_sectors else None
            rubro_id = random.choice(rubro_ids)
            monto = _rand_guaranies(2_000_000, 20_000_000)
            estado = random.choice(["VIGENTE", "FINALIZADO"])
            fecha = _rand_date(date(2024, 7, 1), date(2025, 9, 1))
            rec_id = _rand_rec_id()
            presup_sub_records.append((rec_id, monto))

            dst.execute(
                """INSERT INTO raw."fact_presupuesto_subcontratista"
                   (airtable_id, "PresupuestoSubcontratistaNro",
                    "TrabajadorID", "ObraID", "SectorID", "RubroID",
                    "FechaPresupuesto", "Concepto/Descripcion",
                    "MontoPresupuestado", "PorcentajeFacturacion",
                    "Estado", "Observaciones", "_extracted_at")
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    rec_id, max_nro,
                    trab_id, obra_id, sector_id, rubro_id,
                    str(fecha), random.choice(CONCEPTO_SUBCONTRATISTA),
                    monto, None,
                    estado, None, _extracted_at(),
                ],
            )

    print(f"  Added {ps_count} rows\n")

    # ── 8. Generate synthetic fact_facturacion_subcontratista rows ──
    print("Generating synthetic data: fact_facturacion_subcontratista...")
    max_nro = get_max_nro(
        "fact_facturacion_subcontratista", "FacturacionNro"
    )
    fs_count = 0

    # Also include existing presupuesto records
    existing_presup = dst.execute(
        """SELECT airtable_id, "MontoPresupuestado"
           FROM raw."fact_presupuesto_subcontratista"
           WHERE airtable_id NOT IN (
               SELECT DISTINCT "PresupuestoSubcontratistaID"
               FROM raw."fact_facturacion_subcontratista"
               WHERE "PresupuestoSubcontratistaID" IS NOT NULL
           )"""
    ).fetchall()
    all_presup_for_billing = [
        (r[0], r[1]) for r in existing_presup
    ] + presup_sub_records

    for presup_id, monto_presup in all_presup_for_billing:
        n_facturas = random.randint(2, 4)
        monto_restante = monto_presup
        for j in range(n_facturas):
            max_nro += 1
            fs_count += 1
            if j == n_facturas - 1:
                monto_fact = monto_restante
            else:
                pct = random.uniform(0.2, 0.4)
                monto_fact = int(monto_presup * pct)
                monto_fact = (monto_fact // 50_000) * 50_000
                monto_fact = min(monto_fact, monto_restante)
            monto_restante -= monto_fact

            pct_aplicado = round(monto_fact / monto_presup * 100, 2) if monto_presup else 0
            fecha = _rand_date(date(2024, 8, 1), date(2025, 12, 1))

            dst.execute(
                """INSERT INTO raw."fact_facturacion_subcontratista"
                   (airtable_id, "FacturacionNro",
                    "PresupuestoSubcontratistaID", "FechaFactura",
                    "NumeroFactura", "MontoFacturado",
                    "PorcentajeAplicado", "Observaciones", "_extracted_at")
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    _rand_rec_id(), max_nro,
                    presup_id, str(fecha),
                    f"FSUB-{max_nro:04d}", monto_fact,
                    pct_aplicado, None, _extracted_at(),
                ],
            )

    print(f"  Added {fs_count} rows\n")

    # ── Summary ─────────────────────────────────────────────────────
    print("=" * 50)
    print("SAMPLE DATABASE SUMMARY")
    print("=" * 50)
    tables = dst.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'raw' ORDER BY table_name"
    ).fetchall()
    for (t,) in tables:
        count = dst.execute(f'SELECT COUNT(*) FROM raw."{t}"').fetchone()[0]
        print(f"  raw.{t}: {count} rows")

    dst.close()

    size_mb = SAMPLE_DB.stat().st_size / (1024 * 1024)
    print(f"\nSample DB size: {size_mb:.2f} MB")
    print(f"Saved to: {SAMPLE_DB}")


if __name__ == "__main__":
    random.seed(42)  # Reproducible output
    main()
