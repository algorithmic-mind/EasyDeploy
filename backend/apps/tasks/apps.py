from django.apps import AppConfig


class TasksConfig(AppConfig):
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tasks"

    def ready(self) -> None:
        from apps.tasks import signals  # noqa: F401
