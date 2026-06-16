from flask import Flask, request, jsonify
from flask_cors import CORS
import replicate
import os
import requests
import base64

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

# LCW / TRENDYOL ENGELİNİ AŞAN RESİM İNDİRİCİ FONKSİYON
def get_image_as_base64(url):
    try:
        # Siteyi kandırmak için kendimizi normal bir Chrome tarayıcı gibi gösteriyoruz
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        encoded = base64.b64encode(response.content).decode('utf-8')
        return f"data:{content_type};base64,{encoded}"
    except Exception as e:
        print(f"Resim indirme hatası: {e}")
        return None

@app.route('/api/v1/try-on', methods=['POST', 'OPTIONS'])
def process_try_on():
    if request.method == 'OPTIONS':
        return '', 200

    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key not in VALID_API_KEYS:
        return jsonify({"status": "error", "message": "Geçersiz veya eksik API Anahtarı!"}), 401

    try:
        data = request.json
        user_image_b64 = data.get('user_image')
        clothing_url = data.get('clothing_src')
        category = data.get('category', 'upper_body') 

        if not user_image_b64 or not clothing_url:
            return jsonify({"status": "error", "message": "Eksik görsel veya ürün verisi!"}), 400

        print(f"[{VALID_API_KEYS[api_key]}] Hızlı GPU İşlemi Başlatıldı. Kategori: {category}")

        # GÜVENLİK DUVARINI AŞ: Kıyafeti indir ve şifrele
        garm_b64 = get_image_as_base64(clothing_url)
        
        # Eğer bir nedenden indiremezse, eski yöntem olan doğrudan URL'yi kullan (yedek plan)
        garm_input = garm_b64 if garm_b64 else clothing_url

        # YAPAY ZEKA MODELİNE İSTEK GÖNDERME
        output = replicate.run(
            "yisol/idm-vton:c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4",
            input={
                "human_img": user_image_b64,
                "garm_img": garm_input,
                "garment_des": f"A piece of {category} clothing",
                "category": category,
                "crop": False,
                "steps": 30, 
                "seed": 42
            }
        )

        if output:
            return jsonify({
                "status": "success",
                "processed_image": output, 
                "message": "Giydirme işlemi başarıyla tamamlandı!"
            }), 200
        else:
            return jsonify({"status": "error", "message": "GPU sunucusu boş yanıt döndürdü."}), 500

    except Exception as e:
        print(f"Hata Detayı: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
