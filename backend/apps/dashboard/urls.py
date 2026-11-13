from django.urls import path

from apps.dashboard import views

urlpatterns = [path("system-info", views.SystemInfoView.as_view(), name="system-info")]
