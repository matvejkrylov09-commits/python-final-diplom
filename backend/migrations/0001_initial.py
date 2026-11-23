# Создано Django 5.2.19, 04.11.2026, 10:57 UTC.

import backend.models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
            ],
        ),
        migrations.CreateModel(
            name='Parameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Характеристика')),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('type', models.CharField(choices=[('buyer', 'Покупатель'), ('shop', 'Поставщик')], default='buyer', max_length=5, verbose_name='Тип пользователя')),
                ('is_active', models.BooleanField(default=False, verbose_name='Активен')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', backend.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='ConfirmEmailToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default=backend.models.generate_confirmation_key, editable=False, max_length=64, unique=True, verbose_name='Токен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='confirm_email_tokens', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city', models.CharField(max_length=50, verbose_name='Город')),
                ('street', models.CharField(max_length=100, verbose_name='Улица')),
                ('house', models.CharField(blank=True, max_length=15, verbose_name='Дом')),
                ('structure', models.CharField(blank=True, max_length=15, verbose_name='Корпус')),
                ('building', models.CharField(blank=True, max_length=15, verbose_name='Строение')),
                ('apartment', models.CharField(blank=True, max_length=15, verbose_name='Квартира')),
                ('phone', models.CharField(max_length=20, verbose_name='Телефон')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contacts', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dt', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('state', models.CharField(choices=[('basket', 'Корзина'), ('new', 'Новый'), ('confirmed', 'Подтверждён'), ('assembled', 'Собран'), ('sent', 'Отправлен'), ('delivered', 'Доставлен'), ('canceled', 'Отменён')], default='basket', max_length=15, verbose_name='Статус')),
                ('contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='backend.contact')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='backend.category', verbose_name='Категория')),
            ],
        ),
        migrations.CreateModel(
            name='Shop',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='Название')),
                ('url', models.URLField(blank=True, verbose_name='URL прайс-листа')),
                ('state', models.BooleanField(default=True, verbose_name='Приём заказов')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='shop', to=settings.AUTH_USER_MODEL, verbose_name='Владелец')),
            ],
        ),
        migrations.CreateModel(
            name='ProductInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.PositiveBigIntegerField(verbose_name='Внешний ID')),
                ('model', models.CharField(blank=True, max_length=80, verbose_name='Модель')),
                ('price', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Цена')),
                ('price_rrc', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Рекомендованная цена')),
                ('quantity', models.PositiveIntegerField(verbose_name='Остаток')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_infos', to='backend.product')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_infos', to='backend.shop')),
            ],
        ),
        migrations.AddField(
            model_name='category',
            name='shops',
            field=models.ManyToManyField(blank=True, related_name='categories', to='backend.shop', verbose_name='Магазины'),
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name='Количество')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ordered_items', to='backend.order')),
                ('product_info', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ordered_items', to='backend.productinfo')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('order', 'product_info'), name='unique_order_item'), models.CheckConstraint(condition=models.Q(('quantity__gte', 1)), name='order_item_quantity_positive')],
            },
        ),
        migrations.CreateModel(
            name='ProductParameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.TextField(verbose_name='Значение')),
                ('parameter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_parameters', to='backend.parameter')),
                ('product_info', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_parameters', to='backend.productinfo')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('product_info', 'parameter'), name='unique_product_parameter')],
            },
        ),
        migrations.AddConstraint(
            model_name='productinfo',
            constraint=models.UniqueConstraint(fields=('shop', 'external_id'), name='unique_shop_external_id'),
        ),
        migrations.AddConstraint(
            model_name='productinfo',
            constraint=models.CheckConstraint(condition=models.Q(('price__gte', 0)), name='product_price_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='productinfo',
            constraint=models.CheckConstraint(condition=models.Q(('price_rrc__gte', 0)), name='product_rrc_nonnegative'),
        ),
    ]
