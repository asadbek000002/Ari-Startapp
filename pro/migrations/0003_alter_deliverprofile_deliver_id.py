# Generated by Django 5.1.6 on 2025-05-02 15:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pro', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deliverprofile',
            name='deliver_id',
            field=models.CharField(editable=False, max_length=8, unique=True),
        ),
    ]
