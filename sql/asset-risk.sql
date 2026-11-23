-- Borrar resultados de una ejecución anterior
DROP VIEW IF EXISTS riesgo_clientes;
DROP TABLE IF EXISTS activos_riesgo;

-- Convierte una volatilidad anual (%) en nivel de riesgo con las clases PRIIPs: bajo < 5, medio de 5 a menos de 20, alto 20 o más
CREATE OR REPLACE FUNCTION nivel_por_volatilidad(volatilidad NUMERIC)
RETURNS VARCHAR AS $$
    SELECT CASE
        WHEN volatilidad IS NULL THEN NULL
        WHEN volatilidad < 5 THEN 'bajo'
        WHEN volatilidad < 20 THEN 'medio'
        ELSE 'alto'
    END;
$$ LANGUAGE SQL IMMUTABLE;

-- Tabla de referencia: nivel de riesgo de cada activo y de dónde sale ese dato
CREATE TABLE activos_riesgo (
    id                SERIAL PRIMARY KEY,
    moneda            VARCHAR(3)   NOT NULL CHECK (moneda IN ('COP', 'USD')),
    cod_activo        INT          REFERENCES catalogo_activos (cod_activo),
    isin              VARCHAR(20),
    nombre            VARCHAR(120) NOT NULL,
    tipo_activo       VARCHAR(80)  NOT NULL,
    metodo            VARCHAR(80)  NOT NULL,
    volatilidad_anual NUMERIC(6, 2),
    nivel_riesgo      VARCHAR(5)   NOT NULL CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto')),
    puntaje_riesgo    SMALLINT GENERATED ALWAYS AS (
                          CASE nivel_riesgo WHEN 'bajo' THEN 1 WHEN 'medio' THEN 2 ELSE 3 END
                      ) STORED,
    referencia        TEXT         NOT NULL,
    fuente            TEXT         NOT NULL,
    UNIQUE (moneda, cod_activo),
    UNIQUE (isin)
);

-- FICs y CDT locales: perfil de riesgo publicado por la entidad
INSERT INTO activos_riesgo (moneda, cod_activo, nombre, tipo_activo, metodo, nivel_riesgo, referencia, fuente) VALUES
('COP', 1007, 'Fiducuenta', 'FIC de liquidez', 'Perfil publicado por la entidad', 'bajo',
 'Ficha técnica: instrumento de renta fija de baja duración con perfil de riesgo bajo',
 'https://im.sura-am.com/sites/default/files/2021-04/fondo-de-inversion-colectiva-abierto-fiducuenta.pdf'),
('COP', 1019, 'Renta Liquidez', 'FIC de liquidez', 'Perfil publicado por la entidad', 'bajo',
 'Bancolombia: instrumento de corto plazo y de riesgo conservador',
 'https://bancolombia.com/personas/productos-servicios/inversiones/fondos-inversion-colectiva'),
('COP', 1008, 'Fidurenta', 'FIC de renta fija', 'Perfil publicado por la entidad', 'medio',
 'FIC de renta fija para inversionistas con perfil de riesgo moderado',
 'https://finanzasplus.co/blog/que-es-la-fidurenta-de-bancolombia'),
('COP', 1018, 'Plan Semilla', 'FIC de renta fija', 'Perfil publicado por la entidad', 'medio',
 'FIC de renta fija de riesgo medio',
 'https://www.rankia.co/blog/fondos-inversion-colectiva-colombia/3716614-que-fondos-inversion-ofrece-bancolombia'),
('COP', 1020, 'Sura Credito Privado', 'FIC cerrado de crédito privado', 'Perfil publicado por la entidad', 'alto',
 'Prospecto: perfil de riesgo Alto',
 'https://im.sura-am.com/sites/default/files/2025-04/250422-Prospecto-FIC-SURA-CP-V.pdf'),
('COP', 1000, 'CDT BANCOLOMBIA B360', 'CDT', 'Perfil publicado por la entidad', 'bajo',
 'Depósito a plazo amparado por el seguro de depósitos de Fogafín (hasta $50 millones por persona y entidad)',
 'https://www.bancolombia.com/personas/productos-servicios/seguro-fogafin/'),
