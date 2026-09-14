# Hisse Senedi Değerlendirme Aracı

BIST ve ABD borsalarındaki hisseler için temel + teknik analiz verisini
toplayıp, şeffaf bir puanlamayla okunabilir bir özet üreten araştırma
yardımcısı.

## ⚠️ Yasal uyarı

Bu araç **yatırım tavsiyesi vermez**. Ürettiği tüm çıktılar (puan dahil)
yalnızca araştırma ve eğitim amaçlıdır. Yatırım kararlarınız için lisanslı
bir finansal danışmana başvurun. Veriler üçüncü taraf kaynaklardan gelir
ve hatalı/gecikmeli olabilir (özellikle BIST temel verisi).

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Web arayüzü

```bash
streamlit run streamlit_app.py
```

Sayfalar: **Ana Sayfa** (trend listeleri + piyasa haberleri), **Hisse Detay**
(fiyat grafiği + temel/teknik + puan kırılımı + ilgili haberler), **Karşılaştır**,
**Watchlist**, **Gün Sonu**, **Radar** (BIST/ABD ayrı; skoru iyi + ilgi gören;
satıra tıkla → yan panelde detay; watchlist'e hızlı ekle/çıkar),
**Snapshot & Değişim** (günlük snapshot al, iki günü karşılaştır), **Terimler**.
Tüm hesaplama CLI ile ortak (`src/analysis`, `src/evaluator`); arayüz sadece
sunum + `@st.cache_data`.

## Haberler

`src/providers/news.py` — genel piyasa haberi Türkçe RSS akışlarından (Investing TR
market_overview + döviz/makro; Dünya + Bloomberg HT finans-kelime filtreli);
hisse-bazlı haber yfinance'ten (ABD'de dolu + thumbnail, BIST'te sınırlı). Sadece
başlık + kaynak + link + zaman (+ hisse haberinde görsel); içerik analiz edilmez,
puanı etkilemez. Streamlit'te kart yapısı — Ana Sayfa 2 sütun metin kartı,
Hisse Detay görselli kart. RSS'ler belgesiz — her biri ayrı try/except.

## Kullanım

```bash
# Tek hisse — detaylı (snapshot + temel + teknik + puan)
python -m src.app AAPL
python -m src.app THYAO.IS

# Çoklu — piyasaya göre gruplu karşılaştırma tablosu, puana göre sıralı
python -m src.app AAPL MSFT NVDA THYAO.IS ASELS.IS

# Değerlendirmeyi veritabanına kaydet (bugünün tarihiyle)
python -m src.app AAPL MSFT --save

# Gün sonu değerlendirmesi: watchlist.txt'i değerlendir + kaydet +
# önceki kayıtla kıyasla (puan değişimi, yeni teknik sinyaller)
python -m src.app --eod

# Ana sayfa: ABD + BIST trend listeleri (yükselen/düşen/hacimli)
python -m src.app --trending
python -m src.app --trending --deep      # ilk sıraları da puanla (yavaş)

# Radar: skoru iyi + ilgi gören hisseler + trend/konumlanma notu (yavaş)
python -m src.app --radar

# Terim sözlüğü (F/K, PD/DD, RSI... ne demek)
python -m src.app --terimler

# Son piyasa haberleri (Türkçe RSS kaynakları)
python -m src.app --haberler

# Bir sembolün kayıtlı geçmişi (ağa çıkmaz)
python -m src.app --history AAPL

# Önbelleği temizle
python -m src.app --clear-cache
```

Yararlı bayraklar: `--detail`, `--no-fundamentals`, `--no-technical`,
`--no-cache`, `--db YOL`.

## Puanlama

Taban 50; her temel/teknik ölçüt gerekçesiyle birlikte puan ekler/çıkarır,
sonuç 0–100'e kırpılır. Eşikler BIST ve ABD için ayrıdır (F/K, PD/DD
çarpanları yapısal olarak farklı). Ayrıntı: `src/analysis/scoring.py`.

## Tarama (Screener) & Portföy & Sektörel puanlama

- **Tarama** (`analysis/screener.py`, `pages/8_Tarama.py`): evreni (bist100 + us100)
  F/K, PD/DD, ROE, marj, trend, RSI, temettü, puan kriterlerine göre süzer, puana
  göre sıralar. İlk çalıştırma yavaş (~evren boyu değerlendirme), sonra 1 saat cache.
- **Portföy** (`analysis/portfolio.py`, `storage/portfolio_repo.py`, `pages/9_Portföy.py`):
  pozisyon (adet + alış fiyatı) gir → güncel değer, K/Z, ağırlıklı puan, sektör
  dağılımı (pasta), tahmini yıllık temettü. Farklı para birimi varsa toplam yaklaşık.
- **Sektörel puanlama** (`analysis/sector.py`): `--refresh-sectors` (veya Tarama'daki
  buton) evren geneli sektör medyanlarını (F/K, PD/DD) hesaplar, KVStore'da saklar.
  Skorlama bunları kullanınca F/K/PD/DD mutlak eşik yerine sektör medyanına göre
  değerlendirilir ("sektör medyanının %31 üstünde (pahalı)"). Yoksa mutlak eşiğe düşer.

