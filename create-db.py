
import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

#Cargar las variables de entorno desde el archivo .env
load_dotenv()

#Conectar con PostgreSQL utilizando la base de datos predeterminada
connection = psycopg2.connect(
    host=os.getenv("PGHOST"),
    port=os.getenv("PGPORT"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    dbname="postgres"
)

#Permitir ejecutar la creación de bases de datos
connection.autocommit = True

#Obtener el nombre de la nueva base de datos desde el archivo .env
database_name = os.getenv("PGDATABASE")

try:
    with connection.cursor() as cursor:
        #Crear la nueva base de datos
        cursor.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(database_name)
            )
        )

    print(f"Base de datos '{database_name}' creada correctamente.")

except psycopg2.errors.DuplicateDatabase:
    print(f"La base de datos '{database_name}' ya existe.")

finally:
    # Cerrar la conexión con PostgreSQL
    connection.close()

# Queries para crear las tablas en la nueva base de datos
SCHEMA = """
CREATE TABLE IF NOT EXISTS cat_perfil_riesgo (
    cod_perfil_riesgo INT PRIMARY KEY,
    perfil_riesgo     VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS catalogo_activos (
    cod_activo INT PRIMARY KEY,
    activo     VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS catalogo_banca (
    cod_banca VARCHAR(5) PRIMARY KEY,
    banca     VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS historico_aba_macroactivos (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingestion_year     TEXT,
    ingestion_month    TEXT,
    ingestion_day      TEXT,
    id_sistema_cliente TEXT,
    macroactivo        TEXT,
    cod_activo         TEXT,
    aba                TEXT,
    cod_perfil_riesgo  TEXT,
    cod_banca          TEXT,
    year               TEXT,
    month              TEXT
);

CREATE TABLE IF NOT EXISTS historico_aba_usd_internacional (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingestion_year     TEXT,
    ingestion_month    TEXT,
    ingestion_day      TEXT,
    id_sistema_cliente TEXT,
    simbol             TEXT,
    cusip              TEXT,
    isin               TEXT,
    nombre_activo      TEXT,
    cantidad           TEXT,
    valor_mercado      TEXT,
    fecha_vencimiento  TEXT,
    tasa_cupon         TEXT
);
"""

# Conectar a la base de datos
db_connection = psycopg2.connect(
    host=os.getenv("PGHOST"),
    port=os.getenv("PGPORT"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    dbname=os.getenv("PGDATABASE")
)

try:
    with db_connection:
        with db_connection.cursor() as cursor:
            cursor.execute(SCHEMA)
    print("Tablas creadas correctamente.")
finally:
    db_connection.close()