('COP', 1001, 'CDT TUYA TF B360', 'CDT', 'Perfil publicado por la entidad', 'bajo',
 'Depósito a plazo amparado por el seguro de depósitos de Fogafín (hasta $50 millones por persona y entidad)',
 'https://www.fogafin.gov.co/sites/default/files/2025-12/ABC%20del%20proceso%20de%20pago%20del%20seguro%20de%20dep%C3%B3sitos.pdf');

-- Acciones colombianas: volatilidad anual calculada con los datos diarios entregados
INSERT INTO activos_riesgo (moneda, cod_activo, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente)
WITH serie AS (
    SELECT
        cod_activo,
        aba,
        LAG(aba) OVER (PARTITION BY id_sistema_cliente, cod_activo ORDER BY fecha_ingesta) AS aba_anterior
    FROM macroactivos_limpio
    WHERE macroactivo = 'Renta Variable'
      AND cod_activo IS NOT NULL
),
retornos AS (
    SELECT cod_activo, LN(aba / aba_anterior) AS retorno
    FROM serie
    WHERE aba > 0 AND aba_anterior > 0
),
volatilidad AS (
    SELECT
        cod_activo,
        COUNT(*) AS retornos,
        ROUND((STDDEV_SAMP(retorno) * SQRT(252) * 100)::NUMERIC, 2) AS volatilidad_anual
    FROM retornos
    GROUP BY cod_activo
),
-- Promedio de las acciones con datos suficientes (mínimo 20 retornos diarios)
promedio AS (
    SELECT ROUND(AVG(volatilidad_anual), 2) AS volatilidad_anual
    FROM volatilidad
    WHERE retornos >= 20
)
SELECT
    'COP',
    v.cod_activo,
    a.activo,
    'Acción colombiana',
    CASE WHEN v.retornos >= 20 THEN 'Volatilidad calculada con los datos'
         ELSE 'Promedio de las acciones colombianas del archivo' END,
    CASE WHEN v.retornos >= 20 THEN v.volatilidad_anual ELSE p.volatilidad_anual END,
    nivel_por_volatilidad(CASE WHEN v.retornos >= 20 THEN v.volatilidad_anual ELSE p.volatilidad_anual END),
    CASE WHEN v.retornos >= 20 THEN v.retornos || ' retornos diarios del ABA, anualizados con raíz de 252'
         ELSE 'Solo ' || v.retornos || ' retornos diarios: se usa el promedio de las demás acciones' END,
    'Cálculo propio con historico_aba_macroactivos'
FROM volatilidad v
JOIN catalogo_activos a ON a.cod_activo = v.cod_activo
CROSS JOIN promedio p;

-- Liquidez en dólares: efectivo y fondo del mercado monetario de BNY Mellon
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, nivel_riesgo, referencia, fuente) VALUES
('USD', 'Liquidez', 'Efectivo y BNY Mellon US Dollar Liquidity Fund', 'Liquidez', 'Volatilidad de la clase de activo', 'bajo',
 'Fondo del mercado monetario con calificación AAAm de S&P (capacidad muy fuerte de mantener el capital)',
 'https://www.bny.com/investments/us/en/intermediary/products/nra-offshore/fund/bny-mellon-liquidity-funds-plc-bny-mellon-us-dollar-liquidity-fu.shareclass.Investor%20Shares.html');

-- Acciones individuales de EE.UU. y ADR: volatilidad típica de una acción del S&P 500
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente)
SELECT
    'USD', isin, nombre, 'Acción individual', 'Volatilidad de la clase de activo', 34.70, nivel_por_volatilidad(34.70),
    'VIX EQ (volatilidad implícita de las acciones del S&P 500): cerca de 34,7 desde 2021',
    'https://am.jpmorgan.com/us/en/asset-management/adv/insights/market-insights/market-updates/on-the-minds-of-investors/whats-happening-to-stocks-beneath-the-index'
