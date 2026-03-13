from math import log
from multiprocessing.dummy.connection import Client
import os
import re
import requests
import tempfile
import uvicorn
from fastapi import FastAPI, HTTPException, Request, logger
from pydantic import BaseModel
from typing import Optional
# import imghdr
import base64
import requests

import redis
import requests
# ...existing code...
import base64
import requests
import os
from .chat_bot import log_info, log_error, process_message, ingest_pdf_for_tenant
import base64
import requests
import os
import time

def log_debug(msg, tenant_id, conversation_id):
    # Stub for log_debug if not imported
    from .logger_utils import logger
    logger.debug(f"[Tenant: {tenant_id} | Conversation: {conversation_id}] {msg}")



app = FastAPI(title="Chatbot API", description="FastAPI Refactor with WhatsApp Integration")

DEFAULT_EMPLOYEE_ID = "obinna.kelechi.adewale@dignityconcept.tech"

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = "DMC"
    employee_id: Optional[str] = DEFAULT_EMPLOYEE_ID
    pushName: Optional[str] = "User"

class LoadPDFRequest(BaseModel):
    tenant_id: str
    file_path: str

def convert_drive_link_to_direct(url: str) -> str:
    """
    Convert a Google Drive link into a direct download URL.
    """
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if not match:
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url)

    if match:
        file_id = match.group(1)
        direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        log_debug(f"Converted Google Drive link to direct: {direct_url}", "N/A", "system")
        return direct_url
    else:
        raise ValueError("Could not extract file ID from Google Drive link")
def fetch_and_save_pdf(url: str) -> str:
    log_info(f"Attempting to download PDF from URL: {url}", "N/A", "system")
    
    session = requests.Session()
    # Initial request to check for the Google Drive virus scan warning
    resp = session.get(url, allow_redirects=True, stream=True, timeout=30)
    
    if resp.status_code != 200:
        raise ValueError(f"Failed to download URL. Status code: {resp.status_code}")

    # --- Handling Google Drive Large File "Confirm" Step ---
    if "drive.google.com" in url and "text/html" in resp.headers.get("Content-Type", ""):
        # Check if there is a 'confirm' token in the cookies/page
        confirm_token = None
        for key, value in resp.cookies.items():
            if key.startswith('download_warning'):
                confirm_token = value
                break
        
        if confirm_token:
            url = url + f"&confirm={confirm_token}"
            resp = session.get(url, stream=True, timeout=30)

    ct = resp.headers.get("Content-Type", "").lower()
    
    if any(allowed in ct for allowed in ["pdf", "binary", "octet-stream", "x-download"]):
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, "wb") as tmp:
            try:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
            except Exception as e:
                # Catching the EOF error during the stream
                os.close(fd)
                raise ConnectionError(f"Stream interrupted: {e}")
        
        log_info(f"Successfully downloaded PDF to {temp_path}", "N/A", "system")
        return temp_path
    else:
        raise ValueError(f"URL did not return a PDF. Got Content-Type: {ct}")
def fetch_and_save_pdfv1(url: str) -> str:
    """
    Download a PDF (or binary stream) from a URL and save it locally.
    Returns the local file path.
    """
    log_info(f"Attempting to download PDF from URL: {url}", "N/A", "system")
    resp = requests.get(url, allow_redirects=True, stream=True, timeout=30)
    
    if resp.status_code != 200:
        raise ValueError(f"Failed to download URL. Status code: {resp.status_code}")
        
    ct = resp.headers.get("Content-Type", "").lower()
    log_info(f"Download response Content-Type: {ct}", "N/A", "system")
    
    # Allow some flexibility in content types
    if "pdf" in ct or "binary" in ct or "octet-stream" in ct or "application/x-download" in ct:
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, "wb") as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
        log_info(f"Successfully downloaded PDF to {temp_path}", "N/A", "system")
        return temp_path
    else:
        # For Google Drive, sometimes it returns text/html for auth or virus warnings
        if "text/html" in ct and "drive.google.com" in url:
            raise ValueError("Google Drive returned an HTML page (possibly a virus warning or authorization requirement) instead of the PDF binary.")
        raise ValueError(f"URL did not return a PDF. Got Content-Type: {ct}")



