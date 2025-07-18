def update_shop_rating(shop):
    feedbacks = shop.feedbacks.all()
    ratings = [f.rating for f in feedbacks if f.rating is not None]
    if ratings:
        avg = sum(ratings) / len(ratings)
        shop.rating = round(avg, 2)
    else:
        shop.rating = 0
    shop.save(update_fields=['rating'])
