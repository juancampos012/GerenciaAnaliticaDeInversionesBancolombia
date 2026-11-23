# Queries SQL que usa la página de portafolio

# Lista de clientes de los dos históricos limpios.
# confiable = FALSE si el ID venía en notación científica.
CLIENTS_SQL = """
SELECT
    id_sistema_cliente,
    id_sistema_cliente ~ '^[0-9]+$' AS confiable
FROM (
    SELECT id_sistema_cliente FROM macroactivos_limpio
    UNION
    SELECT id_sistema_cliente FROM usd_internacional_limpio
) AS clientes
ORDER BY confiable DESC, id_sistema_cliente;
"""

# Portafolio local (COP) del cliente en su última fecha disponible
COP_PORTFOLIO_SQL = """
SELECT
    m.fecha_ingesta,
    m.macroactivo,
    COALESCE(a.activo, 'Sin catálogo (' || COALESCE(m.cod_activo_origen, 'sin código') || ')') AS activo,
    m.aba,
    b.banca,
    p.perfil_riesgo
FROM macroactivos_limpio m
LEFT JOIN catalogo_activos  a ON a.cod_activo = m.cod_activo
LEFT JOIN catalogo_banca    b ON b.cod_banca = m.cod_banca
LEFT JOIN cat_perfil_riesgo p ON p.cod_perfil_riesgo = m.cod_perfil_riesgo
WHERE m.id_sistema_cliente = %s
  AND m.fecha_ingesta = (
      SELECT MAX(fecha_ingesta)
      FROM macroactivos_limpio
      WHERE id_sistema_cliente = %s
  )
ORDER BY m.aba DESC;
"""

# Portafolio internacional (USD) del cliente en su última fecha disponible
USD_PORTFOLIO_SQL = """
SELECT
    fecha_ingesta,
    simbolo,
    isin,
    nombre_activo,
    cantidad,
    valor_mercado_usd
FROM usd_internacional_limpio
WHERE id_sistema_cliente = %s
  AND fecha_ingesta = (
      SELECT MAX(fecha_ingesta)
      FROM usd_internacional_limpio
      WHERE id_sistema_cliente = %s
  )
ORDER BY valor_mercado_usd DESC;
"""
