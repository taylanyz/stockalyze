"""
Terim sözlüğü — temel/teknik analiz kavramlarının kısa açıklamaları.

Tek kaynak: hem CLI (`--terimler`) hem ileride Streamlit arayüzü buradan
okur. Metinler kısa ve "yeni başlayan" seviyesinde tutulur.

Bu açıklamalar genel bilgi amaçlıdır, yatırım tavsiyesi değildir.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    key: str            # kısa ad (tabloda görünen)
    name: str           # açık ad
    what: str           # nedir
    reading: str        # nasıl yorumlanır (genel kural, kesin değil)


TERMS: list[Term] = [
    Term(
        "F/K", "Fiyat / Kazanç oranı",
        "Hisse fiyatının, şirketin hisse başına yıllık net kârına oranı. "
        "‘Bu kârı bu fiyatla kaç yılda geri kazanırım’ sorusunun kaba cevabı.",
        "Düşük = görece ucuz, yüksek = pahalı ya da yüksek büyüme beklentisi. "
        "Sadece aynı sektör/piyasa içinde kıyaslanır. Negatif kâr → anlamsız.",
    ),
    Term(
        "PD/DD", "Piyasa Değeri / Defter Değeri",
        "Şirketin borsadaki toplam değerinin, muhasebe kayıtlarındaki öz "
        "sermayesine (varlıklar eksi borçlar) oranı.",
        "1’in altı = piyasa şirketi defter değerinin altında fiyatlıyor "
        "(ucuz olabilir ya da sorun seziyor olabilir). Bankalarda ~1 normal, "
        "teknolojide çok yüksek olabilir.",
    ),
    Term(
        "Net kâr marjı", "Net Kâr Marjı",
        "Her 100 TL satıştan geriye kalan net kâr.",
        "Yüksek marj = fiyatlama gücü / verimli operasyon. Sektöre göre çok "
        "değişir (marketler düşük, yazılım yüksek).",
    ),
    Term(
        "Faaliyet marjı", "Faaliyet Kâr Marjı",
        "Esas işten (finansman ve tek seferlik kalemler hariç) elde edilen "
        "kârın satışlara oranı.",
        "Şirketin ‘asıl işi’ ne kadar kârlı onu gösterir. Net marjdan çok "
        "farklıysa, kâr/zarar büyük ölçüde faiz-kur gibi kalemlerden geliyor.",
    ),
    Term(
        "ROE", "Öz Sermaye Kârlılığı (Return on Equity)",
        "Net kârın, ortakların şirkette bıraktığı öz sermayeye oranı. "
        "‘Şirket, sahiplerinin parasını yılda % kaç büyütüyor’.",
        "Yüksek ROE genelde iyi, ama aşırı borçla da şişirilebilir — "
        "borç/özkaynak ile birlikte bakılır.",
    ),
    Term(
        "Borç/Özkaynak", "Borç / Öz Sermaye (kaldıraç)",
        "Toplam yabancı kaynağın (borçların) öz sermayeye oranı.",
        "1 = borç kadar öz sermaye. Yükseldikçe risk artar (faiz yükü, kriz "
        "dayanıklılığı düşer). Sektöre göre ‘normal’ değişir.",
    ),
    Term(
        "Cari oran", "Cari Oran (likidite)",
        "Dönen varlıkların (1 yıl içinde nakde çevrilebilir) kısa vadeli "
        "borçlara oranı.",
        "1’in altı = kısa vadeli borçları döndürmek için ek finansman "
        "gerekebilir. 1.5–2 arası rahat kabul edilir.",
    ),
    Term(
        "Temettü verimi", "Temettü Verimi",
        "Yıllık dağıtılan temettünün, güncel hisse fiyatına oranı.",
        "Nakit getiri beklentisi için. Çok yüksekse fiyat düşmüş ya da "
        "temettü sürdürülemez olabilir.",
    ),
    Term(
        "SMA 50 / 200", "Basit Hareketli Ortalama (50 / 200 gün)",
        "Son 50 (veya 200) günün kapanış fiyatı ortalaması. Fiyatın "
        "gürültüsünü süzüp yönü gösterir.",
        "Fiyat > SMA50 > SMA200 = yükseliş dizilişi. SMA50’nin SMA200’ü "
        "yukarı kesmesi ‘altın kesişim’ (boğa), aşağı kesmesi ‘ölüm kesişimi’.",
    ),
    Term(
        "RSI", "Göreceli Güç Endeksi (Relative Strength Index)",
        "0–100 arası momentum göstergesi; son ~14 günün kazanç/kayıp "
        "dengesini ölçer.",
        "70 üstü = ‘aşırı alım’ (hızlı yükselmiş, düzeltme gelebilir), "
        "30 altı = ‘aşırı satım’. Tek başına al-sat sinyali değildir.",
    ),
    Term(
        "Hacim trendi", "Hacim (işlem miktarı) trendi",
        "Son günkü işlem hacminin, son 20 günün ortalamasına oranı.",
        "1’in belirgin üstü = harekete ilgi/teyit var. Düşük hacimli "
        "hareketler daha az güvenilir.",
    ),
    Term(
        "Puan", "Araç puanı (0–100)",
        "Taban 50; her temel/teknik ölçüt gerekçesiyle puan ekler/çıkarır. "
        "Eşikler BIST ve ABD için ayrıdır.",
        "Sadece ‘önce hangisine bakayım’ elemesi içindir. Yüksek puan "
        "‘al’ demek DEĞİLDİR — sonrası kendi araştırman.",
    ),
]

TERMS_BY_KEY = {t.key: t for t in TERMS}
