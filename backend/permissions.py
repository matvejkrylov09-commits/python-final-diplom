"""Права доступа покупателей и поставщиков."""

from rest_framework.permissions import BasePermission

from .models import User


class IsBuyer(BasePermission):
    message = 'Операция доступна только покупателям.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.type == User.Type.BUYER
        )


class IsSupplier(BasePermission):
    message = 'Операция доступна только поставщикам.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.type == User.Type.SHOP
        )
