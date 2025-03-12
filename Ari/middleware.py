from django.http import JsonResponse

BLOCKED_PATHS = [
    "/api/",
    "/users/",
]

ALLOWED_PATHS = [
    "/admin/",
    "/swagger/",
    "/redoc/",
    "/swagger/",
    "/open-api/",
]

EXEMPT_USER_AGENTS = [
    "PostmanRuntime",
    "Swagger",
    "Django-Mobile-App",  # Mobil ilovalar uchun User-Agent
]

class BlockAPIMiddleware:
    """Middleware to block API access from browsers"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Agar User-Agent ruxsat berilgan ro‘yxatda bo‘lsa, API ishlaydi
        if any(agent in user_agent for agent in EXEMPT_USER_AGENTS):
            return self.get_response(request)

        # Ruxsat berilgan URL’lar
        if any(request.path.startswith(path) for path in ALLOWED_PATHS):
            return self.get_response(request)

        # Bloklangan URL’lar
        if any(request.path.startswith(path) for path in BLOCKED_PATHS):
            return JsonResponse(
                {"error": "This domain is not allowed."},
                status=403
            )

        return self.get_response(request)
