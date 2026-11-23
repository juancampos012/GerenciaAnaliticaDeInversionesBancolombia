# Consultas de la página Modelo (usan sql/asset-risk.sql, sql/client-risk.sql y el notebook)

# ¿Ya existe la tabla de segmentos que guarda el notebook?
SEGMENTS_TABLE_EXISTS_SQL = "SELECT to_regclass('public.segmentos_clientes') IS NOT NULL AS existe"

# Riesgo de cada cliente con su segmento
MODEL_CLIENTS_SQL = """
SELECT r.*, s.segmento, s.nombre_segmento
FROM riesgo_clientes r
LEFT JOIN segmentos_clientes s ON s.id_sistema_cliente = r.id_sistema_cliente
ORDER BY r.aba_cop DESC
"""

# Riesgo de cada cliente sin segmentos (cuando el notebook no se ha ejecutado)
MODEL_CLIENTS_NO_SEGMENTS_SQL = """
SELECT r.*, NULL AS segmento, NULL AS nombre_segmento
FROM riesgo_clientes r
ORDER BY r.aba_cop DESC
"""

# Perfil de cada segmento
SEGMENTS_SQL = """
SELECT
    s.segmento,
    s.nombre_segmento,
    COUNT(*) AS clientes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.aba_cop) AS aba_cop_mediana,
    ROUND(AVG(r.pct_renta_variable), 2) AS pct_renta_variable,
    ROUND(AVG(r.pct_renta_fija), 2) AS pct_renta_fija,
    ROUND(AVG(r.pct_fics), 2) AS pct_fics,
    ROUND(AVG(r.puntaje_cop), 2) AS puntaje_cop,
    COUNT(r.valor_usd) AS clientes_usd,
    ROUND(AVG(r.puntaje_usd), 2) AS puntaje_usd
FROM segmentos_clientes s
JOIN riesgo_clientes r ON r.id_sistema_cliente = s.id_sistema_cliente
GROUP BY s.segmento, s.nombre_segmento
ORDER BY s.segmento
"""

# Perfil declarado frente al nivel real del portafolio COP
PROFILE_VS_LEVEL_SQL = """
SELECT
    perfil_riesgo,
    COUNT(*) FILTER (WHERE nivel_cop = 'bajo') AS bajo,
    COUNT(*) FILTER (WHERE nivel_cop = 'medio') AS medio,
    COUNT(*) FILTER (WHERE nivel_cop = 'alto') AS alto,
    COUNT(*) AS total
FROM riesgo_clientes
GROUP BY perfil_riesgo
ORDER BY perfil_riesgo
"""

# Tabla de referencia de riesgo por activo
ASSET_RISK_SQL = """
SELECT moneda, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente
FROM activos_riesgo
ORDER BY moneda, puntaje_riesgo DESC, tipo_activo, nombre
"""
