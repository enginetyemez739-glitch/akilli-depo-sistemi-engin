import streamlit as st
import pandas as pd
from datetime import datetime
import os
import qrcode
from io import BytesIO
from PIL import Image
import requests
import cv2
import numpy as np
import json
import gspread
from google.oauth2.service_account import Credentials

# --- GİZLİ KASA AYARLARI ---
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
    google_json_str = st.secrets["google_json"]
except:
    st.error("Gizli kasa (Secrets) ayarları bulunamadı!")
    st.stop()

# --- GOOGLE SHEETS BAĞLANTISI ---
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(google_json_str)
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# Tabloya bağlan (Adının tam olarak 'Depo_Sistemi' olması gerekir)
try:
    sheet = client.open('Depo_Sistemi')
except:
    st.error("Google Drive'da 'Depo_Sistemi' adında bir tablo bulunamadı. Lütfen ismini kontrol edin ve paylaşıma açtığınızdan emin olun.")
    st.stop()

# Sayfaları (Sekmeleri) kontrol et, yoksa oluştur
try:
    ws_malzemeler = sheet.worksheet("Malzemeler")
except:
    ws_malzemeler = sheet.add_worksheet(title="Malzemeler", rows="1000", cols="20")
    ws_malzemeler.append_row(["ID", "Stok No", "Ürün Adı", "Miktar", "Birim", "Eklenme Tarihi", "SKT", "Üretim Tarihi", "Giriş Tarihi", "Resim Yolu", "Kritik Stok"])

try:
    ws_hareket = sheet.worksheet("Hareket_Gecmisi")
except:
    ws_hareket = sheet.add_worksheet(title="Hareket_Gecmisi", rows="1000", cols="10")
    ws_hareket.append_row(["ID", "Tarih", "Kullanıcı", "İşlem", "Ürün Adı", "Miktar", "Açıklama"])

def log_kaydet(kullanici, islem_tipi, urun_adi, miktar, aciklama):
    zaman = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mevcut_id = len(ws_hareket.get_all_values())
    ws_hareket.append_row([mevcut_id, zaman, kullanici, islem_tipi, urun_adi, miktar, aciklama])

def verileri_getir():
    kayitlar = ws_malzemeler.get_all_records()
    if not kayitlar:
        return pd.DataFrame(columns=["ID", "Stok No", "Ürün Adı", "Miktar", "Birim", "Eklenme Tarihi", "SKT", "Üretim Tarihi", "Giriş Tarihi", "Resim Yolu", "Kritik Stok"])
    df = pd.DataFrame(kayitlar)
    df['Kritik Stok'] = df['Kritik Stok'].fillna(10)
    return df

def hareketleri_getir():
    kayitlar = ws_hareket.get_all_records()
    if not kayitlar:
        return pd.DataFrame(columns=["ID", "Tarih", "Kullanıcı", "İşlem", "Ürün Adı", "Miktar", "Açıklama"])
    return pd.DataFrame(kayitlar).sort_values(by="ID", ascending=False)

def qr_olustur(metin):
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(metin)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}
    try: requests.post(url, data=payload)
    except: pass

st.set_page_config(page_title="Akıllı Depo PRO", page_icon="📦", layout="wide")

if 'giris_yapildi' not in st.session_state:
    st.session_state.update({'giris_yapildi': False, 'kullanici': "", 'rol': ""})

