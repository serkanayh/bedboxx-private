# Generated by Django 4.2.7 on 2025-04-21 11:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotels", "0005_marketalias_junipercontractmarket"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="marketalias",
            name="market",
        ),
        migrations.AddField(
            model_name="marketalias",
            name="markets",
            field=models.ManyToManyField(
                help_text="The canonical Juniper Market(s) this alias maps to.",
                related_name="aliases",
                to="hotels.market",
            ),
        ),
    ]
