# HousingBot — Berlin Ev Arama & Otomatik Başvuru Botu

Berlin'de kiralık ev ilanlarını düzenli aralıklarla tarar, kriterlerine uyan **yeni** ilanları bulur, Telegram'dan haber verir ve istersen ilan sahibine otomatik başvuru mesajı gönderir.

Desteklenen siteler:

| Site | Tarama | Otomatik başvuru |
|---|---|---|
| [WG-Gesucht](https://www.wg-gesucht.de) | ✅ | ✅ (e-posta + şifre ile login) |
| [Kleinanzeigen](https://www.kleinanzeigen.de) | ✅ | ✅ (tarayıcı çerezi ile oturum) |

## Kurulum

```bash
pip install -r requirements.txt
cp housing_bot/config-template.json housing_bot/config.json
# config.json'ı düzenle (aşağıya bak)
python -m housing_bot.main --config housing_bot/config.json
```

Tek seferlik test turu için: `python -m housing_bot.main --config housing_bot/config.json --once`

## Nasıl çalışır

1. Her `interval_seconds` saniyede bir (varsayılan 300 + rastgele sapma) tüm `search_urls` sayfaları taranır.
2. Daha önce görülmemiş ilanlar SQLite veritabanına (`state_db`) kaydedilir — **aynı ilana asla iki kez başvurulmaz**, bot yeniden başlasa bile.
3. Yeni ilan `search` kriterlerinden geçerse:
   - `apply.enabled=false` → sadece Telegram bildirimi.
   - `apply.enabled=true, dry_run=true` → başvuru **gönderilmez**, gönderilecek mesaj bildirimle sana iletilir (önerilen başlangıç modu).
   - `apply.enabled=true, dry_run=false` → 20–90 sn insansı gecikmeyle başvuru mesajı gönderilir, sonuç bildirilir.
4. İlk turda mevcut ilanlar sadece "görüldü" olarak işaretlenir (`skip_existing_on_first_run`) — bot açılır açılmaz ilk sayfadaki her şeye başvurmaz.

## Yapılandırma

### Arama kriterleri (`search`)

```json
"search": {
  "max_rent": 1500,          // € üst limit (0 = limitsiz)
  "min_rooms": 2,
  "min_size": 50,            // m²
  "districts": ["Neukölln", "Kreuzberg"],   // boş liste = tüm Berlin
  "exclude_keywords": ["tausch", "zwischenmiete"]  // başlık/açıklamada geçerse ele
}
```

`search_urls` alanına sitelerin kendi filtre sayfalarının URL'sini yapıştırabilirsin (sitede filtreyi kur, adres çubuğundaki URL'yi kopyala). Birden fazla URL desteklenir.

### WG-Gesucht başvurusu

`sites.wg_gesucht.email` ve `password` alanlarına WG-Gesucht hesabını gir. Bot sitenin kendi mesajlaşma API'siyle ilan sahibine mesaj gönderir.

### Kleinanzeigen başvurusu

Login formu captcha korumalı olduğu için bot şifreyle giriş yapmaz. Bunun yerine:

1. Tarayıcıda kleinanzeigen.de'ye giriş yap.
2. Geliştirici araçları → Network → herhangi bir istek → `Cookie` başlığının tamamını kopyala.
3. `sites.kleinanzeigen.cookies` alanına yapıştır.

Çerez süresi dolunca (`login_required_refresh_cookies` hatası) yenilemen gerekir.

### Başvuru mesajı

`apply.applicant` bilgilerini doldur. Varsayılan Almanca şablon `{title}`, `{name}`, `{occupation}`, `{phone}` gibi alanları otomatik doldurur; `apply.message_template` ile kendi şablonunu yazabilirsin.

`apply.ai.enabled=true` yaparsan bot-on-anything'in ana `config.json`'ında tanımlı model (ör. ChatGPT) her ilana özel kişiselleştirilmiş mesaj üretir; hata olursa şablona geri düşer.

### Telegram bildirimi

1. [@BotFather](https://t.me/BotFather) ile bot oluştur, token'ı `notify.telegram.bot_token`'a yaz.
2. Bota bir mesaj at, sonra `https://api.telegram.org/bot<TOKEN>/getUpdates` adresinden `chat.id` değerini alıp `chat_id`'ye yaz.

## Güvenlik ve sorumluluk notları

- **`dry_run: true` ile başla.** Birkaç gün mesajları kontrol et, memnun kalınca kapat.
- `max_per_hour` (varsayılan 8) saatlik başvuru limitidir — spam görünmemek ve hesabının kapanmaması için düşük tut.
- Otomatik istekler sitelerin kullanım koşullarına aykırı olabilir; hesabın askıya alınabilir. Bu riski bilerek kullan. Tarama aralığını çok düşürme (300 sn altına inme).
- Siteler HTML/endpoint değiştirdikçe parser veya başvuru kodu güncelleme isteyebilir. Başvuru hataları logda `[HousingBot][site] apply failed` satırlarında görünür; tarayıcının geliştirici araçlarından gerçek isteği karşılaştırarak düzeltebilirsin.

## Dosya yapısı

```
housing_bot/
├── main.py            # giriş noktası (python -m housing_bot.main)
├── runner.py          # ana döngü: tara → filtrele → başvur → bildir
├── filters.py         # ilan kriter filtresi
├── storage.py         # SQLite: görülen ilanlar + başvuru kaydı
├── message.py         # şablon / AI mesaj üretimi
├── notifier.py        # Telegram bildirimi
└── sites/
    ├── base.py        # site adaptörü taban sınıfı
    ├── wg_gesucht.py
    └── kleinanzeigen.py
```

Yeni site eklemek için `sites/base.py`'deki `BaseSite`'ı türet (`search()` + `apply()`), `sites/__init__.py`'ye kaydet.