# --- Redis Setup ---
REDIS_URL = os.getenv("REDIS_URL", "redis://default:65f11924ebc7c9e25051@whatsapp-1_evolution-api-redis:6379")
redis_client = redis.Redis.from_url(REDIS_URL)
# Ollama client setup 

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://whatsapp-1_evolution-api:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "session1")
def send_whatsapp_message_wrond__deployed(number: str, text: str):
    url = f"{EVOLUTION_API_URL}/message/send"
    headers = {"Authorization": f"Bearer {EVOLUTION_API_KEY}"}
    clean_number = number.replace("+", "").strip()
    if "@" not in clean_number:
        recipient = f"{clean_number}@s.whatsapp.net"
    else:
        recipient = clean_number

    payload = {"number": recipient, "text": text}
    
    response = requests.post(url, json=payload, headers=headers)
    return response.json()




def send_media_message(number: str, base64_image: str, caption: str):
    log_info(f"Preparing to send media message to {number}. Image length: {len(base64_image)}", "system", "system")
    # Strip any data URI prefix
    if base64_image.startswith("data:"):
        base64_image = base64_image.split(",", 1)[1]

    base64_image = base64_image.strip()

    try:
        img_bytes = base64.b64decode(base64_image, validate=True)
    except Exception as e:
        log_error(f"Invalid base64 image data: {e}", "system", "system")
        return None

    # Detect Mimetype/Extension
    if img_bytes.startswith(b'\x89PNG'):
        mimetype, ext = "image/png", ".png"
    elif img_bytes.startswith(b'\xff\xd8'):
        mimetype, ext = "image/jpeg", ".jpg"
    else:
        mimetype, ext = "image/png", ".png"

    # --- LOCAL FALLBACK: Save to /temp ---
    # try:
    #     temp_dir = os.path.join(os.getcwd(), "temp_viz")
    #     os.makedirs(temp_dir, exist_ok=True)
    #     filename = f"viz_{int(time.time())}_{number.replace('@', '_')}{ext}"
    #     filepath = os.path.join(temp_dir, filename)
        
    #     with open(filepath, "wb") as f:
    #         f.write(img_bytes)
    #     log_info(f"Image saved locally to: {filepath}", "system", "system")
    # except Exception as e:
    #     log_error(f"Failed to save local image copy: {e}", "system", "system")

    # --- API DISPATCH ---
    payload = {
        "number": number.replace("+", "").strip() if "@" not in number else number,
        "mediatype": "image",
        "mimetype": mimetype,
        "media": base64_image, 
        "caption": caption,
    }

    url = os.getenv(
        "WHATSAPP_MEDIA_URL",
        "https://whatsapp-1-evolution-api.xqqhik.easypanel.host/message/sendMedia/session1"
    )

    headers = {
        "Content-Type": "application/json",
        "apikey": os.getenv("EVOLUTION_API_KEY") 
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        log_info(f"Media API response status: {resp.status_code}", "system", "system")
        return resp
    except Exception as e:
        log_error(f"API delivery failed: {e}", "system", "system")
        return None


def send_whatsapp_message(number: str, text: str):
    # Update this to include your instance name (e.g., session1)
    # The endpoint should be /message/sendText/{{instance_name}}
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    # Evolution API uses 'apikey' in the header, not 'Authorization' Bearer
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    
    clean_number = number.replace("+", "").strip()
    recipient = f"{clean_number}@s.whatsapp.net" if "@" not in clean_number else clean_number

    payload = {
        "number": recipient,
        "text": text,
        "linkPreview": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

@app.get("/")
def read_root():
    return {"status": "online", "message": "Chatbot API is running"}

@app.post("/chatbot_webhook")
async def chatbot_webhook(request: ChatRequest):
    try:
        response = process_message(
            message_content=request.message,
            conversation_id=request.conversation_id or "postman_session",
            tenant_id=request.tenant_id or "DMC",
            employee_id=request.employee_id or DEFAULT_EMPLOYEE_ID,
            push_name=request.pushName or "User"
        )
        return response
    except Exception as e:
        log_error(f"Error in chatbot_webhook: {e}", request.tenant_id or "DMC", "postman_session")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/load_pdf")
async def load_pdf(request: LoadPDFRequest):
    tenant_id = request.tenant_id
    raw_file_path = request.file_path.strip()
    local_pdf_path = None
    
    log_info(f"load_pdf triggered for tenant {tenant_id}. Input path: {raw_file_path}", tenant_id, "system")

    try:
        # 1. Determine if it's a URL or local path
        if raw_file_path.startswith(("http://", "https://")):
            processed_url = raw_file_path
            
            # Convert viewer link to direct download format if it's Google Drive
            if "drive.google.com" in processed_url:
                try:
                    processed_url = convert_drive_link_to_direct(processed_url)
                except ValueError as ve:
                    log_error(f"Failed to convert drive link: {ve}", tenant_id, "system")
                    raise HTTPException(status_code=400, detail=str(ve))
            
            # Download and save locally
            try:
                local_pdf_path = fetch_and_save_pdf(processed_url)
                log_info(f"URL processed. Local path set to: {local_pdf_path}", tenant_id, "system")
            except Exception as e:
                log_error(f"Failed to download PDF from {processed_url}: {e}", tenant_id, "system")
                raise HTTPException(status_code=500, detail=f"Download failed: {e}")
        else:
            # Assume local path
            if os.path.exists(raw_file_path):
                local_pdf_path = raw_file_path
                log_info(f"Using local file path: {local_pdf_path}", tenant_id, "system")
            else:
                log_error(f"Local file not found: {raw_file_path}", tenant_id, "system")
                raise HTTPException(status_code=404, detail=f"Local file not found: {raw_file_path}")

        if not local_pdf_path:
            raise ValueError("Failed to resolve local_pdf_path")

        # 2. Ingest using local path
        log_info(f"Calling ingest_pdf_for_tenant with path: {local_pdf_path}", tenant_id, "system")
        result = ingest_pdf_for_tenant(
            tenant_id=tenant_id,
            file_path=local_pdf_path
        )
        
        if result["status"] == "success":
            return result
        else:
            log_error(f"ingest_pdf_for_tenant reported failure: {result['message']}", tenant_id, "system")
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Unexpected error in load_pdf: {e}", tenant_id, "system")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    log_info("Received webhook request", "unknown", "unknown")
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            message_text = ""
            phone_number = "unknown"
            push_name = "User"
            
            # Evolution API specific data structure
            if "data" in payload and isinstance(payload["data"], dict):
                data = payload["data"]
                phone_number = data.get("key", {}).get("remoteJid", "").split("@")[0]
                push_name = data.get("pushName") or "User"
                message_text = data.get("message", {}).get("conversation", "") or \
                               data.get("message", {}).get("extendedTextMessage", {}).get("text", "")
            
            # Fallback for other JSON formats
            if not message_text:
                message_text = payload.get("message", {}).get("text") or payload.get("text", "")
            if phone_number == "unknown":
                phone_number = payload.get("sender") or payload.get("from") or "anonymous"
            if push_name == "User":
                push_name = payload.get("pushName") or "User"
            
            tenant_id = payload.get("tenant_id", "DMC")
            employee_id = payload.get("employee_id", DEFAULT_EMPLOYEE_ID)
            
        else:
            # Form data handling
            form_data = await request.form()
            message_text = form_data.get("message", "")
            phone_number = form_data.get("phone_number") or form_data.get("sender") or "anonymous"
            push_name = form_data.get("pushName") or "User"
            tenant_id = form_data.get("tenant_id", "DMC")
            employee_id = form_data.get("employee_id", DEFAULT_EMPLOYEE_ID)

        if not message_text:
            return {"status": "ignored", "reason": "empty message"}
        # message_text='I need chart of monhtly transaction count from inception till date check customer_transaction schema e'
        # employee_id = DEFAULT_EMPLOYEE_ID
        # phone_number = "2348021299221"
        # conversation_id = "phone_numbdeeeddeDdssdDDssDr"
        # tenant_id = "DMC"
        # push_name = "User"
        log_info(f"Processing message from {phone_number}: {message_text}", tenant_id, phone_number)
        
        response = process_message(
            message_content=message_text,
            conversation_id=phone_number,
            tenant_id=tenant_id,
            employee_id=employee_id,
            push_name=push_name
        )
        
        log_info(f"Chatbot response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}", tenant_id, phone_number)
        if isinstance(response, dict):
            viz_image = response.get("viz_image")
            log_info(f"Response viz_image present: {bool(viz_image)}", tenant_id, phone_number)
            if viz_image:
                log_info(f"Entering image sending block. Image length: {len(viz_image)}", tenant_id, phone_number)
                # Send image first
                media_res = send_media_message(
                    phone_number, 
                    viz_image, 
                    caption="Here is the chart you requested."
                )
                log_info(f"Media API response status: {media_res.status_code}", tenant_id, phone_number)
                
                # Send analysis text separately
                text_to_send = response.get("text", "Analysis complete.")
                return send_whatsapp_message(phone_number, text_to_send)
            else:
                log_info("No visualization image found in dict response.", tenant_id, phone_number)
        else:
            log_info(f"Response is not a dict, it is a {type(response)}. Skipping image logic.", tenant_id, phone_number)
        
        # Fallback for text-only responses
        text_content = response.get("text", str(response)) if isinstance(response, dict) else str(response)
        message_res = send_whatsapp_message(phone_number, text_content)
        log_info(f"Text message API response: {message_res}", tenant_id, phone_number)
        return message_res

    except Exception as e:
        log_error(f"Error in webhook: {e}", "unknown", "unknown")
        raise HTTPException(status_code=500, detail=str(e))

# if __name__ == "__main__":
#     uvicorn.run(app, host=" (")


def send_whatsapp_message1(number: str, text: str):
    url = f"{EVOLUTION_API_URL}/message/send"
    headers = {"Authorization": f"Bearer {EVOLUTION_API_KEY}"}
    payload = {"number": number, "text": text}
    response = requests.post(url, json=payload, headers=headers)
    return response.json()



def send_media_messagevgemini(number: str, base64_image: str, caption: str):
    # Strip any data URI prefix if present
    if base64_image.startswith("data:"):
        base64_image = base64_image.split(",", 1)[1]

    base64_image = base64_image.strip()

    try:
        img_bytes = base64.b64decode(base64_image, validate=True)
    except Exception as e:
        logger.error(f"Invalid base64 image data: {e}")
        return None

    # Detect Mimetype by checking file signatures (magic bytes)
    # PNG starts with \x89PNG, JPEG starts with \xff\xd8
    if img_bytes.startswith(b'\x89PNG'):
        mimetype = "image/png"
    elif img_bytes.startswith(b'\xff\xd8'):
        mimetype = "image/jpeg"
    else:
        mimetype = "image/png" # Default fallback

    # Note: Evolution API expects the base64 string in the "media" or "base64" key
    # depending on your specific version/instance setup.
    payload = {
        "number": number.replace("+", "").strip() if "@" not in number else number,
        "mediatype": "image",
        "mimetype": mimetype,
        "media": base64_image, 
        "caption": caption,
    }

    url = os.getenv(
        "WHATSAPP_MEDIA_URL",
        "https://whatsapp-1-evolution-api.xqqhik.easypanel.host/message/sendMedia/session1"
    )

    # CRITICAL: Added 'apikey' to headers as Evolution API requires it
    headers = {
        "Content-Type": "application/json",
        "apikey": os.getenv("EVOLUTION_API_KEY") 
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        log_info(f"Media API response status: {resp.status_code} body: {resp.text}", "system", "system")
        return resp
    except Exception as e:
        log_error(f"Failed to send media request: {e}", "system", "system")
        return None


def send_media_messagev2(number: str, base64_image: str, caption: str):
    # Strip any data URI prefix
    if base64_image.startswith("data:"):
        base64_image = base64_image.split(",", 1)[1]

    base64_image = base64_image.strip()

    try:
        img_bytes = base64.b64decode(base64_image, validate=True)
    except Exception as e:
        logger.error(f"Invalid base64 image data: {e}")
        return None

    kind = imghdr.what(None, h=img_bytes)
    mimetype = "image/png" if kind == "png" else "image/jpeg" if kind in ("jpeg", "jpg") else "application/octet-stream"

    payload = {
        "number": number,
        "mediatype": "image",
        "mimetype": mimetype,
        "media": base64_image,
        "caption": caption,
    }

    url = os.getenv(
        "WHATSAPP_MEDIA_URL",
        "https://whatsapp-1-evolution-api.xqqhik.easypanel.host/message/sendMedia/session1"
    )

    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    log_info(f"Media API response status: {resp.status_code} body: {resp.text}", "system", "system")
    return resp


def send_media_messagev1(number: str, base64_image: str, caption: str):
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    payload = {
        "number": f"{number.replace('+', '').strip()}",  # Some versions don't want @s.whatsapp.net here if it's appended by the API
        "mediatype": "image",
        "mimetype": "image/png",
        "media": base64_image,
        "caption": caption
    }
    log_info(f"Sending media message to {number}. Payload keys: {payload.keys()}", "system", "system")
    return requests.post(url, json=payload, headers=headers)