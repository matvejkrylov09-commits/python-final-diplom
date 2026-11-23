"""Импорт прайса и оформление заказа."""

import math
from decimal import Decimal, InvalidOperation

import yaml
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F

from .emails import schedule_order_emails
from .models import (
    Category,
    Contact,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


def _text(value, label, max_length=None, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValidationError(f'{label}: ожидается строка.')
    if max_length is not None and len(value) > max_length:
        raise ValidationError(f'{label}: не более {max_length} символов.')
    return value


def _integer(value, label, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValidationError(
            f'{label}: ожидается целое число от 0 до {maximum}.',
        )
    return value


def _price(value, field_name, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValidationError(f'{label}: некорректная цена.')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError(f'{label}: некорректная цена.') from exc
    if not result.is_finite():
        raise ValidationError(f'{label}: цена должна быть конечным числом.')
    try:
        return ProductInfo._meta.get_field(field_name).clean(result, None)
    except ValidationError as exc:
        raise ValidationError(f'{label}: {"; ".join(exc.messages)}') from exc


def _read_price_list(content):
    if not isinstance(content, (str, bytes)):
        raise ValidationError(
            'Содержимое YAML должно быть текстом или байтами.',
        )
    try:
        data = yaml.safe_load(content)
    except (yaml.YAMLError, UnicodeError, ValueError) as exc:
        raise ValidationError('Не удалось прочитать YAML.') from exc
    if not isinstance(data, dict):
        raise ValidationError('Корень YAML должен быть словарём.')
    if {'user', 'user_id', 'owner', 'owner_id', 'shop_id'} & data.keys():
        raise ValidationError('Владелец и ID магазина не задаются в YAML.')
    shop_name = _text(data.get('shop'), 'shop', 50)
    categories = data.get('categories')
    goods = data.get('goods')
    if not isinstance(categories, list) or not isinstance(goods, list):
        raise ValidationError('categories и goods должны быть списками.')

    category_names = {}
    for category in categories:
        if not isinstance(category, dict):
            raise ValidationError('Категория должна быть словарём.')
        category_id = _integer(category.get('id'), 'ID категории', 2**63 - 1)
        if category_id in category_names:
            raise ValidationError(f'Повторный ID категории: {category_id}.')
        category_names[category_id] = _text(
            category.get('name'), 'Название категории', 100,
        )

    offers = []
    external_ids = set()
    for index, item in enumerate(goods, start=1):
        label = f'Товар {index}'
        if not isinstance(item, dict):
            raise ValidationError(f'{label}: ожидается словарь.')
        external_id = _integer(item.get('id'), f'{label}, id', 2**63 - 1)
        if external_id in external_ids:
            raise ValidationError(
                f'{label}: повторный внешний ID {external_id}.',
            )
        external_ids.add(external_id)
        category_id = _integer(
            item.get('category'), f'{label}, category', 2**63 - 1,
        )
        if category_id not in category_names:
            raise ValidationError(
                f'{label}: категория {category_id} отсутствует.',
            )
        parameters = item.get('parameters')
        if not isinstance(parameters, dict):
            raise ValidationError(f'{label}: parameters должен быть словарём.')
        values = {}
        for name, value in parameters.items():
            _text(name, f'{label}, название характеристики', 100)
            if type(value) not in (str, int, float, bool):
                raise ValidationError(
                    f'{label}, {name}: ожидается строка, число или bool.',
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise ValidationError(f'{label}, {name}: некорректное число.')
            values[name] = str(value)
        offers.append({
            'external_id': external_id,
            'category_id': category_id,
            'name': _text(item.get('name'), f'{label}, name', 255),
            'model': _text(
                item.get('model'), f'{label}, model', 80, allow_empty=True,
            ),
            'price': _price(item.get('price'), 'price', f'{label}, price'),
            'price_rrc': _price(
                item.get('price_rrc'), 'price_rrc', f'{label}, price_rrc',
            ),
            'quantity': _integer(
                item.get('quantity'), f'{label}, quantity', 2**31 - 1,
            ),
            'parameters': values,
        })
    return shop_name, category_names, offers


@transaction.atomic
def import_products(content, supplier):
    """Проверяет прайс и обновляет каталог одного поставщика целиком."""
    if (
        not isinstance(supplier, User)
        or supplier.pk is None
        or supplier._state.adding
        or supplier.type != User.Type.SHOP
    ):
        raise PermissionDenied(
            'Импорт доступен только сохранённому поставщику.',
        )
    shop_name, category_names, offers = _read_price_list(content)
    shop, _ = Shop.objects.update_or_create(
        user=supplier, defaults={'name': shop_name},
    )
    categories = {}
    for source_id, name in category_names.items():
        # ID категории действует только внутри исходного прайса.
        categories[source_id], _ = Category.objects.get_or_create(name=name)
    shop.categories.set(categories.values())

    created_count = 0
    imported_ids = []
    for item in offers:
        product, _ = Product.objects.get_or_create(
            name=item['name'], category=categories[item['category_id']],
        )
        offer = ProductInfo.objects.filter(
            shop=shop, external_id=item['external_id'],
        ).first()
        if (
            offer is not None
            and offer.product_id != product.pk
            and offer.ordered_items.exclude(order__state='basket').exists()
        ):
            raise ValidationError(
                f'Внешний ID {item["external_id"]} уже используется '
                'в заказе другого товара.',
            )
        offer, created = ProductInfo.objects.update_or_create(
            shop=shop,
            external_id=item['external_id'],
            defaults={
                'product': product,
                'model': item['model'],
                'price': item['price'],
                'price_rrc': item['price_rrc'],
                'quantity': item['quantity'],
            },
        )
        created_count += int(created)
        imported_ids.append(offer.pk)
        parameter_ids = []
        for name, value in item['parameters'].items():
            parameter, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.update_or_create(
                product_info=offer, parameter=parameter,
                defaults={'value': value},
            )
            parameter_ids.append(parameter.pk)
        offer.product_parameters.exclude(
            parameter_id__in=parameter_ids,
        ).delete()

    zeroed_count = (
        shop.product_infos.exclude(pk__in=imported_ids)
        .exclude(quantity=0).update(quantity=0)
    )
    return {
        'shop_id': shop.pk,
        'categories': len(category_names),
        'processed': len(offers),
        'created': created_count,
        'updated': len(offers) - created_count,
        'zeroed': zeroed_count,
    }


@transaction.atomic
def checkout_order(user, basket_id, contact_id):
    """Фиксирует цены и адрес, списывает остатки и оформляет корзину."""
    if user.type != User.Type.BUYER or not user.is_active:
        raise PermissionDenied('Оформление доступно активному покупателю.')

    # Первая запись захватывает право оформления и блокировку SQLite.
    claimed = Order.objects.filter(
        pk=basket_id, user=user, state=Order.State.BASKET,
    ).update(state=Order.State.NEW)
    if claimed != 1:
        raise ValidationError({
            'basket': ['Корзина недоступна или уже оформлена.'],
        })

    order = Order.objects.select_for_update().select_related('user').get(
        pk=basket_id,
    )
    contact = Contact.objects.select_for_update().filter(
        pk=contact_id, user=user,
    ).first()
    if contact is None:
        raise ValidationError({'contact': ['Контакт недоступен.']})

    items = list(OrderItem.objects.select_for_update().filter(
        order=order,
    ).order_by('product_info_id'))
    if not items:
        raise ValidationError({'basket': ['Корзина пуста.']})

    for item in items:
        if item.quantity <= 0:
            raise ValidationError({
                'basket': ['Количество должно быть больше 0.'],
            })
        offer = ProductInfo.objects.select_for_update().get(
            pk=item.product_info_id,
        )
        # Условное списание защищает остаток и без блокировок строк.
        changed = ProductInfo.objects.filter(
            pk=offer.pk, quantity__gte=item.quantity, shop__state=True,
        ).update(quantity=F('quantity') - item.quantity)
        if changed != 1:
            raise ValidationError({
                'basket': ['Недостаточно товара или магазин отключён.'],
            })
        item.price = offer.price
        item.save(update_fields=['price'])

    order.contact = contact
    order.delivery_address = contact.get_snapshot()
    order.save(update_fields=['contact', 'delivery_address'])
    schedule_order_emails(order)
    return order
