from django.urls import path

from goo.views import cancel_order
from pro.views import ProRegistrationView, DeliverHomeView, DeliverProfileView, ToggleDeliverActiveView, \
    DeliverOrderView, CourierOrderDirectionUpdateView

urlpatterns = [
    path('register/', ProRegistrationView.as_view(), name='pro-register'),

    path('deliver-home/', DeliverHomeView.as_view(), name='deliver-home'),
    path('deliver-profile/', DeliverProfileView.as_view(), name='deliver-profile'),
    path("deliver-active/", ToggleDeliverActiveView.as_view(), name="toggle-deliver-active"),

    path('order/<int:order_id>/cancel/', cancel_order, name='cancel_order_pro'),

    path('active/orders/', DeliverOrderView.as_view(), name='courier-orders'),
    path('order/<int:order_id>/direction/', CourierOrderDirectionUpdateView.as_view()),

]
