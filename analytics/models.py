from django.db import models


# Query SQL guardado desde la aplicación
class SavedQuery(models.Model):
    name = models.CharField("nombre", max_length=100, unique=True)
    description = models.TextField("descripción", blank=True)
    sql = models.TextField("SQL")
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        db_table = "saved_queries"
        ordering = ["name"]

    def __str__(self):
        return self.name


# Último precio de mercado de una acción o ETF de EE.UU. (Yahoo Finance)
class MarketPrice(models.Model):
    ticker = models.CharField("ticker", max_length=20, unique=True)
    price = models.DecimalField("precio", max_digits=14, decimal_places=4)
    price_date = models.DateField("fecha del precio")
    # Splits después de la fecha de los datos: lista de [fecha, factor]
    splits = models.JSONField("splits", default=list)
    fetched_at = models.DateTimeField("consultado", auto_now=True)

    class Meta:
        db_table = "precios_mercado"
        ordering = ["ticker"]

    def __str__(self):
        return self.ticker


# TRM oficial publicada en datos.gov.co
class ExchangeRate(models.Model):
    valid_from = models.DateField("vigente desde", unique=True)
    valid_to = models.DateField("vigente hasta")
    value = models.DecimalField("valor", max_digits=10, decimal_places=2)
    fetched_at = models.DateTimeField("consultado", auto_now=True)

    class Meta:
        db_table = "trm"
        ordering = ["-valid_from"]

    def __str__(self):
        return f"{self.valid_from}: {self.value}"
