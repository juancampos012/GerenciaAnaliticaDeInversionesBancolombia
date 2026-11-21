-- Borrar resultados de una ejecución anterior
DROP TABLE IF EXISTS macroactivos_limpio, macroactivos_rechazados,
                     usd_internacional_limpio, usd_internacional_rechazados CASCADE;

-- Quita espacios y convierte '', 'None' y 'nan' en NULL
CREATE OR REPLACE FUNCTION limpiar_texto(valor TEXT)
RETURNS TEXT AS $$
    SELECT CASE
        WHEN TRIM(valor) IN ('', 'None', 'nan', 'NaN') THEN NULL
        ELSE TRIM(valor)
    END;
$$ LANGUAGE SQL IMMUTABLE;

-- Devuelve TRUE si el texto es un número,
CREATE OR REPLACE FUNCTION es_numero(valor TEXT)
RETURNS BOOLEAN AS $$
    SELECT valor ~ '^-?[0-9]+(\.[0-9]+)?$';
$$ LANGUAGE SQL IMMUTABLE;

-- Supuesto PFCEMARGOS tiene el código 1115, pero en los históricos aparece como 1015 y siempre Renta Variable .
UPDATE catalogo_activos SET cod_activo = 1015 WHERE cod_activo = 1115;

-- Normalizar textos y quitar filas exactamente repetidas id_origen guarda el id de la tabla original.
DROP TABLE IF EXISTS macro_base;

CREATE TEMP TABLE macro_base AS
SELECT
    MIN(id) AS id_origen,
    ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, macroactivo,
    cod_activo, aba, cod_perfil_riesgo, cod_banca, year, month
FROM (
    SELECT
        id,
        limpiar_texto(ingestion_year)     AS ingestion_year,
        limpiar_texto(ingestion_month)    AS ingestion_month,
        limpiar_texto(ingestion_day)      AS ingestion_day,
        limpiar_texto(id_sistema_cliente) AS id_sistema_cliente,
        limpiar_texto(macroactivo)        AS macroactivo,
        limpiar_texto(cod_activo)         AS cod_activo,
        limpiar_texto(aba)                AS aba,
        limpiar_texto(cod_perfil_riesgo)  AS cod_perfil_riesgo,
        UPPER(limpiar_texto(cod_banca))   AS cod_banca,
        limpiar_texto(year)               AS year,
        limpiar_texto(month)              AS month
    FROM historico_aba_macroactivos
) AS normalizado
GROUP BY ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, macroactivo,
         cod_activo, aba, cod_perfil_riesgo, cod_banca, year, month;

-- Revisar cada fila y anotar el motivo de rechazo (NULL = fila válida)
DROP TABLE IF EXISTS macro_revisado;

CREATE TEMP TABLE macro_revisado AS
SELECT
    b.*,
    CASE
        -- Valores que quedaron en la columna equivocada
        WHEN b.year IS NULL
          OR b.year NOT IN ('2023', '2024')
          OR b.month IS NULL
          OR b.month !~ '^([1-9]|1[0-2])$'
          OR b.ingestion_day !~ '^([1-9]|[12][0-9]|3[01])$'
          OR b.macroactivo NOT IN ('Renta Variable', 'Renta Fija', 'FICs')
          OR NOT es_numero(b.aba)
          OR b.cod_banca NOT IN (SELECT cod_banca FROM catalogo_banca)
          OR b.cod_perfil_riesgo NOT IN (SELECT cod_perfil_riesgo::TEXT FROM cat_perfil_riesgo)
            THEN 'Columnas corridas'

        -- Sin ID, o un ID incompleto como '100'
        WHEN b.id_sistema_cliente IS NULL
          OR NOT (b.id_sistema_cliente ~ '^[0-9]{10,11}$'
               OR b.id_sistema_cliente ~ '^[0-9.]+E\+[0-9]+$')
            THEN 'Cliente sin identificar'

        WHEN b.aba IS NULL
            THEN 'Sin valor de ABA'

        WHEN b.ingestion_year IS NULL
          OR b.ingestion_month IS NULL
          OR b.ingestion_day IS NULL
            THEN 'Fecha de ingesta incompleta'
    END AS motivo_rechazo
FROM macro_base b;

-- Filas rechazadas
CREATE TABLE macroactivos_rechazados AS
SELECT *
FROM macro_revisado
WHERE motivo_rechazo IS NOT NULL;

