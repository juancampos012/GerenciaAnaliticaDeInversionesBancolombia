import sqlparse
from django.db import connection, transaction

# Máximo de filas que se muestran por resultado
MAX_ROWS = 500


# Devuelve el título de un query: su primer comentario con texto o el inicio del SQL
def get_title(statement):
    for line in statement.strip().splitlines():
        line = line.strip()
        if line.startswith("--"):
            comment = line.lstrip("-").strip()
            # Se saltan los comentarios que solo son líneas de separación (=====)
            if any(character.isalnum() for character in comment):
                return comment
        elif line:
            return line[:80]
    return ""


# Separa un texto SQL en queries, sin contar los que solo tienen comentarios
def split_statements(sql_text):
    statements = []
    for statement in sqlparse.split(sql_text):
        only_code = sqlparse.format(statement, strip_comments=True).strip()
        if only_code:
            statements.append(statement)
    return statements


# Ejecuta uno o varios queries en una sola transacción.
# Si un query falla, se deshacen todos los cambios.
def run_sql(sql_text):
    results = []
    statements = split_statements(sql_text)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
                    result = {"title": get_title(statement)}

                    # El query devolvió filas (por ejemplo un SELECT)
                    if cursor.description:
                        rows = cursor.fetchmany(MAX_ROWS + 1)
                        result["columns"] = [column.name for column in cursor.description]
                        result["rows"] = rows[:MAX_ROWS]
                        result["truncated"] = len(rows) > MAX_ROWS
                    # El query cambió datos o tablas (INSERT, UPDATE, CREATE...)
                    else:
                        result["rowcount"] = cursor.rowcount

                    results.append(result)

        return {"ok": True, "results": results, "error": None}

    except Exception as error:
        return {"ok": False, "results": results, "error": str(error)}
