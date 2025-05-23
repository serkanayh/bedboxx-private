# Generated by Django 5.2 on 2025-05-12 07:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0021_alter_email_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='RobotConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('output_directory', models.CharField(help_text='Directory where robot JSON files will be saved', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Robot Configuration',
                'verbose_name_plural': 'Robot Configurations',
            },
        ),
    ]
