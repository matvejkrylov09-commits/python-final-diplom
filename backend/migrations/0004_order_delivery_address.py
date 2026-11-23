# Создано Django 5.2.19, 04.11.2026, 11:43 UTC.

from django.db import migrations, models


def fill_delivery_addresses(apps, schema_editor):
    """Сохраняет доступные адреса ранее оформленных заказов."""
    order_model = apps.get_model('backend', 'Order')
    database = schema_editor.connection.alias
    orders = order_model.objects.using(database).exclude(
        state='basket',
    ).filter(contact__isnull=False).select_related('contact')
    fields = (
        'city', 'street', 'house', 'structure', 'building', 'apartment',
        'phone',
    )
    for order in orders.iterator():
        address = {name: getattr(order.contact, name) for name in fields}
        order_model.objects.using(database).filter(pk=order.pk).update(
            delivery_address=address,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0003_order_unique_user_basket'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_address',
            field=models.JSONField(
                blank=True, default=dict, editable=False,
                verbose_name='Адрес на момент покупки',
            ),
        ),
        migrations.RunPython(
            fill_delivery_addresses, migrations.RunPython.noop,
        ),
    ]