-- Tabla limpia
CREATE TABLE macroactivos_limpio (
    id_origen            BIGINT PRIMARY KEY,
    fecha_ingesta        DATE         NOT NULL,
    anio                 INT          NOT NULL,
    mes                  INT          NOT NULL,
    fecha_corte          DATE         NOT NULL, 
    id_sistema_cliente   VARCHAR(30)  NOT NULL,
    id_cliente_confiable BOOLEAN      NOT NULL,   
    macroactivo          VARCHAR(30)  NOT NULL,
    cod_activo           INT REFERENCES catalogo_activos(cod_activo),
    cod_activo_origen    VARCHAR(30),             
    aba                  NUMERIC(20,2) NOT NULL,
    cod_perfil_riesgo    INT REFERENCES cat_perfil_riesgo(cod_perfil_riesgo),
    cod_banca            VARCHAR(5) REFERENCES catalogo_banca(cod_banca)
);

INSERT INTO macroactivos_limpio (
    id_origen, fecha_ingesta, anio, mes, fecha_corte, id_sistema_cliente, id_cliente_confiable,
    macroactivo, cod_activo, cod_activo_origen, aba, cod_perfil_riesgo, cod_banca
)
WITH validas AS (
    SELECT *
    FROM macro_revisado
    WHERE motivo_rechazo IS NULL
),

-- Macroactivo de cada código de activo, según el resto de los datos.
-- Sirve para llenar las filas que traen el macroactivo vacío.
macro_por_activo AS (
    SELECT cod_activo, MIN(macroactivo) AS macroactivo
    FROM validas
    WHERE cod_activo IS NOT NULL
      AND macroactivo IS NOT NULL
    GROUP BY cod_activo
    HAVING COUNT(DISTINCT macroactivo) = 1
),

-- Banca y perfil de cada cliente, solo si el cliente tiene un único valor.
-- Sirve para llenar las filas que traen esos campos vacíos.
datos_cliente AS (
    SELECT
        id_sistema_cliente,
        CASE WHEN COUNT(DISTINCT cod_banca) = 1 THEN MIN(cod_banca) END                 AS cod_banca,
        CASE WHEN COUNT(DISTINCT cod_perfil_riesgo) = 1 THEN MIN(cod_perfil_riesgo) END AS cod_perfil_riesgo
    FROM validas
    GROUP BY id_sistema_cliente
),

transformado AS (
    SELECT
        v.id_origen,
        MAKE_DATE(v.ingestion_year::INT,
                  v.ingestion_month::INT,
                  v.ingestion_day::INT)              AS fecha_ingesta,
        v.year::INT                                  AS anio,
        v.month::INT                                 AS mes,
        MAKE_DATE(v.year::INT, v.month::INT, 1)      AS fecha_corte,
        CASE
            -- Supuesto: 1002203023 es 10020203023 sin un 0. Es una sola fila,
            -- del mismo producto, banca y perfil, y llena un día que le falta a ese cliente.
            WHEN v.id_sistema_cliente = '1002203023' THEN '10020203023'
            ELSE v.id_sistema_cliente
        END                                          AS id_sistema_cliente,
        v.id_sistema_cliente ~ '^[0-9]+$'            AS id_cliente_confiable,
        COALESCE(v.macroactivo, m.macroactivo)       AS macroactivo,
        CASE
            -- Supuesto: 10007 es 1007 (Fiducuenta) con un 0 de más; siempre es FICs
            WHEN v.cod_activo = '10007' THEN 1007
            -- Código que sí existe en el catálogo
            WHEN v.cod_activo IN (SELECT cod_activo::TEXT FROM catalogo_activos) THEN v.cod_activo::INT
            -- 1022, 'None' y vacíos quedan en NULL
        END                                          AS cod_activo,
        v.cod_activo                                 AS cod_activo_origen,
        v.aba::NUMERIC                               AS aba,
        -- Si el cliente no tiene perfil, se usa 1466 (SIN DEFINIR)
        COALESCE(v.cod_perfil_riesgo, c.cod_perfil_riesgo, '1466')::INT AS cod_perfil_riesgo,
        COALESCE(v.cod_banca, c.cod_banca)           AS cod_banca
    FROM validas v
    LEFT JOIN macro_por_activo m ON m.cod_activo = v.cod_activo
    LEFT JOIN datos_cliente c    ON c.id_sistema_cliente = v.id_sistema_cliente
),

