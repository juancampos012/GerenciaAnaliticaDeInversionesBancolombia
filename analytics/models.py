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
