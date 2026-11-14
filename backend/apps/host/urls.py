from django.urls import path, re_path

from apps.host import views

UNIT = r"(?P<unit>[A-Za-z0-9@:._-]{1,255})"

urlpatterns = [
    path("processes", views.ProcessListView.as_view(), name="host-processes"),
    path("processes/<int:pid>", views.ProcessDetailView.as_view(), name="host-process"),
    path(
        "processes/<int:pid>/signal", views.ProcessSignalView.as_view(), name="host-process-signal"
    ),
    path("services", views.ServiceListView.as_view(), name="host-services"),
    re_path(
        rf"^services/{UNIT}/action$", views.ServiceActionView.as_view(), name="host-service-action"
    ),
    path("journal", views.JournalView.as_view(), name="host-journal"),
]
