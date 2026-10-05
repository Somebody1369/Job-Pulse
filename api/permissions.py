from typing import override

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasBotAccess(BasePermission):
    message = "This endpoint is reserved for the Telegram bot account."

    @override
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and user.has_perm("subscriptions.access_bot_api")
        )
