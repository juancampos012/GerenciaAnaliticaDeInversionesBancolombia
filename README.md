# Gerencia Analítica de Inversiones Bancolombia

Prueba técnica para aprendiz de la Gerencia Analítica de Inversiones.

El proyecto carga los históricos de portafolio en PostgreSQL, los limpia con SQL y los muestra en una aplicación web en Django. Además incluye un modelo de riesgo y segmentación de clientes, y funcionalidades adicionales: ficha del cliente, rebalanceo y precios de mercado.

| Paso | Qué se hizo | Dónde |
|---|---|---|
| 1 | Crear la base de datos y cargar los CSV | `create-db.py`, `load-data.py` |
| 2 | Limpiar y validar los datos | `sql/clear.sql`, `sql/consultas.sql` |
| 3 | Aplicación web con gráficas | `config/`, `analytics/` |
| 4 | Modelo analítico de riesgo y segmentación | `sql/asset-risk.sql`, `sql/client-risk.sql`, `notebooks/client-model.ipynb` |
| 5 | Ficha del cliente, rebalanceo y precios de mercado | `analytics/` (páginas Ficha, Rebalanceo y Mercado) |

## Estructura

```
├── create-db.py            # crea la base de datos y las tablas
├── load-data.py            # carga los CSV en las tablas
├── run-sql.py              # ejecuta la limpieza y el modelo de riesgo
├── sql/
│   ├── clear.sql           # limpieza: tablas *_limpio y *_rechazados
│   ├── consultas.sql       # consultas de revisión de calidad
│   ├── asset-risk.sql      # nivel de riesgo de cada activo
│   └── client-risk.sql     # riesgo de cada portafolio y alineación con el perfil
├── notebooks/
│   └── client-model.ipynb  # modelo completo y segmentación con K-means
├── config/                 # configuración de Django
├── analytics/              # app de Django (vistas, queries, plantillas)
├── manage.py
└── requirements.txt
```

Los archivos CSV **no** están en el repositorio.

## Requisitos

- Python 3.12
- PostgreSQL 14 o superior (Django 5.2 no funciona con versiones anteriores)
- Los 5 archivos CSV de la prueba en una carpeta: `cat_perfil_riesgo.csv`, `catalogo_activos.csv`, `catalogo_banca.csv`, `historico_aba_macroactivos.csv` y `historico_aba_usd_internacional.csv`

## Configuración

Cree un archivo `.env` en la raíz del proyecto. Este archivo no se sube a git.

```
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=su_contraseña
PGDATABASE=PruebaBancolombia
DATA_DIR=/ruta/a/la/carpeta/de/los/csv

# Opcionales
DJANGO_SECRET_KEY=una_clave_para_django
DJANGO_DEBUG=True
```

## Cómo ejecutarlo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python create-db.py          # 1. crea la base de datos y las tablas
python load-data.py          # 1. carga los CSV
python run-sql.py            # 2 y 4. limpieza, riesgo de activos y riesgo de clientes

jupyter notebook notebooks/client-model.ipynb   # 4. "Run All" crea la tabla de segmentos

