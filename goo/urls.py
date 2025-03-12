from django.urls import path

from goo.views import GooRegistrationView, LocationListView, LocationCreateView, create_order

urlpatterns = [
    path('register/', GooRegistrationView.as_view(), name='goo-register'),

    path('locations/', LocationListView.as_view(), name='location-list'),
    path('locations/create/', LocationCreateView.as_view(), name='location-create'),

    path("shops/<int:shop_id>/order/", create_order, name="create-order"),

]
