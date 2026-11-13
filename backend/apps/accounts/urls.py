from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.accounts import views

router = SimpleRouter(trailing_slash=False)
router.register("api-keys", views.ApiKeyViewSet, basename="api-key")

urlpatterns = [
    path("csrf", views.CsrfView.as_view(), name="csrf"),
    path("login", views.LoginView.as_view(), name="login"),
    path("login/2fa", views.SecondFactorView.as_view(), name="login-2fa"),
    path("logout", views.LogoutView.as_view(), name="logout"),
    path("me", views.MeView.as_view(), name="me"),
    path("sudo", views.SudoView.as_view(), name="sudo"),
    path("password", views.PasswordChangeView.as_view(), name="password"),
    path("2fa/setup", views.TotpSetupView.as_view(), name="2fa-setup"),
    path("2fa/enable", views.TotpEnableView.as_view(), name="2fa-enable"),
    path("2fa/disable", views.TotpDisableView.as_view(), name="2fa-disable"),
    path("2fa/recovery-codes", views.RecoveryCodesView.as_view(), name="2fa-recovery-codes"),
    *router.urls,
]
