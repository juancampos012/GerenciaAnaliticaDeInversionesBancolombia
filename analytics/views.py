from django.conf import settings
from django.db import DatabaseError, connection
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SavedQueryForm
from .models import SavedQuery
from . import report_queries
from .portfolio_queries import CLIENTS_SQL, COP_PORTFOLIO_SQL, USD_PORTFOLIO_SQL
from .sql_runner import run_sql

# Mensaje cuando todavía no se ha ejecutado el archivo de limpieza
MISSING_TABLES_ERROR = "No se encontraron las tablas limpias. Ejecute primero el archivo de limpieza."


# ---------------------------------------------------------------------
# Archivos .sql del proyecto
# ---------------------------------------------------------------------

# Archivos .sql que se pueden ver y ejecutar desde la app
VISIBLE_SQL_FILES = ["consultas.sql"]


# Devuelve los archivos visibles que existen en la carpeta sql/
def get_sql_files():
    return [name for name in VISIBLE_SQL_FILES if (settings.SQL_DIR / name).exists()]


def sql_file_list(request):
    return render(request, "analytics/sql_file_list.html", {"files": get_sql_files()})


def sql_file_detail(request, filename):
    # Solo se permiten archivos que estén dentro de la carpeta sql/
    if filename not in get_sql_files():
        raise Http404("Archivo SQL no encontrado")

    sql_text = (settings.SQL_DIR / filename).read_text(encoding="utf-8")

    # Al presionar "Ejecutar" se corre todo el archivo
    execution = None
    if request.method == "POST":
        execution = run_sql(sql_text)

    context = {"filename": filename, "sql_text": sql_text, "execution": execution}
    return render(request, "analytics/sql_file_detail.html", context)


# ---------------------------------------------------------------------
# Queries guardados (crear, ver, editar, borrar y ejecutar)
# ---------------------------------------------------------------------

def query_list(request):
    return render(request, "analytics/query_list.html", {"queries": SavedQuery.objects.all()})


def query_create(request):
    form = SavedQueryForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        query = form.save()
        return redirect("query_detail", pk=query.pk)

    return render(request, "analytics/query_form.html", {"form": form})


def query_detail(request, pk):
    query = get_object_or_404(SavedQuery, pk=pk)

    # Al presionar "Ejecutar" se corre el query
    execution = None
    if request.method == "POST":
        execution = run_sql(query.sql)

    return render(request, "analytics/query_detail.html", {"query": query, "execution": execution})


def query_edit(request, pk):
    query = get_object_or_404(SavedQuery, pk=pk)
    form = SavedQueryForm(request.POST or None, instance=query)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("query_detail", pk=query.pk)

    return render(request, "analytics/query_form.html", {"form": form, "query": query})


def query_delete(request, pk):
    query = get_object_or_404(SavedQuery, pk=pk)

    if request.method == "POST":
        query.delete()
        return redirect("query_list")

    return render(request, "analytics/query_confirm_delete.html", {"query": query})


# ---------------------------------------------------------------------
# Portafolio por cliente
# ---------------------------------------------------------------------

