# Generated by Django 5.2 on 2025-05-23 08:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0025_alter_email_status_emailblocklist'),
    ]

    operations = [
        migrations.AddField(
            model_name='email',
            name='robot_status',
            field=models.CharField(choices=[('pending', 'Bekliyor'), ('processing', 'İşleniyor'), ('processed', 'Tamamlandı'), ('error', 'Hata')], default='pending', max_length=20),
        ),
    ]
