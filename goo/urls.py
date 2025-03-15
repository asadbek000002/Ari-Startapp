from django.urls import path

from goo.views import GooRegistrationView, list_locations, LocationCreateView, create_order, set_active_location

urlpatterns = [
    path('register/', GooRegistrationView.as_view(), name='goo-register'),

    path('locations/', list_locations, name='location-list'),
    path('locations/create/', LocationCreateView.as_view(), name='location-create'),
    path('locations/<int:location_id>/active/', set_active_location, name='set-active-location'),

    path("shops/<int:shop_id>/order/", create_order, name="create-order"),

]
