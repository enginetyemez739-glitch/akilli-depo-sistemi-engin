import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import qrcode
from io import BytesIO
from PIL import Image
import requests
import cv2
import numpy as np

# --- TELEGRAM VE GİZLİ KASA AYARLARI ---
try:
    # İnternete (Buluta) yüklendiğinde şifreleri başkası görmesin diye gizli kasadan alacak
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    # Bilgisayarında (yerel) çalışırken buradaki bilgileri kullanacak
    TELEGRAM_TOKEN = "8829389587:AAHqEglV5ZuwGU0VABU1OnpNuFHMoA5mc6U"
    TELEGRAM_CHAT_ID = "1234926869"

KLASOR = os.path.dirname(os.path.abspath(__file__))
DB_YOLU = os.path.join(KLASOR, 'depo_sistemi.db')
RESIM_KLASORU = os.path.join(KLASOR, 'urun_resimleri')

if not os.path.exists(RESIM_KLASORU):
    os.makedirs(RESIM_KLASORU)

def veritabani_olustur():
    conn = sqlite3.connect(DB_YOLU)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS malzemeler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stok_no TEXT, urun_adi TEXT, miktar INTEGER, birim TEXT,
        eklenme_tarihi TEXT, son_kullanma_tarihi TEXT,
        uretim_tarihi TEXT, giris_tarihi TEXT, resim_yolu TEXT,
        kritik_stok INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS hareket_gecmisi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT, kullanici TEXT, islem_tipi TEXT, 
        urun_adi TEXT, miktar INTEGER, aciklama TEXT)''')
    
    try: c.execute("ALTER TABLE malzemeler ADD COLUMN kritik_stok INTEGER")
    except: pass
    conn.commit()
    conn.close()

def log_kaydet(kullanici, islem_tipi, urun_adi, miktar, aciklama):
    conn = sqlite3.connect(DB_YOLU)
    c = conn.cursor()
    zaman = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO hareket_gecmisi (tarih, kullanici, islem_tipi, urun_adi, miktar, aciklama) VALUES (?, ?, ?, ?, ?, ?)',
              (zaman, kullanici, islem_tipi, urun_adi, miktar, aciklama))
    conn.commit()
    conn.close()

def verileri_getir():
    conn = sqlite3.connect(DB_YOLU)
    df = pd.read_sql_query("SELECT id as ID, stok_no as 'Stok No', urun_adi as 'Ürün Adı', miktar as Miktar, birim as Birim, uretim_tarihi as 'Üretim Tarihi', giris_tarihi as 'Giriş Tarihi', son_kullanma_tarihi as 'SKT', kritik_stok as 'Kritik Stok', resim_yolu FROM malzemeler", conn)
    conn.close()
    df['Kritik Stok'] = df['Kritik Stok'].fillna(10)
    return df

def hareketleri_getir():
    conn = sqlite3.connect(DB_YOLU)
    df = pd.read_sql_query("SELECT tarih as Tarih, kullanici as Kullanıcı, islem_tipi as İşlem, urun_adi as 'Ürün Adı', miktar as Miktar, aciklama as Açıklama FROM hareket_gecmisi ORDER BY id DESC", conn)
    conn.close()
    return df

def df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sayfa1')
    return output.getvalue()

def qr_olustur(metin):
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(metin)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def telegram_mesaj_gonder(mesaj):
    if TELEGRAM_TOKEN != "8829389587:AAHqEglV5ZuwGU0VABU1OnpNuFHMoA5mc6U":
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}
        try: requests.post(url, data=payload)
        except: pass

st.set_page_config(page_title="Akıllı Depo PRO", page_icon="📦", layout="wide")
veritabani_olustur()

if 'giris_yapildi' not in st.session_state:
    st.session_state['giris_yapildi'] = False
    st.session_state['kullanici'] = ""
    st.session_state['rol'] = ""

if not st.session_state['giris_yapildi']:
    st.markdown("<h1 style='text-align: center;'>🔐 Depo Yönetim Sistemi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            secilen_rol = st.selectbox("Kullanıcı Tipi", ["Yönetici", "Personel"])
            girilen_sifre = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş Yap", use_container_width=True):
                # YENİ GÜVENLİ ŞİFRELER EKLENDİ
                if secilen_rol == "Yönetici" and girilen_sifre == "Engin5307":
                    st.session_state.update({'giris_yapildi': True, 'kullanici': "Yönetici", 'rol': "admin"})
                    st.rerun()
                elif secilen_rol == "Personel" and girilen_sifre == "Depo5307":
                    st.session_state.update({'giris_yapildi': True, 'kullanici': "Personel", 'rol': "personel"})
                    st.rerun()
                else:
                    st.error("❌ Hatalı şifre!")
else:
    df = verileri_getir()
    bugun = datetime.now().date()
    
    c_ust1, c_ust2 = st.columns([4, 1])
    with c_ust1: st.title("📦 Akıllı Depo PRO")
    with c_ust2:
        st.write(f"👤 *{st.session_state['kullanici']}*")
        if st.button("🚪 Çıkış Yap"):
            st.session_state['giris_yapildi'] = False
            st.rerun()

    sekme1, sekme2, sekme3, sekme6, sekme4, sekme5 = st.tabs(["📊 Özet", "➕ Ürün Ekle", "🔄 Güncelle", "📷 Kamerayla İşlem", "🪪 Ürün Kartı", "📝 Geçmiş"])

    with sekme1:
        st.markdown("### 📋 Güncel Depo Tablosu")
        krt_sayisi = 0
        telegram_raporu = "⚠️ DEPO KRİTİK UYARI RAPORU ⚠️\n\n"
        
        for index, row in df.iterrows():
            try:
                skt = datetime.strptime(row['SKT'], '%Y-%m-%d').date()
                kalan = (skt - bugun).days
                if kalan < 0:
                    st.error(f"❌ {row['Ürün Adı']} - TARİHİ GEÇTİ!")
                    telegram_raporu += f"❌ {row['Ürün Adı']} - TARİHİ GEÇTİ!\n"
                    krt_sayisi += 1
                elif 0 <= kalan <= 30:
                    st.warning(f"⚠️ {row['Ürün Adı']} - SKT'ye {kalan} gün kaldı!")
                    telegram_raporu += f"⚠️ {row['Ürün Adı']} - {kalan} gün kaldı!\n"
                    krt_sayisi += 1
            except: pass
            
            try:
                if int(float(row['Miktar'])) <= int(float(row['Kritik Stok'])):
                    st.error(f"📉 STOK ALARMI: {row['Ürün Adı']} bitmek üzere! (Kalan: {row['Miktar']})")
                    telegram_raporu += f"📉 ALARM: {row['Ürün Adı']} (Kalan: {row['Miktar']})\n"
                    krt_sayisi += 1
            except: pass

        if st.button("📲 Telegram'a Rapor Gönder", type="primary"):
            telegram_mesaj_gonder(telegram_raporu)
            st.toast("✅ Gönderildi!")
            
        st.download_button("📥 Excel İndir", data=df_to_excel(df.drop(columns=['resim_yolu'])), file_name="Depo.xlsx")
        st.dataframe(df.drop(columns=['resim_yolu']), use_container_width=True, hide_index=True)

    with sekme2:
        st.subheader("➕ Yeni Ürün Girişi")
        if st.session_state['rol'] == "personel":
            st.warning("Yetkiniz yok. Sadece yöneticiler yeni ürün ekleyebilir.")
        else:
            with st.form("ekleme_formu", clear_on_submit=True):
                c1, c2, c3, c4 = st.columns(4)
                stok = c1.text_input("Stok No")
                ad = c2.text_input("Ürün Adı")
                miktar = c3.number_input("Miktar", min_value=0, step=1)
                kritik = c4.number_input("Kritik Stok", value=10)
                birim = st.text_input("Birim (Adet, Kg vb.)")
                skt_t = st.date_input("⏳ SKT")
                if st.form_submit_button("🚀 Ekle"):
                    if ad and stok:
                        conn = sqlite3.connect(DB_YOLU)
                        c = conn.cursor()
                        c.execute('''INSERT INTO malzemeler (stok_no, urun_adi, miktar, birim, son_kullanma_tarihi, kritik_stok) 
                            VALUES (?, ?, ?, ?, ?, ?)''', (stok, ad, miktar, birim, skt_t.strftime('%Y-%m-%d'), kritik))
                        conn.commit()
                        conn.close()
                        log_kaydet(st.session_state['kullanici'], "YENİ ÜRÜN", ad, miktar, "Eklendi.")
                        st.rerun()

    with sekme3:
        st.subheader("🔄 Manuel Güncelleme")
        if not df.empty:
            secili_guncelleme = st.selectbox("Ürün Seçin:", df['ID'].astype(str) + " - " + df['Ürün Adı'])
            secili_id = int(secili_guncelleme.split(" - ")[0])
            urun = df[df['ID'] == secili_id].iloc[0]
            st.info(f"Mevcut: {urun['Miktar']} {urun['Birim']}")
            
            dus = st.number_input("➖ Çıkış:", min_value=0, max_value=int(urun['Miktar']), step=1)
            ekle = st.number_input("➕ Giriş:", min_value=0, step=1)
            if st.button("💾 Kaydet"):
                yeni = urun['Miktar'] - dus + ekle
                conn = sqlite3.connect(DB_YOLU)
                c = conn.cursor()
                c.execute('UPDATE malzemeler SET miktar=? WHERE id=?', (yeni, secili_id))
                conn.commit()
                conn.close()
                if dus > 0: log_kaydet(st.session_state['kullanici'], "ÇIKIŞ", urun['Ürün Adı'], dus, "")
                if ekle > 0: log_kaydet(st.session_state['kullanici'], "GİRİŞ", urun['Ürün Adı'], ekle, "")
                st.rerun()
                
            st.divider()
            if st.session_state['rol'] == "admin":
                st.markdown("### 🗑️ Ürünü Tamamen Sil")
                if st.button("Seçili Ürünü Depodan Tamamen Sil"):
                    conn = sqlite3.connect(DB_YOLU)
                    c = conn.cursor()
                    c.execute('DELETE FROM malzemeler WHERE id=?', (secili_id,))
                    conn.commit()
                    conn.close()
                    log_kaydet(st.session_state['kullanici'], "ÜRÜN SİLİNDİ", urun['Ürün Adı'], urun['Miktar'], "Ürün silindi.")
                    st.success("Ürün silindi!")
                    st.rerun()

    with sekme6:
        st.subheader("📷 QR Kod Okutarak Hızlı İşlem")
        resim = st.camera_input("Kamerayı Aç ve Okut")
        if resim is not None:
            img = Image.open(resim)
            img_array = np.array(img)
            cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(cv_img)
            
            if data:
                st.success("✅ QR Kod Okundu!")
                try:
                    okunan_stok = None
                    for satir in data.split('\n'):
                        if "Stok No:" in satir:
                            okunan_stok = satir.split("Stok No:")[1].strip()
                            break
                    if okunan_stok:
                        eslesen_urun = df[df['Stok No'] == okunan_stok]
                        if not eslesen_urun.empty:
                            urun_isim = eslesen_urun.iloc[0]['Ürün Adı']
                            urun_id = eslesen_urun.iloc[0]['ID']
                            urun_miktar = eslesen_urun.iloc[0]['Miktar']
                            
                            st.info(f"📦 Bulunan Ürün: *{urun_isim}* (Mevcut: {urun_miktar})")
                            
                            with st.form("qr_hizli_form"):
                                col_qr1, col_qr2 = st.columns(2)
                                with col_qr1:
                                    miktar_dus = st.number_input("➖ Çıkarılacak:", min_value=0, max_value=int(urun_miktar), step=1)
                                with col_qr2:
                                    miktar_ekle = st.number_input("➕ Eklenecek:", min_value=0, step=1)
                                
                                if st.form_submit_button("💾 Güncelle", type="primary"):
                                    if miktar_dus > 0 or miktar_ekle > 0:
                                        yeni_toplam = urun_miktar - miktar_dus + miktar_ekle
                                        conn = sqlite3.connect(DB_YOLU)
                                        c = conn.cursor()
                                        c.execute('UPDATE malzemeler SET miktar=? WHERE id=?', (yeni_toplam, urun_id))
                                        conn.commit()
                                        conn.close()
                                        if miktar_dus > 0: log_kaydet(st.session_state['kullanici'], "QR ÇIKIŞ", urun_isim, miktar_dus, "")
                                        if miktar_ekle > 0: log_kaydet(st.session_state['kullanici'], "QR GİRİŞ", urun_isim, miktar_ekle, "")
                                        st.rerun()
                        else:
                            st.error("Ürün bulunamadı.")
                except:
                    st.error("QR kod anlaşılamadı.")
            else:
                st.warning("QR kod algılanamadı.")

    with sekme4:
        st.subheader("🪪 Ürün Tanıtım Kartı")
        if not df.empty:
            secilen = st.selectbox("Kartı Göster:", df['ID'].astype(str) + " - " + df['Ürün Adı'], key="qr_krt")
            urun_bilgisi = df[df['ID'] == int(secilen.split(" - ")[0])].iloc[0]
            qr_icerik = f"Ürün: {urun_bilgisi['Ürün Adı']}\nStok No: {urun_bilgisi['Stok No']}\nMiktar: {urun_bilgisi['Miktar']}\nSKT: {urun_bilgisi['SKT']}"
            st.image(qr_olustur(qr_icerik), caption="Bu Kodu Okutabilirsiniz")

    with sekme5:
        st.subheader("📝 Hareket Geçmişi")
        hareket_df = hareketleri_getir()
        st.dataframe(hareket_df, use_container_width=True)