FROM (VALUES
    ('US0079031078', 'ADVANCED MICRO DEVICES INC'),
    ('US02079K1079', 'ALPHABET INC CL C'),
    ('US0231351067', 'AMAZON COM INC'),
    ('US0378331005', 'APPLE INC'),
    ('US0846707026', 'BERKSHIRE HATHAWAY INC CL B'),
    ('US8522341036', 'BLOCK INC CL A'),
    ('US15961R1059', 'CHARGEPOINT HLDGS INC CL A'),
    ('US1729674242', 'CITIGROUP INC'),
    ('US2546871060', 'WALT DISNEY CO'),
    ('US5394391099', 'LLOYDS BANKING GROUP PLC ADR'),
    ('US30303M1027', 'META PLATFORMS INC CL A'),
    ('US64110L1061', 'NETFLIX INC'),
    ('US69608A1088', 'PALANTIR TECHNOLOGIES INC CL A'),
    ('US70450Y1038', 'PAYPAL HLDGS INC'),
    ('US71654V4086', 'PETROLEO BRASILEIRO SA ADR'),
    ('US74767V1098', 'QUANTUMSCAPE CORP CL A'),
    ('US83406F1021', 'SOFI TECHNOLOGIES INC')
) AS acciones (isin, nombre);

-- Notas estructuradas ligadas al peor de S&P 500, Nasdaq-100 y Dow Jones: se usa el índice más volátil
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente)
SELECT
    'USD', isin, nombre, 'Nota estructurada sobre índices de EE.UU.', 'Volatilidad de la clase de activo', 22.33, nivel_por_volatilidad(22.33),
    'Volatilidad anual del Nasdaq-100 desde 2006: 22,33% (índice más volátil de la canasta)',
    'https://devo.bnpparibas.com/pdfDocuments/nasdaq-100-futures-defined-vol-35-dec-6-index-product-card-us-11.pdf'
FROM (VALUES
    ('XS2673628587', 'BNP PARIBAS TWIN-WIN LKD TO INDU NDX SPX'),
    ('XS2506535900', 'BNP PARIBAS ISSUANCE LKD TO DJ INDUSTRIAL NASDAQ 100'),
    ('XS2484885491', 'BNP PARIBAS LNKD TO NDX SPX INDU'),
    ('XS2759143550', 'BNP PARIBAS MTN LKD TO INDU NDX SPX'),
    ('XS2565512410', 'CITIFIRST AUTOCALL LKD TO DJI NDX SPX'),
    ('CH1234256894', 'UBS AG LKD TO INDU SPX NDX'),
    ('CH1308762611', 'UBS AG LONDON LNKD TO SPX NDX INDU')
) AS notas (isin, nombre);

-- Bonos corporativos y bancarios de emisores latinoamericanos en dólares
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente)
SELECT
    'USD', isin, nombre, 'Bono corporativo de mercado emergente', 'Volatilidad de la clase de activo', 4.18, nivel_por_volatilidad(4.18),
    'Desviación estándar 3 años del iShares J.P. Morgan EM Corporate Bond ETF (CEMB): 4,18%',
    'https://www.ishares.com/us/products/239525/ishares-j-p-morgan-em-corporate-bond-etf-cemb'
FROM (VALUES
    ('USP09252AK62', 'BANCO DE BOGOTA 6.250% 2026'),
    ('USP1265VAD49', 'BANCO GNB SUDAMERIS 7.051% 2027'),
    ('USP1265VAH52', 'BANCO GNB SUDAMERIS 7.500% 2031'),
    ('XS2715165846', 'BANCOLOMBIA PANAMA 6.100% 2024'),
    ('XS2580672231', 'BANCOLOMBIA PANAMA 5.650% 2025'),
    ('XS2589907570', 'BANCOLOMBIA PUERTO RICO 5.500% 2025'),
    ('XS2729353438', 'BANISTMO 6.250% 06/04/2025'),
    ('XS2737008388', 'BANISTMO 6.250% 06/19/2025'),
    ('USP15383CD50', 'BANISTMO 4.250% 2027'),
    ('USP1850NAA92', 'BRASKEM IDESA 7.450% 2029'),
    ('USP28768AC69', 'COLOMBIA TELECOMUNICACIONES 4.950% 2030'),
    ('US279158AS81', 'ECOPETROL 8.875% 2033'),
    ('USP9379RBC09', 'EMPRESAS PUBLICAS DE MEDELLIN 4.375% 2031'),
    ('USP9810XAA92', 'VTR COMUNICACIONES 5.125% 2028')
) AS bonos (isin, nombre);

