from django.db import DatabaseError
from django.shortcuts import render

from . import client_queries, market_data
from .model_views import fetch_all
from .models import ExchangeRate, MarketPrice
from .rebalance import PROFILE_LEVELS, suggest_rebalance

# Mensaje cuando faltan las tablas del modelo
MISSING_MODEL_ERROR = "No se encontró el modelo. Ejecute python run-sql.py (limpieza, asset-risk y client-risk)."


# Agrupa las filas de posiciones por cliente
def group_by_client(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["id_sistema_cliente"], []).append(row)
    return groups


# Nombres de los activos de referencia agrupados por moneda y nivel: {("COP", "bajo"): [...]}
def assets_by_level():
    options = {}
    for row in fetch_all(client_queries.ASSETS_BY_LEVEL_SQL):
        options.setdefault((row["moneda"], row["nivel_riesgo"]), []).append(row["nombre"])
    return options


# TRM en la fecha de los datos y la más reciente
def exchange_rates():
    data_date = fetch_all(client_queries.LAST_USD_DATE_SQL)[0]["fecha"]
    old = market_data.rate_on(data_date) if data_date else None
    latest = ExchangeRate.objects.first()
    rates = {"data_date": data_date, "old": old, "latest": latest, "variation": None}
    if old and latest:
        rates["variation"] = (float(latest.value) / float(old.value) - 1) * 100
    return rates


# Precios guardados: {ticker: MarketPrice}
def saved_prices():
    return {price.ticker: price for price in MarketPrice.objects.all()}


# Rebalanceo: traslado mínimo para que cada portafolio quede alineado con el perfil
def rebalance(request):
    try:
        clients = fetch_all(client_queries.RISK_CLIENTS_SQL)
        positions = {
            "COP": group_by_client(fetch_all(client_queries.COP_POSITIONS_SQL)),
            "USD": group_by_client(fetch_all(client_queries.USD_POSITIONS_SQL)),
        }
        options = assets_by_level()
    except DatabaseError:
        return render(request, "analytics/rebalance.html", {"error": MISSING_MODEL_ERROR})

    rows = []
    for client in clients:
        for currency in ("COP", "USD"):
            client_positions = positions[currency].get(client["id_sistema_cliente"], [])
            suggestion = suggest_rebalance(client_positions, client["perfil_riesgo"])
            if suggestion and suggestion["moves"]:
                rows.append({
                    "client": client,
                    "currency": currency,
                    "alignment": client["alineacion_" + currency.lower()],
                    "suggestion": suggestion,
                    "options": len(options.get((currency, suggestion["profile_level"]), [])),
                })

    context = {
        "rows": rows,
        "clients_to_move": len({row["client"]["id_sistema_cliente"] for row in rows}),
        "compared": sum(1 for client in clients if client["perfil_riesgo"] in PROFILE_LEVELS),
        "total_cop": sum(row["suggestion"]["total_to_move"] for row in rows if row["currency"] == "COP"),
        "total_usd": sum(row["suggestion"]["total_to_move"] for row in rows if row["currency"] == "USD"),
    }
    return render(request, "analytics/rebalance.html", context)


