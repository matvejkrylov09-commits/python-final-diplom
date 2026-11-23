"""API покупателей, поставщиков, каталога и заказов."""

import logging
import re
import sqlite3

from django.conf import settings
from django.core.mail import send_mail
from django.db import (
    DatabaseError,
    IntegrityError,
    OperationalError,
    connection,
    transaction,
)
from django.db.models import Prefetch
from django.urls import reverse
from rest_framework import generics, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Category,
    ConfirmEmailToken,
    Contact,
    Order,
    OrderItem,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)
from .permissions import IsBuyer, IsSupplier
from .serializers import (
    BasketAddSerializer,
    BasketDeleteSerializer,
    BasketSerializer,
    BasketUpdateSerializer,
    CategorySerializer,
    CheckoutSerializer,
    ConfirmEmailSerializer,
    ContactSerializer,
    LoginSerializer,
    OrderDetailsSerializer,
    OrderSerializer,
    OrderStatusSerializer,
    PartnerOrderSerializer,
    PartnerStateSerializer,
    PartnerUpdateSerializer,
    ProductFilterSerializer,
    ProductInfoSerializer,
    RegisterSerializer,
    ShopSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class RegisterView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                token = ConfirmEmailToken.objects.create(user=user)
                send_mail(
                    'Подтверждение регистрации',
                    f'Токен подтверждения email: {token.key}\n'
                    'Отправьте token методом POST на '
                    f'{reverse("backend:user-register-confirm")}.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
        except IntegrityError as exc:
            raise serializers.ValidationError({
                'email': ['Этот email уже зарегистрирован.'],
            }) from exc
        return Response(
            {'detail': 'Проверьте почту для подтверждения регистрации.'},
            status=status.HTTP_201_CREATED,
        )


class ConfirmEmailView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = ConfirmEmailSerializer

    @transaction.atomic
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = (
            ConfirmEmailToken.objects.select_related('user')
            .select_for_update()
            .filter(key=serializer.validated_data['token']).first()
        )
        if token is None:
            raise serializers.ValidationError({
                'token': ['Токен недействителен или уже использован.'],
            })
        user = token.user
        user.is_active = True
        user.save(update_fields=['is_active'])
        user.confirm_email_tokens.all().delete()
        return Response({'detail': 'Email подтверждён.'})


class LoginView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, _ = Token.objects.get_or_create(
            user=serializer.validated_data['user'],
        )
        return Response({'token': token.key})


class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserDetailsView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ShopListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ShopSerializer
    queryset = Shop.objects.order_by('pk')


class CategoryListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.order_by('pk')


class ProductListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ProductInfoSerializer
    queryset = (
        ProductInfo.objects.select_related('product__category', 'shop')
        .prefetch_related(Prefetch(
            'product_parameters',
            queryset=ProductParameter.objects.select_related('parameter')
            .order_by('pk'),
        )).order_by('pk')
    )

    def get_queryset(self):
        filters = ProductFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = super().get_queryset()
        if 'category' in values:
            queryset = queryset.filter(product__category_id=values['category'])
        if 'shop' in values:
            queryset = queryset.filter(shop_id=values['shop'])
        if values.get('search'):
            # В SQLite LIKE не сопоставляет регистр кириллицы.
            queryset = queryset.filter(
                product__name__iregex=re.escape(values['search']),
            )
        return queryset


class ProductDetailsView(generics.RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ProductInfoSerializer
    queryset = ProductListView.queryset


class BasketView(generics.GenericAPIView):
    permission_classes = (IsBuyer,)
    serializer_class = BasketSerializer

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user, state=Order.State.BASKET,
        ).prefetch_related(Prefetch(
            'ordered_items',
            queryset=OrderItem.objects.select_related(
                'product_info__product', 'product_info__shop',
            ).order_by('pk'),
        ))

    def basket_response(self):
        basket = self.get_queryset().first()
        if basket is None:
            return Response({'id': None, 'items': [], 'total': '0.00'})
        return Response(self.get_serializer(basket).data)

    def get(self, request):
        return self.basket_response()

    def change_basket(self, request, serializer_class):
        with transaction.atomic():
            # Параллельные добавления не должны терять количество.
            User.objects.select_for_update().get(pk=request.user.pk)
            serializer = serializer_class(
                data=request.data, context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return self.basket_response()

    def post(self, request):
        return self.change_basket(request, BasketAddSerializer)

    def put(self, request):
        return self.change_basket(request, BasketUpdateSerializer)

    def delete(self, request):
        return self.change_basket(request, BasketDeleteSerializer)


class ContactListCreateView(generics.ListCreateAPIView):
    serializer_class = ContactSerializer

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user).order_by('pk')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        User.objects.select_for_update().get(pk=request.user.pk)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ContactDeleteView(generics.DestroyAPIView):
    serializer_class = ContactSerializer

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        User.objects.select_for_update().get(pk=request.user.pk)
        return super().destroy(request, *args, **kwargs)


def _user_orders(user):
    return Order.objects.filter(user=user).exclude(
        state=Order.State.BASKET,
    ).prefetch_related(Prefetch(
        'ordered_items',
        queryset=OrderItem.objects.select_related(
            'product_info__product', 'product_info__shop',
        ).order_by('pk'),
    )).order_by('-dt', '-pk')


class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsBuyer,)
    serializer_class = OrderSerializer

    def get_queryset(self):
        return _user_orders(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = CheckoutSerializer(
            data=request.data, context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        try:
            order = serializer.save()
        except OperationalError as exc:
            code = getattr(exc.__cause__, 'sqlite_errorcode', 0)
            if connection.vendor != 'sqlite' or code & 255 not in (
                sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED,
            ):
                raise
            return Response(
                {'detail': 'База занята. Повторите оформление позже.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({'id': order.pk}, status=status.HTTP_201_CREATED)


class OrderDetailsView(generics.RetrieveAPIView):
    permission_classes = (IsBuyer,)
    serializer_class = OrderDetailsSerializer

    def get_queryset(self):
        return _user_orders(self.request.user)


class PartnerUpdateView(generics.GenericAPIView):
    permission_classes = (IsSupplier,)
    serializer_class = PartnerUpdateSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except DatabaseError as exc:
            logger.exception('Ошибка сохранения прайса поставщика.')
            raise APIException('Не удалось сохранить прайс.') from exc
        return Response(result)


def _partner_shop(user, lock=False):
    queryset = Shop.objects.filter(user=user)
    if lock:
        queryset = queryset.select_for_update()
    shop = queryset.first()
    if shop is None:
        raise NotFound('Магазин ещё не создан. Сначала загрузите прайс.')
    return shop


class PartnerStateView(generics.GenericAPIView):
    permission_classes = (IsSupplier,)
    serializer_class = PartnerStateSerializer

    def get(self, request):
        return Response(ShopSerializer(_partner_shop(request.user)).data)

    @transaction.atomic
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = _partner_shop(request.user, lock=True)
        shop.state = serializer.validated_data['state']
        shop.save(update_fields=['state'])
        return Response(ShopSerializer(shop).data)


class PartnerOrdersView(generics.ListAPIView):
    permission_classes = (IsSupplier,)
    serializer_class = PartnerOrderSerializer

    def get_queryset(self):
        shop = _partner_shop(self.request.user)
        items = OrderItem.objects.filter(
            product_info__shop=shop,
        ).select_related('product_info__product', 'product_info__shop')
        return Order.objects.filter(
            ordered_items__product_info__shop=shop,
        ).exclude(state=Order.State.BASKET).distinct().select_related(
            'user',
        ).prefetch_related(Prefetch(
            'ordered_items', queryset=items.order_by('pk'),
            to_attr='supplier_items',
        )).order_by('-dt', '-pk')


class OrderStatusView(generics.GenericAPIView):
    permission_classes = (IsAdminUser,)
    serializer_class = OrderStatusSerializer

    @transaction.atomic
    def patch(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = Order.objects.select_for_update().filter(pk=pk).first()
        if order is None:
            raise NotFound('Заказ не найден.')
        if order.state == Order.State.BASKET:
            raise serializers.ValidationError({
                'status': ['Нельзя менять статус корзины.'],
            })
        new_status = serializer.validated_data['status']
        if order.state != new_status:
            order.state = new_status
            order.save(update_fields=['state'])
        return Response({'id': order.pk, 'status': order.state})
