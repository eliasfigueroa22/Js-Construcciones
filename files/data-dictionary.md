# Data Dictionary

## Fact Tables

### FactCompra
Material purchases across all construction projects.

| Field | Type | Description |
|-------|------|-------------|
| CompraNro | Integer | Primary key (auto-increment) |
| ObraID | Text (FK) | Reference to DimObras |
| SectorID | Text (FK) | Reference to DimSector |
| ProveedorID | Text (FK) | Reference to DimProveedores |
| RubroID | Text (FK) | Reference to DimRubro |
| FechaCompra | Date | Purchase date |
| NumeroDocumento | Text | Invoice/receipt number |
| TipoDocumento | Enum | FACTURA, BOLETA CREDITO, RECIBO |
| Descripcion | Text | Item description |
| Cantidad | Decimal | Quantity purchased |
| Unidad | Text | Unit of measure (UN, GL, M2, etc.) |
| PrecioUnitario | Currency | Unit price (PYG) |
| MontoTotal | Currency | Total amount (PYG) |
| Observaciones | Text | Additional notes |

---

### FactPago
Payments to workers and contractors.

| Field | Type | Description |
|-------|------|-------------|
| PagoNro | Integer | Primary key (auto-increment) |
| ObraID | Text (FK) | Reference to DimObras |
| SectorID | Text (FK) | Reference to DimSector |
| TrabajadorID | Text (FK) | Reference to DimTrabajador |
| RubroID | Text (FK) | Reference to DimRubro |
| PresupuestoSubcontratistaID | Text (FK) | Reference to budget (if applicable) |
| FechaPago | Date | Payment date |
| Concepto | Text | Payment description |
| TipoPago | Enum | PAGO, ADELANTO |
| MontoPago | Currency | Payment amount (PYG) |
| MetodoPago | Enum | EFECTIVO, TRANSFERENCIA, DESCONOCIDO |
| Observaciones | Text | Additional notes |

---

### FactIngreso
Client payments and project income.

| Field | Type | Description |
|-------|------|-------------|
| IngresoNro | Integer | Primary key (auto-increment) |
| ObraID | Text (FK) | Reference to DimObras |
| FechaIngreso | Date | Income receipt date |
| FechaFactura | Date | Invoice date |
| NumeroFactura | Text | Invoice number |
| TipoIngreso | Text | Income type |
| Concepto | Text | Description/concept |
| MontoFacturado | Currency | Invoiced amount (PYG) |
| MontoRecibido | Currency | Received amount (PYG) |
| EstadoCobro | Enum | COBRADO, PENDIENTE |
| FechaCobro | Date | Collection date |
| MetodoPago | Text | Payment method |
| Observaciones | Text | Additional notes |

---

### FactDeuda
Worker debts and advances tracking.

| Field | Type | Description |
|-------|------|-------------|
| DeudaNro | Integer | Primary key (auto-increment) |
| TrabajadorID | Text (FK) | Reference to DimTrabajador |
| ObraID | Text (FK) | Reference to DimObras |
| TipoDeuda | Enum | PRESTAMO, ADELANTO_PERSONAL, COMPRA_PERSONAL |
| FechaSolicitud | Date | Request date |
| MontoDeuda | Currency | Debt amount (PYG) |
| Estado | Enum | ACTIVO, PAGADO |
| Observaciones | Text | Additional notes |

---

### FactPagoDeuda
Debt payment tracking.

| Field | Type | Description |
|-------|------|-------------|
| PagoDeudaNro | Integer | Primary key (auto-increment) |
| DeudaID | Integer (FK) | Reference to FactDeuda |
| FechaPago | Date | Payment date |
| MontoPagado | Currency | Amount paid (PYG) |
| MetodoPago | Enum | EFECTIVO, DESCUENTO_SUELDO, TRANSFERENCIA |
| Observaciones | Text | Additional notes |

---

### FactPresupuestoCliente
Client budgets and quotes.

| Field | Type | Description |
|-------|------|-------------|
| PresupuestoClienteNro | Integer | Primary key (auto-increment) |
| ObraID | Text (FK) | Reference to DimObras |
| SectorID | Text (FK) | Reference to DimSector |
| RubroID | Text (FK) | Reference to DimRubro |
| TipoPresupuesto | Text | Budget type |
| NumeroVersion | Text | Version number |
| FechaPresupuesto | Date | Budget date |
| FechaAprobacion | Date | Approval date |
| Descripcion | Text | Item description |
| Cantidad | Decimal | Quantity |
| Unidad | Text | Unit of measure |
| PrecioUnitario | Currency | Unit price (PYG) |
| MontoTotal | Currency | Total amount (PYG) |
| Estado | Enum | Budget status |
| Observaciones | Text | Additional notes |

---

### FactPresupuestoSubcontratista
Subcontractor budget tracking.

| Field | Type | Description |
|-------|------|-------------|
| PresupuestoSubcontratistaNro | Integer | Primary key (auto-increment) |
| TrabajadorID | Text (FK) | Reference to DimTrabajador |
| ObraID | Text (FK) | Reference to DimObras |
| SectorID | Text (FK) | Reference to DimSector |
| RubroID | Text (FK) | Reference to DimRubro |
| FechaPresupuesto | Date | Budget date |
| Concepto/Descripcion | Text | Work description |
| MontoPresupuestado | Currency | Budgeted amount (PYG) |
| PorcentajeFacturacion | Percentage | Invoicing percentage |
| Estado | Enum | VIGENTE, FINALIZADO |
| Observaciones | Text | Additional notes |

---

### FactFacturacionSubcontratista
Subcontractor invoicing and certificates.

