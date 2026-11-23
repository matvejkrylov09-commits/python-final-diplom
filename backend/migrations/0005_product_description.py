# Создано Django 5.2.19, 04.11.2026, 12:16 UTC.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0004_order_delivery_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True, verbose_name='Описание'),
        ),
    ]
