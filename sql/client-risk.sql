-- Borrar resultados de una ejecución anterior
DROP VIEW IF EXISTS riesgo_clientes;

-- Convierte un puntaje promedio (1 a 3) en el nivel más cercano
CREATE OR REPLACE FUNCTION nivel_por_puntaje(puntaje NUMERIC)
RETURNS VARCHAR AS $$
    SELECT CASE
        WHEN puntaje IS NULL THEN NULL
        WHEN puntaje < 1.5 THEN 'bajo'
        WHEN puntaje < 2.5 THEN 'medio'
        ELSE 'alto'
    END;
$$ LANGUAGE SQL IMMUTABLE;

-- Compara el nivel del portafolio con el perfil declarado (conservador = bajo, moderado = medio, agresivo = alto)
CREATE OR REPLACE FUNCTION comparar_con_perfil(nivel VARCHAR, perfil VARCHAR)
RETURNS VARCHAR AS $$
    SELECT CASE
        WHEN perfil IS NULL OR perfil = 'SIN DEFINIR' THEN 'Sin perfil para comparar'
        WHEN perfil LIKE '%,%' THEN 'Perfil no único'
        WHEN nivel IS NULL THEN 'Sin activos clasificados'
        WHEN (CASE nivel WHEN 'bajo' THEN 1 WHEN 'medio' THEN 2 ELSE 3 END)
           = (CASE perfil WHEN 'CONSERVADOR' THEN 1 WHEN 'MODERADO' THEN 2 ELSE 3 END) THEN 'Alineado'
        WHEN (CASE nivel WHEN 'bajo' THEN 1 WHEN 'medio' THEN 2 ELSE 3 END)
           > (CASE perfil WHEN 'CONSERVADOR' THEN 1 WHEN 'MODERADO' THEN 2 ELSE 3 END) THEN 'Más riesgo que su perfil'
        ELSE 'Menos riesgo que su perfil'
    END;
$$ LANGUAGE SQL IMMUTABLE;

-- Riesgo del portafolio de cada cliente en su última fecha disponible (COP y USD por separado, sin convertir)
CREATE VIEW riesgo_clientes AS
WITH ultima_cop AS (
    SELECT id_sistema_cliente, MAX(fecha_ingesta) AS fecha
    FROM macroactivos_limpio
    GROUP BY id_sistema_cliente
),
posiciones_cop AS (
    SELECT m.id_sistema_cliente, m.macroactivo, m.aba, m.cod_perfil_riesgo, m.cod_banca,
           m.id_cliente_confiable, r.puntaje_riesgo
    FROM macroactivos_limpio m
    JOIN ultima_cop u
      ON u.id_sistema_cliente = m.id_sistema_cliente
     AND u.fecha = m.fecha_ingesta
    LEFT JOIN activos_riesgo r
      ON r.moneda = 'COP'
     AND r.cod_activo = m.cod_activo
),
resumen_cop AS (
    SELECT
        p.id_sistema_cliente,
        BOOL_AND(p.id_cliente_confiable) AS id_confiable,
        STRING_AGG(DISTINCT c.perfil_riesgo, ', ') AS perfil_riesgo,
        STRING_AGG(DISTINCT b.banca, ', ') AS banca,
        SUM(p.aba) AS aba_cop,
        COUNT(*) AS activos_cop,
        ROUND(COALESCE(SUM(p.aba) FILTER (WHERE p.macroactivo = 'Renta Variable'), 0) / SUM(p.aba) * 100, 2) AS pct_renta_variable,
        ROUND(COALESCE(SUM(p.aba) FILTER (WHERE p.macroactivo = 'Renta Fija'), 0) / SUM(p.aba) * 100, 2) AS pct_renta_fija,
        ROUND(COALESCE(SUM(p.aba) FILTER (WHERE p.macroactivo = 'FICs'), 0) / SUM(p.aba) * 100, 2) AS pct_fics,
        ROUND(SUM(p.aba * p.puntaje_riesgo) / NULLIF(SUM(p.aba) FILTER (WHERE p.puntaje_riesgo IS NOT NULL), 0), 2) AS puntaje_cop,
        ROUND(COALESCE(SUM(p.aba) FILTER (WHERE p.puntaje_riesgo IS NULL), 0) / SUM(p.aba) * 100, 2) AS pct_sin_clasificar_cop
    FROM posiciones_cop p
    LEFT JOIN cat_perfil_riesgo c ON c.cod_perfil_riesgo = p.cod_perfil_riesgo
    LEFT JOIN catalogo_banca b ON b.cod_banca = p.cod_banca
    GROUP BY p.id_sistema_cliente
),
ultima_usd AS (
    SELECT id_sistema_cliente, MAX(fecha_ingesta) AS fecha
    FROM usd_internacional_limpio
    GROUP BY id_sistema_cliente
),
posiciones_usd AS (
    SELECT u.id_sistema_cliente, u.valor_mercado_usd, r.puntaje_riesgo
    FROM usd_internacional_limpio u
    JOIN ultima_usd f
      ON f.id_sistema_cliente = u.id_sistema_cliente
     AND f.fecha = u.fecha_ingesta
    LEFT JOIN activos_riesgo r
      ON r.moneda = 'USD'
     AND r.isin = u.isin
),
resumen_usd AS (
    SELECT
        id_sistema_cliente,
        SUM(valor_mercado_usd) AS valor_usd,
        COUNT(*) AS activos_usd,
        ROUND(SUM(valor_mercado_usd * puntaje_riesgo) / NULLIF(SUM(valor_mercado_usd) FILTER (WHERE puntaje_riesgo IS NOT NULL), 0), 2) AS puntaje_usd,
        ROUND(COALESCE(SUM(valor_mercado_usd) FILTER (WHERE puntaje_riesgo IS NULL), 0) / SUM(valor_mercado_usd) * 100, 2) AS pct_sin_clasificar_usd
    FROM posiciones_usd
    GROUP BY id_sistema_cliente
)
SELECT
    c.id_sistema_cliente,
    c.id_confiable,
    c.banca,
    c.perfil_riesgo,
    c.aba_cop,
    c.activos_cop,
    c.pct_renta_variable,
    c.pct_renta_fija,
    c.pct_fics,
    c.puntaje_cop,
    nivel_por_puntaje(c.puntaje_cop) AS nivel_cop,
    c.pct_sin_clasificar_cop,
    comparar_con_perfil(nivel_por_puntaje(c.puntaje_cop), c.perfil_riesgo) AS alineacion_cop,
    u.valor_usd,
    COALESCE(u.activos_usd, 0) AS activos_usd,
    u.puntaje_usd,
    nivel_por_puntaje(u.puntaje_usd) AS nivel_usd,
    u.pct_sin_clasificar_usd,
    CASE WHEN u.id_sistema_cliente IS NULL THEN 'Sin portafolio USD'
         ELSE comparar_con_perfil(nivel_por_puntaje(u.puntaje_usd), c.perfil_riesgo) END AS alineacion_usd
FROM resumen_cop c
LEFT JOIN resumen_usd u ON u.id_sistema_cliente = c.id_sistema_cliente;
