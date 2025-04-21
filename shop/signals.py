from django.db.models.signals import post_save
from django.dispatch import receiver
from shop.models import Shop
from shop.tasks import schedule_shop_tasks


@receiver(post_save, sender=Shop)
def schedule_tasks_on_save(sender, instance, created, **kwargs):
    """Do'kon yaratilgan yoki yangilanganida taskni rejalashtirish"""
    # Skip if _skip_signal flag is set
    if hasattr(instance, '_skip_signal') and instance._skip_signal:
        return

    # Schedule tasks only for this specific shop
    schedule_shop_tasks.delay(instance.id)