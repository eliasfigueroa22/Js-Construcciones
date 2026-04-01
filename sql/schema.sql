-- =============================================================================
-- JS Construcciones — Supabase Schema
-- Kimball Dimensional Model
-- Convenciones:
--   dim_*  → dimensiones
--   fact_* → tablas de hechos
--   op_*   → tablas operacionales (mediciones, certificaciones)
--   aux_*  → auxiliares (falsos duplicados, sync log)
--   bkp_*  → backup / archivo (no usadas en la app)
--
-- Tipos de datos:
--   Montos en Guaraníes : NUMERIC(18,0)
--   Cantidades/medidas  : NUMERIC(15,3)
--   Porcentajes         : NUMERIC(7,4)  → 0.7500 = 75%
--   Surrogate keys      : BIGSERIAL
--   Natural keys Airtable: airtable_id TEXT UNIQUE NOT NULL
-- =============================================================================

-- =============================================================================
-- EXTENSIONES
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- =============================================================================
-- FUNCIÓN HELPER — updated_at automático
-- =============================================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


-- =============================================================================
-- AUTH — perfiles y permisos por herramienta
-- =============================================================================

CREATE TABLE public.user_profiles (
    id          UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre      TEXT        NOT NULL,
    email       TEXT        NOT NULL UNIQUE,
    role        TEXT        NOT NULL DEFAULT 'viewer'
                            CHECK (role IN ('admin', 'operador', 'viewer')),
    activo      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.user_tool_permissions (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    tool_slug   TEXT        NOT NULL
                            CHECK (tool_slug IN (
                                'verificador_facturas',
                                'resumen_pagos',
                                'gestor_duplicados',
                                'reporte_obra',
                                'mediciones',
                                'certificaciones',
                                'planilla_pagos'
                            )),
    can_access  BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, tool_slug)
);

CREATE INDEX idx_utp_user_id ON public.user_tool_permissions(user_id);

CREATE TRIGGER trg_utp_updated_at
    BEFORE UPDATE ON public.user_tool_permissions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- DIM_FECHA — dimensión fecha pre-populada (ver dim_fecha_seed.sql)
-- No tiene airtable_id — es generada localmente
-- =============================================================================

CREATE TABLE public.dim_fecha (
    fecha           DATE        PRIMARY KEY,
    anio            SMALLINT    NOT NULL,
    mes             SMALLINT    NOT NULL,
    dia             SMALLINT    NOT NULL,
    trimestre       SMALLINT    NOT NULL,
    semana_iso      SMALLINT    NOT NULL,
    nombre_dia      TEXT        NOT NULL,   -- 'Lunes'..'Domingo' (resuelto en app)
    nombre_mes      TEXT        NOT NULL,   -- 'Enero'..'Diciembre' (resuelto en app)
    es_fin_semana   BOOLEAN     NOT NULL
);


-- =============================================================================
-- DIMENSIONES
-- Orden de creación respeta dependencias FK:
--   dim_cliente → (nada)
--   dim_obra    → dim_cliente
--   dim_rubro   → (nada)
--   dim_sector  → dim_obra
--   dim_trabajador → dim_rubro
--   dim_proveedor  → (nada)
-- =============================================================================

