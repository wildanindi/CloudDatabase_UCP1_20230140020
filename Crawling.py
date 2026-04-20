from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from pymongo import MongoClient
import time
import random
from datetime import datetime

# --- KONFIGURASI MONGODB ATLAS ---
MONGO_URI = "mongodb+srv://wildanindi2_db_user:Semogaditerima123@testingp2.kghh6i7.mongodb.net/"

try:
    client = MongoClient(MONGO_URI)
    db = client["cnbc_db"]
    collection = db["environment_news"]
    client.server_info() # Cek koneksi ke server
    print("✅ Koneksi ke MongoDB Atlas Berhasil!")
except Exception as e:
    print(f"❌ Gagal konek ke MongoDB Atlas: {e}")
    exit()

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Jalankan tanpa buka jendela browser
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def crawl_cnbc_hybrid():
    driver = get_driver()
    # Target utama: Indeks Berita Terbaru
    target_url = "https://www.cnbcindonesia.com/news"
    
    print(f"🚀 Membuka browser (Headless Mode) ke: {target_url}")
    driver.get(target_url)
    
    # Beri waktu render JavaScript
    time.sleep(5) 
    
    soup = BeautifulSoup(driver.page_source, 'lxml')
    articles = soup.find_all('article')
    
    print(f"🔍 Ditemukan {len(articles)} artikel di halaman utama.")
    
    count = 0
    # Filter tema lingkungan (Aktifkan jika ingin data spesifik)
    keywords = ['lingkungan', 'hijau', 'emisi', 'sustainability', 'iklim', 'energi', 'carbon', 'sampah', 'esg', 'tambang', 'lpg','dunia']

    for artikel in articles:
        try:
            link_tag = artikel.find('a')
            if not link_tag: continue
            link = link_tag['href']

            # Proses Detail Berita
            print(f"\n📄 Memproses: {link}")
            driver.get(link)
            time.sleep(random.uniform(2, 4)) # Jeda manusiawi
            
            detail_soup = BeautifulSoup(driver.page_source, 'lxml')

          
            
            
            judul_meta = detail_soup.find('meta', property='og:title')
            judul = judul_meta['content'] if judul_meta else "N/A"

            if not any(k in judul.lower() for k in keywords):
                print(f"⏩ Skip: Judul tidak relevan dengan tema lingkungan.")
                continue

            # 2. Tanggal Publish
            tanggal_tag = detail_soup.find('meta', attrs={'name': 'dtk:publishdate'})
            tanggal = tanggal_tag['content'] if tanggal_tag else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 3. Author
            author_tag = detail_soup.find('meta', attrs={'name': 'dtk:author'})
            author = author_tag['content'] if author_tag else "Redaksi CNBC"

            # 4. Tag / Keywords
            tags_tag = detail_soup.find('meta', attrs={'name': 'keywords'})
            tags = tags_tag['content'] if tags_tag else "N/A"

            # 5. Thumbnail
            thumb_meta = detail_soup.find('meta', property='og:image')
            thumbnail = thumb_meta['content'] if thumb_meta else "N/A"

            # 6. Isi Berita
            # --- PERBAIKAN PENGAMBILAN ISI BERITA ---
            # Kita coba beberapa kemungkinan class yang dipakai CNBC
            # --- SELEKTOR SAPU JAGAT ---
            # Cari di berbagai kemungkinan kontainer teks CNBC
            # --- PERBAIKAN: HANYA AMBIL AREA KONTEN UTAMA ---
            # Cari di kontainer yang spesifik milik artikel CNBC
            body_div = (
                detail_soup.select_one('.detail_text') or 
                detail_soup.select_one('.detail__body-text') or
                detail_soup.select_one('.detail_video-desc')
            )

            if body_div:
                # BUANG ELEMEN GAK PENTING (Iklan, Navigasi, Market Data)
                # Kita hapus div yang mengandung kata 'market' atau 'running'
                for junk in body_div.select('.detail_tag, .table_market, .listing_seputar, .video-player'):
                    junk.decompose()

                # Ambil teks hanya dari paragraf <p>
                paragraphs = [p.get_text(strip=True) for p in body_div.find_all('p')]
                
                # Filter: Buang paragraf yang isinya promo "Baca Juga" atau teks pendek sampah
                clean_paragraphs = [
                    p for p in paragraphs 
                    if len(p) > 30 and "baca juga" not in p.lower()
                ]

                if clean_paragraphs:
                    isi_berita = " ".join(clean_paragraphs)
                else:
                    # Kalau gak ada <p>, ambil teks langsung tapi buang market data
                    isi_berita = body_div.get_text(separator=" ", strip=True)
            else:
                # FALLBACK TERAKHIR: Cari element article beneran
                article_tag = detail_soup.find('article')
                if article_tag:
                    # Ambil teks dari article tapi batasi biar gak ambil navigasi
                    isi_berita = article_tag.get_text(separator=" ", strip=True)[:1500]
                else:
                    isi_berita = "Isi berita tidak ditemukan"

            # FILTER: Jika isi_berita masih mengandung data market, kita kosongkan
            if "MARKET DATA" in isi_berita or "INDEXES" in isi_berita:
                # Coba cari lagi khusus di tag <p> yang ada di seluruh halaman (paling aman)
                all_ps = detail_soup.find_all('p')
                fallback_text = " ".join([p.get_text(strip=True) for p in all_ps if len(p.get_text()) > 50])
                isi_berita = fallback_text if len(fallback_text) > 100 else "Isi berita tidak ditemukan"
            # Bersihkan dari spasi berlebih
            isi_berita = " ".join(isi_berita.split())

            # --- SIMPAN KE MONGODB ATLAS ---
            news_data = {
                'url': link,
                'judul': judul,
                'tanggal_publish': tanggal,
                'author': author,
                'tag_kategori': tags,
                'isi_berita': isi_berita,
                'thumbnail': thumbnail,
                'scraped_at': datetime.now()
            }

            print(f"💾 Mencoba simpan ke MongoDB Atlas...")
            # Upsert=True agar data dengan URL sama tidak terduplikasi
            result = collection.update_one({'url': link}, {'$set': news_data}, upsert=True)
            
            if result.acknowledged:
                print(f"✅ BERHASIL SIMPAN: {judul[:40]}...")
                count += 1
            else:
                print(f"❌ GAGAL SIMPAN: Atlas tidak merespon.")

        except Exception as e:
            print(f"⚠️ Error pada artikel ini: {e}")
            continue

    driver.quit()
    print(f"\n✨ TUGAS SELESAI!")
    print(f"📊 Total {count} berita lingkungan baru berhasil masuk ke database.")

if __name__ == "__main__":
    crawl_cnbc_hybrid()