
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
