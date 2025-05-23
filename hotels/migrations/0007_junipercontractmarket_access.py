# Generated by Django 5.2 on 2025-05-17 19:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0006_remove_marketalias_market_marketalias_markets'),
    ]

    operations = [
        migrations.AddField(
            model_name='junipercontractmarket',
            name='access',
            field=models.CharField(choices=[('Allowed', 'Allowed'), ('Denied', 'Denied')], default='Allowed', help_text='Whether this market has access to this contract (Allowed/Denied).', max_length=10),
        ),
    ]