CREATE TABLE public.dim_cliente (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    nombre_cliente  TEXT        NOT NULL,
    cliente_nro     INTEGER,
    ruc             TEXT,
    direccion       TEXT,
    telefono        TEXT,
    email           TEXT,
    tipo_cliente    TEXT,
    fecha_registro  DATE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dim_cliente_airtable ON public.dim_cliente(airtable_id);

CREATE TRIGGER trg_dim_cliente_updated_at
    BEFORE UPDATE ON public.dim_cliente
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.dim_obra (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    nombre          TEXT        NOT NULL,
    clave           TEXT        NOT NULL,
    obra_nro        INTEGER,
    estado_obra     TEXT,
    categoria_obra  TEXT,
    cliente_id      BIGINT      REFERENCES public.dim_cliente(id) ON DELETE RESTRICT,
    ubicacion       TEXT,
    superficie      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dim_obra_airtable ON public.dim_obra(airtable_id);
CREATE INDEX idx_dim_obra_clave    ON public.dim_obra(clave);
CREATE INDEX idx_dim_obra_cliente  ON public.dim_obra(cliente_id);
CREATE INDEX idx_dim_obra_estado   ON public.dim_obra(estado_obra);

CREATE TRIGGER trg_dim_obra_updated_at
    BEFORE UPDATE ON public.dim_obra
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.dim_rubro (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    rubro           TEXT        NOT NULL,       -- código corto: ALB, REV, etc.
    nombre_completo TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dim_rubro_airtable ON public.dim_rubro(airtable_id);
CREATE INDEX idx_dim_rubro_codigo   ON public.dim_rubro(rubro);

CREATE TRIGGER trg_dim_rubro_updated_at
    BEFORE UPDATE ON public.dim_rubro
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.dim_sector (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    nombre_sector   TEXT        NOT NULL,
    sector_nro      INTEGER,
    obra_id         BIGINT      REFERENCES public.dim_obra(id) ON DELETE RESTRICT,
    descripcion     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dim_sector_airtable ON public.dim_sector(airtable_id);
CREATE INDEX idx_dim_sector_obra     ON public.dim_sector(obra_id);

CREATE TRIGGER trg_dim_sector_updated_at
    BEFORE UPDATE ON public.dim_sector
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.dim_trabajador (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    nombre_completo TEXT        NOT NULL,
    trabajador_nro  INTEGER,
    tipo_personal   TEXT,
    telefono        TEXT,
    ruc_ci          TEXT,
    rubro_id        BIGINT      REFERENCES public.dim_rubro(id) ON DELETE RESTRICT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dim_trabajador_airtable ON public.dim_trabajador(airtable_id);
CREATE INDEX idx_dim_trabajador_rubro    ON public.dim_trabajador(rubro_id);

CREATE TRIGGER trg_dim_trabajador_updated_at
    BEFORE UPDATE ON public.dim_trabajador
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.dim_proveedor (
    id                  BIGSERIAL   PRIMARY KEY,
    airtable_id         TEXT        NOT NULL UNIQUE,
    nombre_proveedor    TEXT        NOT NULL,
    proveedor_nro       INTEGER,
    ruc                 TEXT,
    telefono            TEXT,
    email               TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dim_proveedor_airtable ON public.dim_proveedor(airtable_id);

CREATE TRIGGER trg_dim_proveedor_updated_at
    BEFORE UPDATE ON public.dim_proveedor
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- TABLAS DE HECHOS
-- =============================================================================

-- Grain: una línea de compra (varias por factura)
CREATE TABLE public.fact_compra (
    id                  BIGSERIAL   PRIMARY KEY,
    airtable_id         TEXT        NOT NULL UNIQUE,
    compra_nro          INTEGER,
    obra_id             BIGINT      REFERENCES public.dim_obra(id)      ON DELETE RESTRICT,
    sector_id           BIGINT      REFERENCES public.dim_sector(id)    ON DELETE RESTRICT,
    rubro_id            BIGINT      REFERENCES public.dim_rubro(id)     ON DELETE RESTRICT,
    proveedor_texto     TEXT,           -- campo libre en Airtable
    proveedor_id        BIGINT      REFERENCES public.dim_proveedor(id) ON DELETE RESTRICT,  -- nullable, cuando hay link
    fecha               DATE,
    nro_factura         TEXT,
    descripcion         TEXT,
    cantidad            NUMERIC(15,3),
    unidad              TEXT,
    monto_total         NUMERIC(18,0),
    tipo_documento      TEXT,
    observaciones       TEXT,
    created_at_source   TIMESTAMPTZ,    -- campo "Created" de Airtable
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fact_compra_obra       ON public.fact_compra(obra_id);
CREATE INDEX idx_fact_compra_fecha      ON public.fact_compra(fecha);
CREATE INDEX idx_fact_compra_nro_fac    ON public.fact_compra(nro_factura);
CREATE INDEX idx_fact_compra_sector     ON public.fact_compra(sector_id);
CREATE INDEX idx_fact_compra_rubro      ON public.fact_compra(rubro_id);
CREATE INDEX idx_fact_compra_proveedor  ON public.fact_compra(proveedor_id);

CREATE TRIGGER trg_fact_compra_updated_at
    BEFORE UPDATE ON public.fact_compra
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: un acuerdo presupuestario (trabajador + obra + sector + rubro)
CREATE TABLE public.fact_presupuesto_subcontratista (
    id                      BIGSERIAL   PRIMARY KEY,
    airtable_id             TEXT        NOT NULL UNIQUE,
    presupuesto_nro         INTEGER,
    trabajador_id           BIGINT      REFERENCES public.dim_trabajador(id) ON DELETE RESTRICT,
    obra_id                 BIGINT      REFERENCES public.dim_obra(id)        ON DELETE RESTRICT,
    sector_id               BIGINT      REFERENCES public.dim_sector(id)      ON DELETE RESTRICT,
    rubro_id                BIGINT      REFERENCES public.dim_rubro(id)       ON DELETE RESTRICT,
    concepto                TEXT,
    fecha_presupuesto       DATE,
    monto_presupuestado     NUMERIC(18,0),
    estado                  TEXT        CHECK (estado IN ('Activo', 'Cerrado')),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fps_airtable   ON public.fact_presupuesto_subcontratista(airtable_id);
CREATE INDEX idx_fps_trabajador ON public.fact_presupuesto_subcontratista(trabajador_id);
CREATE INDEX idx_fps_obra       ON public.fact_presupuesto_subcontratista(obra_id);
CREATE INDEX idx_fps_estado     ON public.fact_presupuesto_subcontratista(estado);

CREATE TRIGGER trg_fps_updated_at
    BEFORE UPDATE ON public.fact_presupuesto_subcontratista
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: un pago a trabajador
CREATE TABLE public.fact_pago (
    id                              BIGSERIAL   PRIMARY KEY,
    airtable_id                     TEXT        NOT NULL UNIQUE,
    pago_nro                        INTEGER,
    presupuesto_subcontratista_id   BIGINT      REFERENCES public.fact_presupuesto_subcontratista(id) ON DELETE RESTRICT,
    obra_id                         BIGINT      NOT NULL REFERENCES public.dim_obra(id)        ON DELETE RESTRICT,
    trabajador_id                   BIGINT      NOT NULL REFERENCES public.dim_trabajador(id)  ON DELETE RESTRICT,
    sector_id                       BIGINT      REFERENCES public.dim_sector(id)      ON DELETE RESTRICT,
    rubro_id                        BIGINT      REFERENCES public.dim_rubro(id)       ON DELETE RESTRICT,
    fecha_pago                      DATE,
    concepto                        TEXT,
    tipo_pago                       TEXT        CHECK (tipo_pago IN ('PAGO', 'ADELANTO', 'PRODUCCION')),
    monto_pago                      NUMERIC(18,0),
    metodo_pago                     TEXT,
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fact_pago_airtable    ON public.fact_pago(airtable_id);
CREATE INDEX idx_fact_pago_obra        ON public.fact_pago(obra_id);
CREATE INDEX idx_fact_pago_trabajador  ON public.fact_pago(trabajador_id);
CREATE INDEX idx_fact_pago_fecha       ON public.fact_pago(fecha_pago);
CREATE INDEX idx_fact_pago_presup      ON public.fact_pago(presupuesto_subcontratista_id);

CREATE TRIGGER trg_fact_pago_updated_at
    BEFORE UPDATE ON public.fact_pago
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: una factura emitida por un subcontratista contra su presupuesto
CREATE TABLE public.fact_facturacion_subcontratista (
    id                              BIGSERIAL   PRIMARY KEY,
    airtable_id                     TEXT        NOT NULL UNIQUE,
    facturacion_nro                 INTEGER,
    presupuesto_subcontratista_id   BIGINT      REFERENCES public.fact_presupuesto_subcontratista(id) ON DELETE RESTRICT,
    fecha_factura                   DATE,
    numero_factura                  TEXT,
    monto_facturado                 NUMERIC(18,0),
    porcentaje_aplicado             NUMERIC(7,4),
    observaciones                   TEXT,
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ffs_presupuesto ON public.fact_facturacion_subcontratista(presupuesto_subcontratista_id);
CREATE INDEX idx_ffs_fecha       ON public.fact_facturacion_subcontratista(fecha_factura);

CREATE TRIGGER trg_ffs_updated_at
    BEFORE UPDATE ON public.fact_facturacion_subcontratista
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: una línea de presupuesto al cliente
CREATE TABLE public.fact_presupuesto_cliente (
    id                      BIGSERIAL   PRIMARY KEY,
    airtable_id             TEXT        NOT NULL UNIQUE,
    presupuesto_cliente_nro INTEGER,
    obra_id                 BIGINT      REFERENCES public.dim_obra(id)     ON DELETE RESTRICT,
    sector_id               BIGINT      REFERENCES public.dim_sector(id)   ON DELETE RESTRICT,
    rubro_id                BIGINT      REFERENCES public.dim_rubro(id)    ON DELETE RESTRICT,
    tipo_presupuesto        TEXT,
    numero_version          INTEGER,
    fecha_presupuesto       DATE,
    fecha_aprobacion        DATE,
    descripcion             TEXT,
    cantidad                NUMERIC(15,3),
    unidad                  TEXT,
    precio_unitario         NUMERIC(18,0),
    monto_total             NUMERIC(18,0),
    estado                  TEXT,
    observaciones           TEXT,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fpc_obra    ON public.fact_presupuesto_cliente(obra_id);
CREATE INDEX idx_fpc_version ON public.fact_presupuesto_cliente(obra_id, numero_version);

CREATE TRIGGER trg_fpc_updated_at
    BEFORE UPDATE ON public.fact_presupuesto_cliente
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: un cobro recibido del cliente
CREATE TABLE public.fact_ingreso (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    ingreso_nro     INTEGER,
    obra_id         BIGINT      REFERENCES public.dim_obra(id) ON DELETE RESTRICT,
    fecha_ingreso   DATE,
    fecha_factura   DATE,
    numero_factura  TEXT,
    tipo_ingreso    TEXT,
    concepto        TEXT,
    monto_facturado NUMERIC(18,0),
    monto_recibido  NUMERIC(18,0),
    estado_cobro    TEXT,
    fecha_cobro     DATE,
    metodo_pago     TEXT,
    observaciones   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fact_ingreso_obra  ON public.fact_ingreso(obra_id);
CREATE INDEX idx_fact_ingreso_fecha ON public.fact_ingreso(fecha_ingreso);

CREATE TRIGGER trg_fact_ingreso_updated_at
    BEFORE UPDATE ON public.fact_ingreso
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: un registro de deuda con trabajador
CREATE TABLE public.fact_deuda (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    deuda_nro       INTEGER,
    obra_id         BIGINT      REFERENCES public.dim_obra(id)        ON DELETE RESTRICT,
    trabajador_id   BIGINT      REFERENCES public.dim_trabajador(id)  ON DELETE RESTRICT,
    tipo_deuda      TEXT        CHECK (tipo_deuda IN ('ADELANTO_PERSONAL', 'COMPRA_PERSONAL', 'PRESTAMO')),
    fecha_solicitud DATE,
    monto_deuda     NUMERIC(18,0),
    estado          TEXT,
    observaciones   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fact_deuda_trabajador ON public.fact_deuda(trabajador_id);
CREATE INDEX idx_fact_deuda_obra       ON public.fact_deuda(obra_id);

CREATE TRIGGER trg_fact_deuda_updated_at
    BEFORE UPDATE ON public.fact_deuda
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- Grain: un pago aplicado a una deuda
CREATE TABLE public.fact_pago_deuda (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    pago_deuda_nro  INTEGER,
    deuda_id        BIGINT      NOT NULL REFERENCES public.fact_deuda(id) ON DELETE RESTRICT,
    fecha_pago      DATE,
    monto_pagado    NUMERIC(18,0),
    metodo_pago     TEXT,
    observaciones   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fpd_deuda ON public.fact_pago_deuda(deuda_id);
CREATE INDEX idx_fpd_fecha ON public.fact_pago_deuda(fecha_pago);

CREATE TRIGGER trg_fact_pago_deuda_updated_at
    BEFORE UPDATE ON public.fact_pago_deuda
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- TABLAS OPERACIONALES (op_*)
-- =============================================================================

CREATE TABLE public.op_medicion_cabecera (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    medicion_ref    TEXT        NOT NULL,
    obra_id         BIGINT      REFERENCES public.dim_obra(id)        ON DELETE RESTRICT,
    trabajador_id   BIGINT      REFERENCES public.dim_trabajador(id)  ON DELETE RESTRICT,
    fecha           DATE,
    estado          TEXT        CHECK (estado IN ('Borrador', 'Confirmado')),
    observaciones   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_omc_obra       ON public.op_medicion_cabecera(obra_id);
CREATE INDEX idx_omc_trabajador ON public.op_medicion_cabecera(trabajador_id);
CREATE INDEX idx_omc_estado     ON public.op_medicion_cabecera(estado);

CREATE TRIGGER trg_omc_updated_at
    BEFORE UPDATE ON public.op_medicion_cabecera
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.op_medicion_linea (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    cabecera_id     BIGINT      NOT NULL REFERENCES public.op_medicion_cabecera(id) ON DELETE RESTRICT,
    sector_id       BIGINT      REFERENCES public.dim_sector(id)  ON DELETE RESTRICT,
    rubro_id        BIGINT      REFERENCES public.dim_rubro(id)   ON DELETE RESTRICT,
    descripcion     TEXT,
    unidad          TEXT,
    largo           NUMERIC(12,3),
    ancho           NUMERIC(12,3),
    alto            NUMERIC(12,3),
    cantidad        NUMERIC(12,3),
    precio_unitario NUMERIC(18,0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_oml_cabecera ON public.op_medicion_linea(cabecera_id);
CREATE INDEX idx_oml_sector   ON public.op_medicion_linea(sector_id);
CREATE INDEX idx_oml_rubro    ON public.op_medicion_linea(rubro_id);

CREATE TRIGGER trg_oml_updated_at
    BEFORE UPDATE ON public.op_medicion_linea
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.op_cert_presupuesto_linea (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    rubro_texto     TEXT,               -- campo "Rubro" (primary field libre en Airtable)
    rubro_id        BIGINT      REFERENCES public.dim_rubro(id)   ON DELETE RESTRICT,
    obra_id         BIGINT      REFERENCES public.dim_obra(id)    ON DELETE RESTRICT,
    orden           INTEGER,
    item_nro        TEXT,
    zona            TEXT,
    grupo_nombre    TEXT,
    unidad          TEXT,
    cantidad        NUMERIC(15,3),
    precio_unitario NUMERIC(18,0),
    observaciones   TEXT,
    sin_cotizar     BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ocpl_obra  ON public.op_cert_presupuesto_linea(obra_id);
CREATE INDEX idx_ocpl_orden ON public.op_cert_presupuesto_linea(obra_id, orden);
CREATE INDEX idx_ocpl_zona  ON public.op_cert_presupuesto_linea(zona);

CREATE TRIGGER trg_ocpl_updated_at
    BEFORE UPDATE ON public.op_cert_presupuesto_linea
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.op_cert_cabecera (
    id                  BIGSERIAL   PRIMARY KEY,
    airtable_id         TEXT        NOT NULL UNIQUE,
    cert_ref            TEXT        NOT NULL,
    obra_id             BIGINT      REFERENCES public.dim_obra(id) ON DELETE RESTRICT,
    numero              INTEGER,
    fecha_certificado   DATE,
    estado              TEXT        CHECK (estado IN ('Borrador', 'Confirmado')),
    observaciones       TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_occ_obra   ON public.op_cert_cabecera(obra_id);
CREATE INDEX idx_occ_estado ON public.op_cert_cabecera(estado);
CREATE INDEX idx_occ_numero ON public.op_cert_cabecera(obra_id, numero);

CREATE TRIGGER trg_occ_updated_at
    BEFORE UPDATE ON public.op_cert_cabecera
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.op_cert_linea (
    id                      BIGSERIAL   PRIMARY KEY,
    airtable_id             TEXT        NOT NULL UNIQUE,
    linea_ref               TEXT,
    cabecera_id             BIGINT      NOT NULL REFERENCES public.op_cert_cabecera(id)        ON DELETE RESTRICT,
    presupuesto_linea_id    BIGINT      REFERENCES public.op_cert_presupuesto_linea(id)         ON DELETE RESTRICT,
    cantidad_certificada    NUMERIC(15,3),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ocl_cabecera     ON public.op_cert_linea(cabecera_id);
CREATE INDEX idx_ocl_presup_linea ON public.op_cert_linea(presupuesto_linea_id);

CREATE TRIGGER trg_ocl_updated_at
    BEFORE UPDATE ON public.op_cert_linea
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- TABLAS AUXILIARES (aux_*)
-- =============================================================================

CREATE TABLE public.aux_falsos_duplicados (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    clave_grupo     TEXT        NOT NULL UNIQUE,
    tipo            TEXT,
    nro_factura     TEXT,
    proveedor       TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_afd_clave ON public.aux_falsos_duplicados(clave_grupo);

CREATE TRIGGER trg_afd_updated_at
    BEFORE UPDATE ON public.aux_falsos_duplicados
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


CREATE TABLE public.aux_sync_log (
    id                  BIGSERIAL   PRIMARY KEY,
    table_name          TEXT        NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    records_upserted    INTEGER,
    status              TEXT        NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'error')),
    error_message       TEXT
);

CREATE INDEX idx_sync_log_table  ON public.aux_sync_log(table_name);
CREATE INDEX idx_sync_log_status ON public.aux_sync_log(status);
CREATE INDEX idx_sync_log_start  ON public.aux_sync_log(started_at DESC);


-- =============================================================================
-- TABLAS DE BACKUP (bkp_*)
-- Datos históricos del jefe — no usadas en la app
-- =============================================================================

CREATE TABLE public.bkp_proveedor_personal (
    id          BIGSERIAL   PRIMARY KEY,
    airtable_id TEXT        NOT NULL UNIQUE,
    nombre      TEXT,
    ruc_ci      TEXT,
    telefono    TEXT,
    otros       TEXT,
    es_backup   BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.bkp_compra_personal (
    id              BIGSERIAL   PRIMARY KEY,
    airtable_id     TEXT        NOT NULL UNIQUE,
    compra_nro      INTEGER,
    obra_texto      TEXT,
    proveedor_texto TEXT,
    fecha           DATE,
    nro_factura     TEXT,
    descripcion     TEXT,
    cantidad        NUMERIC(15,3),
    unidad          TEXT,
    monto_total     NUMERIC(18,0),
    tipo_documento  TEXT,
    observaciones   TEXT,
    es_backup       BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Función helper: obtiene el rol del usuario autenticado actual
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS TEXT
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT role
    FROM public.user_profiles
    WHERE id = auth.uid() AND activo = TRUE
    LIMIT 1;
$$;

-- Habilitar RLS en todas las tablas de negocio
ALTER TABLE public.user_profiles               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_tool_permissions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_cliente                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_obra                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_rubro                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_sector                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_trabajador              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_proveedor               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_compra                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_pago                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_presupuesto_subcontratista ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_facturacion_subcontratista ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_presupuesto_cliente    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_ingreso                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_deuda                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_pago_deuda             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.op_medicion_cabecera        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.op_medicion_linea           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.op_cert_presupuesto_linea   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.op_cert_cabecera            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.op_cert_linea               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aux_falsos_duplicados       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aux_sync_log                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bkp_proveedor_personal      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bkp_compra_personal         ENABLE ROW LEVEL SECURITY;

-- dim_fecha: sin RLS (datos de referencia, no sensibles)


-- --------------------------------------------------------------------------
-- user_profiles
-- --------------------------------------------------------------------------
CREATE POLICY "profiles_select" ON public.user_profiles
    FOR SELECT USING (id = auth.uid() OR public.current_user_role() = 'admin');

CREATE POLICY "profiles_insert" ON public.user_profiles
    FOR INSERT WITH CHECK (public.current_user_role() = 'admin');

CREATE POLICY "profiles_update" ON public.user_profiles
    FOR UPDATE USING (public.current_user_role() = 'admin');

CREATE POLICY "profiles_delete" ON public.user_profiles
    FOR DELETE USING (public.current_user_role() = 'admin');

-- --------------------------------------------------------------------------
-- user_tool_permissions
-- --------------------------------------------------------------------------
CREATE POLICY "utp_select" ON public.user_tool_permissions
    FOR SELECT USING (user_id = auth.uid() OR public.current_user_role() = 'admin');

CREATE POLICY "utp_insert" ON public.user_tool_permissions
    FOR INSERT WITH CHECK (public.current_user_role() = 'admin');

CREATE POLICY "utp_update" ON public.user_tool_permissions
    FOR UPDATE USING (public.current_user_role() = 'admin');

CREATE POLICY "utp_delete" ON public.user_tool_permissions
    FOR DELETE USING (public.current_user_role() = 'admin');

-- --------------------------------------------------------------------------
-- Macro de políticas para tablas de negocio
-- Patrón: viewer=SELECT, operador=SELECT+INSERT+UPDATE, admin=todo
-- El sync corre con service_role y bypassa RLS completamente.
-- --------------------------------------------------------------------------

-- Macro implementada tabla por tabla (mismo patrón en todas):
-- SELECT: viewer | operador | admin
-- INSERT: operador | admin
-- UPDATE: operador | admin
-- DELETE: admin

DO $$
DECLARE
    tbl TEXT;
    tbls TEXT[] := ARRAY[
        'dim_cliente', 'dim_obra', 'dim_rubro', 'dim_sector',
        'dim_trabajador', 'dim_proveedor',
        'fact_compra', 'fact_pago', 'fact_presupuesto_subcontratista',
        'fact_facturacion_subcontratista', 'fact_presupuesto_cliente',
        'fact_ingreso', 'fact_deuda', 'fact_pago_deuda',
        'op_medicion_cabecera', 'op_medicion_linea',
        'op_cert_presupuesto_linea', 'op_cert_cabecera', 'op_cert_linea',
        'aux_falsos_duplicados',
        'bkp_proveedor_personal', 'bkp_compra_personal'
    ];
BEGIN
    FOREACH tbl IN ARRAY tbls LOOP
        EXECUTE format(
            'CREATE POLICY "%s_select" ON public.%I
             FOR SELECT USING (public.current_user_role() IN (''viewer'', ''operador'', ''admin''));',
            tbl, tbl
        );
        EXECUTE format(
            'CREATE POLICY "%s_insert" ON public.%I
             FOR INSERT WITH CHECK (public.current_user_role() IN (''operador'', ''admin''));',
            tbl, tbl
        );
        EXECUTE format(
            'CREATE POLICY "%s_update" ON public.%I
             FOR UPDATE USING (public.current_user_role() IN (''operador'', ''admin''));',
            tbl, tbl
        );
        EXECUTE format(
            'CREATE POLICY "%s_delete" ON public.%I
             FOR DELETE USING (public.current_user_role() = ''admin'');',
            tbl, tbl
        );
    END LOOP;
END;
$$;

-- aux_sync_log: solo admin puede SELECT; service_role escribe
CREATE POLICY "sync_log_select" ON public.aux_sync_log
    FOR SELECT USING (public.current_user_role() = 'admin');
