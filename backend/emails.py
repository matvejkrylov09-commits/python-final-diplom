"""Уведомления о сохранённом заказе."""

from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction


def schedule_order_emails(order):
    """Готовит письма и откладывает отправку до фиксации транзакции."""
    items = order.ordered_items.select_related(
        'product_info__product', 'product_info__shop',
    ).order_by('pk')
    lines = []
    total = Decimal('0.00')
    for item in items:
        subtotal = item.price * item.quantity
        total += subtotal
        lines.append(
            f'{item.product_info.product.name} '
            f'({item.product_info.shop.name}): '
            f'{item.quantity} шт. × {item.price:.2f} = {subtotal:.2f}',
        )
    address = order.delivery_address
    address_lines = [
        f'Город: {address.get("city", "")}',
        f'Улица: {address.get("street", "")}',
        f'Дом: {address.get("house", "")}',
        f'Корпус: {address.get("structure", "")}',
        f'Строение: {address.get("building", "")}',
        f'Квартира: {address.get("apartment", "")}',
        f'Телефон: {address.get("phone", "")}',
    ]
    body = '\n'.join([
        f'Заказ №{order.pk}',
        *lines,
        f'Итого: {total:.2f}',
        'Доставка:',
        *address_lines,
    ])
    def send_buyer_email():
        send_mail(
            f'Подтверждение заказа №{order.pk}', body,
            settings.DEFAULT_FROM_EMAIL, [order.user.email],
        )

    transaction.on_commit(send_buyer_email, robust=True)

    recipients = [email for _, email in settings.ADMINS]
    if recipients:
        invoice = '\n'.join([
            f'Покупатель: {order.user.get_full_name()}',
            f'Email: {order.user.email}',
            body,
        ])
        def send_admin_email():
            send_mail(
                f'Накладная по заказу №{order.pk}', invoice,
                settings.DEFAULT_FROM_EMAIL, recipients,
            )

        transaction.on_commit(send_admin_email, robust=True)
