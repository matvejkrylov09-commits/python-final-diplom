"""Данные пользователей, каталога, корзины и заказов."""

from collections.abc import Mapping
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    Category,
    Contact,
    Order,
    OrderItem,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)
from .services import checkout_order, import_products


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128,
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password')
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
            'email': {'validators': []},
        }

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                'Этот email уже зарегистрирован.',
            )
        return email

    def validate(self, attrs):
        user = User(
            email=attrs['email'], first_name=attrs['first_name'],
            last_name=attrs['last_name'],
        )
        try:
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ConfirmEmailSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128,
    )

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            email=User.objects.normalize_email(attrs['email']),
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError('Неверный email или пароль.')
        return {'user': user}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'type')
        read_only_fields = fields


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'state')
        read_only_fields = fields


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name')
        read_only_fields = fields


class ProductParameterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='parameter.name', read_only=True)

    class Meta:
        model = ProductParameter
        fields = ('name', 'value')
        read_only_fields = fields


class ProductInfoSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='product.name', read_only=True)
    description = serializers.CharField(
        source='product.description', read_only=True,
    )
    category = CategorySerializer(source='product.category', read_only=True)
    shop = ShopSerializer(read_only=True)
    parameters = ProductParameterSerializer(
        source='product_parameters', many=True, read_only=True,
    )

    class Meta:
        model = ProductInfo
        fields = (
            'id', 'name', 'description', 'category', 'shop', 'model', 'price',
            'price_rrc', 'quantity', 'parameters',
        )
        read_only_fields = fields


class ProductFilterSerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False, allow_blank=True, max_length=255,
    )
    category = serializers.IntegerField(required=False, min_value=1)
    shop = serializers.IntegerField(required=False, min_value=1)


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail('invalid')
        return super().to_internal_value(data)


class BasketQuantitySerializer(serializers.Serializer):
    quantity = StrictIntegerField(min_value=1, max_value=2**31 - 1)

    def check_availability(self, offer, quantity):
        if not offer.shop.state:
            raise serializers.ValidationError({
                'product_info': ['Магазин не принимает заказы.'],
            })
        if quantity > offer.quantity:
            raise serializers.ValidationError({
                'quantity': ['Недостаточный остаток товара.'],
            })


class BasketAddSerializer(BasketQuantitySerializer):
    product_info = serializers.PrimaryKeyRelatedField(
        queryset=ProductInfo.objects.select_related('shop')
        .select_for_update(),
    )

    def validate(self, attrs):
        offer = attrs['product_info']
        item = OrderItem.objects.filter(
            order__user=self.context['request'].user,
            order__state=Order.State.BASKET, product_info=offer,
        ).first()
        quantity = attrs['quantity'] + (item.quantity if item else 0)
        self.check_availability(offer, quantity)
        attrs['quantity'] = quantity
        return attrs

    def create(self, validated_data):
        basket, _ = Order.objects.get_or_create(
            user=self.context['request'].user, state=Order.State.BASKET,
        )
        OrderItem.objects.update_or_create(
            order=basket, product_info=validated_data['product_info'],
            defaults={'quantity': validated_data['quantity']},
        )
        return basket


class BasketUpdateSerializer(BasketQuantitySerializer):
    id = serializers.PrimaryKeyRelatedField(
        source='item', queryset=OrderItem.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].queryset = (
            OrderItem.objects.filter(
                order__user=self.context['request'].user,
                order__state=Order.State.BASKET,
            ).select_related('product_info__shop', 'order').select_for_update()
        )

    def validate(self, attrs):
        self.check_availability(
            attrs['item'].product_info, attrs['quantity'],
        )
        return attrs

    def create(self, validated_data):
        item = validated_data['item']
        item.quantity = validated_data['quantity']
        item.save(update_fields=['quantity'])
        return item.order


class BasketDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=StrictIntegerField(min_value=1), allow_empty=False,
    )

    def validate_ids(self, value):
        ids = set(value)
        found = set(OrderItem.objects.select_for_update().filter(
            order__user=self.context['request'].user,
            order__state=Order.State.BASKET, pk__in=ids,
        ).values_list('pk', flat=True))
        if found != ids:
            raise serializers.ValidationError(
                'Позиции не найдены в вашей корзине.',
            )
        return list(ids)

    def create(self, validated_data):
        basket = Order.objects.get(
            user=self.context['request'].user, state=Order.State.BASKET,
        )
        basket.ordered_items.filter(pk__in=validated_data['ids']).delete()
        return basket


class BasketItemSerializer(serializers.ModelSerializer):
    product_info = serializers.IntegerField(source='product_info_id')
    name = serializers.CharField(source='product_info.product.name')
    shop = ShopSerializer(source='product_info.shop')
    price = serializers.DecimalField(
        source='product_info.price', max_digits=12, decimal_places=2,
    )
    total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            'id', 'product_info', 'name', 'shop', 'price', 'quantity', 'total',
        )
        read_only_fields = fields

    def get_total(self, item):
        return format(item.product_info.price * item.quantity, '.2f')


class BasketSerializer(serializers.ModelSerializer):
    items = BasketItemSerializer(source='ordered_items', many=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'items', 'total')
        read_only_fields = fields

    def get_total(self, basket):
        total = sum((
            item.product_info.price * item.quantity
            for item in basket.ordered_items.all()
        ), Decimal('0.00'))
        return format(total, '.2f')


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ('id', *Contact.ADDRESS_FIELDS)
        read_only_fields = ('id',)

    def validate(self, attrs):
        if self.context['request'].user.contacts.count() >= 5:
            raise serializers.ValidationError(
                'Можно сохранить не более пяти адресов доставки.',
            )
        return attrs


class CheckoutSerializer(serializers.Serializer):
    basket = StrictIntegerField(min_value=1)
    contact = StrictIntegerField(min_value=1)

    def create(self, validated_data):
        try:
            return checkout_order(
                self.context['request'].user,
                validated_data['basket'], validated_data['contact'],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class OrderItemSerializer(BasketItemSerializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=2)

    def get_total(self, item):
        return format(item.price * item.quantity, '.2f')


class OrderSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'dt', 'state', 'total')
        read_only_fields = fields

    def get_total(self, order):
        total = sum((
            item.price * item.quantity for item in order.ordered_items.all()
        ), Decimal('0.00'))
        return format(total, '.2f')


class OrderDetailsSerializer(OrderSerializer):
    items = OrderItemSerializer(source='ordered_items', many=True)

    class Meta(OrderSerializer.Meta):
        fields = (*OrderSerializer.Meta.fields, 'items', 'delivery_address')
        read_only_fields = fields


class StrictFieldsSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                unknown_fields = ', '.join(sorted(unknown))
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f'Неподдерживаемые поля: {unknown_fields}.',
                    ],
                })
        return super().to_internal_value(data)


class PartnerUpdateSerializer(StrictFieldsSerializer):
    yaml = serializers.CharField(trim_whitespace=False)

    def create(self, validated_data):
        try:
            return import_products(
                validated_data['yaml'], self.context['request'].user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'yaml': exc.messages}) from exc
        except RecursionError as exc:
            raise serializers.ValidationError({
                'yaml': ['Слишком глубокая структура YAML.'],
            }) from exc


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail('invalid')
        return super().to_internal_value(data)


class PartnerStateSerializer(StrictFieldsSerializer):
    state = StrictBooleanField()


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        read_only_fields = fields


class PartnerOrderSerializer(OrderSerializer):
    items = OrderItemSerializer(source='supplier_items', many=True)
    recipient = RecipientSerializer(source='user')

    class Meta(OrderSerializer.Meta):
        fields = (
            *OrderSerializer.Meta.fields, 'items', 'delivery_address',
            'recipient',
        )
        read_only_fields = fields

    def get_total(self, order):
        total = sum((
            item.price * item.quantity for item in order.supplier_items
        ), Decimal('0.00'))
        return format(total, '.2f')


class OrderStatusSerializer(StrictFieldsSerializer):
    status = serializers.ChoiceField(choices=[
        (value, label) for value, label in Order.State.choices
        if value != Order.State.BASKET
    ])
