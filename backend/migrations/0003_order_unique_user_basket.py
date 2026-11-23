# Создано Django 5.2.19, 04.11.2026, 11:35 UTC.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0002_orderitem_price'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(
                condition=models.Q(('state', 'basket')),
                fields=('user',), name='unique_user_basket',
            ),
        ),
    ]
