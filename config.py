"""Configuración central de JS Tools.

Lee secretos desde st.secrets (Streamlit Cloud) o .env (desarrollo local).
Define IDs de tablas y campos de Airtable, y nombres de tablas de Supabase.
"""

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parent / ".env")


def get_secret(key: str) -> str:
    """Obtiene un secreto desde st.secrets o variables de entorno.

    Prioridad: st.secrets > .env / variable de entorno del sistema.
    """
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        value = os.getenv(key)
        if value is None:
            raise ValueError(
                f"Secreto '{key}' no encontrado. "
                f"Configuralo en .streamlit/secrets.toml o en .env"
            )
        return value


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
SUPABASE_URL         = get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY    = get_secret("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = get_secret("SUPABASE_SERVICE_KEY")

# Mapeo clave legible → nombre de tabla en PostgreSQL/Supabase
SUPABASE_TABLES: dict[str, str] = {
    # Dimensiones
    "dim_fecha":        "dim_fecha",
    "dim_cliente":      "dim_cliente",
    "dim_obra":         "dim_obra",
    "dim_rubro":        "dim_rubro",
    "dim_sector":       "dim_sector",
    "dim_trabajador":   "dim_trabajador",
    "dim_proveedor":    "dim_proveedor",
    # Hechos
    "fact_compra":                       "fact_compra",
    "fact_pago":                         "fact_pago",
    "fact_presupuesto_subcontratista":   "fact_presupuesto_subcontratista",
    "fact_facturacion_subcontratista":   "fact_facturacion_subcontratista",
    "fact_presupuesto_cliente":          "fact_presupuesto_cliente",
    "fact_ingreso":                      "fact_ingreso",
    "fact_deuda":                        "fact_deuda",
    "fact_pago_deuda":                   "fact_pago_deuda",
    # Operacionales
    "op_medicion_cabecera":       "op_medicion_cabecera",
    "op_medicion_linea":          "op_medicion_linea",
    "op_cert_presupuesto_linea":  "op_cert_presupuesto_linea",
    "op_cert_cabecera":           "op_cert_cabecera",
    "op_cert_linea":              "op_cert_linea",
    # Auxiliares
    "aux_falsos_duplicados": "aux_falsos_duplicados",
    "aux_sync_log":          "aux_sync_log",
    # Auth
    "user_profiles":         "user_profiles",
    "user_tool_permissions": "user_tool_permissions",
}

# Nombres en español para dim_fecha (PostgreSQL devuelve inglés desde TO_CHAR)
MESES_ES: dict[str, str] = {
    "January": "Enero",   "February": "Febrero", "March":     "Marzo",
    "April":   "Abril",   "May":       "Mayo",    "June":      "Junio",
    "July":    "Julio",   "August":    "Agosto",  "September": "Septiembre",
    "October": "Octubre", "November":  "Noviembre","December": "Diciembre",
}
DIAS_ES: dict[str, str] = {
    "Monday":    "Lunes",     "Tuesday":  "Martes",   "Wednesday": "Miércoles",
    "Thursday":  "Jueves",    "Friday":   "Viernes",  "Saturday":  "Sábado",
    "Sunday":    "Domingo",
}

# ---------------------------------------------------------------------------
# Airtable
# ---------------------------------------------------------------------------
AIRTABLE_BASE_ID = "app2cOTrbiNx10o2d"

# Mapeo: clave legible → field ID de Airtable
# Esto permite cambiar nombres de campo en Airtable sin tocar código.
TABLES = {
    "facturas": {
        "id": "tbl47ExnBN9stlzlW",  # FactCompra
        "fields": {
            # Orden idéntico al de la tabla FactCompra en Airtable
            "CompraNro":     "fldl8L00IU5MPqg5z",  # autoNumber (clave primaria)
            "ObraID":        "fldF5ij51Ut6tqU9I",  # multipleRecordLinks
            "Proveedor":     "fldgDjXKiWpFQPo8n",  # ProveedorID (linked)
            "Fecha":         "fldX46nHSZ7sVW7lN",  # FechaCompra
            "NroFactura":    "fldduo2WKZhq49DvD",  # NumeroDocumento
            "Descripcion":   "fldALSjObIdCx2EQ3",  # singleLineText
            "Cantidad":      "fldruh5c0AeryTIkt",  # number
            "Unidad":        "fldE698lZxnAWNnHi",  # singleSelect
            "MontoTotal":    "flduEuFXZkbPWxVGW",  # number
            "SectorID":      "fldm6qquKU99va5fI",  # multipleRecordLinks → DimSector
            "RubroID":       "fldZ5GUaBefdPrpJX",  # multipleRecordLinks → DimRubro
            "TipoDocumento": "fldYHAdvYgPKZ9diw",  # singleSelect
            "Observaciones": "fldSyjvKQ11gAkiOq",  # multilineText
            "Created":       "fld3Sq4oK7AiIOMIy",  # createdTime
        },
    },
    "obras": {
        "id": "tbldULscM4zk2oPBu",  # DimObras
        "fields": {
            "Nombre":       "fldNPEPDiQj0CIRjK",  # NombreObra
            "Clave":        "fldBnIYEYgWz33ZHL",  # Clave (primary/formula)
            "ObraNro":      "fldza59YNzHiMm7E3",  # ObraNro (autoNumber)
            "EstadoObra":   "flduteeL3rkP6qVtj",  # singleSelect
            "CategoriaObra":"fldmNS0vbggFuyzbF",  # singleSelect (Obra/Servicio/Proyecto)
            "ClienteID":    "fld6YfXE9ozuXxzRg",  # multipleRecordLinks → DimClientes
            "Ubicacion":    "fldJ1RZplo0gb27Tn",  # singleLineText
            "Superficie":   "fldKeOKb4YK2nF2c5",  # singleLineText
        },
    },
    "DimClientes": {
        "id": "tblkZ3FHekPCk651F",
        "fields": {
            "NombreCliente": "fldRwdvT58lgtEhSE",  # multilineText (primary)
            "ClienteNro":    "fldwggbRY5XeUtrK2",  # autoNumber
            "RUC":           "fldwf9eND0e4MyAoP",  # singleLineText
            "Direccion":     "flde9PUJqjqOk2imt",  # singleLineText
            "Telefono":      "fldxEwo8tAdmjJTDM",  # singleLineText
            "Email":         "fldcuFpKBNEBUnm4P",  # singleLineText
            "TipoCliente":   "fld9aUKLMTiN6jqtV",  # singleSelect
            "FechaRegistro": "fldCMkfbjDwUkXCop",  # date
        },
    },
    "DimSector": {
        "id": "tblWIKPSI9QLoQovC",
        "fields": {
            "NombreSector": "fldl2ERBFrqKCjwFn",  # singleLineText (primary)
            "SectorNro":    "flduZL4LejKqOdjH5",  # autoNumber
            "ObraID":       "fld67PRfCGMr5mwUC",  # multipleRecordLinks → obras
            "Descripcion":  "fld7SvHoHrKhGEn6L",  # singleLineText
        },
    },
    "DimRubro": {
        "id": "tblusMPTyS1CivZM5",
        "fields": {
            "Rubro":         "fldC3NVoEPnBvz5ER",
            "NombreCompleto":"fldICPpnwwsmk1Tmc",
        },
    },
    "DimTrabajador": {
        "id": "tblgBuKAq7z8N7wgu",
        "fields": {
            "NombreCompleto":  "fldsjU4I1UI5XQ3f9",  # multilineText (primary)
            "TrabajadorNro":   "fldEgPtU9prdFHKi1",  # autoNumber
            "TipoPersonal":    "fldikliA0VKvbabYX",  # singleSelect
            "Telefono":        "fldS714mQwVqaMATb",  # singleLineText
            "RUC_CI":          "fld16pTkpIoPEGkoL",  # singleLineText
            "RubroID":         "fldDPBu4C6JPV9uiM",  # multipleRecordLinks → DimRubro
        },
    },
    "FactPago": {
        "id": "tblTNEawQcaBtN76b",
        "fields": {
            "PagoNro":                     "fldwIRcs5jDtb8byl",
            "PresupuestoSubcontratistaID": "fldlVIdMQVktJi0Ri",
            "ObraID":                      "fldBaRWN3uJbJ2qAl",
            "TrabajadorID":                "fldmwlTBMecf7Fbat",
            "FechaPago":                   "fldTdlMhWVz6ZVDUz",
            "Concepto":                    "fldJjWhjpPI9tzh6T",
            "SectorID":                    "fldK3kO1VtGCU7iq4",  # multipleRecordLinks → DimSector
            "RubroID":                     "fld8DGPyYLZYemYCI",  # multipleRecordLinks → DimRubro
            "TipoPago":                    "fld9hPe2mNMWHbIOw",
            "MontoPago":                   "fldUCNP6yULBXT2qA",
            "MetodoPago":                  "fldLMImjTIm41R1RL",
        },
    },
    "DimProveedores": {
        "id": "tbl5N8FMH2Yk5HZ1H",
        "fields": {
            "NombreProveedor": "fldqcWKLCeRsOMx5t",  # multilineText (primary)
            "ProveedorNro":    "fldlJuTw48zcxxgT9",  # autoNumber
            "RUC":             "fldTarpmykKIVPyfe",  # singleLineText
            "Telefono":        "fldEWCjInXTf27BCB",  # singleLineText
            "Email":           "fldc15cqsnDUgyl3l",  # singleLineText
        },
    },
    "FactPresupuestoCliente": {
        "id": "tbl7K2uE74waZ6Hu5",
        "fields": {
            "PresupuestoClienteNro": "fldBAm0TGihV4qtiN",  # autoNumber (primary)
            "ObraID":                "fldwpaIw4NZ9TGQqD",  # multipleRecordLinks → obras
            "SectorID":              "fldpenOtxeRxho7fs",  # multipleRecordLinks → DimSector
            "RubroID":               "fldvv2mUWp0T9TdEt",  # multipleRecordLinks → DimRubro
            "TipoPresupuesto":       "fld39H407KeziAKoZ",  # singleSelect
            "NumeroVersion":         "fldtVAS2xFDOkFBHH",  # number
            "FechaPresupuesto":      "fldajXhg75hXTYvfL",  # date
            "FechaAprobacion":       "fldzDZlo97wJGYOLU",  # date
            "Descripcion":           "fldLdznt2xnC3CbB2",  # multilineText
            "Cantidad":              "fldcjCNODQ7xCOTe1",  # number
            "Unidad":                "fldCLFQdJnOchebow",  # singleSelect
            "PrecioUnitario":        "fldU8IRrGU8pu7bLN",  # number
            "MontoTotal":            "fldCnB8SgOZ1IKreN",  # number
            "Estado":                "fldZBp4ChBo2xlXnw",  # singleSelect
            "Observaciones":         "fldxUG2Ipoe4bNFFK",  # multilineText
        },
    },
    "FactFacturacionSubcontratista": {
        "id": "tblEk7Btplj6WZSyr",
        "fields": {
            "FacturacionNro":              "fld7hdORkMApVPUN5",  # autoNumber (primary)
            "PresupuestoSubcontratistaID": "fldMRKdfFc6fubruR",  # multipleRecordLinks → FactPresupuestoSubcontratista
            "FechaFactura":                "fldnpVMj8hD8jI0Cf",  # date
            "NumeroFactura":               "fldpSxjuaVLxp8cRC",  # multilineText
            "MontoFacturado":              "fldfl5rkUheQOfZ1A",  # number
            "PorcentajeAplicado":          "fldFDgRFqS66wRRcw",  # percent
            "Observaciones":               "fldUKlXglYtwNGBNW",  # multilineText
        },
    },
    "FactDeuda": {
        "id": "tblrmoDOxyYODIYHl",
        "fields": {
            "DeudaNro":       "fldNoVHrAiqIbzW4r",  # autoNumber (primary)
            "ObraID":         "fldfm0HeWWblIyBQt",  # multipleRecordLinks → obras
            "TrabajadorID":   "flds7TYd6NFQKTYJT",  # multipleRecordLinks → DimTrabajador
            "TipoDeuda":      "fld24nVoG4iLPCNrW",  # multipleSelects
            "FechaSolicitud": "fld4tEPADyon3veLE",  # date
            "MontoDeuda":     "fldpfFYMV5WNg2NOj",  # number
            "Estado":         "fldguBWU08QKmOHvE",  # singleSelect
            "Observaciones":  "fldpcbZuZwS3Wdh22",  # multilineText
        },
    },
    "FactPagoDeuda": {
        "id": "tblWzMK0j1vV7cldl",
        "fields": {
            "PagoDeudaNro": "fldk3LeZDMQbkPWGJ",  # autoNumber (primary)
            "DeudaID":      "fldypuoffjRvzITyt",  # multipleRecordLinks → FactDeuda
            "FechaPago":    "fldqhjBE2WD9qgsJG",  # date
            "MontoPagado":  "fld82gWayLIQdSvFH",  # number
            "MetodoPago":   "fldWBAXUR4qRyXUYG",  # singleSelect
            "Observaciones":"fldjMyPNWKih2Ormb",  # multilineText
        },
    },
    "FalsosDuplicados": {
        "id": "tblWfO1SkNS0xRDOb",
        "fields": {
            "ClaveGrupo": "fldxBiXDJBg2qZxDz",
            "Tipo":       "fldv29hrj2dfvc93s",
            "NroFactura": "fldfr63U7TlvznA7f",
            "Proveedor":  "fldtJwQHywPAnbOV5",
        },
    },
    "FactPresupuestoSubcontratista": {
        "id": "tblxeg6cYjNFJYONv",
        "fields": {
            "PresupuestoNro":     "fldvlPd0T3Jx5Z2k9",
            "TrabajadorID":       "flddlaBaXF6YJSunK",
            "ObraID":             "fld5lCKwuFUoV5RNE",
            "SectorID":           "fldJm5SfEy9wt2wOD",  # multipleRecordLinks → DimSector
            "RubroID":            "fldv9idZT56d4Zaoo",  # multipleRecordLinks → DimRubro
            "Concepto":           "fldqJCxNHoxbjmrhZ",
            "FechaPresupuesto":   "fldBLGM1mwH3SM84P",
            "MontoPresupuestado": "flduwlkZAw7K8z76H",
            "Estado":             "fldCKIIFi99zHWJ9j",
        },
    },
    "MedicionCabecera": {
        "id": "tbl1de55MknW6Qc5c",
        "fields": {
            "MedicionRef":   "fldWGE48RqaIDlgVt",  # singleLineText (primary)
            "ObraID":        "fldD7Db3QpXv8Sp4a",  # multipleRecordLinks → obras
            "TrabajadorID":  "fld0FdPWn7dnhERB3",  # multipleRecordLinks → DimTrabajador
            "Fecha":         "fldqiXQpGz3Cpsxdo",  # date
            "Estado":        "fldwdw1YwJ8fgtw2h",  # singleSelect: Borrador / Confirmado
            "Observaciones": "fldFvYZF4FkfWVjEr",  # multilineText
        },
    },
    "MedicionLinea": {
        "id": "tblgz5ThXwxHcG7Jz",
        "fields": {
            "Descripcion":    "fld6bpyV7GTw5TYxk",  # singleLineText (primary)
            "CabeceraID":     "fldxriYn3yy0kgHIM",  # multipleRecordLinks → MedicionCabecera
            "SectorID":       "fld51y5Ez3tiw8xwU",  # multipleRecordLinks → DimSector
            "RubroID":        "fldrdh24w1WwJxrAn",  # multipleRecordLinks → DimRubro
            "Unidad":         "fldBtKv5it63NYXAD",  # singleSelect: m², m³, ml, kg, un
            "Largo":          "fldaaxgerLaXZyLhx",  # number (3 decimales)
            "Ancho":          "fldr6nskTVGkWFfrY",  # number (3 decimales)
            "Alto":           "fldrepdVzenpWMuh0",  # number (3 decimales)
            "Cantidad":       "fldON84SQp0Kf7x3n",  # number (3 decimales)
            "PrecioUnitario": "fldn2zSYtZuNcMjtY",  # number (0 decimales, Gs.)
        },
    },
    "FactIngreso": {
        "id": "tblyF7UraXgsqrGDO",
        "fields": {
            "IngresoNro":     "fld2CogpEBFDSh3g2",  # autoNumber (primary)
            "ObraID":         "fldBRJ4i4djKZTncX",  # multipleRecordLinks → obras
            "FechaIngreso":   "fldrgQKF3C9QRmBgr",  # date
            "FechaFactura":   "fldrCJbo577AkWDEc",  # date
            "NumeroFactura":  "fldJmecGPPatk6Noj",  # singleLineText
            "TipoIngreso":    "fld4iOdz6LBOmP34N",  # singleSelect
            "Concepto":       "fldUqLSuyQBRZiV2J",  # multilineText
            "MontoFacturado": "fldvLblSaGkTex2ZL",  # number
            "MontoRecibido":  "fldYF48Q5YopBomg1",  # number
            "EstadoCobro":    "fldSAjfI3He77lK1f",  # singleSelect
            "FechaCobro":     "fldKyYICoVOOOIyxe",  # date
            "MetodoPago":     "fldn8k0UjLn2hADzo",  # singleSelect
            "Observaciones":  "fldcm8f0aQk99u3Xt",  # multilineText
        },
    },
    # ----- Certificaciones de Obra -----
    "CertPresupuestoLinea": {
        "id": "tbldbBQ2PKDG00tpU",
        "fields": {
            "Rubro":          "fldajfromv3lRBj2F",  # singleLineText (primary)
            "ObraID":         "fld2fiQDmRFnFPBQT",  # multipleRecordLinks → obras
            "Orden":          "fld7Yxzz6Y0w20Apx",  # number (int)
            "ItemNro":        "fldrukX65C2fP7zJ2",  # singleLineText
            "Zona":           "fldKd8aNtbDMwZ4IO",  # singleLineText (top-level section)
            "GrupoNombre":    "fld4cplKsLHqPXU6F",  # singleLineText
            "Unidad":         "fldbuxkBva0LfXq6N",  # singleLineText
            "Cantidad":       "fldauus8Z7VOqocXm",  # number (3 dec)
            "PrecioUnitario": "fldEXRXSlLzhyCA7b",  # number (0 dec, Gs.)
            "Observaciones":  "fldEOSHpmSglsyJmV",  # singleLineText
            "SinCotizar":     "fldODasEapzzDMCiQ",  # checkbox
        },
    },
    "CertCabecera": {
        "id": "tblVczhdMzhU1Gs3N",
        "fields": {
            "CertRef":         "fldgeOpV6vYN4yEAE",  # singleLineText (primary)
            "ObraID":          "fldFDwSURog3LBVDF",  # multipleRecordLinks → obras
            "Numero":          "fld04B4hF0NqllN9E",  # number (int)
            "FechaCertificado":"fldrBQbQHgWXV863d",  # date
            "Estado":          "fldWTxxGM7jVY3DJq",  # singleSelect: Borrador/Confirmado
            "Observaciones":   "fldw18tt4FhbckHXb",  # multilineText
        },
    },
    "CertLinea": {
        "id": "tblvuBjNxuIDnIYXM",
        "fields": {
            "LineaRef":            "fld4Lk3iR8OEZJhvz",  # singleLineText (primary)
            "CabeceraID":          "fld4bAsLAGRi2gwQA",  # multipleRecordLinks → CertCabecera
            "PresupuestoLineaID":  "fldXbayc65QSkaeEg",  # multipleRecordLinks → CertPresupuestoLinea
            "CantidadCertificada": "fldIpQd9qFlSstUcs",  # number (3 dec)
        },
    },
}
