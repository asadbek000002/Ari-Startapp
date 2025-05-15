from django.urls import path

from goo.views import GooRegistrationView, list_locations, LocationCreateView, create_order, update_location, \
    detail_location, active_location, UserProfileView, UpdateUserView, LatestContactView, update_order, \
    retry_order_delivery, cancel_order, CustomerOrderView, delete_location

urlpatterns = [
    path('register/', GooRegistrationView.as_view(), name='goo-register'),

    path('locations/', list_locations, name='location-list'),
    path('locations-active/', active_location, name='location-active'),
    path('locations/create/', LocationCreateView.as_view(), name='location-create'),
    path('locations/<int:location_id>/active/', update_location, name='set-active-location'),
    path('locations/<int:location_id>/detail/', detail_location, name='detail-location'),
    path('locations/<int:location_id>/delete/', delete_location, name='delete-location'),

    path('profile-get/', UserProfileView.as_view(), name='get-profile'),
    path('profile/update/', UpdateUserView.as_view(), name='update-profile'),

    path('contact/', LatestContactView.as_view(), name='latest-contact'),

    path("create_order/<int:shop_id>/", create_order, name="create-order"),
    path("orders/<int:order_id>/update/", update_order, name="update_order"),

    path("orders/<int:order_id>/retry/", retry_order_delivery, name="update_order"),

    path('order/<int:order_id>/cancel/', cancel_order, name='cancel_order_goo'),

    path('active/orders/', CustomerOrderView.as_view(), name='courier-orders'),

]
