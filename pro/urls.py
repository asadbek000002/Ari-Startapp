from django.urls import path
from pro.views import ProRegistrationView, DeliverProfileView

urlpatterns = [
    path('register/', ProRegistrationView.as_view(), name='pro-register'),

    path('deliver-profile/', DeliverProfileView.as_view(), name='deliver-profile'),
]
