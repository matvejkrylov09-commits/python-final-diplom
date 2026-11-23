"""Маршруты приложения backend."""

from django.urls import path
from django_rest_passwordreset.views import (
    reset_password_confirm,
    reset_password_request_token,
)

from .views import (
    BasketView,
    CategoryListView,
    ConfirmEmailView,
    ContactDeleteView,
    ContactListCreateView,
    LoginView,
    LogoutView,
    OrderDetailsView,
    OrderListCreateView,
    OrderStatusView,
    PartnerOrdersView,
    PartnerStateView,
    PartnerUpdateView,
    ProductDetailsView,
    ProductListView,
    RegisterView,
    ShopListView,
    UserDetailsView,
)

app_name = 'backend'
urlpatterns = [
    path('user/register/', RegisterView.as_view(), name='user-register'),
    path(
        'user/register/confirm/', ConfirmEmailView.as_view(),
        name='user-register-confirm',
    ),
    path('user/login/', LoginView.as_view(), name='user-login'),
    path('user/logout/', LogoutView.as_view(), name='user-logout'),
    path('user/details/', UserDetailsView.as_view(), name='user-details'),
    path(
        'user/contacts/', ContactListCreateView.as_view(), name='contacts',
    ),
    path(
        'user/contacts/<int:pk>/', ContactDeleteView.as_view(),
        name='contact-delete',
    ),
    path('basket/', BasketView.as_view(), name='basket'),
    path('orders/', OrderListCreateView.as_view(), name='orders'),
    path('orders/<int:pk>/', OrderDetailsView.as_view(), name='order-details'),
    path(
        'orders/<int:pk>/status/', OrderStatusView.as_view(),
        name='order-status',
    ),
    path(
        'partner/update/', PartnerUpdateView.as_view(), name='partner-update',
    ),
    path('partner/state/', PartnerStateView.as_view(), name='partner-state'),
    path(
        'partner/orders/', PartnerOrdersView.as_view(), name='partner-orders',
    ),
    path(
        'user/password_reset/', reset_password_request_token,
        name='password-reset',
    ),
    path(
        'user/password_reset/confirm/', reset_password_confirm,
        name='password-reset-confirm',
    ),
    path('shops/', ShopListView.as_view(), name='shops'),
    path('categories/', CategoryListView.as_view(), name='categories'),
    path('products/', ProductListView.as_view(), name='products'),
    path(
        'products/<int:pk>/', ProductDetailsView.as_view(),
        name='product-details',
    ),
]
