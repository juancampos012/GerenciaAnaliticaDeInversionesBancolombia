from django.urls import path
from django.views.generic import RedirectView

from . import model_views, views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="portfolio"), name="home"),

    # Portafolio por cliente
    path("portafolio/", views.portfolio, name="portfolio"),

    # Reportes
    path("clientes/", views.client_ranking, name="client_ranking"),
    path("resumen/", views.summary, name="summary"),
    path("calidad/", views.data_quality, name="data_quality"),
    path("modelo/", model_views.model, name="model"),

    # Archivos .sql del proyecto
    path("sql/", views.sql_file_list, name="sql_file_list"),
    path("sql/<str:filename>/", views.sql_file_detail, name="sql_file_detail"),

    # Queries guardados
    path("queries/", views.query_list, name="query_list"),
    path("queries/nuevo/", views.query_create, name="query_create"),
    path("queries/<int:pk>/", views.query_detail, name="query_detail"),
    path("queries/<int:pk>/editar/", views.query_edit, name="query_edit"),
    path("queries/<int:pk>/eliminar/", views.query_delete, name="query_delete"),
]