# Precios de mercado actuales de las acciones y ETF de EE.UU. y TRM
def market(request):
    notices = []
    errors = []

    try:
        usd_rows = fetch_all(client_queries.USD_POSITIONS_SQL)
        clients = {row["id_sistema_cliente"]: row for row in fetch_all(client_queries.RISK_CLIENTS_SQL)}
    except DatabaseError:
        return render(request, "analytics/market.html", {"error": MISSING_MODEL_ERROR})

    listed = [row for row in usd_rows if market_data.is_listed(row)]

    # Al presionar "Actualizar" se consultan Yahoo Finance y datos.gov.co
    if request.method == "POST" and listed:
        tickers = [market_data.to_ticker(row["simbolo"]) for row in listed]
        since_date = min(row["fecha_ingesta"] for row in listed)
        updated, price_errors = market_data.update_prices(tickers, since_date)
        notices.append(f"Precios actualizados: {updated} de {len(set(tickers))} tickers.")
        errors.extend(price_errors)

        data_date = fetch_all(client_queries.LAST_USD_DATE_SQL)[0]["fecha"]
        try:
            market_data.update_exchange_rates(data_date)
            notices.append("TRM actualizada.")
        except Exception as error:
            errors.append(f"TRM: {error}")

    prices = saved_prices()

    # Tabla por ticker: precio en los datos y precio de hoy
    tickers = {}
    for row in market_data.value_positions(listed, prices):
        ticker = tickers.setdefault(row["ticker"], {"ticker": row["ticker"], "activo": row["activo"], "clientes": 0, "rows": []})
        ticker["clientes"] += 1
        ticker["rows"].append(row)
    ticker_rows = []
    for ticker in tickers.values():
        # Se toma la posición con la fecha de datos más reciente
        last = max(ticker["rows"], key=lambda row: row["fecha_datos"])
        ticker_rows.append({**last, "clientes": ticker["clientes"]})
    ticker_rows.sort(key=lambda row: row["ticker"])

    # Tabla por cliente: valor de los datos frente al valor con precios de hoy
    client_rows = []
    for client_id, positions in group_by_client(usd_rows).items():
        valued = market_data.value_positions(positions, prices)
        if not valued:
            continue
        total_usd = sum(float(row["valor"]) for row in positions)
        summary = market_data.summarize_values(valued, total_usd)
        client_rows.append({
            "client": clients.get(client_id, {"id_sistema_cliente": client_id, "id_confiable": True}),
            "total_usd": total_usd,
            **summary,
        })
    client_rows.sort(key=lambda row: -row["valor_datos"])

    last_update = max((price.fetched_at for price in prices.values()), default=None)
    context = {
        "notices": notices,
        "errors": errors,
        "has_prices": bool(prices),
        "last_update": last_update,
        "rates": exchange_rates(),
        "ticker_rows": ticker_rows,
        "client_rows": client_rows,
    }
    return render(request, "analytics/market.html", context)


# Ficha del cliente: riesgo, rebalanceo y precios de hoy
def client_card(request):
    try:
        clients = fetch_all(client_queries.RISK_CLIENTS_SQL)
    except DatabaseError:
        return render(request, "analytics/client_card.html", {"error": MISSING_MODEL_ERROR})

    client_id = request.GET.get("cliente", "")
    context = {"clients": clients, "client_id": client_id}

    client = next((row for row in clients if row["id_sistema_cliente"] == client_id), None)
    if not client:
        return render(request, "analytics/client_card.html", context)

    segment = None
    if fetch_all(client_queries.SEGMENTS_TABLE_EXISTS_SQL)[0]["existe"]:
        segment = next(iter(fetch_all(client_queries.CLIENT_SEGMENT_SQL, [client_id])), None)

    cop_positions = [row for row in fetch_all(client_queries.COP_POSITIONS_SQL) if row["id_sistema_cliente"] == client_id]
    usd_positions = [row for row in fetch_all(client_queries.USD_POSITIONS_SQL) if row["id_sistema_cliente"] == client_id]
    options = assets_by_level()

    cop_suggestion = suggest_rebalance(cop_positions, client["perfil_riesgo"])
    usd_suggestion = suggest_rebalance(usd_positions, client["perfil_riesgo"]) if usd_positions else None

    # Valor de hoy de las acciones y ETF de EE.UU. (si ya se consultaron los precios)
    prices = saved_prices()
    market_rows = market_data.value_positions(usd_positions, prices)
    for position in usd_positions:
        valued = market_data.value_positions([position], prices)
        position["valor_hoy"] = valued[0].get("valor_hoy") if valued else None
        position["variacion"] = valued[0].get("variacion") if valued else None
    market_summary = None
    if prices and market_rows:
        market_summary = market_data.summarize_values(market_rows, client["valor_usd"])

    card = {
        "client": client,
        "segment": segment,
        "cop_positions": cop_positions,
        "usd_positions": usd_positions,
        "cop_date": cop_positions[0]["fecha_ingesta"] if cop_positions else None,
        "usd_date": usd_positions[0]["fecha_ingesta"] if usd_positions else None,
        "cop_suggestion": cop_suggestion,
        "usd_suggestion": usd_suggestion,
        "market_summary": market_summary,
        "rates": exchange_rates(),
    }

    if cop_suggestion:
        card["cop_options"] = options.get(("COP", cop_suggestion["profile_level"]), [])
    if usd_suggestion:
        card["usd_options"] = options.get(("USD", usd_suggestion["profile_level"]), [])

    context.update(card)
    context.update({"market_rows": market_rows, "has_prices": bool(prices)})
    return render(request, "analytics/client_card.html", context)