-- Bono de gobierno subnacional (Bogotá D.C.)
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente) VALUES
('USD', 'USP17460AB56', 'BOGOTA DISTRITO CAPITAL 9.750% 2028', 'Bono de gobierno de mercado emergente', 'Volatilidad de la clase de activo',
 6.97, nivel_por_volatilidad(6.97),
 'Desviación estándar 3 años del iShares J.P. Morgan USD Emerging Markets Bond ETF (EMB): 6,97%',
 'https://www.ishares.com/uk/professionals/en/products/239572');

-- Notas del Tesoro de EE.UU. con vencimiento entre 2025 y 2026
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente)
SELECT
    'USD', isin, nombre, 'Tesoro de EE.UU. de corto plazo', 'Volatilidad de la clase de activo', 1.39, nivel_por_volatilidad(1.39),
    'Volatilidad anual del Vanguard Short-Term Treasury ETF (VGSH, Tesoros de 1 a 3 años): 1,39%',
    'https://seekingalpha.com/symbol/VGSH/risk'
FROM (VALUES
    ('US91282CDZ14', 'US TREASURY 1.500% 02/15/2025'),
    ('US912828P469', 'US TREASURY 1.625% 02/15/2026'),
    ('US91282CED92', 'US TREASURY 1.750% 03/15/2025'),
    ('US91282CGU99', 'US TREASURY 3.875% 03/31/2025'),
    ('US91282CJK80', 'US TREASURY 4.625% 11/15/2026'),
    ('US91282CJE21', 'US TREASURY 5.000% 10/31/2025')
) AS tesoros (isin, nombre);

-- Fondos y ETF internacionales: volatilidad publicada de cada fondo
INSERT INTO activos_riesgo (moneda, isin, nombre, tipo_activo, metodo, volatilidad_anual, nivel_riesgo, referencia, fuente)
SELECT
    'USD', isin, nombre, tipo_activo, 'Volatilidad publicada del fondo', volatilidad, nivel_por_volatilidad(volatilidad), referencia, fuente
