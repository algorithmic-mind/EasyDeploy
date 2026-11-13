from django.urls import path

from apps.panel import views

urlpatterns = [
    path("info", views.PanelInfoView.as_view(), name="panel-info"),
    path("version", views.PanelVersionView.as_view(), name="panel-version"),
]
