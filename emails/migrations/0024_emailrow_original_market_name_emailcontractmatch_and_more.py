# Generated by Django 5.2 on 2025-05-20 18:22

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0023_add_selected_contracts_field'),
        ('hotels', '0007_junipercontractmarket_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailrow',
            name='original_market_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.CreateModel(
            name='EmailContractMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_hotel_name', models.CharField(max_length=255, verbose_name='Kaynak Otel Adı')),
                ('source_room_type', models.CharField(max_length=255, verbose_name='Kaynak Oda Tipi')),
                ('source_market_names', models.CharField(blank=True, max_length=500, null=True, verbose_name='Kaynak Pazar Adları (virgülle ayrılmış)')),
                ('matched_contracts', models.CharField(max_length=500, verbose_name='Eşleşen Kontratlar (virgülle ayrılmış)')),
                ('confidence_score', models.IntegerField(default=80, help_text='Bu eşleştirmenin güven puanı (0-100)', verbose_name='Güven Puanı')),
                ('match_count', models.IntegerField(default=1, help_text='Kaç kez eşleştirildi', verbose_name='Eşleştirme Sayısı')),
                ('first_matched_at', models.DateTimeField(auto_now_add=True, verbose_name='İlk Eşleştirme')),
                ('last_matched_at', models.DateTimeField(auto_now=True, verbose_name='Son Eşleştirme')),
                ('email_row_sample', models.ForeignKey(blank=True, help_text='Bu eşleşmenin öğrenildiği örnek satır (opsiyonel)', null=True, on_delete=django.db.models.deletion.SET_NULL, to='emails.emailrow', verbose_name='Örnek E-posta Satırı')),
                ('juniper_hotel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contract_matches', to='hotels.hotel', verbose_name='Juniper Otel')),
                ('juniper_markets', models.ManyToManyField(blank=True, related_name='contract_matches', to='hotels.market', verbose_name='Juniper Pazarlar')),
                ('juniper_rooms', models.ManyToManyField(blank=True, related_name='contract_matches', to='hotels.room', verbose_name='Juniper Odalar')),
            ],
            options={
                'verbose_name': 'E-posta Kontrat Eşleştirmesi',
                'verbose_name_plural': 'E-posta Kontrat Eşleştirmeleri',
                'ordering': ('-match_count', 'source_hotel_name'),
            },
        ),
        migrations.CreateModel(
            name='EmailMarketMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_market_name', models.CharField(max_length=255, verbose_name='E-postadaki Pazar Adı')),
                ('confidence_score', models.IntegerField(default=80, help_text='Bu eşleştirmenin güven puanı (0-100)', verbose_name='Güven Puanı')),
                ('match_count', models.IntegerField(default=1, help_text='Kaç kez eşleştirildi', verbose_name='Eşleştirme Sayısı')),
                ('first_matched_at', models.DateTimeField(auto_now_add=True, verbose_name='İlk Eşleştirme')),
                ('last_matched_at', models.DateTimeField(auto_now=True, verbose_name='Son Eşleştirme')),
                ('juniper_market', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_matches', to='hotels.market', verbose_name='Juniper Pazar')),
            ],
            options={
                'verbose_name': 'E-posta Pazar Eşleştirmesi',
                'verbose_name_plural': 'E-posta Pazar Eşleştirmeleri',
                'ordering': ('-match_count', 'email_market_name'),
                'unique_together': {('email_market_name', 'juniper_market')},
            },
        ),
    ]
