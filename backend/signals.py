"""Письма восстановления пароля и отзыв токенов после смены пароля."""

from django.conf import settings
from django.core.mail import send_mail
from django.dispatch import receiver
from django.urls import reverse
from django_rest_passwordreset.signals import (
    post_password_reset,
    reset_password_token_created,
)
from rest_framework.authtoken.models import Token


@receiver(
    reset_password_token_created, dispatch_uid='backend.password_reset_email',
)
def send_password_reset_email(sender, reset_password_token, **kwargs):
    send_mail(
        'Восстановление пароля',
        f'Токен восстановления пароля: {reset_password_token.key}\n'
        'Отправьте token и password методом POST на '
        f'{reverse("backend:password-reset-confirm")}.',
        settings.DEFAULT_FROM_EMAIL,
        [reset_password_token.user.email],
    )


@receiver(post_password_reset, dispatch_uid='backend.revoke_auth_token')
def revoke_auth_token(sender, user, **kwargs):
    Token.objects.filter(user=user).delete()
