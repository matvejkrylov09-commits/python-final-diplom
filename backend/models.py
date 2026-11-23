import secrets

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models


def generate_confirmation_key():
    """32 случайных байта в виде 64 шестнадцатеричных символов."""
    return secrets.token_hex(32)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Необходимо указать email.')
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', False)
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        for field in ('is_staff', 'is_superuser', 'is_active'):
            extra_fields.setdefault(field, True)
            if extra_fields[field] is not True:
                raise ValueError(
                    f'Для суперпользователя {field} должен быть True.',
                )
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Type(models.TextChoices):
        BUYER = 'buyer', 'Покупатель'
        SHOP = 'shop', 'Поставщик'

    # AbstractUser уже содержит отдельные first_name и last_name.
    username = None
    email = models.EmailField('Email', unique=True)
    type = models.CharField(
        'Тип пользователя', max_length=5,
        choices=Type.choices, default=Type.BUYER,
    )
    is_active = models.BooleanField('Активен', default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.email


class Shop(models.Model):
    name = models.CharField('Название', max_length=50)
    url = models.URLField('URL прайс-листа', blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='shop', verbose_name='Владелец',
    )
    state = models.BooleanField('Приём заказов', default=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('Название', max_length=100)
    shops = models.ManyToManyField(
        Shop, related_name='categories', blank=True, verbose_name='Магазины',
    )

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE,
        related_name='products', verbose_name='Категория',
    )

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='product_infos',
    )
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='product_infos',
    )
    external_id = models.PositiveBigIntegerField('Внешний ID')
    model = models.CharField('Модель', max_length=80, blank=True)
    price = models.DecimalField(
        'Цена', max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    price_rrc = models.DecimalField(
        'Рекомендованная цена', max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    quantity = models.PositiveIntegerField('Остаток')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'external_id'], name='unique_shop_external_id',
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='product_price_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(price_rrc__gte=0),
                name='product_rrc_nonnegative',
            ),
        ]

    def __str__(self):
        return f'{self.product} ({self.shop})'


class Parameter(models.Model):
    name = models.CharField('Характеристика', max_length=100, unique=True)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(
        ProductInfo, on_delete=models.CASCADE,
        related_name='product_parameters',
    )
    parameter = models.ForeignKey(
        Parameter, on_delete=models.CASCADE, related_name='product_parameters',
    )
    # Значения характеристик хранятся как текст.
    value = models.TextField('Значение')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product_info', 'parameter'],
                name='unique_product_parameter',
            ),
        ]

    def __str__(self):
        return f'{self.parameter}: {self.value}'


class Contact(models.Model):
    ADDRESS_FIELDS = (
        'city', 'street', 'house', 'structure', 'building', 'apartment',
        'phone',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='contacts',
    )
    city = models.CharField('Город', max_length=50)
    street = models.CharField('Улица', max_length=100)
    house = models.CharField('Дом', max_length=15, blank=True)
    structure = models.CharField('Корпус', max_length=15, blank=True)
    building = models.CharField('Строение', max_length=15, blank=True)
    apartment = models.CharField('Квартира', max_length=15, blank=True)
    phone = models.CharField('Телефон', max_length=20)

    def get_snapshot(self):
        return {name: getattr(self, name) for name in self.ADDRESS_FIELDS}

    def __str__(self):
        return f'{self.city}, {self.street}, {self.house}'


class Order(models.Model):
    class State(models.TextChoices):
        BASKET = 'basket', 'Корзина'
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтверждён'
        ASSEMBLED = 'assembled', 'Собран'
        SENT = 'sent', 'Отправлен'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELED = 'canceled', 'Отменён'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='orders',
    )
    dt = models.DateTimeField('Дата создания', auto_now_add=True)
    state = models.CharField(
        'Статус', max_length=15, choices=State.choices, default=State.BASKET,
    )
    # У корзины адреса ещё нет; удаление контакта не должно удалять заказ.
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, related_name='orders',
        null=True, blank=True,
    )
    delivery_address = models.JSONField(
        'Адрес на момент покупки', default=dict, blank=True, editable=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'], condition=models.Q(state='basket'),
                name='unique_user_basket',
            ),
        ]

    def __str__(self):
        return f'Заказ {self.pk}: {self.get_state_display()}'


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='ordered_items',
    )
    product_info = models.ForeignKey(
        ProductInfo, on_delete=models.PROTECT, related_name='ordered_items',
    )
    quantity = models.PositiveIntegerField(
        'Количество', validators=[MinValueValidator(1)],
    )
    price = models.DecimalField(
        'Цена на момент добавления', max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)], editable=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'product_info'], name='unique_order_item',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='order_item_quantity_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='order_item_price_nonnegative',
            ),
        ]

    def save(self, *args, **kwargs):
        # Обновление прайса не должно менять цену сохранённой позиции.
        if self._state.adding and self.price is None:
            self.price = self.product_info.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product_info} × {self.quantity}'


class ConfirmEmailToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='confirm_email_tokens',
    )
    key = models.CharField(
        'Токен', max_length=64, unique=True,
        default=generate_confirmation_key, editable=False,
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    def __str__(self):
        return f'Подтверждение email пользователя {self.user_id}'
