from django.db import DatabaseError, connection
from django.shortcuts import render

from . import model_queries


# Ejecuta un query y devuelve las filas como diccionarios
def fetch_all(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Modelo analítico: riesgo del portafolio, alineación con el perfil y segmentos

# Orden en que se muestran los resultados de la comparación con el perfil
ALIGNMENT_ORDER = [
    "Alineado",
    "Más riesgo que su perfil",
    "Menos riesgo que su perfil",
    "Sin perfil para comparar",
    "Perfil no único",
    "Sin portafolio USD",
]


# Cuenta los clientes de cada resultado, en el orden de ALIGNMENT_ORDER
def count_alignment(clients, column):
    counts = {name: 0 for name in ALIGNMENT_ORDER}
    for client in clients:
        counts[client[column]] = counts.get(client[column], 0) + 1
    return {name: total for name, total in counts.items() if total > 0}


def model(request):
    try:
        has_segments = fetch_all(model_queries.SEGMENTS_TABLE_EXISTS_SQL)[0]["existe"]
        if has_segments:
            clients = fetch_all(model_queries.MODEL_CLIENTS_SQL)
            segments = fetch_all(model_queries.SEGMENTS_SQL)
        else:
            clients = fetch_all(model_queries.MODEL_CLIENTS_NO_SEGMENTS_SQL)
            segments = []
        profile_vs_level = fetch_all(model_queries.PROFILE_VS_LEVEL_SQL)
        assets = fetch_all(model_queries.ASSET_RISK_SQL)
    except DatabaseError:
        error = "No se encontró el modelo. Ejecute sql/asset-risk.sql y sql/client-risk.sql (o el notebook)."
        return render(request, "analytics/model.html", {"error": error})

    cop_alignment = count_alignment(clients, "alineacion_cop")
    usd_alignment = count_alignment(clients, "alineacion_usd")

    # Datos que usan las gráficas de ECharts
    chart_data = {
        "cop_alignment": {"names": list(cop_alignment), "values": list(cop_alignment.values())},
        "usd_alignment": {"names": list(usd_alignment), "values": list(usd_alignment.values())},
        "segments": {
            "names": [f"{row['segmento']}. {row['nombre_segmento']}" for row in segments],
            "values": [row["clientes"] for row in segments],
        },
    }

    context = {
        "clients": clients,
        "segments": segments,
        "has_segments": has_segments,
        "profile_vs_level": profile_vs_level,
        "assets": assets,
        "total_clients": len(clients),
        "compared": sum(cop_alignment.get(name, 0) for name in ALIGNMENT_ORDER[:3]),
        "aligned": cop_alignment.get("Alineado", 0),
        "more_risk": cop_alignment.get("Más riesgo que su perfil", 0),
        "less_risk": cop_alignment.get("Menos riesgo que su perfil", 0),
        "no_profile": cop_alignment.get("Sin perfil para comparar", 0),
        "chart_data": chart_data,
        # Alto de la gráfica de segmentos: 40 px por segmento, mínimo 220 px
        "segments_chart_height": max(220, 40 * len(segments) + 40),
    }
    return render(request, "analytics/model.html", context)
