from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os
import replicate
import requests

app = Flask(__name__)
CORS(app)

# ==========================================
# REPLICATE API AYARLARI
# ==========================================
# API Token artık bulut sunucunun gizli ayarlarından (Environment Variables) çekilecek 

@app.route('/try-on', methods=['POST'])
def process_try_on():
    try:
        data = request.json
        user_image_b64 = data.get('user_image')
        clothing_src = data.get('clothing_src')
        
        print("Fotoğraf alındı! İşlem başlatılıyor...")

        # 1. Müşteri fotoğrafını geçici olarak kaydet
        user_image_path = "temp_user.jpg"
        with open(user_image_path, "wb") as fh:
            fh.write(base64.b64decode(user_image_b64.split(",")[1]))

        # 2. Kıyafet Fotoğrafını Hazırla (YENİ SİSTEM)
        garm_input = None
        if clothing_src.startswith("http"):
            # Eğer Firebase (URL) üzerinden geliyorsa resmi indirip geçici kaydet
            print("Kıyafet Firebase üzerinden indiriliyor...")
            # Kendimizi gerçek bir tarayıcı (Chrome) gibi tanıtıyoruz ki güvenlik duvarlarına takılmayalım
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
            }
            garm_response = requests.get(clothing_src, headers=headers, timeout=20)
            garm_path = "temp_garm.jpg"
            with open(garm_path, "wb") as f:
                f.write(garm_response.content)
            garm_input = open(garm_path, "rb")
        else:
            # Eski sistem (yerel dosya) kullanılıyorsa
            garm_filename = clothing_src.split('/')[-1]
            garm_input = open(garm_filename, "rb")

        # 3. IDM-VTON API'sine istek at
        print("IDM-VTON sunucularına bağlanılıyor...")
        
        output = replicate.run(
            "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
            input={
                "human_img": open(user_image_path, "rb"), 
                "garm_img": garm_input, # İndirilen dosyayı buraya veriyoruz
                "category": "upper_body",
                "garment_des": "T-shirt",
                "crop": True, 
                "steps": 30
            }
        )

        print("Yapay Zeka işlemi tamamlandı!")
        
        # 4. URL'yi al
        result_image_url = ""
        if isinstance(output, list):
            result_image_url = str(output[0])
        elif hasattr(output, 'url'):
            result_image_url = output.url
        else:
            result_image_url = str(output)

        # 5. Gelen sonucu base64'e çevir Frontend'e yolla
        response = requests.get(result_image_url, timeout=30)
        processed_base64 = "data:image/jpeg;base64," + base64.b64encode(response.content).decode('utf-8')

        return jsonify({
            "status": "success",
            "message": "Giydirme işlemi başarılı!",
            "processed_image": processed_base64
        })

    except Exception as e:
        print(f"HATA OLUŞTU: {e}")
        return jsonify({"status": "error", "message": str(e)})

    if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
