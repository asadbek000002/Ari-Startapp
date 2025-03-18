from celery import shared_task
from django.utils.timezone import localtime
from django.utils.timezone import localtime, make_aware
from datetime import datetime, timedelta
from shop.models import Shop

@shared_task
def update_shop_status(shop_id, status):
    """Do‘kon holatini yangilash"""
    try:
        shop = Shop.objects.get(id=shop_id)
        shop.is_active = status
        shop.save()
        return f"✅ Shop {shop_id} holati yangilandi: {status}"
    except Shop.DoesNotExist:
        return f"❌ Xatolik: Shop {shop_id} topilmadi"


@shared_task
def schedule_shop_tasks():
    """Har bir do‘kon uchun ochilish va yopilish vaqtlarini avtomatik rejalashtirish"""
    now = localtime()  # Offset-aware datetime
    shops = Shop.objects.all()

    for shop in shops:
        if shop.work_start and shop.work_end:
            open_time = datetime.combine(now.date(), shop.work_start)
            close_time = datetime.combine(now.date(), shop.work_end)

            # Offset-naive datetime obyektlarini offset-aware qilish
            open_time = make_aware(open_time)
            close_time = make_aware(close_time)

            # Agar vaqt kechikkan bo‘lsa, keyingi kunga suramiz
            if open_time < now:
                open_time += timedelta(days=1)
            if close_time < now:
                close_time += timedelta(days=1)

            # Tasklarni rejalashtirish
            update_shop_status.apply_async((shop.id, True), eta=open_time)
            update_shop_status.apply_async((shop.id, False), eta=close_time)

            print(f"🔔 {shop.title} uchun vazifa rejalashtirildi:")
            print(f"   - 📌 Ochiladi: {open_time}")
            print(f"   - ❌ Yopiladi: {close_time}")

    return "✅ Do‘konlar uchun vazifalar muvaffaqiyatli rejalashtirildi!"