## Risk & Özet Profil

`src/analysis/risk.py` — fiyat geçmişinden yıllık volatilite, beta (endekse göre),
maksimum düşüş, endekse relatif getiri. `src/analysis/snowflake.py` — hisseyi
Değer/Kârlılık/Sağlık/Büyüme/Temettü olmak üzere 5 eksende 0-100 puanlayan "kar
tanesi" profili (sayı değil, profil). Hisse Detay'da Plotly mum grafik (SMA +
hacim + RSI panelleri) + radar profil + risk maddeleri.

## Bilanço Karnesi

`src/providers/statements.py` — çok dönemli mali tablo (BIST: İş Yatırım MaliTablo
çok yıl · ABD: yfinance yıllık gelir tablosu/bilanço/nakit akışı) → `FinancialHistory`.
`src/analysis/statements.py` büyüme/trend çıkarır: satış YoY + CAGR, marj trendi,
borç/özkaynak trendi, faaliyet nakit akışı ile kâr kalitesi. Hisse Detay + CLI
detayında "📊 Bilanço Karnesi" tablosu + madde madde özet. Tahmin değil, tarif.

## Trend okuması

"Yükseliş trendinde" tek başına yeterince açıklayıcı olmadığından, trendin
**yaşı** (fiyat kaç işlem günüdür 200 günlük ortalamanın aynı tarafında) ve
**öncesi** (dönüşten önceki baskın trend + fiyat değişimi) de gösterilir —
tahmin değil, tarif. Örn: *"~110 işlem günü (~5 ay) önce başladı; öncesinde
yatay seyrediyordu"* vs *"~1 işlem günü önce başladı — taze, henüz teyitsiz"*.
İleriye dönük olasılık/istatistik verilmez (tek hisse geçmişiyle güvenilmez).

## Mimari

Katmanlı yapı — her katman yalnızca bir alttakinin *arayüzünü* tanır:

| Katman | Klasör | Sorumluluk |
|---|---|---|
| Sunum | `src/app.py` (CLI) · `streamlit_app.py` + `pages/` + `src/ui/` (web) | iki ayrı sunum, aynı çekirdek |
| Orkestrasyon | `src/evaluator.py` | sembol → veri toplama, kısmi hata toleransı |
| Hesaplama | `src/analysis/` | teknik göstergeler, puanlama, gün sonu diff |
| Veri | `src/providers/` | `MarketDataProvider` arayüzü; yfinance + İş Yatırım (BIST temel) `CompositeProvider` altında |
| Depolama | `src/storage/` | SQLite: günlük snapshot (Repository) + önbellek (Decorator) |
| Model | `src/models.py` | veri taşıyan dataclass'lar |

Desenler: ABC/arayüz (provider), factory (`build_provider`),
decorator (`CachingProvider`), repository (`SnapshotRepository`),
dependency injection (`Evaluator(provider)`).

## Testler

```bash
python -m pytest -q
```

`analysis` katmanı saf fonksiyonlardan oluştuğu için ağ olmadan test edilir.

## Yol haritası

1. ✅ MVP — tek hisse anlık görüntü
2. ✅ Temel analiz oranları
3. ✅ Teknik analiz göstergeleri (SMA, RSI, hacim, kesişim)
4. ✅ Çoklu hisse karşılaştırma
5. ✅ SQLite kayıt katmanı (cache + günlük snapshot)
6. ✅ Şeffaf puanlama + gün sonu değerlendirmesi
7. ✅ BIST temel verisi için İş Yatırım (`CompositeProvider`) — PD/DD, F/K, ROE,
   marj, borç/özkaynak, cari oran İş Yatırım MaliTablo'dan; banka olmayan
   (XI_29) şirketlerde. Banka/hata → yfinance'e düşer.
8. ✅ Ana sayfa trend listeleri — ABD: `yf.screen`; BIST: `bist100.txt` toplu indirme.
   Terim sözlüğü (`src/glossary.py`, `--terimler`).
9. ✅ Streamlit arayüz (6 sayfa) — mevcut katmanları değiştirmeden yeniden kullanır.
10. ✅ Radar — `analysis/radar.py`: BIST 100 + ABD aktifleri + watchlist evreni,
    bulk indirme ile trend/RSI, "ilgi puanı" (hacim + hareket), her piyasadan en
    çok ilgi göreni tam puanlama, trende göre konumlanma notu (alıcı / elde tutan
    bakışı), `describe_trend()` gerekçesi. Streamlit'te BIST/ABD ayrı bölüm,
    skoru-iyi/sadece-ilgi ayrımı, satır seç → yan panelde detay.
11. ✅ Snapshot & Değişim — `analysis/eod.diff_stored()`: iki kayıtlı günü ağsız
    karşılaştır (puan değişimi + yeni teknik sinyaller). `--eod` + `--save` bunun
    CLI karşılığı; Windows Görev Zamanlayıcı ile otomatikleştirilebilir.

Sonraki olası işler: BIST bankalar için İş Yatırım (UFRS formatı), sektör-göreceli
puanlama, skorun backtest'i, watchlist'i DB'ye taşıma.
