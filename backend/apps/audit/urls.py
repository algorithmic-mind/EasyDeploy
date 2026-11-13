from rest_framework.routers import SimpleRouter

from apps.audit import views

router = SimpleRouter(trailing_slash=False)
router.register("logs", views.AuditLogViewSet, basename="audit-log")
router.register("login-logs", views.LoginLogViewSet, basename="login-log")
urlpatterns = router.urls
