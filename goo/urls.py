from django.urls import path

from goo.views import GooRegistrationView, list_locations, LocationCreateView, create_order, update_location, \
    detail_location, active_location, UserProfileView, UpdateUserView, LatestContactView

urlpatterns = [
    path('register/', GooRegistrationView.as_view(), name='goo-register'),

    path('locations/', list_locations, name='location-list'),
    path('locations-active/', active_location, name='location-active'),
    path('locations/create/', LocationCreateView.as_view(), name='location-create'),
    path('locations/<int:location_id>/active/', update_location, name='set-active-location'),
    path('locations/<int:location_id>/detail/', detail_location, name='set-active-location'),

    path('profile-get/', UserProfileView.as_view(), name='get-profile'),
    path('profile/update/', UpdateUserView.as_view(), name='update-profile'),

    path('contact/', LatestContactView.as_view(), name='latest-contact'),

    path("shops/<int:shop_id>/order/", create_order, name="create-order"),

]
