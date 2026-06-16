from flask import Flask, request, jsonify
from flask_cors import CORS
import replicate
import os
import requests
import base64
import tempfile

app = Flask(__name__)

# NETLIFY AYNANIZA KESİN İZİN VE CORS AYARLARI
CORS(app, resources={r"/*": {"origins": "*"}}, allow_headers=["Content-Type", "X-API-Key", "Authorization"], methods=["GET", "POST", "OPTIONS"])

# ==========================================
# GÜVENLİK AYARLARI
# ==========================================
VALID_API_KEYS = {
    "lcwaikiki_secret_prod_9912": "Sistem TR",
    "trendyol_kabin_key_8841": "Pazaryeri",
    "test_partner_demo_1122": "Demo Test Kullanıcısı"
}

# ZIRH DELİCİ: İNDİRME VE FİZİKSEL DOSYA OLUŞTURMA FONKSİYONU
def create_temp_file(img_data):
    try:
        # Geçici bir dosya oluştur (.jpg formatında)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        
        if img_data.startswith('data:image'):
            # Kamera görüntünüzü (Base64) fiziksel dosyaya çevir
            header, encoded = img_data.split(",", 1)
            temp_file.write(base64.b64decode(encoded))
        elif img_data.startswith('http'):
            # LCW / Trendyol kıyafetini normal bir kullanıcı gibi indir
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            res = requests.get(img_data, headers=headers, timeout=15)
            res.raise_for_status()
            temp_file.write(res.content)
        
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Dosya oluşturma hatası: {e}")
        return None

@app.route('/api/v1/try-on', methods=['POST', 'OPTIONS'])
def process_try_on():
    if request.method == 'OPTIONS':
        return '', 200

    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key not in VALID_API_KEYS:
        return jsonify({"status": "error", "message": "Geçersiz veya eksik API Anahtarı!"}), 401

    human_path = None
    garm_path = None

    try:
        data = request.json
        user_image_b64 = data.get('user_image')
        clothing_url = data.get('clothing_src')
        category = data.get('category', 'upper_body') 

        if not user_image_b64 or not clothing_url:
            return jsonify({"status": "error", "message": "Eksik görsel veya ürün verisi!"}), 400

        print(f"[{VALID_API_KEYS[api_key]}] Hızlı GPU İşlemi Başlatıldı. Kategori: {category}")

        # 1. GÖRSELLERİ SUNUCUYA FİZİKSEL OLARAK İNDİR (Tüm Engelleri Aşar)
        human_path = create_temp_file(user_image_b64)
        garm_path = create_temp_file(clothing_url)

        if not human_path or not garm_path:
            return jsonify({"status": "error", "message": "Resimler sunucuya indirilemedi. Bağlantı engellenmiş olabilir."}), 500

        # 2. YAPAY ZEKA MODELİNE GERÇEK DOSYA OLARAK GÖNDERME
        with open(human_path, "rb") as h_file, open(garm_path, "rb") as g_file:
            output = replicate.run(
                "yisol/idm-vton:c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4",
                input={
                    "human_img": h_file,
                    "garm_img": g_file,
                    "garment_des": f"A piece of {category} clothing",
                    "category": category,
                    "crop": False,
                    "steps": 30, 
                    "seed": 42
                }
            )

        # 3. İŞLEM BİTİNCE GEÇİCİ DOSYALARI SİL (Sunucu hafızası dolmasın diye)
        os.remove(human_path)
        os.remove(garm_path)

        if output:
            return jsonify({
                "status": "success",
                "processed_image": output, 
                "message": "Giydirme işlemi başarıyla tamamlandı!"
            }), 200
        else:
            return jsonify({"status": "error", "message": "GPU sunucusu boş yanıt döndürdü."}), 500

    except Exception as e:
        # Hata anında da dosyaları silmeyi unutma
        if human_path and os.path.exists(human_path): os.remove(human_path)
        if garm_path and os.path.exists(garm_path): os.remove(garm_path)
        
        print(f"Hata Detayı: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
