from django.db.models.signals import post_save
from django.dispatch import receiver
from shop.models import Shop
from shop.tasks import schedule_shop_tasks

@receiver(post_save, sender=Shop)
def schedule_tasks_on_save(sender, instance, created, **kwargs):
    """Do‘kon yaratilgan yoki yangilanganida taskni rejalashtirish"""
    if created:  # Agar do‘kon yangi yaratilgan bo‘lsa
        print(f"🔔 Do‘kon yaratildi: {instance.title}")
        schedule_shop_tasks.delay()
    else:
        print(f"🔔 Do‘kon yangilandi: {instance.title}")
        schedule_shop_tasks.delay()
