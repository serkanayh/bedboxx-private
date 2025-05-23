# Generated by Django 5.2 on 2025-04-12 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS hotels_market_temp;",
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            "CREATE TABLE hotels_market_temp AS SELECT id, mail_market_name as name, market_code as juniper_code, 1 as is_active, created_at, updated_at FROM hotels_market;",
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            "DROP TABLE hotels_market;",
            migrations.RunSQL.noop
        ),
        migrations.CreateModel(
            name='Market',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('juniper_code', models.CharField(blank=True, max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Market',
                'verbose_name_plural': 'Markets',
                'ordering': ['name'],
            },
        ),
        migrations.RunSQL(
            "INSERT INTO hotels_market SELECT id, name, juniper_code, is_active, created_at, updated_at FROM hotels_market_temp;",
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            "DROP TABLE hotels_market_temp;",
            migrations.RunSQL.noop
        ),
    ]
