from django.urls import path
from pro.views import ProRegistrationView

urlpatterns = [
    path('register/', ProRegistrationView.as_view(), name='pro-register')
]
