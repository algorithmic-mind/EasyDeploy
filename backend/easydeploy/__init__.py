"""EasyDeploy Django project."""

from easydeploy.celery import app as celery_app

__all__ = ["celery_app"]
