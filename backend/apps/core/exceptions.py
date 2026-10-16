"""Единый формат ошибок API: {"code": ..., "message": ..., "fields": {...}}."""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(exceptions.APIException):
    """Ошибка бизнес-логики с машиночитаемым кодом."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "error"
    default_detail = "Ошибка запроса."

    def __init__(self, code, message, status_code=None):
        self.code = code
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=message, code=code)


class Conflict(ApiError):
    status_code = status.HTTP_409_CONFLICT


_CODE_BY_CLASS = {
    exceptions.NotAuthenticated: "not_authenticated",
    exceptions.AuthenticationFailed: "authentication_failed",
    exceptions.PermissionDenied: "permission_denied",
    exceptions.NotFound: "not_found",
    exceptions.MethodNotAllowed: "method_not_allowed",
    exceptions.Throttled: "throttled",
    exceptions.ValidationError: "validation_error",
    exceptions.ParseError: "parse_error",
}


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ApiError):
        response.data = {"code": exc.code, "message": exc.message, "fields": {}}
        return response

    code = next((c for cls, c in _CODE_BY_CLASS.items() if isinstance(exc, cls)), "error")
    if isinstance(exc, exceptions.ValidationError):
        fields = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        response.data = {"code": code, "message": "Проверьте данные.", "fields": fields}
    else:
        detail = response.data.get("detail", "") if isinstance(response.data, dict) else ""
        response.data = {"code": code, "message": str(detail), "fields": {}}
    return response


def error_response(code, message, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({"code": code, "message": message, "fields": {}}, status=http_status)
