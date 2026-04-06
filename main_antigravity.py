import base64
import time
import requests
import tempfile
import uvicorn
import imghdr
import redis
import logging
import os
import re
from fastapi import FastAPI, HTTPException, Request, Form, logger as fastapi_logger
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import create_engine, text
from .chat_bot import log_info, log_error, process_message, ingest_pdf_for_tenant

logger = logging.getLogger(__name__)

# query ="Whay is my account balance 08027790963"
query ="I want to buy airtime "
# query =" Ayodele Adeyinka 1994-04-05 ayodelefestusng1@gmail.com 08027790963 Male NIN is 89475355532 Software Engineer Nigeriam"
# query ="Banking Nigeriam"
# query ="16 04 1979 13012345670 08021299221"
# query ="Ayodele Adeyinka Nigerian Banking ayodelefestusng@gmail.com male 08021299221 16 04 1979"
conversation_ids = "debug_conversarrrrrteddddddddd12s77dd22errrre2ell7"

def log_debug(msg, tenant_id, conversation_id):
    # Stub for log_debug if not imported
    from .logger_utils import logger
    logger.debug(f"[Tenant: {tenant_id} | Conversation: {conversation_id}] {msg}")

app = FastAPI(title="Chatbot API", description="FastAPI Refactor with WhatsApp Integration")

DEFAULT_EMPLOYEE_ID = "obinna.kelechi.adewale@dignityconcept.tech"
DEBUG_MODE = True

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = "DMC"
    employee_id: Optional[str] = DEFAULT_EMPLOYEE_ID
    pushName: Optional[str] = "User"

class LoadPDFRequest(BaseModel):
    tenant_id: str
    file_path: str

class CTAPayload(BaseModel):
    phone_number: str
    event: str
    tenant_id: str = "DMC"
    employee_id: str = "unknown"
    customer_name: str = "Customer"
    pending_intent: str = ""
    amount: Optional[float] = None
    reference: Optional[str] = None

class VFDInwardCredit(BaseModel):
    reference: str
    amount: float
    accountNumber: str
    originatorAccountName: str
    originatorAccountNumber: str
    originatorBankCode: str
    narration: str
    createdAt: str

def convert_drive_link_to_direct(url: str) -> str:
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
    resp = session.get(url, allow_redirects=True, stream=True, timeout=30)
    if resp.status_code != 200:
        raise ValueError(f"Failed to download URL. Status code: {resp.status_code}")
    if "drive.google.com" in url and "text/html" in resp.headers.get("Content-Type", ""):
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
                os.close(fd)
                raise ConnectionError(f"Stream interrupted: {e}")
        log_info(f"Successfully downloaded PDF to {temp_path}", "N/A", "system")
        return temp_path
    else:
        raise ValueError(f"URL did not return a PDF. Got Content-Type: {ct}")

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://default:65f11924ebc7c9e25051@whatsapp-1_evolution-api-redis:6379")
redis_client = redis.Redis.from_url(REDIS_URL)

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
def send_whatsapp_message(number: str, text: str):
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    clean_number = str(number).replace("+", "").strip()
    recipient = f"{clean_number}@s.whatsapp.net" if "@" not in clean_number else clean_number
    payload = {"number": recipient, "text": str(text), "linkPreview": False}
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

@app.get("/")
def read_root():
    return {"status": "online", "message": "Chatbot API is running"}

