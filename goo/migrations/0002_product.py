# Generated by Django 5.1.6 on 2025-03-12 10:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goo', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('percentages', models.CharField(blank=True, help_text='Foizlar vergul bilan ajratiladi (masalan: 1%, 1.5%, 2%)', max_length=255)),
            ],
        ),
    ]
