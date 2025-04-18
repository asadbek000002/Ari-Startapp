# goo/routing.py
from django.urls import re_path
from .consumers import OrderOfferConsumer
from user.middleware import TokenAuthMiddleware

websocket_urlpatterns = [
    re_path(r'ws/goo/connect/$', TokenAuthMiddleware(OrderOfferConsumer.as_asgi())),
    re_path(r'ws/pro/connect/$', TokenAuthMiddleware(OrderOfferConsumer.as_asgi())),
    re_path(r'ws/shop/connect/$', TokenAuthMiddleware(OrderOfferConsumer.as_asgi())),
]