if not st.session_state['giris_yapildi']:
    st.markdown("<h1 style='text-align: center;'>🔐 Depo Yönetim Sistemi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            secilen_rol = st.selectbox("Kullanıcı Tipi", ["Yönetici", "Personel"])
            girilen_sifre = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş Yap", use_container_width=True):
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
    with c_ust1: st.title("📦 Akıllı Depo PRO (Bulut)")
    with c_ust2:
        st.write(f"👤 *{st.session_state['kullanici']}*")
        if st.button("🚪 Çıkış Yap"):
            st.session_state['giris_yapildi'] = False
            st.rerun()

    sekme1, sekme2, sekme3, sekme6, sekme4, sekme5 = st.tabs(["📊 Özet", "➕ Ürün Ekle", "🔄 Güncelle", "📷 QR İşlem", "🪪 Ürün Kartı", "📝 Geçmiş"])

    with sekme1:
        st.markdown("### 📋 Güncel Depo Tablosu")
        if st.button("📲 Telegram'a Acil Rapor Gönder", type="primary"):
            telegram_mesaj_gonder("Sistem Kontrolü: Depo uygulamasına buluttan erişildi.")
            st.toast("✅ Gönderildi!")
            
        gosterilecek_df = df.drop(columns=['Resim Yolu'], errors='ignore')
        st.dataframe(gosterilecek_df, use_container_width=True, hide_index=True)

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
                        yeni_id = len(ws_malzemeler.get_all_values())
                        eklenme_tarihi = datetime.now().strftime('%Y-%m-%d')
                        ws_malzemeler.append_row([yeni_id, stok, ad, miktar, birim, eklenme_tarihi, skt_t.strftime('%Y-%m-%d'), "-", "-", "", kritik])
                        log_kaydet(st.session_state['kullanici'], "YENİ ÜRÜN", ad, miktar, "Eklendi.")
                        st.success("✅ Ürün Google Tablolara eklendi!")
                        st.rerun()

    with sekme3:
        st.subheader("🔄 Ürün Bilgilerini ve Stoğu Güncelle")
        if not df.empty:
            secili_guncelleme = st.selectbox("İşlem yapılacak ürünü seçin:", df['ID'].astype(str) + " - " + df['Ürün Adı'])
            secili_id = int(secili_guncelleme.split(" - ")[0])
            urun = df[df['ID'] == secili_id].iloc[0]
            
            st.info(f"📦 Mevcut Stok: *{urun['Miktar']} {urun['Birim']}*")
            
            with st.form("guncelleme_formu"):
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    yeni_stok_no = st.text_input("Stok No (Değiştirebilirsiniz):", value=str(urun['Stok No']))
                    kullanilan_miktar = st.number_input("➖ Depodan Çıkış (Kullanılan):", min_value=0, max_value=int(urun['Miktar']), step=1)
                    eklenen_miktar = st.number_input("➕ Depoya Giriş (Yeni Gelen):", min_value=0, step=1)
                    
                with col_g2:
                    try:
                        mevcut_skt = datetime.strptime(str(urun['SKT']), '%Y-%m-%d').date()
                    except:
                        mevcut_skt = bugun
                        
                    yeni_skt = st.date_input("Son Kullanma Tarihi (SKT):", value=mevcut_skt)
                    yeni_kritik = st.number_input("Kritik Stok Sınırı:", value=int(urun['Kritik Stok']), min_value=1, step=1)
                
                if st.form_submit_button("💾 Değişiklikleri Kaydet", type="primary"):
                    yeni_toplam = int(urun['Miktar']) - kullanilan_miktar + eklenen_miktar
                    # Tablodaki satır numarasını bul (ID başlık satırı nedeniyle +2)
                    satir_no = df[df['ID'] == secili_id].index[0] + 2
                    
                    # Google Tablolardaki hücreleri tek tek güncelle
                    ws_malzemeler.update_cell(satir_no, 2, yeni_stok_no) # 2. Sütun Stok No
                    ws_malzemeler.update_cell(satir_no, 4, yeni_toplam)  # 4. Sütun Miktar
                    ws_malzemeler.update_cell(satir_no, 7, yeni_skt.strftime('%Y-%m-%d')) # 7. Sütun SKT
                    ws_malzemeler.update_cell(satir_no, 11, yeni_kritik) # 11. Sütun Kritik Stok
                    
                    # Log Kayıtları
                    if kullanilan_miktar > 0: 
                        log_kaydet(st.session_state['kullanici'], "ÇIKIŞ", urun['Ürün Adı'], kullanilan_miktar, "")
                    if eklenen_miktar > 0: 
                        log_kaydet(st.session_state['kullanici'], "GİRİŞ", urun['Ürün Adı'], eklenen_miktar, "")
                    if yeni_stok_no != str(urun['Stok No']) or yeni_skt.strftime('%Y-%m-%d') != str(urun['SKT']):
                        log_kaydet(st.session_state['kullanici'], "BİLGİ GÜNCELLEME", urun['Ürün Adı'], 0, "Stok No, Kritik Sınır veya SKT değiştirildi.")
                        
                    st.success("Ürün bilgileri ve stok başarıyla güncellendi!")
                    st.rerun()
                    
            st.divider()
            if st.session_state['rol'] == "admin":
                st.markdown("### 🗑️ Ürünü Tamamen Sil")
                if st.button("Seçili Ürünü Depodan Tamamen Sil"):
                    satir_no = df[df['ID'] == secili_id].index[0] + 2
                    ws_malzemeler.delete_rows(satir_no)
                    log_kaydet(st.session_state['kullanici'], "ÜRÜN SİLİNDİ", urun['Ürün Adı'], urun['Miktar'], "Ürün tamamen silindi.")
                    st.success("Ürün silindi!")
                    st.rerun()

    with sekme6:
        st.subheader("📷 QR Kod Okutarak Hızlı İşlem")
        resim = st.camera_input("Kamerayı Aç ve Okut")
        if resim is not None:
            img = Image.open(resim)
            cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv_img)
            
            if data:
                st.success("✅ QR Kod Okundu!")
                try:
                    okunan_stok = next((s.split("Stok No:")[1].strip() for s in data.split('\n') if "Stok No:" in s), None)
                    if okunan_stok:
                        eslesen = df[df['Stok No'] == str(okunan_stok)]
                        if not eslesen.empty:
                            u_isim, u_id, u_mik = eslesen.iloc[0]['Ürün Adı'], eslesen.iloc[0]['ID'], eslesen.iloc[0]['Miktar']
                            st.info(f"📦 Bulunan: *{u_isim}* (Mevcut: {u_mik})")
                            with st.form("qr_form"):
                                miktar_dus = st.number_input("➖ Çıkarılacak:", min_value=0, max_value=int(u_mik), step=1)
                                miktar_ekle = st.number_input("➕ Eklenecek:", min_value=0, step=1)
                                if st.form_submit_button("💾 Güncelle", type="primary"):
                                    if miktar_dus > 0 or miktar_ekle > 0:
                                        yeni = int(u_mik) - miktar_dus + miktar_ekle
                                        satir_no = eslesen.index[0] + 2
                                        ws_malzemeler.update_cell(satir_no, 4, yeni)
                                        if miktar_dus > 0: log_kaydet(st.session_state['kullanici'], "QR ÇIKIŞ", u_isim, miktar_dus, "")
                                        if miktar_ekle > 0: log_kaydet(st.session_state['kullanici'], "QR GİRİŞ", u_isim, miktar_ekle, "")
                                        st.rerun()
                        else: st.error("Ürün bulunamadı.")
                except: st.error("QR okunamadı.")

    with sekme4:
        st.subheader("🪪 Ürün Tanıtım Kartı")
        if not df.empty:
            secilen = st.selectbox("Kartı Göster:", df['ID'].astype(str) + " - " + df['Ürün Adı'], key="qr_krt")
            urun_bilgisi = df[df['ID'] == int(secilen.split(" - ")[0])].iloc[0]
            qr_icerik = f"Ürün: {urun_bilgisi['Ürün Adı']}\nStok No: {urun_bilgisi['Stok No']}\nMiktar: {urun_bilgisi['Miktar']}\nSKT: {urun_bilgisi['SKT']}"
            st.image(qr_olustur(qr_icerik), caption="Bu Kodu Okutabilirsiniz")

    with sekme5:
        st.subheader("📝 Hareket Geçmişi")
        st.dataframe(hareketleri_getir(), use_container_width=True)