# Ejecuta un query y devuelve las filas como diccionarios
def fetch_all(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def portfolio(request):
    client_id = request.GET.get("cliente", "")
    context = {"client_id": client_id}

    try:
        clients = fetch_all(CLIENTS_SQL)
    except DatabaseError:
        # Las tablas limpias todavía no existen
        context["error"] = MISSING_TABLES_ERROR
        return render(request, "analytics/portfolio.html", context)

    context["clients"] = clients

    if not client_id:
        return render(request, "analytics/portfolio.html", context)

    # Portafolio COP y USD del cliente en su última fecha disponible
    cop_rows = fetch_all(COP_PORTFOLIO_SQL, [client_id, client_id])
    usd_rows = fetch_all(USD_PORTFOLIO_SQL, [client_id, client_id])

    # Total COP por macroactivo, para la gráfica de dona
    totals_by_macro = {}
    for row in cop_rows:
        totals_by_macro[row["macroactivo"]] = totals_by_macro.get(row["macroactivo"], 0) + float(row["aba"])

    # Datos que usan las gráficas de ECharts
    chart_data = {
        "cop_by_macro": [{"name": name, "value": value} for name, value in totals_by_macro.items()],
        "cop_by_asset": {
            "names": [row["activo"] for row in cop_rows],
            "values": [float(row["aba"]) for row in cop_rows],
        },
        "usd_by_asset": {
            "names": [row["nombre_activo"] for row in usd_rows],
            "values": [float(row["valor_mercado_usd"]) for row in usd_rows],
        },
    }

    # ¿El ID del cliente es confiable?
    reliable = next((c["confiable"] for c in clients if c["id_sistema_cliente"] == client_id), True)

    context.update({
        "reliable": reliable,
        "cop_rows": cop_rows,
        "usd_rows": usd_rows,
        "cop_total": sum(float(row["aba"]) for row in cop_rows),
        "usd_total": sum(float(row["valor_mercado_usd"]) for row in usd_rows),
        "cop_date": cop_rows[0]["fecha_ingesta"] if cop_rows else None,
        "usd_date": usd_rows[0]["fecha_ingesta"] if usd_rows else None,
        "banca": cop_rows[0]["banca"] if cop_rows else None,
        "perfil": cop_rows[0]["perfil_riesgo"] if cop_rows else None,
        "chart_data": chart_data,
        # Alto de la gráfica USD: 32 px por activo, mínimo 220 px
        "usd_chart_height": max(220, 32 * len(usd_rows) + 40),
    })
    return render(request, "analytics/portfolio.html", context)


# ---------------------------------------------------------------------
# Resumen: banca y top activos
# ---------------------------------------------------------------------

def summary(request):
    try:
        dates = fetch_all(report_queries.SUMMARY_DATES_SQL)[0]
        banks = fetch_all(report_queries.BANK_SUMMARY_SQL)
        top_cop = fetch_all(report_queries.TOP_COP_ASSETS_SQL)
        top_usd = fetch_all(report_queries.TOP_USD_ASSETS_SQL)
    except DatabaseError:
        return render(request, "analytics/summary.html", {"error": MISSING_TABLES_ERROR})

    # Datos que usan las gráficas de ECharts
    chart_data = {
        "banks": {
            "names": [row["banca"] for row in banks],
            "aba": [float(row["aba_total"]) for row in banks],
            "clients": [row["clientes"] for row in banks],
        },
        "top_cop": {
            "names": [row["activo"] for row in top_cop],
            "values": [float(row["aba_total"]) for row in top_cop],
        },
        "top_usd": {
            "names": [row["nombre_activo"] for row in top_usd],
            "values": [float(row["valor_total"]) for row in top_usd],
        },
    }

    context = {
        "dates": dates,
        "banks": banks,
        "top_cop": top_cop,
        "top_usd": top_usd,
        "bank_total": sum(float(row["aba_total"]) for row in banks),
        "chart_data": chart_data,
    }
    return render(request, "analytics/summary.html", context)


# ---------------------------------------------------------------------
# Ranking de clientes
# ---------------------------------------------------------------------

def client_ranking(request):
    try:
        clients = fetch_all(report_queries.CLIENT_RANKING_SQL)
    except DatabaseError:
        return render(request, "analytics/client_ranking.html", {"error": MISSING_TABLES_ERROR})

    return render(request, "analytics/client_ranking.html", {"clients": clients})


# ---------------------------------------------------------------------
# Calidad de datos
# ---------------------------------------------------------------------

def data_quality(request):
    try:
        rows_by_table = fetch_all(report_queries.QUALITY_ROWS_SQL)
        rejected = fetch_all(report_queries.REJECTED_BY_REASON_SQL)
        id_types = fetch_all(report_queries.ID_TYPES_SQL)
        unreliable = fetch_all(report_queries.UNRELIABLE_IDS_SQL)[0]
        out_of_catalog = fetch_all(report_queries.OUT_OF_CATALOG_SQL)
        corrections = fetch_all(report_queries.CORRECTIONS_SQL)
    except DatabaseError:
        return render(request, "analytics/data_quality.html", {"error": MISSING_TABLES_ERROR})

    # Filas que se quitaron por estar repetidas el mismo día después de llenar vacíos.
    # Es lo que falta para que cuadren las cuentas.
    for row in rows_by_table:
        row["otras"] = row["originales"] - row["repetidas"] - row["rechazadas"] - row["limpias"]

    # Datos que usan las gráficas de ECharts
    chart_data = {
        "rejected": {
            "names": [f"{row['tabla']}: {row['motivo_rechazo']}" for row in rejected],
            "values": [row["filas"] for row in rejected],
        },
        "id_types": [{"name": row["tipo_id"], "value": row["filas"]} for row in id_types],
        "out_of_catalog": {
            "names": [row["cod_activo"] for row in out_of_catalog],
            "values": [row["filas"] for row in out_of_catalog],
        },
    }

    context = {
        "rows_by_table": rows_by_table,
        "rejected": rejected,
        "id_types": id_types,
        "unreliable": unreliable,
        "out_of_catalog": out_of_catalog,
        "corrections": corrections,
        "chart_data": chart_data,
        "catalog_chart_height": max(220, 32 * len(out_of_catalog) + 40),
    }
    return render(request, "analytics/data_quality.html", context)

