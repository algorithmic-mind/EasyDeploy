from django.urls import path

from apps.monitoring import views

urlpatterns = [
    path("current", views.CurrentMetricsView.as_view(), name="monitoring-current"),
    path("history", views.HistoryView.as_view(), name="monitoring-history"),
]
