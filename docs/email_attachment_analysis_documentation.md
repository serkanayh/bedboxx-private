# E-posta Ekleri Analiz Özelliği Dokümantasyonu

Bu dokümantasyon, StopSale Automation System'e eklenen e-posta eklerini analiz etme özelliğini detaylı olarak açıklamaktadır. Bu özellik, e-posta içeriğinde stop sale/open sale bilgisi olmadığında, sistem otomatik olarak e-posta eklerini analiz ederek gerekli bilgileri çıkarmaktadır.

## İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Mimari](#mimari)
3. [Bileşenler](#bileşenler)
   - [AttachmentAnalyzer Sınıfı](#attachmentanalyzer-sınıfı)
   - [E-posta İşleme Mantığı](#e-posta-i̇şleme-mantığı)
   - [Ek Analiz Sonuçlarını Onaylama](#ek-analiz-sonuçlarını-onaylama)
   - [Manuel Veri Eşleştirme](#manuel-veri-eşleştirme)
4. [Kullanım Senaryoları](#kullanım-senaryoları)
5. [Teknik Detaylar](#teknik-detaylar)
6. [Test Senaryoları](#test-senaryoları)
7. [Bilinen Sınırlamalar](#bilinen-sınırlamalar)
8. [Gelecek Geliştirmeler](#gelecek-geliştirmeler)

## Genel Bakış

StopSale Automation System, otel rezervasyon sistemlerinde "stop sale" (satış durdurma) ve "open sale" (satış açma) işlemlerini otomatikleştiren bir Django tabanlı web uygulamasıdır. Sistem, e-posta içeriğini Claude AI kullanarak analiz eder ve kullanıcıların bu bilgileri onaylamasını sağlar.

Yeni eklenen özellik, e-posta içeriğinde stop sale/open sale bilgisi olmadığında, sistem otomatik olarak e-posta eklerini analiz ederek gerekli bilgileri çıkarabilmektedir. Bu özellik şu dosya türlerini desteklemektedir:

- PDF dosyaları (.pdf)
- Excel dosyaları (.xlsx, .xls)
- Word dosyaları (.docx, .doc)
- Metin dosyaları (.txt)

## Mimari

E-posta ekleri analiz özelliği, mevcut sistemin üzerine inşa edilmiştir ve şu ana bileşenlerden oluşmaktadır:

1. **AttachmentAnalyzer Sınıfı**: Farklı dosya türlerinden veri çıkarmak için kullanılır.
2. **E-posta İşleme Mantığı**: E-posta içeriği analiz edilemediğinde ekleri işler.
3. **Ek Analiz Sonuçlarını Onaylama Arayüzü**: Kullanıcıların ek analizinden çıkarılan bilgileri onaylamasını sağlar.
4. **Manuel Veri Eşleştirme Arayüzü**: Kullanıcıların veriyi manuel olarak eşleştirmesini sağlar.

## Bileşenler

### AttachmentAnalyzer Sınıfı

`AttachmentAnalyzer` sınıfı, farklı dosya türlerinden stop sale/open sale bilgilerini çıkarmak için kullanılır. Bu sınıf, `/project/core/ai/attachment_analyzer.py` dosyasında bulunmaktadır.

#### Temel Özellikler

- Farklı dosya türlerini analiz etme (PDF, Excel, Word, metin)
- Otel adları, oda tipleri, tarihler ve marketleri çıkarma
- Metin içeriğinden stop sale/open sale bilgilerini çıkarma
- Excel tablolarından yapılandırılmış veri çıkarma

#### Örnek Kullanım

```python
from core.ai.attachment_analyzer import AttachmentAnalyzer

# AttachmentAnalyzer sınıfını başlat
analyzer = AttachmentAnalyzer()

# Bir dosyayı analiz et
result = analyzer.analyze('/path/to/attachment.pdf')

# Sonuçları işle
if 'error' not in result:
    hotels_data = result.get('hotels', [])
    for hotel_data in hotels_data:
        print(f"Hotel: {hotel_data['name']}")
        print(f"Room Type: {hotel_data['room_type']}")
        print(f"Date Range: {hotel_data['date_range']}")
        print(f"Market: {hotel_data['market']}")
        print(f"Action: {hotel_data['action']}")
else:
    print(f"Error: {result['error']}")
```

### E-posta İşleme Mantığı

E-posta işleme mantığı, `process_email_with_ai` ve `process_email_attachments` fonksiyonlarında uygulanmıştır. Bu fonksiyonlar, `/project/emails/views.py` dosyasında bulunmaktadır.

#### İşleyiş

1. Sistem önce e-posta içeriğini Claude AI ile analiz etmeye çalışır.
2. Eğer içerik analizi başarısız olursa ve e-postanın ekleri varsa, `process_email_attachments` fonksiyonu çağrılır.
3. Bu fonksiyon, her eki `AttachmentAnalyzer` kullanarak analiz eder.
4. Analiz sonuçları, `EmailRow` nesneleri olarak veritabanına kaydedilir ve `from_attachment` alanı `True` olarak işaretlenir.
5. Kullanıcı, ek analiz sonuçlarını onaylamak için bir arayüz görür.

### Ek Analiz Sonuçlarını Onaylama

Ek analiz sonuçlarını onaylama arayüzü, kullanıcıların ek analizinden çıkarılan bilgileri incelemesini ve onaylamasını sağlar. Bu arayüz, `/project/templates/emails/confirm_attachment_analysis.html` şablonunda tanımlanmıştır ve `confirm_attachment_analysis` view fonksiyonu tarafından kontrol edilir.

#### Özellikler

- Eklerden çıkarılan tüm satırları görüntüleme
- Satırları seçme/seçimi kaldırma
- Seçilen satırları onaylama
- Onaylanmayan satırları silme

### Manuel Veri Eşleştirme

Manuel veri eşleştirme arayüzü, kullanıcıların çıkarılan verileri Juniper varlıklarıyla manuel olarak eşleştirmesini sağlar. Bu arayüz, `/project/templates/emails/manual_mapping.html` şablonunda tanımlanmıştır ve `manual_mapping` view fonksiyonu tarafından kontrol edilir.

#### Özellikler

- Otel seçme
- Oda tiplerini seçme (tek veya tümü)
- Market seçme
- Tarih aralığını ayarlama
- Satış tipini seçme (stop sale veya open sale)

## Kullanım Senaryoları

### Senaryo 1: E-posta İçeriği Analiz Edilemediğinde Ekleri Analiz Etme

1. Kullanıcı, e-posta detay sayfasında "AI ile İşle" düğmesine tıklar.
2. Sistem, e-posta içeriğini Claude AI ile analiz etmeye çalışır.
3. İçerik analizi başarısız olur ve e-postanın ekleri varsa, sistem otomatik olarak ekleri analiz eder.
4. Analiz sonuçları, kullanıcının onaylaması için görüntülenir.

### Senaryo 2: Ek Analiz Sonuçlarını Onaylama

1. Kullanıcı, eklerden çıkarılan bilgileri içeren bir e-posta detay sayfasını görüntüler.
2. "Ek Analiz Sonuçlarını Onayla" düğmesine tıklar.
3. Sistem, eklerden çıkarılan tüm satırları görüntüler.
4. Kullanıcı, doğru olan satırları seçer ve "Seçilen Satırları Onayla" düğmesine tıklar.
5. Sistem, seçilen satırları kaydeder ve seçilmeyen satırları siler.

### Senaryo 3: Manuel Veri Eşleştirme

1. Kullanıcı, bir e-posta satırı için "Manuel Eşleştir" düğmesine tıklar.
2. Sistem, manuel eşleştirme formunu görüntüler.
3. Kullanıcı, otel, oda tipleri, market, tarih aralığı ve satış tipini seçer.
4. "Eşleştirmeyi Kaydet" düğmesine tıklar.
5. Sistem, eşleştirmeyi kaydeder ve kullanıcıyı e-posta detay sayfasına yönlendirir.

## Teknik Detaylar

### Veritabanı Değişiklikleri

`EmailRow` modeline `from_attachment` alanı eklenmiştir. Bu alan, bir satırın e-posta içeriğinden mi yoksa eklerden mi çıkarıldığını belirtir.

```python
from_attachment = models.BooleanField(default=False, help_text="Whether this row was extracted from an attachment")
```

### Bağımlılıklar

E-posta ekleri analiz özelliği, şu kütüphanelere bağımlıdır:

- **PyPDF2**: PDF dosyalarını işlemek için
- **pandas**: Excel dosyalarını işlemek için
- **openpyxl**: Excel dosyalarını işlemek için pandas tarafından kullanılır
- **python-docx**: Word dosyalarını işlemek için

Bu kütüphaneler, `requirements.txt` dosyasına eklenmelidir:

```
PyPDF2>=3.0.0
pandas>=2.0.0
openpyxl>=3.1.0
python-docx>=0.8.11
```

## Test Senaryoları

E-posta ekleri analiz özelliği, şu test senaryolarıyla test edilmiştir:

1. **AttachmentAnalyzer Testi**: Farklı dosya türlerinden veri çıkarma yeteneğini test eder.
2. **E-posta İşleme Testi**: E-posta içeriği analiz edilemediğinde ekleri işleme yeteneğini test eder.
3. **Ek Analiz Sonuçlarını Onaylama Testi**: Kullanıcıların ek analiz sonuçlarını onaylama yeteneğini test eder.
4. **Manuel Veri Eşleştirme Testi**: Kullanıcıların veriyi manuel olarak eşleştirme yeteneğini test eder.

Test senaryoları, `/project/test_attachment_analyzer.py` ve `/project/test_email_attachment_feature.py` dosyalarında bulunmaktadır.

## Bilinen Sınırlamalar

- **.doc Dosyaları**: .doc dosyaları için tam destek bulunmamaktadır. Bu dosyalar, .docx formatına dönüştürülmelidir.
- **Karmaşık Tablolar**: Karmaşık yapılandırılmış tablolar, doğru şekilde analiz edilemeyebilir.
- **Dil Desteği**: Şu anda İngilizce ve Türkçe dilleri desteklenmektedir. Diğer diller için destek sınırlıdır.
- **OCR Desteği**: Taranan PDF'ler için OCR desteği bulunmamaktadır. Bu dosyalar, metin tabanlı PDF'lere dönüştürülmelidir.

## Gelecek Geliştirmeler

- **OCR Desteği**: Taranan PDF'ler için OCR desteği eklemek.
- **Daha Fazla Dil Desteği**: Daha fazla dil için destek eklemek.
- **Gelişmiş Tablo Analizi**: Karmaşık tabloları daha iyi analiz etmek.
- **Makine Öğrenimi**: Veri çıkarma doğruluğunu artırmak için makine öğrenimi kullanmak.
- **.doc Dosyaları için Tam Destek**: .doc dosyaları için tam destek eklemek.
