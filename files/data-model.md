# Data Model Documentation

## Overview

This project uses a **dimensional model** based on the Kimball methodology with a **star schema** design. The model separates transactional data (facts) from descriptive data (dimensions), enabling efficient querying and reporting.

## Design Principles

### Star Schema
- Fact tables at the center contain measurable events (transactions)
- Dimension tables surround facts and provide context (who, what, where, when)
- Simple joins between facts and dimensions for straightforward queries

### Grain Definition
Each fact table has a clearly defined grain (what one row represents):

| Fact Table | Grain (One Row = ) |
|------------|-------------------|
| FactCompra | One material purchase transaction |
| FactPago | One payment to a worker |
| FactIngreso | One income receipt from a client |
| FactDeuda | One debt record (loan or advance) |
| FactPagoDeuda | One debt payment |
| FactPresupuestoCliente | One budget line item for client |
| FactPresupuestoSubcontratista | One subcontractor budget |
| FactFacturacionSubcontratista | One subcontractor invoice |
| FactComprasPersonal | One personal expense (owner) |

## Entity Relationships

```
                    ┌─────────────────┐
                    │   DimClientes   │
                    └────────┬────────┘
                             │
                             │ 1:N
                             ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  DimProveedores │    │    DimObras     │    │  DimTrabajador  │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │ 1:N                  │ 1:N                  │ 1:N
         ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FACT TABLES                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ FactCompra  │ │  FactPago   │ │FactIngreso  │ │FactDeuda  │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ▲                      ▲
         │ 1:N                  │ 1:N
         │                      │
┌────────┴────────┐    ┌────────┴────────┐
│    DimRubro     │    │   DimSector     │
└─────────────────┘    └─────────────────┘
```

## Key Design Decisions

### 1. Separate Provider Dimensions
The model uses two provider dimensions:
- **DimProveedores** (336 records): Company suppliers for business expenses
- **DimProveedoresPersonal** (270 records): Vendors for owner's personal expenses

**Rationale:** The owner's personal expenses flow through the same system but must remain separate from company finances for accounting purposes. This separation also simplified the deduplication process.

### 2. Sector as Sub-dimension of Obra
**DimSector** provides granularity within construction projects. One project (Obra) can have multiple sectors (e.g., "ALGESA - FRANCO" has sectors for COMEDOR, BAÑO, OFICINA, GARITA).

**Rationale:** Enables detailed cost tracking by area within large projects while maintaining the ability to roll up to project-level totals.

### 3. Rubro (Category) Hierarchy
**DimRubro** categorizes expenses with codes like:
- ALB (Albañilería/Masonry)
- ELEC (Electrical)
- PLOM (Plumbing)
- PIN (Painting)
- GG (General Expenses)

**Rationale:** Consistent categorization enables meaningful comparisons across projects and time periods.

### 4. Subcontractor Budget Tracking
The model includes a complete subcontractor management flow:
```
FactPresupuestoSubcontratista (Budget)
         │
         │ Links to
         ▼
FactFacturacionSubcontratista (Invoices/Certificates)
         │
         │ Links to
         ▼
    FactPago (Payments)
```

**Rationale:** Construction projects require tracking not just what was paid, but what was budgeted and what percentage has been invoiced.

## Naming Conventions

| Prefix | Meaning | Example |
|--------|---------|---------|
| Fact | Transaction/event table | FactCompra |
| Dim | Dimension/lookup table | DimProveedores |
| ID | Foreign key | ObraID, ProveedorID |
| Nro | Record number (surrogate key) | CompraNro, PagoNro |
| _ | Linked records (Airtable) | _FactCompra |

## Data Types

| Field Pattern | Data Type | Example |
|---------------|-----------|---------|
| *Nro | Integer (auto-increment) | CompraNro: 1, 2, 3... |
| *ID | Text (lookup) | ObraID: "ALGESA - FRANCO" |
| Fecha* | Date | FechaCompra: 18/4/2024 |
| Monto* | Currency (PYG) | MontoTotal: 2.800.000 |
| Estado | Status enum | "ACTIVO", "FINALIZADO" |
| Tipo* | Type enum | TipoDocumento: "FACTURA" |
