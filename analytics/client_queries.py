# Queries SQL que usan la ficha del cliente, el rebalanceo y los precios de mercado

# Riesgo y alineación de todos los clientes (vista de sql/client-risk.sql)
RISK_CLIENTS_SQL = """
SELECT *
FROM riesgo_clientes
ORDER BY id_confiable DESC, id_sistema_cliente;
"""

# Riesgo y alineación de un cliente
RISK_CLIENT_SQL = """
SELECT *
FROM riesgo_clientes
WHERE id_sistema_cliente = %s;
"""

# Segmento del cliente (tabla que crea el notebook)
CLIENT_SEGMENT_SQL = """
SELECT segmento, nombre_segmento
FROM segmentos_clientes
WHERE id_sistema_cliente = %s;
"""

# Revisa si el notebook ya creó la tabla de segmentos
SEGMENTS_TABLE_EXISTS_SQL = """
SELECT to_regclass('segmentos_clientes') IS NOT NULL AS existe;
"""

# Posiciones COP de cada cliente en su última fecha, con el nivel de riesgo del activo
COP_POSITIONS_SQL = """
SELECT
    m.id_sistema_cliente,
    m.fecha_ingesta,
    m.macroactivo,
    m.cod_activo,
    COALESCE(a.activo, 'Sin catálogo (' || COALESCE(m.cod_activo_origen, 'sin código') || ')') AS activo,
    m.aba AS valor,
    r.nivel_riesgo,
    r.puntaje_riesgo
FROM macroactivos_limpio m
JOIN (
    SELECT id_sistema_cliente, MAX(fecha_ingesta) AS fecha
    FROM macroactivos_limpio
    GROUP BY id_sistema_cliente
) u ON u.id_sistema_cliente = m.id_sistema_cliente AND u.fecha = m.fecha_ingesta
LEFT JOIN catalogo_activos a ON a.cod_activo = m.cod_activo
LEFT JOIN activos_riesgo r ON r.moneda = 'COP' AND r.cod_activo = m.cod_activo
ORDER BY m.id_sistema_cliente, m.aba DESC;
"""

# Posiciones USD de cada cliente en su última fecha, con el nivel de riesgo del activo
USD_POSITIONS_SQL = """
SELECT
    u.id_sistema_cliente,
    u.fecha_ingesta,
    u.simbolo,
    u.isin,
    u.nombre_activo AS activo,
    u.cantidad,
    u.valor_mercado_usd AS valor,
    r.tipo_activo,
    r.nivel_riesgo,
    r.puntaje_riesgo
FROM usd_internacional_limpio u
JOIN (
    SELECT id_sistema_cliente, MAX(fecha_ingesta) AS fecha
    FROM usd_internacional_limpio
    GROUP BY id_sistema_cliente
) f ON f.id_sistema_cliente = u.id_sistema_cliente AND f.fecha = u.fecha_ingesta
LEFT JOIN activos_riesgo r ON r.moneda = 'USD' AND r.isin = u.isin
ORDER BY u.id_sistema_cliente, u.valor_mercado_usd DESC;
"""

# Activos de la tabla de referencia con su nivel, para sugerir destinos del rebalanceo
ASSETS_BY_LEVEL_SQL = """
SELECT moneda, nivel_riesgo, nombre, tipo_activo
FROM activos_riesgo
ORDER BY moneda, nivel_riesgo, nombre;
"""

# Última fecha de los datos USD (para comparar la TRM)
LAST_USD_DATE_SQL = """
SELECT MAX(fecha_ingesta) AS fecha
FROM usd_internacional_limpio;
"""
