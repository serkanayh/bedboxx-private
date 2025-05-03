# StopSale Automation System - Dokümantasyon

## Genel Bakış

StopSale Automation System, otel rezervasyon sistemlerinde "stop sale" (satış durdurma) ve "open sale" (satış açma) işlemlerini otomatikleştiren bir Django tabanlı web uygulamasıdır. Sistem, e-posta içeriklerini Claude AI kullanarak analiz eder ve kullanıcıların bu bilgileri onaylamasını sağlar.

## Sistem Bileşenleri

### 1. AI Analiz Bileşeni

AI Analiz Bileşeni, e-posta içeriklerini analiz ederek yapılandırılmış veri çıkarmak için Claude AI'yı kullanır. Bu bileşen şu özelliklere sahiptir:

- **Prompt Optimizasyonu ve A/B Testi**: Farklı prompt versiyonlarını test eder ve en iyi performansı gösteren promptu seçer.
- **Ek Dosya Formatları Desteği**: PDF, Excel, Word ve CSV dosyalarından veri çıkarma yetenekleri.
- **Çoklu Dil Desteği**: Türkçe, İngilizce, Almanca, İspanyolca ve Fransızca için özel destek.
- **Geliştirilmiş Analizör**: Performans metrikleri ve raporlama özellikleri ile zenginleştirilmiş analiz.

### 2. Performans Optimizasyonları

Performans Optimizasyonları, sistemin daha hızlı ve verimli çalışmasını sağlar:

- **Veritabanı Optimizasyonu**: Veritabanı indeksleme ve sorgu optimizasyonu.
- **Önbellek Mekanizması**: Redis tabanlı önbellek sistemi ile sık kullanılan verileri önbelleğe alma.
- **Asenkron İşleme**: Zaman alıcı görevleri arka planda işleme.

### 3. Güvenlik İyileştirmeleri

Güvenlik İyileştirmeleri, sistemin güvenliğini artırır:

- **Güvenli API Anahtarı Yönetimi**: API anahtarlarını ve hassas kimlik bilgilerini güvenli bir şekilde depolama.
- **Hassas Veri Şifreleme**: Kişisel bilgiler, kimlik bilgileri ve iş açısından kritik verileri şifreleme.
- **Gelişmiş Kimlik Doğrulama ve Yetkilendirme**: Rol tabanlı erişim kontrolü ve güvenli oturum yönetimi.

### 4. Kod Kalitesi İyileştirmeleri

Kod Kalitesi İyileştirmeleri, kodun bakımını ve genişletilmesini kolaylaştırır:

- **Birim Test Çerçevesi**: Kapsamlı birim test sınıfları ve yardımcı fonksiyonlar.
- **Bağımlılık Yönetimi**: Proje bağımlılıklarını yönetme ve izleme araçları.
- **Kod Stili ve Dokümantasyon**: Kod stili standartlarını uygulama ve otomatik dokümantasyon oluşturma.

## Kurulum

### Sistem Gereksinimleri

- Python 3.8+
- Django 4.2+
- PostgreSQL 12+
- Redis (önbellek ve asenkron işleme için)

### Kurulum Adımları

1. Projeyi klonlayın:
   ```
   git clone https://github.com/your-organization/stopsale-automation.git
   cd stopsale-automation
   ```

2. Sanal ortam oluşturun ve etkinleştirin:
   ```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate  # Windows
   ```

3. Bağımlılıkları yükleyin:
   ```
   pip install -r requirements.txt
   ```

4. Veritabanını oluşturun:
   ```
   python manage.py migrate
   ```

5. Yönetici kullanıcısı oluşturun:
   ```
   python manage.py createsuperuser
   ```

6. Geliştirme sunucusunu başlatın:
   ```
   python manage.py runserver
   ```

## Yapılandırma

### Ortam Değişkenleri

Aşağıdaki ortam değişkenlerini `.env` dosyasında tanımlayın:

```
# Django
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:password@localhost:5432/stopsale

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Claude AI
CLAUDE_API_KEY=your-claude-api-key

# Security
SECURE_SSL_REDIRECT=False
```

### Django Ayarları

Performans ve güvenlik ayarlarını entegre etmek için:

```python
# settings.py

# Performans ayarlarını entegre et
from performance.settings_integration import integrate_all_performance_settings
integrate_all_performance_settings(sys.modules[__name__])

# Güvenlik ayarlarını entegre et
from security.settings_integration import integrate_security_settings
integrate_security_settings(sys.modules[__name__])
```

## Kullanım

### E-posta İşleme

1. E-posta alındığında, sistem e-posta içeriğini otomatik olarak analiz eder.
2. Analiz sonuçları kullanıcıya gösterilir.
3. Kullanıcı, analiz sonuçlarını onaylar veya düzenler.
4. Onaylanan veriler, otel rezervasyon sistemine gönderilir.

### Yönetim Arayüzü

Yönetim arayüzü şu özelliklere sahiptir:

- E-posta işleme durumunu izleme
- Otel ve oda bilgilerini yönetme
- Kullanıcı ve rol yönetimi
- Sistem ayarlarını yapılandırma

## Geliştirme

### Kod Stili

Kod stili kontrolü için:

```
python -m code_quality.management_commands CheckCodeStyleCommand
```

### Testler

Testleri çalıştırmak için:

```
python -m code_quality.management_commands RunTestsCommand
```

### Dokümantasyon

Dokümantasyon oluşturmak için:

```
python -m code_quality.management_commands GenerateDocsCommand
```

### Entegrasyon Testleri

Entegrasyon testlerini çalıştırmak için:

```
python integration_test.py
```

## Lisans

Bu proje [LICENSE](LICENSE) dosyasında belirtilen lisans altında dağıtılmaktadır.
