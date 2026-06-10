from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os
import replicate
import requests

app = Flask(__name__)
# Güvenlik polisinin (CORS) özel VIP anahtarımıza (X-API-Key) izin vermesini sağlıyoruz:
CORS(app, resources={r"/*": {"origins": "*"}}, allow_headers="*")

# ==========================================
# SAAS / B2B E-TİCARET API AYARLARI
# ==========================================
VALID_API_KEYS = {
    "lcwaikiki_secret_prod_9912": "LC Waikiki TR",
    "trendyol_kabin_key_8841": "Trendyol Pazaryeri",
    "test_partner_demo_1122": "Demo Test Kullanıcısı"
}

@app.route('/api/v1/try-on', methods=['POST'])
def process_try_on():
    # ------------------------------------------------------------------
    # GÜVENLİK KONTROLÜ (API KEY CHECK)
    # ------------------------------------------------------------------
    api_key = request.headers.get('X-API-Key')
    
    if not api_key or api_key not in VALID_API_KEYS:
        print("YETKİSİZ ERİŞİM DENEMESİ: Geçersiz veya eksik API Key!")
        return jsonify({
            "status": "error",
            "message": "Unauthorized. Invalid or missing X-API-Key header."
        }), 401

    partner_name = VALID_API_KEYS[api_key]
    print(f"İstek Doğrulandı! Müşteri: {partner_name}. İşlem başlatılıyor...")

    try:
        data = request.json
        user_image_b64 = data.get('user_image')
        clothing_src = data.get('clothing_src')
        
        if not user_image_b64 or not clothing_src:
            return jsonify({
                "status": "error",
                "message": "Missing 'user_image' or 'clothing_src' in request body."
            }), 400

        # 1. Müşteri fotoğrafını geçici olarak kaydet
        user_image_path = "temp_user.jpg"
        with open(user_image_path, "wb") as fh:
            if "," in user_image_b64:
                user_image_b64 = user_image_b64.split(",")[1]
            fh.write(base64.b64decode(user_image_b64))

        # 2. Kıyafet Fotoğrafını İndir
        print(f"Kıyafet görseli {partner_name} sunucularından indiriliyor...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
        }
        
        garm_response = requests.get(clothing_src, headers=headers, timeout=20)
        if garm_response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"Failed to fetch clothing image. HTTP {garm_response.status_code}"
            }), 400
            
        garm_path = "temp_garm.jpg"
        with open(garm_path, "wb") as f:
            f.write(garm_response.content)

        # 3. IDM-VTON Yapay Zeka Modelini Çalıştır
        print("IDM-VTON yapay zeka işlem hattı tetiklendi...")
        
        output = replicate.run(
            "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
            input={
                "human_img": open(user_image_path, "rb"), 
                "garm_img": open(garm_path, "rb"),
                "category": "upper_body",
                "garment_des": "Clothing Item",
                "crop": True, 
                "steps": 30
            }
        )

        print("Yapay Zeka işlemi başarıyla tamamlandı!")
        
        # 4. Çıktı URL'sini Belirle
        result_image_url = ""
        if isinstance(output, list):
            result_image_url = str(output[0])
        elif hasattr(output, 'url'):
            result_image_url = output.url
        else:
            result_image_url = str(output)

        # 5. Sonucu Base64'e çevir ve Frontend'e yolla
        response = requests.get(result_image_url, timeout=30)
        processed_base64 = "data:image/jpeg;base64," + base64.b64encode(response.content).decode('utf-8')

        return jsonify({
            "status": "success",
            "partner": partner_name,
            "message": "Giydirme işlemi başarıyla sonuçlandı.",
            "processed_image": processed_base64
        })

    except Exception as e:
        print(f"HATA OLUŞTU [{partner_name}]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
