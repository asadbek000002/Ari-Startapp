def update_user_rating(user):
    feedbacks = user.received_feedbacks.all()
    ratings = [f.rating for f in feedbacks if f.rating is not None]
    if ratings:
        avg = sum(ratings) / len(ratings)
        user.rating = round(avg, 2)
    else:
        user.rating = 0
    user.save(update_fields=['rating'])
