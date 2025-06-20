from django.urls import path
# ProRegistrationView
from pro.views import DeliverHomeView, DeliverProfileView, ToggleDeliverActiveView, \
    DeliverOrderView, CourierOrderDirectionUpdateView, cancel_order_by_courier, complete_order_by_courier, \
    AssignedOrdersProView, DeliverActiveOrderView, SendProVerificationCodeView, VerifyProCodeLoginView

urlpatterns = [
    # path('register/', ProRegistrationView.as_view(), name='pro_register'),
    path('send-code/', SendProVerificationCodeView.as_view(), name='pro_send_code'),
    path('verify-code/', VerifyProCodeLoginView.as_view(), name='pro_verify_code'),

    path('deliver-home/', DeliverHomeView.as_view(), name='deliver_home'),
    path('deliver-profile/', DeliverProfileView.as_view(), name='deliver_profile'),
    path("deliver-active/", ToggleDeliverActiveView.as_view(), name="toggle_deliver_active"),

    path('order/<int:order_id>/cancel/', cancel_order_by_courier, name='cancel_order_pro'),

    path('active/orders/<int:id>/', DeliverOrderView.as_view(), name='courier_orders'),
    path('active/orders/', DeliverActiveOrderView.as_view(), name='courier_orders'),
    path('orders/assigned/', AssignedOrdersProView.as_view(), name='assigned_orders'),
    path('order/<int:order_id>/direction/', CourierOrderDirectionUpdateView.as_view()),
    path('order/<int:order_id>/feedback/', complete_order_by_courier, name='cancel_order_pro'),

]
