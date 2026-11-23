"""Сохранение цены позиции независимо от текущего прайса."""

import django.core.validators
from django.db import migrations, models


def fill_order_item_prices(apps, schema_editor):
    """Заполняет цены существующих позиций до следующего импорта."""
    order_item = apps.get_model('backend', 'OrderItem')
    database = schema_editor.connection.alias
    items = order_item.objects.using(database).select_related('product_info')
    for item in items.iterator():
        order_item.objects.using(database).filter(pk=item.pk).update(
            price=item.product_info.price,
        )


class Migration(migrations.Migration):
    dependencies = [('backend', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='price',
            field=models.DecimalField(
                max_digits=12, decimal_places=2, null=True, editable=False,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Цена на момент добавления',
            ),
        ),
        migrations.RunPython(
            fill_order_item_prices, migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='price',
            field=models.DecimalField(
                max_digits=12, decimal_places=2, editable=False,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Цена на момент добавления',
            ),
        ),
        migrations.AddConstraint(
            model_name='orderitem',
            constraint=models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='order_item_price_nonnegative',
            ),
        ),
    ]
