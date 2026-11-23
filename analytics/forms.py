from django import forms

from .models import SavedQuery


# Formulario para crear y editar queries guardados
class SavedQueryForm(forms.ModelForm):
    class Meta:
        model = SavedQuery
        fields = ["name", "description", "sql"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "sql": forms.Textarea(attrs={"rows": 14, "class": "sql-editor"}),
        }
