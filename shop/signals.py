from django.db.models.signals import post_save
from django.dispatch import receiver
from shop.models import Shop
from shop.tasks import schedule_shop_tasks

@receiver(post_save, sender=Shop)
def schedule_tasks_on_save(sender, instance, **kwargs):
    """Shop saqlanganda Celery tasklarini ishga tushirish"""
    schedule_shop_tasks.delay()
