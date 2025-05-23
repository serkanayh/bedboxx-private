# Generated by Django 5.2 on 2025-05-05 21:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0016_alter_emailhotelmatch_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailrow',
            name='reject_reason',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='emailrow',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('matching', 'Matching in Progress'), ('hotel_not_found', 'Hotel Not Found'), ('room_not_found', 'Room Not Found'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('rejected_hotel_not_found', 'Rejected - JP Hotel Not Found'), ('rejected_room_not_found', 'Rejected - JP Room Not Found'), ('robot_processing', 'Robot Processing'), ('robot_success', 'Robot Success'), ('robot_failed', 'Robot Failed'), ('ignored', 'Ignored')], default='pending', max_length=50),
        ),
    ]
