# Generated by Django 5.1.6 on 2025-04-11 14:38

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('telegram_link', models.URLField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('items', models.TextField()),
                ('allow_other_shops', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('assigned', 'Assigned'), ('completed', 'Completed')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('variants', models.CharField(blank=True, help_text='Foizlar vergul bilan ajratiladi (masalan: 1%, 1.5%, 2%)', max_length=255)),
            ],
        ),
    ]
