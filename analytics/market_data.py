import requests
import yfinance as yf

from .models import ExchangeRate, MarketPrice

# Tipos de activo de activos_riesgo que cotizan en bolsa de EE.UU. y tienen precio en Yahoo Finance
LISTED_TYPES = ["Acción individual", "ETF de acciones", "ETF de renta fija", "ETF apalancado"]

# Tickers que cambiaron después de la fecha de los datos.
# Block Inc pasó de SQ a XYZ el 21 de enero de 2025 (comunicado de Block Inc).
TICKER_CHANGES = {"SQ": "XYZ"}

# API de datos abiertos con la TRM oficial (Superintendencia Financiera)
TRM_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"


# Convierte el símbolo de los datos en el ticker de Yahoo Finance ("BRK B" -> "BRK-B")
def to_ticker(symbol):
    ticker = symbol.strip().replace(" ", "-")
    return TICKER_CHANGES.get(ticker, ticker)


# Devuelve True si la posición USD es una acción o ETF de EE.UU. con cantidad
def is_listed(position):
    isin = position["isin"] or ""
    return (
        position["simbolo"] is not None
        and isin.startswith("US")
        and position["tipo_activo"] in LISTED_TYPES
        and position["cantidad"] > 0
    )


# Consulta el último precio de cierre y los splits de cada ticker y los guarda en la base
def update_prices(tickers, since_date):
    errors = []
    updated = 0

    for ticker in sorted(set(tickers)):
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(period="5d", auto_adjust=False)
            if history.empty:
                errors.append(f"{ticker}: Yahoo Finance no devolvió precios")
                continue

            # Splits después de la fecha más antigua de los datos
            splits = [
                [day.date().isoformat(), float(ratio)]
                for day, ratio in stock.splits.items()
                if day.date() > since_date
            ]

            MarketPrice.objects.update_or_create(
                ticker=ticker,
                defaults={
                    "price": round(float(history["Close"].iloc[-1]), 4),
                    "price_date": history.index[-1].date(),
                    "splits": splits,
                },
            )
            updated += 1
        except Exception as error:
            errors.append(f"{ticker}: {error}")

    return updated, errors


# Guarda una fila de la API de la TRM
def save_rate(row):
    ExchangeRate.objects.update_or_create(
        valid_from=row["vigenciadesde"][:10],
        defaults={"valid_to": row["vigenciahasta"][:10], "value": row["valor"]},
    )


# Consulta la TRM vigente hoy y la vigente en la fecha de los datos
def update_exchange_rates(data_date):
    # TRM más reciente
    latest = requests.get(TRM_URL, params={"$order": "vigenciadesde DESC", "$limit": 1}, timeout=20)
    latest.raise_for_status()

    # TRM vigente en la fecha de los datos
    day = f"{data_date.isoformat()}T00:00:00"
    old = requests.get(
        TRM_URL,
        params={"$where": f"vigenciadesde <= '{day}' AND vigenciahasta >= '{day}'", "$limit": 1},
        timeout=20,
    )
    old.raise_for_status()

    rows = latest.json() + old.json()
    for row in rows:
        save_rate(row)
    return len(rows)


# TRM vigente en una fecha (None si no se ha consultado)
def rate_on(day):
    return ExchangeRate.objects.filter(valid_from__lte=day, valid_to__gte=day).first()


# Factor para pasar una cantidad de la fecha de los datos a acciones de hoy (por ejemplo 10 si hubo un split 10 a 1)
def split_factor(price, position_date):
    factor = 1.0
    for day, ratio in price.splits:
        if day > position_date.isoformat():
            factor *= ratio
    return factor


# Valor de hoy de cada acción o ETF de EE.UU. del portafolio
# prices: diccionario {ticker: MarketPrice}
def value_positions(positions, prices):
    rows = []
    for position in positions:
        if not is_listed(position):
            continue
        ticker = to_ticker(position["simbolo"])
        price = prices.get(ticker)
        row = {
            "ticker": ticker,
            "activo": position["activo"],
            "fecha_datos": position["fecha_ingesta"],
            "cantidad": float(position["cantidad"]),
            "valor_datos": float(position["valor"]),
            "precio_datos": float(position["valor"]) / float(position["cantidad"]),
            "precio_hoy": None,
        }
        if price:
            factor = split_factor(price, position["fecha_ingesta"])
            row["factor_split"] = factor
            row["precio_hoy"] = float(price.price)
            row["fecha_precio"] = price.price_date
            row["valor_hoy"] = row["cantidad"] * factor * float(price.price)
            row["variacion"] = (row["valor_hoy"] / row["valor_datos"] - 1) * 100
        rows.append(row)
    return rows


# Totales del portafolio USD con precios de hoy
def summarize_values(rows, total_usd):
    priced = [row for row in rows if row["precio_hoy"] is not None]
    value_data = sum(row["valor_datos"] for row in priced)
    value_today = sum(row["valor_hoy"] for row in priced)
    return {
        "valor_datos": round(value_data, 2),
        "valor_hoy": round(value_today, 2),
        "variacion": round((value_today / value_data - 1) * 100, 2) if value_data else None,
        "cobertura": round(value_data / float(total_usd) * 100, 2) if total_usd else None,
        "con_precio": len(priced),
        "sin_precio": len(rows) - len(priced),
    }
