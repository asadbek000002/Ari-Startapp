from django.urls import path
from pro.views import ProRegistrationView, DeliverHomeView, DeliverProfileView, ToggleDeliverActiveView

urlpatterns = [
    path('register/', ProRegistrationView.as_view(), name='pro-register'),

    path('deliver-home/', DeliverHomeView.as_view(), name='deliver-home'),
    path('deliver-profile/', DeliverProfileView.as_view(), name='deliver-profile'),
    path("deliver-active/", ToggleDeliverActiveView.as_view(), name="toggle-deliver-active"),
]
