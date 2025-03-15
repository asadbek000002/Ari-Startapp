from modeltranslation.translator import register, TranslationOptions
from .models import Shop, ShopRole, Advertising


@register(Shop)
class ShopTranslationOptions(TranslationOptions):
    fields = ('title', 'locations', 'about')  # Ko‘p tilli maydonlar


@register(ShopRole)
class ShopRoleTranslationOptions(TranslationOptions):
    fields = ('name',)  # Ko‘p tilli maydon


@register(Advertising)
class AdvertisingTranslationOptions(TranslationOptions):
    fields = ('title', 'text')  # Tarjima qilinadigan maydonlar
