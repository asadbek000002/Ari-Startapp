# Generated by Django 5.1.6 on 2025-04-11 14:38

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('pro', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='deliver_profile', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='deliverlocation',
            name='deliver',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliver_locations', to='pro.deliverprofile'),
        ),
    ]
