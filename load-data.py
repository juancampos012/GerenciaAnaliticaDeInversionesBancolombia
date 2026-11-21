import os
import csv
import psycopg2
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Carpeta donde están los archivos CSV
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", ""))

# Tablas en orden de carga.
TABLES = [
    "cat_perfil_riesgo",
    "catalogo_activos",
    "catalogo_banca",
    "historico_aba_macroactivos",
    "historico_aba_usd_internacional",
]

# Revisa la primera línea del CSV para saber si separa con ";" o con ","
def get_delimiter(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig") as file:
        first_line = file.readline()

    if ";" in first_line:
        return ";"
    return ","

# Lee el CSV y devuelve los nombres de las columnas y las filas
def read_csv(csv_path):
    delimiter = get_delimiter(csv_path)

    with open(csv_path, "r", encoding="utf-8-sig") as file:
        reader = csv.reader(file, delimiter=delimiter)
        headers = next(reader)
        rows = list(reader)

    columns = [header.strip().lower() for header in headers]
    return columns, rows

# Conectar a la base de datos creada en el paso anterior
db_connection = psycopg2.connect(
    host=os.getenv("PGHOST"),
    port=os.getenv("PGPORT"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    dbname=os.getenv("PGDATABASE")
)

cursor = db_connection.cursor()

try:
    # Vaciar las tablas para no duplicar datos si el script se ejecuta otra vez
    cursor.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")

    for table in TABLES:
        csv_path = os.path.join(DATA_DIR, f"{table}.csv")
        columns, rows = read_csv(csv_path)

        # Armar el INSERT
        column_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        # si la llave primaria ya existe, se omite la fila repetida
        insert_query = (
            f"INSERT INTO {table} ({column_names}) VALUES ({placeholders}) "
            f"ON CONFLICT DO NOTHING"
        )

        for row in rows:
            # Saltar líneas vacías del archivo
            if not row:
                continue
            
            # Las celdas vacías, "None" y "nan" se guardan como NULL
            values = [None if value.strip().lower() in ["", "none", "nan"] else value for value in row]
            cursor.execute(insert_query, values)

    # Guardar los cambios solo si todas las tablas se cargaron bien
    db_connection.commit()
    print("Todas las tablas se poblaron correctamente.")

except Exception as error:
    # Si algo falla se deshacen todos los cambios
    db_connection.rollback()
    print(f"Error al poblar las tablas: {error}")

finally:
    # Cerrar la conexión con la base de datos
    db_connection.close()