python manage.py migrate     # tablas de la app (queries guardados, precios y TRM)
python manage.py runserver   # abrir http://127.0.0.1:8000
```

## 1. Carga de datos

`create-db.py` crea la base de datos y cinco tablas con los mismos nombres de los CSV. Las tablas históricas se cargan con todas las columnas como texto para no perder filas con valores mal formados; la validación se hace en el paso 2.

`load-data.py` detecta si cada CSV separa con coma o con punto y coma, vacía las tablas y vuelve a cargarlas. Se puede ejecutar varias veces sin duplicar datos.

## 2. Limpieza

`sql/clear.sql` crea dos tablas por cada histórico: `*_limpio` (filas válidas con tipos correctos) y `*_rechazados` (filas descartadas con el motivo).

Reglas principales:

- Convierte `''`, `None` y `nan` en `NULL` y quita espacios.
- Quita filas exactamente repetidas. Si después de completar datos quedan dos filas del mismo cliente, activo y día, deja la primera.
- Rechaza filas con columnas corridas, sin cliente identificable, sin ABA o con la fecha de ingesta incompleta.
- Completa el macroactivo, la banca y el perfil cuando el mismo dato aparece en otras filas y es único.
- Los clientes sin perfil quedan como `SIN DEFINIR`.
- Los IDs en notación científica se conservan, pero se marcan como no confiables porque perdieron dígitos.
- Correcciones de código de activo: PFCEMARGOS aparece como 1015 en los históricos (1115 en el catálogo), y 10007 se toma como 1007 (Fiducuenta). Los códigos que no están en el catálogo quedan sin clasificar.
- En USD, `CASH` puede tener valor negativo (saldo en contra).

`sql/consultas.sql` tiene las consultas que se usaron para encontrar estos problemas. La página **Calidad de datos** muestra cuántas filas quedan en cada etapa y por qué se rechazaron.

## 3. Aplicación web

Django 5.2 con SQL directo sobre PostgreSQL y gráficas con Apache ECharts.

| Página | Qué muestra |
|---|---|
| Portafolio | Portafolio COP y USD de un cliente en su última fecha |
| Clientes | Ranking de clientes por ABA en COP y valor en USD |
| Resumen | ABA por banca y los activos con más saldo |
| Calidad de datos | Resultado de la limpieza y filas rechazadas |
| Modelo | Riesgo, alineación con el perfil y segmentos |
| Ficha | Riesgo, rebalanceo y precios de hoy de un cliente en una vista |
| Rebalanceo | Traslado mínimo para alinear cada portafolio con su perfil |
| Mercado | Precios de hoy de las acciones y ETF de EE.UU. y la TRM |
| Archivos SQL | Ver y ejecutar `consultas.sql` |
| Queries guardados | Crear, editar y ejecutar consultas propias |

Las páginas Archivos SQL y Queries guardados ejecutan SQL escrito por el usuario. **La app es solo para uso local.**

## 4. Modelo analítico

Responde tres preguntas: qué tan riesgoso es cada portafolio, si ese riesgo coincide con el perfil declarado y qué grupos de clientes se parecen.

**Riesgo de cada activo** (`sql/asset-risk.sql`). Cada activo recibe un nivel según su volatilidad anual, con las clases de riesgo de mercado de PRIIPs:

| Nivel | Volatilidad anual | Clases PRIIPs | Puntaje |
|---|---|---|---|
| bajo | menos de 5 % | 1 y 2 | 1 |
| medio | de 5 % a menos de 20 % | 3 y 4 | 2 |
| alto | 20 % o más | 5 a 7 | 3 |

El dato de cada activo sale de una de estas fuentes:

- **Perfil publicado por la entidad:** FICs y CDT.
- **Volatilidad calculada con los datos:** acciones colombianas, con los ABA diarios del archivo.
- **Volatilidad publicada del fondo o ETF.**
- **Volatilidad de su clase de activo:** acciones de EE.UU., bonos, tesoros y notas estructuradas.

La tabla `activos_riesgo` guarda el método, el dato y la URL de la fuente de cada activo.

**Riesgo del portafolio** (`sql/client-risk.sql`). La vista `riesgo_clientes` toma la última fecha de cada cliente y calcula el promedio del puntaje ponderado por saldo:

- bajo si es menor que 1,5; medio si es menor que 2,5; alto en otro caso.
- COP y USD se calculan por separado, sin convertir.
- Se compara con el perfil: conservador = bajo, moderado = medio, agresivo = alto.

**Segmentación** (notebook). K-means con variables de tamaño, composición y riesgo de cada portafolio. El número de grupos se elige con el coeficiente de silueta. El resultado se guarda en la tabla `segmentos_clientes`.

## 5. Funcionalidades adicionales

**Ficha del cliente.** Reúne en una vista el perfil, el segmento, el riesgo COP y USD con el nivel de cada activo, la simulación de rebalanceo, el valor de hoy de las acciones y ETF de EE.UU. y la variación de la TRM.

**Sugerencia de rebalanceo.** Para cada portafolio que no coincide con el perfil calcula el traslado mínimo hacia activos del nivel del perfil:

- El objetivo es el borde más cercano del rango del perfil.
- Se mueve primero desde el nivel más lejano y desde el activo con más saldo.
- Los activos sin nivel no se mueven.

Es una simulación educativa, no una recomendación de inversión.

**Precios de mercado actuales.** Los datos son de 2024. Esta página consulta el último cierre de las acciones y ETF de EE.UU. en Yahoo Finance (`yfinance`) y ajusta la cantidad por los splits posteriores. También trae la TRM oficial de datos.gov.co en la fecha de los datos y hoy. Los precios y la TRM se guardan en la base para no consultarlos en cada visita.

**Cómo potencian la herramienta.** La herramienta pasa de describir el portafolio a apoyar decisiones:

- El rebalanceo convierte el diagnóstico de riesgo en una acción concreta: cuánto mover y desde qué activos.
- Los precios actuales y la TRM ponen al día los datos y muestran el efecto del mercado y del dólar.
- La ficha junta todo lo de un cliente en una sola vista para preparar la conversación con el asesor.

## Privacidad

- Los CSV, el archivo `.env`, los resultados del notebook y la base de datos no se suben al repositorio.
- Antes de hacer commit del notebook, instale `nbstripout` para que git guarde el notebook sin resultados:
  ```bash
  pip install nbstripout
  nbstripout --install
  ```

## Limitaciones

- Las volatilidades publicadas de fondos y ETF son las disponibles en 2025 y 2026, no las de la fecha de los datos.
- Los activos sin código de catálogo no tienen nivel y quedan fuera del promedio de riesgo.
- Los IDs en notación científica pueden mezclar clientes distintos.
- Hay pocos clientes, así que los segmentos son descriptivos y no sirven para predecir.
- Los precios de hoy solo cubren acciones y ETF de EE.UU. y no incluyen dividendos.

## Fuentes

- Escala de riesgo: Reglamento Delegado (UE) 2017/653 (PRIIPs), anexo II — https://handbook.fca.org.uk/techstandards/PRIIPs/2017/reg_del_2017_653_oj/annex02.html
- Perfiles de FICs y CDT: Fiduciaria Bancolombia, Bancolombia, Sura Investments y Fogafín.
- Fondos y ETF: BlackRock / iShares, Franklin Templeton, Ninety One, Schroders, J.P. Morgan, PIMCO (vía easybank, finanzen.net, onvista) y Seeking Alpha.
- Clases de activo: VIX EQ (J.P. Morgan Asset Management), iShares CEMB y EMB, Vanguard VGSH, Nasdaq-100 (BNP Paribas).
- TRM: datos abiertos de Colombia — https://www.datos.gov.co/resource/32sa-8pi3.json
- La URL de cada activo está en la columna `fuente` de la tabla `activos_riesgo`.
