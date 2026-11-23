# Queries SQL de las páginas Resumen, Clientes y Calidad de datos.
# Todas usan la última fecha disponible de cada cliente.


# ---------------------------------------------------------------------
# Partes que se repiten: filas de cada cliente en su última fecha
# ---------------------------------------------------------------------

COP_LATEST_CTE = """
ultima_cop AS (
    SELECT id_sistema_cliente, MAX(fecha_ingesta) AS fecha
    FROM macroactivos_limpio
    GROUP BY id_sistema_cliente
),
cop AS (
    SELECT m.*
    FROM macroactivos_limpio m
    JOIN ultima_cop u
      ON u.id_sistema_cliente = m.id_sistema_cliente
     AND u.fecha = m.fecha_ingesta
)
"""

USD_LATEST_CTE = """
ultima_usd AS (
    SELECT id_sistema_cliente, MAX(fecha_ingesta) AS fecha
    FROM usd_internacional_limpio
    GROUP BY id_sistema_cliente
),
usd AS (
    SELECT u.*
    FROM usd_internacional_limpio u
    JOIN ultima_usd x
      ON x.id_sistema_cliente = u.id_sistema_cliente
     AND x.fecha = u.fecha_ingesta
)
"""


# ---------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------

# Fechas usadas (la última de cada cliente puede variar entre clientes)
SUMMARY_DATES_SQL = f"""
WITH {COP_LATEST_CTE}, {USD_LATEST_CTE}
SELECT
    (SELECT MIN(fecha) FROM ultima_cop) AS cop_desde,
    (SELECT MAX(fecha) FROM ultima_cop) AS cop_hasta,
    (SELECT MIN(fecha) FROM ultima_usd) AS usd_desde,
    (SELECT MAX(fecha) FROM ultima_usd) AS usd_hasta;
"""

# ABA total y número de clientes por banca
BANK_SUMMARY_SQL = f"""
WITH {COP_LATEST_CTE}
SELECT
    COALESCE(b.banca, 'Sin banca')       AS banca,
    COUNT(DISTINCT c.id_sistema_cliente) AS clientes,
    SUM(c.aba)                           AS aba_total
FROM cop c
LEFT JOIN catalogo_banca b ON b.cod_banca = c.cod_banca
GROUP BY COALESCE(b.banca, 'Sin banca')
ORDER BY aba_total DESC;
"""

# Los 10 activos con más ABA en pesos
TOP_COP_ASSETS_SQL = f"""
WITH {COP_LATEST_CTE}
SELECT
    COALESCE(a.activo, 'Sin catálogo (' || COALESCE(c.cod_activo_origen, 'sin código') || ')') AS activo,
    c.macroactivo,
    COUNT(DISTINCT c.id_sistema_cliente) AS clientes,
    SUM(c.aba)                           AS aba_total
FROM cop c
LEFT JOIN catalogo_activos a ON a.cod_activo = c.cod_activo
GROUP BY 1, 2
ORDER BY aba_total DESC
LIMIT 10;
"""

# Los 10 activos con más valor de mercado en dólares
TOP_USD_ASSETS_SQL = f"""
WITH {USD_LATEST_CTE}
SELECT
    nombre_activo,
    isin,
    COUNT(DISTINCT id_sistema_cliente) AS clientes,
    SUM(valor_mercado_usd)             AS valor_total
FROM usd
GROUP BY nombre_activo, isin
ORDER BY valor_total DESC
LIMIT 10;
"""


# ---------------------------------------------------------------------
# Ranking de clientes
# ---------------------------------------------------------------------

# Un cliente por fila con su ABA en COP y su valor en USD.
# Si un cliente tiene más de una banca o perfil, se muestran todos.
CLIENT_RANKING_SQL = f"""
WITH {COP_LATEST_CTE}, {USD_LATEST_CTE},
cop_cliente AS (
    SELECT
        c.id_sistema_cliente,
        MIN(c.fecha_ingesta)                              AS fecha_cop,
        STRING_AGG(DISTINCT b.banca, ', ')                AS banca,
        STRING_AGG(DISTINCT p.perfil_riesgo, ', ')        AS perfil_riesgo,
        SUM(c.aba)                                        AS aba_cop
    FROM cop c
    LEFT JOIN catalogo_banca    b ON b.cod_banca = c.cod_banca
    LEFT JOIN cat_perfil_riesgo p ON p.cod_perfil_riesgo = c.cod_perfil_riesgo
    GROUP BY c.id_sistema_cliente
),
usd_cliente AS (
    SELECT
        id_sistema_cliente,
        MIN(fecha_ingesta)     AS fecha_usd,
        SUM(valor_mercado_usd) AS valor_usd
    FROM usd
    GROUP BY id_sistema_cliente
)
SELECT
    COALESCE(c.id_sistema_cliente, u.id_sistema_cliente)                 AS id_sistema_cliente,
    COALESCE(c.id_sistema_cliente, u.id_sistema_cliente) ~ '^[0-9]+$'   AS confiable,
    c.banca,
    c.perfil_riesgo,
    c.aba_cop,
    c.fecha_cop,
    u.valor_usd,
    u.fecha_usd
FROM cop_cliente c
FULL JOIN usd_cliente u ON u.id_sistema_cliente = c.id_sistema_cliente
ORDER BY c.aba_cop DESC NULLS LAST;
"""


