/*
    Airtable API Connection - Power Query M Code
    JS Construcciones Data Architecture Project
    
    This function connects to Airtable's API and retrieves all records from a specified table.
    It handles pagination automatically and expands all fields defined in the table schema.
    
    Usage:
    1. Create a blank query in Power Query
    2. Paste this code
    3. Call the function with a table ID: GetAirtableData("tblXXXXXXXX")
    
    Note: Replace baseId and apiToken with your actual values before use.
*/

(tableId as text) as table =>
let
    // ============================================
    // CONFIGURATION - Replace with your credentials
    // ============================================
    baseId = "appXXXXXXXXXXXXXX",      // Your Airtable Base ID
    apiToken = "patXXXXXXXXXXXXXX",    // Your Personal Access Token
    
    // ============================================
    // GET TABLE SCHEMA
    // Retrieves all column definitions from Airtable metadata
    // ============================================
    schemaUrl = "https://api.airtable.com/v0/meta/bases/" & baseId & "/tables",
    Schema = Json.Document(Web.Contents(schemaUrl, [Headers=[Authorization="Bearer " & apiToken]])),
    TableSchema = List.First(List.Select(Schema[tables], each _[id] = tableId)),
    
    // Get all field names, excluding internal fields (starting with "_")
    AllDefinedFields = List.Select(
        List.Transform(TableSchema[fields], each _[name]),
        each not Text.StartsWith(_, "_")
    ),
    
    // ============================================
    // PAGINATION FUNCTION
    // Airtable returns max 100 records per request
    // ============================================
    GetPage = (offset as nullable text) as record =>
        let
            url = "https://api.airtable.com/v0/" & baseId & "/" & tableId 
                  & (if offset <> null then "?offset=" & offset else ""),
            Response = Json.Document(Web.Contents(url, [Headers=[Authorization="Bearer " & apiToken]]))
        in
            Response,
    
    // ============================================
    // RECURSIVE DATA RETRIEVAL
    // Continues fetching until no more offset is returned
    // ============================================
    GetAllRecords = (offset as nullable text, accumulated as list) as list =>
        let
            Page = GetPage(offset),
            NewRecords = accumulated & Page[records],
            NextOffset = try Page[offset] otherwise null
        in
            if NextOffset = null then NewRecords
            else @GetAllRecords(NextOffset, NewRecords),
    
    // Get all records
    AllRecords = GetAllRecords(null, {}),
    
    // ============================================
    // DATA TRANSFORMATION
    // Convert JSON to proper Power Query table
    // ============================================
    ToTable = Table.FromList(AllRecords, Splitter.SplitByNothing()),
    ExpandBoth = Table.ExpandRecordColumn(ToTable, "Column1", {"id", "fields"}),
    
    // Expand using ALL schema columns (ensures consistent structure)
    ExpandAll = Table.ExpandRecordColumn(ExpandBoth, "fields", AllDefinedFields),
    
    // ============================================
    // DATA CLEANING
    // Handle linked records (lists) and null values
    // ============================================
    // Airtable returns linked records as lists - extract first value (FK)
    CleanLinks = Table.TransformColumns(ExpandAll, {}, 
        each if _ is list then List.First(_, null)
             else _),
    
    // Rename Airtable's internal ID to a clearer name
    RenameID = Table.RenameColumns(CleanLinks, {{"id", "AirtableID"}})
in
    RenameID


/*
    ============================================
    TABLE IDs REFERENCE
    ============================================
    
    Fact Tables:
    - FactCompra:                    tblXXXXXXXX
    - FactPago:                      tblXXXXXXXX
    - FactIngreso:                   tblXXXXXXXX
    - FactDeuda:                     tblXXXXXXXX
    - FactPagoDeuda:                 tblXXXXXXXX
    - FactPresupuestoCliente:        tblXXXXXXXX
    - FactPresupuestoSubcontratista: tblXXXXXXXX
    - FactFacturacionSubcontratista: tblXXXXXXXX
    - FactComprasPersonal:           tblXXXXXXXX
    
    Dimension Tables:
    - DimObras:                      tblXXXXXXXX
    - DimClientes:                   tblXXXXXXXX
    - DimProveedores:                tblXXXXXXXX
    - DimProveedoresPersonal:        tblXXXXXXXX
    - DimTrabajador:                 tblXXXXXXXX
    - DimRubro:                      tblXXXXXXXX
    - DimSector:                     tblXXXXXXXX
    
    Note: Replace tblXXXXXXXX with actual table IDs from your Airtable base.
    
    ============================================
    USAGE EXAMPLES
    ============================================
    
    // In Power Query, create queries like:
    
    let
        Source = GetAirtableData("tbl123456789")  // FactCompra table ID
    in
        Source
    
*/
