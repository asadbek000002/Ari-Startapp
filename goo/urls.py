from django.urls import path

from goo.views import list_locations, LocationCreateView, create_order, update_location, \
    detail_location, active_location, UserProfileView, UpdateUserView, LatestContactView, address_order, \
    retry_order_delivery, cancel_order_by_customer, CustomerOrderView, delete_location, PendingSearchingOrdersView, \
    update_and_retry_order, OrderDetailView, complete_order_by_customer, AssignedOrdersView, SendVerificationCodeView, \
    VerifyCodeAndLoginView

urlpatterns = [
    # path('register/', GooRegistrationView.as_view(), name='goo-register'),
    path('send-code/', SendVerificationCodeView.as_view(), name='goo_send_code'),
    path('verify-code/', VerifyCodeAndLoginView.as_view(), name='goo_verify_code'),

    path('locations/', list_locations, name='location_list'),
    path('locations-active/', active_location, name='location_active'),
    path('locations/create/', LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:location_id>/active/', update_location, name='set-active_location'),
    path('locations/<int:location_id>/detail/', detail_location, name='detail_location'),
    path('locations/<int:location_id>/delete/', delete_location, name='delete_location'),

    path('profile-get/', UserProfileView.as_view(), name='get_profile'),
    path('profile/update/', UpdateUserView.as_view(), name='update_profile'),

    path('contact/', LatestContactView.as_view(), name='latest-contact'),

    path("create_order/<int:shop_id>/", create_order, name="create_order"),
    path("orders/<int:order_id>/address/", address_order, name="address_order"),  # ozgartrildi
    path("orders/<int:order_id>/retry-update/", update_and_retry_order, name="retry_update"),
    # yangi qoshildi orderni qayta tahrirlab qayta kuryer izlatish

    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),

    path("orders/<int:order_id>/retry/", retry_order_delivery, name="update_order"),

    path('order/<int:order_id>/cancel/', cancel_order_by_customer, name='cancel_order_goo'),
    path('order/<int:order_id>/feedback/', complete_order_by_customer, name='cancel_order_goo'),

    path('orders/active/<int:id>/', CustomerOrderView.as_view(), name='courier_orders'),

    path('orders/pending-searching/', PendingSearchingOrdersView.as_view(), name='pending_searching_orders'),
    path('orders/assigned/', AssignedOrdersView.as_view(), name='assigned-orders'),

]