# ---------------------------------------------------------------------
# Calidad de datos
# ---------------------------------------------------------------------

# Filas de cada tabla en cada etapa de la limpieza
QUALITY_ROWS_SQL = """
SELECT
    'Macroactivos' AS tabla,
    (SELECT COUNT(*) FROM historico_aba_macroactivos) AS originales,
    (SELECT COUNT(*) - COUNT(DISTINCT (
         ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, macroactivo,
         cod_activo, aba, cod_perfil_riesgo, cod_banca, year, month))
     FROM historico_aba_macroactivos) AS repetidas,
    (SELECT COUNT(*) FROM macroactivos_rechazados) AS rechazadas,
    (SELECT COUNT(*) FROM macroactivos_limpio) AS limpias
UNION ALL
SELECT
    'USD internacional',
    (SELECT COUNT(*) FROM historico_aba_usd_internacional),
    (SELECT COUNT(*) - COUNT(DISTINCT (
         ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, simbol, cusip,
         isin, nombre_activo, cantidad, valor_mercado, fecha_vencimiento, tasa_cupon))
     FROM historico_aba_usd_internacional),
    (SELECT COUNT(*) FROM usd_internacional_rechazados),
    (SELECT COUNT(*) FROM usd_internacional_limpio);
"""

# Filas rechazadas por motivo
REJECTED_BY_REASON_SQL = """
SELECT 'Macroactivos' AS tabla, motivo_rechazo, COUNT(*) AS filas
FROM macroactivos_rechazados
GROUP BY motivo_rechazo
UNION ALL
SELECT 'USD internacional', motivo_rechazo, COUNT(*)
FROM usd_internacional_rechazados
GROUP BY motivo_rechazo
ORDER BY tabla, filas DESC;
"""

# Tipos de ID de cliente en el archivo original de macroactivos
ID_TYPES_SQL = """
SELECT
    CASE
        WHEN TRIM(id_sistema_cliente) ~ '^[0-9]{10,11}$'      THEN 'ID completo'
        WHEN TRIM(id_sistema_cliente) ~ '^[0-9.]+E\\+[0-9]+$' THEN 'Notación científica'
        WHEN COALESCE(TRIM(id_sistema_cliente), '') IN ('', 'None', 'nan') THEN 'Vacío'
        ELSE 'Otro (partido o corrido)'
    END AS tipo_id,
    COUNT(*) AS filas
FROM historico_aba_macroactivos
GROUP BY tipo_id
ORDER BY filas DESC;
"""

# Clientes con ID no confiable en la tabla limpia
UNRELIABLE_IDS_SQL = """
SELECT
    COUNT(DISTINCT id_sistema_cliente) AS clientes,
    COUNT(*)                           AS filas
FROM macroactivos_limpio
WHERE NOT id_cliente_confiable;
"""

# Códigos de activo del archivo original que no están en el catálogo
OUT_OF_CATALOG_SQL = """
SELECT
    COALESCE(NULLIF(TRIM(h.cod_activo), ''), '(vacío)') AS cod_activo,
    COUNT(*) AS filas
FROM historico_aba_macroactivos h
LEFT JOIN catalogo_activos c ON c.cod_activo::TEXT = TRIM(h.cod_activo)
WHERE c.cod_activo IS NULL
GROUP BY 1
ORDER BY filas DESC;
"""

# Correcciones aplicadas en la limpieza y cuántas filas de la tabla limpia cambiaron
CORRECTIONS_SQL = """
SELECT 'Código 10007 cambiado a 1007 (Fiducuenta)' AS correccion, COUNT(*) AS filas
FROM macroactivos_limpio
WHERE cod_activo_origen = '10007'
UNION ALL
SELECT 'Catálogo: PFCEMARGOS de 1115 a 1015 (filas con 1015)', COUNT(*)
FROM macroactivos_limpio
WHERE cod_activo = 1015
UNION ALL
SELECT 'Macroactivo vacío llenado según el código de activo', COUNT(*)
FROM macroactivos_limpio l
JOIN historico_aba_macroactivos h ON h.id = l.id_origen
WHERE COALESCE(TRIM(h.macroactivo), '') IN ('', 'None', 'nan')
UNION ALL
SELECT 'Banca vacía llenada con la banca del cliente', COUNT(*)
FROM macroactivos_limpio l
JOIN historico_aba_macroactivos h ON h.id = l.id_origen
WHERE COALESCE(TRIM(h.cod_banca), '') IN ('', 'None', 'nan')
UNION ALL
SELECT 'Perfil vacío llenado con el del cliente o con 1466 (SIN DEFINIR)', COUNT(*)
FROM macroactivos_limpio l
JOIN historico_aba_macroactivos h ON h.id = l.id_origen
WHERE COALESCE(TRIM(h.cod_perfil_riesgo), '') IN ('', 'None', 'nan')
UNION ALL
SELECT 'Código de activo sin catálogo dejado en NULL (1022, None, vacío)', COUNT(*)
FROM macroactivos_limpio
WHERE cod_activo IS NULL;
"""
