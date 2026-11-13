"""Access-control middleware: bind domain, IP allowlist, security entrance, session timeouts.

The entrance is obscurity on top of real authentication (§9.1): until a browser has visited
``/<entrance>``, every route (SPA shell and API) answers like a non-existent site — a plain 404,
or status 444 which Nginx turns into a dropped connection.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _

from apps.accounts.services import api_keys, session
from apps.core.exceptions import envelope
from apps.core.net import client_ip, ip_in_networks, is_local
from apps.panel.services import get_setting

GetResponse = Callable[[HttpRequest], HttpResponse]
HEALTH_PATH = "/api/v1/health"
NGINX_DROP_STATUS = 444


def hidden_response(request: HttpRequest) -> HttpResponse:
    """What an unauthorized visitor sees: nothing that reveals a panel."""
    if get_setting("security.entrance_response") == "drop":
        return HttpResponse(status=NGINX_DROP_STATUS)
    if request.path.startswith("/api/"):
        return JsonResponse(envelope("not_found", _("Not found.")), status=404)
    return HttpResponse("Not Found", status=404, content_type="text/plain; charset=utf-8")


class BindDomainMiddleware:
    """When ``security.bind_domain`` is set, reject requests for any other host name."""

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        domain = get_setting("security.bind_domain")
        if domain and not is_local(client_ip(request)):
            host = request.get_host().rsplit(":", 1)[0].lower().rstrip(".")
            if host != domain:
                return hidden_response(request)
        return self.get_response(request)


class IpAllowlistMiddleware:
    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        allowlist = get_setting("security.ip_allowlist")
        if allowlist:
            ip = client_ip(request)
            if not is_local(ip) and not ip_in_networks(ip, allowlist):
                return hidden_response(request)
        return self.get_response(request)


class EntranceMiddleware:
    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        entrance = get_setting("security.entrance")
        if not entrance:
            return self.get_response(request)
        path = request.path.rstrip("/")
        if path == f"/{entrance}":
            session.mark_entrance(request)
            return HttpResponseRedirect("/")
        if session.passed_entrance(request):
            return self.get_response(request)
        if path == HEALTH_PATH and is_local(client_ip(request)):
            return self.get_response(request)
        raw_key = request.META.get("HTTP_X_API_KEY")
        if raw_key and api_keys.lookup(raw_key, client_ip(request)) is not None:
            return self.get_response(request)
        return hidden_response(request)


class SessionTimeoutMiddleware:
    """Idle and absolute session timeouts (defaults: 2 h idle, 24 h absolute)."""

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and session.LOGIN_AT_KEY in request.session:
            if session.session_expired(request):
                session.end_session(request)
            else:
                session.touch(request)
        return self.get_response(request)


class UserLanguageMiddleware:
    """Signed-in users get their preferred language; others keep Accept-Language."""

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and getattr(user, "language", None):
            translation.activate(user.language)
            request.LANGUAGE_CODE = user.language
        return self.get_response(request)
