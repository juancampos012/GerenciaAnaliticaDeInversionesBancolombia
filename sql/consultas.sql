-- Filas exactamente repetidas (todas las columnas iguales menos el id)
SELECT 'historico_aba_macroactivos' AS tabla, COUNT(*) - COUNT(DISTINCT (
           ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, macroactivo,
           cod_activo, aba, cod_perfil_riesgo, cod_banca, year, month
       )) AS filas_repetidas
FROM historico_aba_macroactivos
UNION ALL
SELECT 'historico_aba_usd_internacional', COUNT(*) - COUNT(DISTINCT (
           ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, simbol, cusip,
           isin, nombre_activo, cantidad, valor_mercado, fecha_vencimiento, tasa_cupon
       ))
FROM historico_aba_usd_internacional;

-- Tipos de ID de cliente en macroactivos
SELECT
    CASE
        WHEN id_sistema_cliente ~ '^[0-9]{10,11}$' THEN 'ID completo'
        WHEN id_sistema_cliente ~ '^[0-9.]+E\+[0-9]+$' THEN 'Notación científica'
        WHEN id_sistema_cliente IS NULL
          OR TRIM(id_sistema_cliente) = '' THEN 'Vacío'
        ELSE 'Otro (partido o corrido)'
    END AS tipo_id,
    COUNT(*) AS filas
FROM historico_aba_macroactivos
GROUP BY tipo_id
ORDER BY filas DESC;

-- Códigos de activo que no existen en el catálogo
SELECT h.cod_activo, COUNT(*) AS filas
FROM historico_aba_macroactivos h
LEFT JOIN catalogo_activos c ON c.cod_activo::TEXT = h.cod_activo
WHERE c.cod_activo IS NULL
GROUP BY h.cod_activo
ORDER BY filas DESC;

-- Macroactivo de cada código de activo
SELECT cod_activo, macroactivo, COUNT(*) AS filas
FROM historico_aba_macroactivos
WHERE macroactivo IN ('Renta Variable', 'Renta Fija', 'FICs')
GROUP BY cod_activo, macroactivo
ORDER BY cod_activo, macroactivo;

-- Valores vacíos, 'None' o 'nan' por columna en macroactivos
SELECT
    COUNT(*) FILTER (WHERE COALESCE(TRIM(id_sistema_cliente), '') IN ('', 'None', 'nan')) AS cliente_vacio,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(macroactivo), '')        IN ('', 'None', 'nan')) AS macroactivo_vacio,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(cod_activo), '')         IN ('', 'None', 'nan')) AS cod_activo_vacio,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(aba), '')                IN ('', 'None', 'nan')) AS aba_vacio,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(cod_perfil_riesgo), '')  IN ('', 'None', 'nan')) AS perfil_vacio,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(cod_banca), '')          IN ('', 'None', 'nan')) AS banca_vacia,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(ingestion_month), '')    IN ('', 'None', 'nan')) AS mes_ingesta_vacio
FROM historico_aba_macroactivos;


