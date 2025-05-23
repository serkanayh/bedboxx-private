# Generated by Django 4.2.7 on 2025-04-21 23:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0010_remove_emailrow_market_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailrow",
            name="source_attachment",
            field=models.ForeignKey(
                blank=True,
                help_text="The specific attachment this row was extracted from, if any.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_rows",
                to="emails.emailattachment",
            ),
        ),
    ]
