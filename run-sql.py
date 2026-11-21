import os
import psycopg2
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Scripts SQL que se ejecutan en orden
SQL_FILES = [
    "sql/clear.sql",
]

# Conectar a la base de datos
db_connection = psycopg2.connect(
    host=os.getenv("PGHOST"),
    port=os.getenv("PGPORT"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    dbname=os.getenv("PGDATABASE")
)

cursor = db_connection.cursor()

try:
    for sql_file in SQL_FILES:
        # Leer el archivo y ejecutar todas sus consultas
        with open(sql_file, "r", encoding="utf-8") as file:
            cursor.execute(file.read())

        print(f"Script '{sql_file}' ejecutado correctamente.")

    # Guardar los cambios solo si todos los scripts terminaron bien
    db_connection.commit()
    print("Limpieza terminada.")

except Exception as error:
    # Si algo falla, se deshacen todos los cambios
    db_connection.rollback()
    print(f"Error al ejecutar los scripts SQL: {error}")

finally:
    # Cerrar el cursor y la conexión con PostgreSQL
    cursor.close()
    db_connection.close()