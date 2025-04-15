from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from user.models import User  # Custom User model bo‘lsa shu joyni o'zgartiring


@database_sync_to_async
def get_user(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        headers = dict(scope['headers'])
        token = None

        if b'authorization' in headers:
            auth_header = headers[b'authorization'].decode()
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        scope['user'] = await get_user(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