FROM (VALUES
    ('LU1196525536', 'BGF CONTINENTAL EUROPEAN FLEXIBLE A2 HEDGED USD', 'Fondo de acciones', 14.47,
     'BlackRock: desviación estándar 3 años 14,47%',
     'https://www.blackrock.com/ae/intermediaries/products/272568/'),
    ('LU0278466700', 'BGF FIXED INCOME GLOBAL OPPORTUNITIES A2 USD', 'Fondo de renta fija', 3.78,
     'BlackRock: desviación estándar 3 años 3,78%',
     'https://www.blackrock.com/lu/individual/products/228362/blackrock-fixed-income-global-opp-a2-usd-fund'),
    ('LU0072462426', 'BGF GLOBAL ALLOCATION A2 USD', 'Fondo multiactivo', 9.49,
     'Volatilidad 3 años 9,49%',
     'https://www.easybank.at/markets/fonds/FU_987142/BGF-Global-Allocation-Fund-A2-USD/profile-kennzahlen'),
    ('LU0784385840', 'BGF GLOBAL MULTI-ASSET INCOME A2 USD', 'Fondo multiactivo', 6.46,
     'BlackRock: desviación estándar 3 años 6,46%',
     'https://www.blackrock.com/uk/intermediaries/products/230304/blackrock-global-multi-asset-income-a2-usd-fund'),
    ('LU0154237225', 'BGF USD SHORT DURATION BOND A2', 'Fondo de renta fija', 1.78,
     'BlackRock: desviación estándar 3 años 1,78%',
     'https://www.blackrock.com/fi/individual/products/228575'),
    ('LU1298145357', 'BLACKROCK MANAGED INDEX PORTFOLIOS GROWTH A2 HEDGED USD', 'Fondo multiactivo', 11.34,
     'BlackRock: desviación estándar 3 años 11,34% (clase I2 del mismo fondo)',
     'https://www.blackrock.com/lu/individual/products/316215/'),
    ('LU1298143493', 'BLACKROCK MANAGED INDEX PORTFOLIOS MODERATE A2 HEDGED USD', 'Fondo multiactivo', 7.01,
     'BlackRock: desviación estándar 3 años 7,01% (clase D2 cubierta en USD del mismo fondo)',
     'https://www.blackrock.com/lu/individual/products/277540/'),
    ('LU0109392836', 'FRANKLIN TECHNOLOGY FUND A ACC USD', 'Fondo de acciones', 27.93,
     'Volatilidad publicada 27,93%',
     'https://www.easybank.at/markets/fonds/FU_937446/Franklin-Technology-Fund-A-acc-USD/risikomatrix'),
    ('LU0109391861', 'FRANKLIN U.S. OPPORTUNITIES FUND A ACC USD', 'Fondo de acciones', 19.58,
     'Volatilidad 3 años 19,58%',
     'https://markets.easybank.at/markets/fonds/FU_937448/Franklin-U-S-Opportunities-Fund-A-acc-USD/profile-kennzahlen'),
    ('IE00BBT3JP45', 'FTGF BRANDYWINE GLOBAL INCOME OPTIMISER A ACC USD', 'Fondo de renta fija', 6.85,
     'Franklin Templeton: desviación estándar 5 años 6,85% (clase A EUR cubierta del mismo fondo)',
     'https://www.franklintempletonme.com/download/gem/factsheet/303ca2f2-1bad-4cbf-85ee-4fbbc15ed68f/Factsheet-FTGFBrandywineGlobalIncomeOptimiserFund-AEURACCH-91037-Z9-FF-LU-en-GB.PDF'),
    ('IE00BD4GTV84', 'FTGF CLEARBRIDGE INFRASTRUCTURE VALUE A HEDGED ACC USD', 'Fondo de acciones', 12.42,
     'Volatilidad publicada 12,42%',
     'https://www.easybank.at/markets/fonds/FU_100055798/Franklin-Templeton-Global-Funds-plc-FTGF-ClearBridge-Infrastructure-Value-Fund-Klasse-A-USD-ACC-H/risikomatrix'),
    ('LU1041599405', 'JPMORGAN INCOME FUND A ACC USD', 'Fondo de renta fija', 2.22,
     'Volatilidad 3 años 2,22%',
     'https://www.onvista.de/fonds/JP-Morgan-Income-Fund-A-USD-Acc-Fonds-LU1041599405'),
    ('LU0292454872', 'JPMORGAN U.S. SELECT EQUITY PLUS A ACC USD', 'Fondo de acciones', 15.28,
     'Volatilidad 3 años 15,28%',
     'https://www.easybank.at/markets/fonds/FU_100017059/JPMorgan-Funds-US-Select-Equity-Plus-Fund-A-acc-USD/profile-kennzahlen'),
    ('LU0426412945', 'NINETY ONE GSF GLOBAL FRANCHISE A ACC USD', 'Fondo de acciones', 19.40,
     'Ninety One: volatilidad anualizada 19,4% (clase I del mismo fondo; KID SRI 4 de 7)',
     'https://wealth.momentum.co.za/investments/factsheets/ninety-one-global-strategy-fund-global-franchise-i-acc,-accumulating.pdf'),
    ('LU0972617095', 'NINETY ONE GSF GLOBAL MULTI-ASSET INCOME A ACC USD', 'Fondo multiactivo', 5.10,
     'Ninety One: volatilidad anualizada 3 años 5,1%',
     'https://app.allfunds.com/docs/fund_info/document/e9517c1af7d6ec5444c56938901c2897_113758/MR_ES_es_LU0972617095_YES_2024-03-31.pdf'),
    ('LU2114231884', 'NINETY ONE GSF GLOBAL MULTI-ASSET INCOME A INC USD', 'Fondo multiactivo', 5.10,
     'Ninety One: volatilidad anualizada 3 años 5,1% (clase A Acc del mismo fondo)',
     'https://app.allfunds.com/docs/fund_info/document/e9517c1af7d6ec5444c56938901c2897_113758/MR_ES_es_LU0972617095_YES_2024-03-31.pdf'),
    ('IE00B7KFL990', 'PIMCO GIS INCOME FUND E ACC USD', 'Fondo de renta fija', 6.37,
     'Volatilidad 3 años 6,37%',
     'https://www.finanzen.net/fonds/volatilitaet/pimco-gis-income-fund-e-class-ie00b7kfl990'),
    ('LU0133713346', 'SCHRODER ISF ASIAN OPPORTUNITIES A1 ACC USD', 'Fondo de acciones', 16.20,
     'Schroders: volatilidad anual 3 años 16,2% (clase A1 EUR del mismo fondo)',
     'https://finanzfluss.de/document/LU0248179623/en/factsheet'),
    ('LU0181495838', 'SCHRODER ISF EMERGING ASIA A ACC USD', 'Fondo de acciones', 19.20,
     'Schroders: volatilidad anual 3 años 19,2%',
     'https://api.schroders.com/document-store/SISF-Emerging-Asia-A-Acc-FMR-LUEN.pdf'),
    ('LU0557290698', 'SCHRODER ISF GLOBAL SUSTAINABLE GROWTH A ACC USD', 'Fondo de acciones', 15.50,
     'Volatilidad 3 años 15,50%',
     'https://markets.easybank.at/markets/fonds/FU_100030878/Schroder-International-Selection-Fund-Global-Sustainable-Growth-A-Accumulation-USD/profile-kennzahlen'),
    ('IE00BP3QZ601', 'ISHARES EDGE MSCI WORLD QUALITY FACTOR UCITS ETF', 'ETF de acciones', 12.09,
     'iShares: desviación estándar 3 años 12,09%',
     'https://www.blackrock.com/lu/intermediaries/products/270054/ishares-msci-world-quality-factor-ucits-etf'),
    ('IE00BYXYYP94', 'ISHARES USD SHORT DURATION CORP BOND UCITS ETF', 'ETF de renta fija', 1.90,
     'iShares: desviación estándar 3 años 1,90% (clase de distribución del mismo fondo)',
     'https://www.blackrock.com/lu/individual/products/258126/ishares-short-duration-corporate-bond-ucits-etf'),
    ('IE00B43HR379', 'ISHARES S&P 500 HEALTH CARE SECTOR UCITS ETF', 'ETF de acciones', 14.07,
     'iShares: desviación estándar 3 años 14,07%',
     'https://www.blackrock.com/uk/intermediaries/products/280507/'),
    ('IE00B3VWN518', 'ISHARES USD TREASURY BOND 7-10YR UCITS ETF', 'ETF de renta fija', 6.58,
     'iShares: desviación estándar 3 años 6,58% (clase de distribución del mismo fondo)',
     'https://www.ishares.com/uk/professionals/en/products/251716/ishares-treasury-bond-7-10yr-ucits-etf'),
    ('IE00B3VWN393', 'ISHARES USD TREASURY BOND 3-7YR UCITS ETF', 'ETF de renta fija', 4.11,
     'iShares: desviación estándar 3 años 4,11%',
     'https://www.ishares.com/uk/institutional/en/products/253744/ishares-treasury-bond-3-7yr-ucits-etf'),
    ('US4642872349', 'ISHARES MSCI EMERGING MARKETS ETF (EEM)', 'ETF de acciones', 16.33,
     'iShares: desviación estándar 3 años 16,33%',
     'https://www.blackrock.com/us/financial-professionals/products/239637/'),
    ('US81369Y6059', 'FINANCIAL SELECT SECTOR SPDR (XLF)', 'ETF de acciones', 20.60,
     'Desviación estándar 3 años 20,6% (febrero 2024)',
     'https://www.thestreet.com/r/ratings/reports/summary/XLF.html'),
    ('US81369Y1001', 'MATERIALS SELECT SECTOR SPDR (XLB)', 'ETF de acciones', 20.67,
     'Volatilidad anualizada 20,67%',
     'https://seekingalpha.com/symbol/XLB/risk'),
    ('US9220428745', 'VANGUARD FTSE EUROPE ETF (VGK)', 'ETF de acciones', 15.44,
     'Desviación estándar 15,44',
     'https://weissratings.com/en/etf/vgk-nyse-arca/comparison'),
    ('US92206C1027', 'VANGUARD SHORT-TERM TREASURY ETF (VGSH)', 'ETF de renta fija', 1.39,
     'Volatilidad anualizada 1,39%',
     'https://seekingalpha.com/symbol/VGSH/risk'),
    ('US25459W4583', 'DIREXION DAILY SEMICONDUCTOR BULL 3X (SOXL)', 'ETF apalancado', 117.01,
     'Volatilidad anualizada 117,01% (ETF apalancado 3 veces)',
     'https://seekingalpha.com/symbol/SOXL/risk')
) AS fondos (isin, nombre, tipo_activo, volatilidad, referencia, fuente);
