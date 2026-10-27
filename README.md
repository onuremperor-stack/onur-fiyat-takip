# Onur Fiyat Takip

Miniöde ürünlerini Akakçe ve Cimri ile karşılaştıran bağımsız fiyat takip uygulaması.

## Özellikler

- Miniöde Shopify kataloğunu kategori bazında okur.
- Akakçe ve Cimri'yi ayrı ayrı tarar.
- İki kaynaktan bulunan en düşük doğrulanmış fiyatı referans alır.
- Sıfır, outlet, teşhir ve yenilenmiş ürünleri farklı kurallarla değerlendirir.
- Sonuçları biçimlendirilmiş Excel raporuna aktarır.
- Her taramayı yerel SQLite fiyat geçmişine kaydeder.
- İsteğe bağlı Telegram özeti ve Excel raporu gönderir.
- Chrome yardımcısı yüklüyse normal Chrome oturumunu tarama için otomatik kullanır.
- GitHub Actions ile her gece 03.00 Türkiye saatinde çalışabilir.

## Windows kurulumu

1. Bilgisayarda Python 3.11 veya daha yeni bir sürümün kurulu olduğundan emin olun.
2. `kurulum.bat` dosyasına çift tıklayın.
3. Kurulum tamamlanınca `baslat.bat` dosyasına çift tıklayın.
4. Tarayıcıda açılan panelden kategori ve filtreleri seçip taramayı başlatın.

## Chrome yardımcısı

Chrome'da `chrome://extensions` adresini açın, **Geliştirici modu**nu etkinleştirin
ve **Paketlenmemiş öğe yükle** ile `chrome-extension` klasörünü seçin. Chrome açıkken
uygulamada taramayı başlatmanız yeterlidir. Uygulama tarama sırasında yalnızca
`127.0.0.1:8765` üzerinde yerel bir köprü açar; eklenti buradan işleri alır ve
Akakçe/Cimri sonuçlarını geri gönderir. Yardımcı yanıt vermezse uygulama yerleşik
tarayıcı yöntemine geri döner.

## Telegram ayarı

`.streamlit/secrets.toml.example` dosyasını `.streamlit/secrets.toml` adıyla kopyalayın:

```toml
TELEGRAM_BOT_TOKEN = "BotFather tarafından verilen yeni token"
TELEGRAM_CHAT_ID = "Telegram sohbet kimliği"
```

Bu dosyayı GitHub'a yüklemeyin. `.gitignore` bunu otomatik olarak engeller.

GitHub gece taraması için aynı iki adı depo ayarlarında **Settings → Secrets and variables → Actions** altında repository secret olarak oluşturun.

## Testler

```powershell
python -m unittest discover -s tests -v
```

## Önemli not

Akakçe veya Cimri sayfa yapısını değiştirdiğinde seçicilerin güncellenmesi gerekebilir. Uygulama erişim engeli veya hız sınırı gördüğünde bunu aşmaya çalışmaz; sonuç ilgili kaynak için bulunamadı olarak kaydedilir.

