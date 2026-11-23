"""Импорт локального прайса через командную строку."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from backend.services import import_products


class Command(BaseCommand):
    help = 'Загрузить YAML-прайс существующего поставщика.'

    def add_arguments(self, parser):
        parser.add_argument('path', type=Path, help='Путь к YAML-файлу.')
        parser.add_argument('--email', required=True, help='Email поставщика.')

    def handle(self, *args, **options):
        user_model = get_user_model()
        email = user_model.objects.normalize_email(options['email'])
        try:
            supplier = user_model.objects.get(email=email)
        except user_model.DoesNotExist as exc:
            raise CommandError('Поставщик с таким email не найден.') from exc
        if supplier.type != user_model.Type.SHOP:
            raise CommandError('Пользователь должен быть поставщиком.')
        try:
            content = options['path'].read_bytes()
        except OSError as exc:
            raise CommandError(f'Не удалось прочитать файл: {exc}') from exc
        try:
            result = import_products(content, supplier)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        except PermissionDenied as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Обработано товаров: {result["processed"]}; '
            f'создано: {result["created"]}; '
            f'обновлено: {result["updated"]}; '
            f'обнулено остатков: {result["zeroed"]}.',
        ))
