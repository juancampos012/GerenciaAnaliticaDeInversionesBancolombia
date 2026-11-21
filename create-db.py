
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
    ingestion_year     INT,
    ingestion_month    INT,
    ingestion_day      INT,
    id_sistema_cliente BIGINT,
    macroactivo        VARCHAR(100),
    cod_activo         INT REFERENCES catalogo_activos(cod_activo),
    aba                NUMERIC(40,4),
    cod_perfil_riesgo  INT REFERENCES cat_perfil_riesgo(cod_perfil_riesgo),
    cod_banca          VARCHAR(5) REFERENCES catalogo_banca(cod_banca),
    year               INT,
    month              INT
);

CREATE TABLE IF NOT EXISTS historico_aba_usd_internacional (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingestion_year     INT,
    ingestion_month    INT,
    ingestion_day      INT,
    id_sistema_cliente BIGINT,
    simbol             VARCHAR(30),
    cusip              VARCHAR(30),
    isin               VARCHAR(30),
    nombre_activo      VARCHAR(300),
    cantidad           NUMERIC(24,6),
    valor_mercado      NUMERIC(24,2),
    fecha_vencimiento  VARCHAR(20),
    tasa_cupon         NUMERIC(12,6)
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