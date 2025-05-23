# Generated by Django 5.2 on 2025-05-01 14:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0012_alter_emailattachment_file_and_more'),
        ('hotels', '0006_remove_marketalias_market_marketalias_markets'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomTypeMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_room_type', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('juniper_room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hotels.room')),
            ],
            options={
                'verbose_name': 'Room Type Match',
                'verbose_name_plural': 'Room Type Matches',
                'unique_together': {('email_room_type', 'juniper_room')},
            },
        ),
    ]