-- Si después de llenar vacíos quedan dos filas del mismo cliente, activo y día,
-- se deja solo una (la primera que aparece en el archivo).
sin_repetidos AS (
    SELECT
        t.*,
        ROW_NUMBER() OVER (
            PARTITION BY id_sistema_cliente, macroactivo, cod_activo_origen, fecha_ingesta
            ORDER BY id_origen
        ) AS fila
    FROM transformado t
)

SELECT
    id_origen, fecha_ingesta, anio, mes, fecha_corte, id_sistema_cliente, id_cliente_confiable,
    macroactivo, cod_activo, cod_activo_origen, aba, cod_perfil_riesgo, cod_banca
FROM sin_repetidos
WHERE fila = 1;

-- USD INTERNACIONAL
-- Normalizar textos y quitar filas exactamente repetidas
DROP TABLE IF EXISTS usd_base;

CREATE TEMP TABLE usd_base AS
SELECT
    MIN(id) AS id_origen,
    ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, simbol, cusip,
    isin, nombre_activo, cantidad, valor_mercado, fecha_vencimiento, tasa_cupon
FROM (
    SELECT
        id,
        limpiar_texto(ingestion_year)     AS ingestion_year,
        limpiar_texto(ingestion_month)    AS ingestion_month,
        limpiar_texto(ingestion_day)      AS ingestion_day,
        limpiar_texto(id_sistema_cliente) AS id_sistema_cliente,
        limpiar_texto(simbol)             AS simbol,
        limpiar_texto(cusip)              AS cusip,
        limpiar_texto(isin)               AS isin,
        limpiar_texto(nombre_activo)      AS nombre_activo,
        limpiar_texto(cantidad)           AS cantidad,
        limpiar_texto(valor_mercado)      AS valor_mercado,
        limpiar_texto(fecha_vencimiento)  AS fecha_vencimiento,
        limpiar_texto(tasa_cupon)         AS tasa_cupon
    FROM historico_aba_usd_internacional
) AS normalizado
GROUP BY ingestion_year, ingestion_month, ingestion_day, id_sistema_cliente, simbol, cusip,
         isin, nombre_activo, cantidad, valor_mercado, fecha_vencimiento, tasa_cupon;

-- Revisar cada fila y anotar el motivo de rechazo (NULL = fila válida)
DROP TABLE IF EXISTS usd_revisado;

CREATE TEMP TABLE usd_revisado AS
SELECT
    b.*,
    CASE
        WHEN b.cantidad IS NULL
          OR NOT es_numero(b.cantidad)
          OR b.valor_mercado IS NULL
          OR NOT es_numero(b.valor_mercado)
          OR b.tasa_cupon IS NULL
          OR NOT es_numero(b.tasa_cupon)
          OR b.fecha_vencimiento !~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
            THEN 'Columnas corridas'
    END AS motivo_rechazo
FROM usd_base b;

-- Filas rechazadas
CREATE TABLE usd_internacional_rechazados AS
SELECT *
FROM usd_revisado
WHERE motivo_rechazo IS NOT NULL;

-- Tabla limpia
CREATE TABLE usd_internacional_limpio (
    id_origen          BIGINT PRIMARY KEY,
    fecha_ingesta      DATE          NOT NULL,
    fecha_corte        DATE          NOT NULL,   
    id_sistema_cliente VARCHAR(30)   NOT NULL,
    simbolo            VARCHAR(30),
    cusip              VARCHAR(30),
    isin               VARCHAR(30),
    nombre_activo      VARCHAR(300)  NOT NULL,
    cantidad           NUMERIC(24,6) NOT NULL,
    valor_mercado_usd  NUMERIC(24,2) NOT NULL,   -- puede ser negativo en CASH (saldo en contra)
    fecha_vencimiento  VARCHAR(20),
    tasa_cupon         NUMERIC(12,6)
);

INSERT INTO usd_internacional_limpio
SELECT
    id_origen,
    MAKE_DATE(ingestion_year::INT, ingestion_month::INT, ingestion_day::INT) AS fecha_ingesta,
    MAKE_DATE(ingestion_year::INT, ingestion_month::INT, 1)                  AS fecha_corte,
    id_sistema_cliente,
    simbol AS simbolo,
    cusip,
    isin,
    nombre_activo,
    cantidad::NUMERIC,
    valor_mercado::NUMERIC,
    fecha_vencimiento,
    tasa_cupon::NUMERIC
FROM usd_revisado
WHERE motivo_rechazo IS NULL;


-- Borrar tablas temporales
DROP TABLE IF EXISTS macro_base, macro_revisado, usd_base, usd_revisado;