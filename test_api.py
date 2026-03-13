
import os
import requests
import base64

EVOLUTION_API_URL = "https://whatsapp-1-evolution-api.xqqhik.easypanel.host"
EVOLUTION_API_KEY = "429683C4C977415CAAFCCE10F7D57E11"
EVOLUTION_INSTANCE = "session1"

def send_media_test(number: str, base64_image: str, caption: str):
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    payload = {
        "number": f"{number}@s.whatsapp.net",
        "mediatype": "image",
        "mimetype": "image/png",
        "media": base64_image,
        "caption": caption
    }
    print(f"Sending to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response

# Create a tiny 1x1 black pixel PNG
dummy_png = base64.b64encode(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00\x00\x00\x00:\x7e\x9bW\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82').decode('utf-8')

if __name__ == "__main__":
    send_media_test("2348021299221", dummy_png, "Test image from Antigravity")