@app.post("/chatbot_webhook")
async def chatbot_webhook(chat_request: ChatRequest):
    try:
        response = process_message(
            message_content=chat_request.message,
            conversation_id=chat_request.conversation_id or "postman_session",
            tenant_id=chat_request.tenant_id or "DMC",
            employee_id=chat_request.employee_id or DEFAULT_EMPLOYEE_ID,
            push_name=chat_request.pushName or "User"
        )
        return response
    except Exception as e:
        log_error(f"Error in chatbot_webhook: {e}", chat_request.tenant_id or "DMC", "postman_session")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    log_info("Received webhook request", "unknown", "unknown")
    try:
        content_type = request.headers.get("content-type", "")
        message_text = ""
        phone_number = "unknown"
        push_name = "User"
        device_type = "unknown"
        tenant_id = "DMC"
        employee_id = DEFAULT_EMPLOYEE_ID
        source = "unknown"

        if "application/json" in content_type:
            payload = await request.json()
            if "data" in payload and isinstance(payload["data"], dict):
                data = payload["data"]
                phone_number = data.get("key", {}).get("remoteJid", "").split("@")[0]
                push_name = data.get("pushName") or "User"
                message_text = data.get("message", {}).get("conversation", "") or \
                               data.get("message", {}).get("extendedTextMessage", {}).get("text", "")
                source = data.get("source") or "unknown"
            if not message_text:
                message_text = payload.get("message", {}).get("text") or payload.get("text", "")
            if phone_number == "unknown":
                phone_number = payload.get("sender") or payload.get("from") or "anonymous"
            tenant_id = payload.get("tenant_id", "DMC")
            employee_id = payload.get("employee_id", DEFAULT_EMPLOYEE_ID)
        else:
            form_data = await request.form()
            message_text = form_data.get("message", "")
            phone_number = form_data.get("phone_number") or form_data.get("sender") or "anonymous"
            push_name = form_data.get("pushName") or "User"
            tenant_id = form_data.get("tenant_id", "DMC")
            employee_id = form_data.get("employee_id", DEFAULT_EMPLOYEE_ID)

        if source in ["ios", "android"]:
            device_type = "phone"
        elif source == "web":
            device_type = "web"

        if not message_text:
            return {"status": "ignored", "reason": "empty message"}
        
        response = process_message(
            message_content=str(message_text),
            conversation_id=str(phone_number),
            phone_number=str(phone_number),
            tenant_id=str(tenant_id),
            employee_id=str(employee_id),
            push_name=str(push_name),
            device_type=str(device_type)
        )
        
        if isinstance(response, dict):
            viz_image = response.get("viz_image")
            if viz_image:
                send_media_message(phone_number, viz_image, caption="Here is the chart you requested.")
                text_to_send = response.get("text", "Analysis complete.")
                return send_whatsapp_message(phone_number, text_to_send)
            text_content = response.get("text", str(response))
            return send_whatsapp_message(phone_number, text_content)
        return send_whatsapp_message(phone_number, str(response))
    except Exception as e:
        log_error(f"Error in webhook: {e}", "unknown", "unknown")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/vfd_inward_credit")
async def vfd_inward_credit_webhook(payload: VFDInwardCredit):
    log_info(f"Received VFD Credit: {payload.reference}", "system", "system")
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        return {"status": "error", "message": "DB URL not set"}
    try:
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_uri)
        with engine.connect() as conn:
            query = text("SELECT phone_number, first_name FROM customer_customer WHERE account_number = :acc")
            cust = conn.execute(query, {"acc": payload.accountNumber}).fetchone()
            if not cust:
                return {"status": "error", "message": "Customer not found"}
            cta_payload = CTAPayload(
                phone_number=cust[0],
                event="inward_credit",
                customer_name=cust[1],
                amount=payload.amount,
                reference=payload.reference
            )
            await trigger_cta_webhook(cta_payload)
            return {"status": "success"}
    except Exception as e:
        log_error(f"VFD Webhook error: {e}", "system", "system")
        return {"status": "error", "message": str(e)}

@app.post("/trigger_cta_webhook")
async def trigger_cta_webhook(payload: CTAPayload):
    log_info(f"Triggering CTA: {payload.event}", payload.tenant_id, payload.phone_number)
    if payload.event == "inward_credit":
        message = f"🔔 *Credit Alert!*\nHello {payload.customer_name}, your account was credited with *₦{payload.amount:,.2f}*.\nRef: {payload.reference}"
        return send_whatsapp_message(payload.phone_number, message)
    
    prompt = f"The customer {payload.customer_name} completed {payload.event}. Congratulate them."
    response = process_message(
        message_content=prompt,
        conversation_id=payload.phone_number,
        phone_number=payload.phone_number,
        tenant_id=payload.tenant_id,
        employee_id="SYSTEM",
        push_name=payload.customer_name,
        device_type="phone"
    )
    text_content = response.get("text", str(response)) if isinstance(response, dict) else str(response)
    return send_whatsapp_message(payload.phone_number, text_content)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


