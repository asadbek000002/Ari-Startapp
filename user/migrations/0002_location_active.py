# Generated by Django 5.1.6 on 2025-03-11 17:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='active',
            field=models.BooleanField(default=False),
        ),
    ]