| Field | Type | Description |
|-------|------|-------------|
| FacturacionNro | Integer | Primary key (auto-increment) |
| PresupuestoSubcontratistaID | Integer (FK) | Reference to budget |
| FechaFactura | Date | Invoice date |
| NumeroFactura | Text | Invoice number |
| MontoFacturado | Currency | Invoiced amount (PYG) |
| PorcentajeAplicado | Percentage | Percentage of budget invoiced |
| Observaciones | Text | Additional notes |

---

### FactComprasPersonal
Owner's personal expense purchases.

| Field | Type | Description |
|-------|------|-------------|
| GastoPersonalNro | Integer | Primary key (auto-increment) |
| ProveedorID | Text (FK) | Reference to DimProveedoresPersonal |
| FechaGasto | Date | Expense date |
| Descripcion | Text | Item description |
| Cantidad | Decimal | Quantity |
| Unidad | Text | Unit of measure |
| MontoGasto | Currency | Expense amount (PYG) |
| TipoDocumento | Enum | FACTURA, RECIBO |
| NumeroDocumento | Text | Document number |
| Observaciones | Text | Additional notes |

---

## Dimension Tables

### DimObras
Construction projects (active and historical).

| Field | Type | Description |
|-------|------|-------------|
| ObraNro | Integer | Primary key (auto-increment) |
| NombreObra | Text | Project name |
| ClienteID | Text (FK) | Reference to DimClientes |
| Clave | Text | Unique key (Client - Project) |
| FechaInicio | Date | Start date |
| FechaFinEstimada | Date | Estimated end date |
| FechaFinReal | Date | Actual end date |
| Ubicacion_Ciudad | Text | City |
| Ubicacion_Zona | Text | Zone/Area |
| Ubicacion_Direccion | Text | Address |
| EstadoObra | Enum | ACTIVO, FINALIZADO |
| CategoriaObra | Enum | OBRA, PROYECTO |
| MontoContrato | Currency | Contract amount (PYG) |
| Observaciones | Text | Additional notes |

**Records:** 45

---

### DimClientes
Company clients.

| Field | Type | Description |
|-------|------|-------------|
| ClienteNro | Integer | Primary key (auto-increment) |
| NombreCliente | Text | Client name |
| RUC | Text | Tax ID |
| Direccion | Text | Address |
| Telefono | Text | Phone number |
| Email | Text | Email address |
| TipoCliente | Enum | Empresa, Persona |
| FechaRegistro | Date | Registration date |

**Records:** 9

---

### DimProveedores
Company suppliers (materials, services).

| Field | Type | Description |
|-------|------|-------------|
| ProveedorNro | Integer | Primary key (auto-increment) |
| NombreProveedor | Text | Provider name |
| RUC | Text | Tax ID |
| Telefono | Text | Phone number |
| Email | Text | Email address |
| FechaRegistro | Date | Registration date |

**Records:** 336

---

### DimProveedoresPersonal
Personal expense vendors (owner accounts).

| Field | Type | Description |
|-------|------|-------------|
| ProveedorPersonalNro | Integer | Primary key (auto-increment) |
| NombreProveedor | Text | Provider name |
| RUC | Text | Tax ID |
| Telefono | Text | Phone number |
| Observaciones | Text | Additional notes |

**Records:** 270

---

### DimTrabajador
Workers and contractors.

| Field | Type | Description |
|-------|------|-------------|
| TrabajadorNro | Integer | Primary key (auto-increment) |
| NombreCompleto | Text | Full name |
| TipoPersonal | Enum | SUBCONTRATISTA, EMPLEADO |
| RUC_CI | Text | Tax ID / ID number |
| Telefono | Text | Phone number |
| RubroID | Text (FK) | Primary work category |

**Records:** 112

---

### DimRubro
Expense categories.

| Field | Type | Description |
|-------|------|-------------|
| RubroNro | Integer | Primary key (auto-increment) |
| Rubro | Text | Category code |
| NombreCompleto | Text | Full category name |

**Common values:**
- ALB: Albañilería (Masonry)
- ELEC: Electrical
- PLOM: Plumbing
- PIN: Painting
- GG: Gastos Generales (General Expenses)
- CARP: Carpentry
- HERR: Metalwork

**Records:** 39

---

### DimSector
Project sectors/areas.

| Field | Type | Description |
|-------|------|-------------|
| SectorNro | Integer | Primary key (auto-increment) |
| ObraID | Text (FK) | Reference to DimObras |
| NombreSector | Text | Sector name |
| Clave | Text | Unique key (Client - Project - Sector) |
| Descripcion | Text | Sector description |

**Records:** 54

---

## Enumerations Reference

### TipoDocumento (Document Type)
- FACTURA (Invoice)
- BOLETA CREDITO (Credit receipt)
- RECIBO (Receipt)

### EstadoObra (Project Status)
- ACTIVO (Active)
- FINALIZADO (Finished)

### TipoDeuda (Debt Type)
- PRESTAMO (Loan)
- ADELANTO_PERSONAL (Personal advance)
- COMPRA_PERSONAL (Personal purchase)

### MetodoPago (Payment Method)
- EFECTIVO (Cash)
- TRANSFERENCIA (Bank transfer)
- DESCUENTO_SUELDO (Payroll deduction)
- DESCONOCIDO (Unknown/Legacy)

### TipoPersonal (Worker Type)
- SUBCONTRATISTA (Subcontractor)
- EMPLEADO (Employee)

---

## Currency Note
All monetary values are in **Paraguayan Guaraníes (PYG)**. Format uses periods as thousand separators (e.g., 2.800.000 = 2,800,000 PYG).
