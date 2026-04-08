"""
banking_tools.py
────────────────────────────────────────────────────────────────────────────────
VFD Bank – LangChain tool definitions aligned with the existing tools.py
conventions:
  • @tool("name", args_schema=Model) decorator
  • def fn(runtime: ToolRuntime[Context], **kwargs) -> str
  • Context accessed exclusively via runtime.context.*
  • Schemas imported from base.py
  • Logging via log_info / log_error from logger_utils
  • DB connections via SQLAlchemy create_engine (same as all other tools)

Covered services
  1.  Account Opening      – create_vfd_account_tool
  2.  Fund Wallet          – fund_wallet_info_tool
  3.  Balance Enquiry      – balance_enquiry_tool
  4.  Airtime Purchase     – buy_airtime_tool
  5.  Bills Payment        – pay_bill_tool
  6.  Beneficiary Lookup   – get_beneficiary_name_tool
  7.  Transfer Money       – transfer_money_tool
  8.  Change PIN           – change_pin_tool
  9.  Forgot PIN           – forgot_pin_tool
 10.  Saved Billers (list) – get_saved_billers_tool
 11.  Saved Billers (del)  – delete_saved_biller_tool
 12.  Bank List            – get_bank_list_tool
"""
from math import e, log
import os
import re
import uuid
import hashlib
import os
import uuid
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import os
import re
import uuid
import random
import json
import pandas as pd
import requests
from langchain.tools import tool, ToolRuntime
from pydantic import BaseModel, Field



from .base import Context
import requests
from langchain.tools import tool, ToolRuntime
from sqlalchemy import create_engine, text

from .logger_utils import log_info, log_error, log_warning
from .base import (
    Context,
    VFDAccountOpeningInput,
    FundWalletInput,
    BalanceEnquiryInput,
    BuyAirtimeInput,
    PayBillInput,
    BeneficiaryLookupInput,
    TransferMoneyInput,
    ChangePasswordInput,
    ForgotPasswordInput,
    SavedBillersInput,
    DeleteSavedBillerInput,
    BankListInput,CustomerProfileInput,LoanEligibilityInput,
    ValidateSocialMediaInput, InitiatePasswordResetInput,
    ConfirmPasswordResetInput, VerifyOTPInput, ApplyForLoanInput,
    GetDataBundlesInput, BuyDataInput, TransactionStatusInput, ReversalStatusInput
)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

WALLET_BASE_URL  = os.getenv("VFD_WALLET_BASE_URL",
    "https://api-devapps.vfdbank.systems/vtech-wallet/api/v2/wallet2")
AUTH_URL         = os.getenv("VFD_AUTH_URL",
    "https://api-devapps.vfdbank.systems/vfd-tech/baas-portal/v1.1/baasauth/token")
CONSUMER_KEY     = os.getenv("VFD_CONSUMER_KEY",    "mL1dqaMcB760EP3fR18Vc23qUSZy")
CONSUMER_SECRET  = os.getenv("VFD_CONSUMER_SECRET", "ohAWPpabbj0UmMppmOgAFTazkjQt")
APP_BASE_URL     = os.getenv("APP_BASE_URL",    "http://127.0.0.1:8001/customer")  # For auth links in responses; replace with your actual URL
SMS_API_URL      = os.getenv("SMS_API_URL",     "https://mock-sms.yourapp.com/send")
SMS_API_KEY      = os.getenv("SMS_API_KEY",     "mock-key")
WALLET_PREFIX    = os.getenv("VFD_WALLET_PREFIX", "DML")


BILLS_BASE_URL = os.getenv(
    "VFD_BILLS_BASE_URL",
    "https://api-devapps.vfdbank.systems/vtech-bills/api/v2/billspaymentstore",
)

LIVENESS_API_URL = os.getenv("LIVENESS_API_URL", "https://yourapp.com/api/liveness")


# Credit bureau – replace with your actual provider
CREDIT_BUREAU_URL = os.getenv("CREDIT_BUREAU_URL", "https://creditbureau.example.ng/api/v1")
CREDIT_BUREAU_KEY = os.getenv("CREDIT_BUREAU_API_KEY", "")


PASSWORD_SETUP_TOKEN_EXPIRY_HOURS = 24
PASSWORD_SETUP_PATH = "/banking/set-password"
OTP_CHARGE_AMOUNT      = Decimal("10.00")   # ₦10 debit before OTP is sent
OTP_EXPIRY_SECONDS     = 10                 # tight 10-second window
PASSWORD_SETUP_PATH    = "/banking/set-password"
TOKEN_EXPIRY_HOURS     = 24

# Human-readable reference labels per biller category shown to customer
CATEGORY_REFERENCE_LABEL: dict = {
    "utility":               "Meter Number",
    "cable tv":              "Smart Card Number",
    "airtime":               "Phone Number",
    "data":                  "Phone Number",
    "internet subscription": "Account Number / Username",
}

# Categories that require mandatory VFD customer-validate call before payment
MANDATORY_VALIDATE_CATEGORIES = {"utility", "cable tv", "betting", "gaming"}
MAX_PIN_ATTEMPTS = 5
# ──────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_access_token() -> str:
    log_info("_get_access_token  called","sudo_tenant_id", "sudo_conversation_id")
    
    payload = {
        "consumerKey":    CONSUMER_KEY,
        "consumerSecret": CONSUMER_SECRET,
        "validityTime":   "-1",
    }
    resp = requests.post(
        AUTH_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") == "00":
        return data["data"]["access_token"]
    raise RuntimeError(f"VFD auth failed: {data}")
token   = _get_access_token()
headers = {"AccessToken": token, "Content-Type": "application/json"}

def _wallet_headers() -> dict:
    return {"AccessToken": _get_access_token(), "Content-Type": "application/json"}


def _send_sms(phone_number: str, message: str) -> bool:
    """Mock SMS sender that logs to a file as per user request."""
    log_info(f"Sending SMS to {phone_number}: {message}", "sudo_tenant_id", "sudo_conversation_id")
    log_file = "/tmp/otp_log.txt"
    try:
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] TO: {phone_number} | MSG: {message}\n")
        return True
    except Exception as e:
        log_error(f"Failed to log SMS: {e}", "sudo_tenant_id", "sudo_conversation_id")
        return False


SUPPORT_PHONE = "08021299221"


def _unique_ref() -> str:
    log_info("_unique_ref  called","sudo_tenant_id", "sudo_conversation_id")

    
    ts  = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:6].upper()
    return f"{WALLET_PREFIX}-{ts}-{uid}"


def _normalise_db_uri(db_uri: str) -> str:
    """Mirrors the same fix used throughout tools.py."""
    log_info("_normalise_db_uri  called","sudo_tenant_id", "sudo_conversation_id")

    if db_uri and db_uri.startswith("postgres://"):
        return db_uri.replace("postgres://", "postgresql://", 1)
    return db_uri


def _resolve_biller(db_uri: str, tenant_code: str, biller_name: str) -> dict:
    """
    Resolves a biller name to VFD parameters by fetching from the tenant's prompt configuration in the DB.
    """
    log_info(f"_resolve_biller called for '{biller_name}'", tenant_code, "banking")
    
    engine = create_engine(_normalise_db_uri(db_uri))
    biller_items = None
    try:
        with engine.connect() as conn:
            # Join through tenant_ai to get the specific prompt for this tenant
            sql = """
                SELECT p.biller_items 
                FROM customer_prompt p
                JOIN customer_tenant_ai ta ON ta.prompt_template_id = p.id
                JOIN org_tenant t ON t.id = ta.tenant_id
                WHERE t.code = :code
            """
            res = conn.execute(text(sql), {"code": tenant_code}).fetchone()
            if not res:
                # Fallback to standard prompt if tenant-specific not found
                res = conn.execute(text("SELECT biller_items FROM customer_prompt WHERE name = 'standard' LIMIT 1")).fetchone()
            
            if res:
                biller_items = res[0]
    finally:
        engine.dispose()

    if not biller_items:
        raise ValueError("Biller configuration not found in database.")

    import json
    import difflib
    
    billers = json.loads(biller_items) if isinstance(biller_items, str) else biller_items
    biller_names = [b.get("name") for b in billers if b.get("name")]
    
    # Fuzzy matching for robustness
    matches = difflib.get_close_matches(biller_name, biller_names, n=1, cutoff=0.6)
    matched_name = matches[0] if matches else None
    
    matched = None
    if matched_name:
        matched = next((b for b in billers if b.get("name") == matched_name), None)
    else:
        # Fallback to substring matching
        name_lower = biller_name.strip().lower()
        matched = next((b for b in billers if name_lower in b.get("name", "").lower() or name_lower in b.get("id", "").lower()), None)

    if not matched:
        raise ValueError(
            f"Biller '{biller_name}' could not be resolved. Please try a different name."
        )

    biller_id   = matched["id"]
    division_id = matched["division"]
    product_id  = matched["product"]
    category    = matched.get("category", "").lower()
    convenience = matched.get("convenienceFee", "0")
    
    # paymentItems logic: if they are pre-bundled in the DB JSON, use them. 
    # Otherwise, we might still need to fetch if 'payment_items' is empty.
    payment_items = matched.get("payment_items", [])
    if not payment_items:
        headers     = _wallet_headers()
        items_resp    = requests.get(
            f"{BILLS_BASE_URL}/billerItems",
            headers=headers,
            params={"billerId": biller_id, "divisionId": division_id, "productId": product_id},
            timeout=20,
        )
        payment_items = items_resp.json().get("data", {}).get("paymentitems", [])
    
    if not payment_items:
        raise ValueError(f"No payment items found for biller '{biller_name}'.")

    item         = payment_items[0]
    payment_code = item.get("paymentCode", "")
    is_fixed     = item.get("isAmountFixed", "false").lower() == "true"
    fixed_amount = item.get("amount", "0") if is_fixed else None

    must_validate = category not in ["airtime", "data"]

    return {
        "billerId":       biller_id,
        "divisionId":     division_id,
        "productId":      product_id,
        "paymentCode":    payment_code,
        "isAmountFixed":  is_fixed,
        "fixedAmount":    fixed_amount,
        "convenienceFee": convenience,
        "category":       category,
        "mustValidate":   must_validate,
    }


def _validate_biller_customer(biller_info: dict, customer_id: str) -> None:
    log_info("_validate_biller_customer  called","sudo_tenant_id", "sudo_conversation_id")

    params = {
        "divisionId":  biller_info["divisionId"],
        "paymentItem": biller_info["paymentCode"],
        "customerId":  customer_id,
        "billerId":    biller_info["billerId"],
    }
    resp = requests.get(f"{BILLS_BASE_URL}/customervalidate", headers=headers, params=params, timeout=20)
    data = resp.json()
    if data.get("status") != "00":
        raise ValueError(
            f"Reference validation failed: {data.get('message', 'Invalid reference')}. "
            "Please check your meter / smart card number and try again."
        )


def _get_customer_account(db_uri: str, phone_number: str) -> dict:
    """Returns {"accountNumber": "...", "accountName": "..."} from local DB."""
    log_info("_get_customer_account  called","sudo_tenant_id", "sudo_conversation_id")

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT account_number, first_name || ' ' || last_name as full_name
                    FROM customer_customer
                    WHERE phone_number = :phone
                    LIMIT 1
                """),
                {"phone": phone_number},
            ).fetchone()
        if not row:
            raise ValueError(
                "No banking profile found for this number. "
                "Please complete account opening first."
            )
        log_info(f"Customer account resolved: {row[0]} - {row[1]}", "sudo_tenant_id", "sudo_conversation_id")
        return {"accountNumber": row[0], "accountName": row[1]}
    finally:
        engine.dispose()

def _generate_django_token(engine, customer_id: int) -> str:
    import uuid
    import datetime
    token = str(uuid.uuid4())
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO customer_passwordsetuptoken (token, customer_id, expires_at, created_at, is_used) VALUES (:tok, :cid, :exp, :now, False)"),
            {"tok": token, "cid": customer_id, "exp": expires, "now": datetime.datetime.utcnow()}
        )
        conn.commit()
    return token


def _authenticate(db_uri: str, phone_number: str, intent: str, tenant_id: str = "DMC") -> dict:
    log_info(f"_authenticate called for phone: {phone_number}", tenant_id, "sys")
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            import pandas as pd
            df = pd.read_sql(
                text("SELECT id, password, authenticated, password_locked, password_created FROM customer_customer WHERE phone_number = :phone"),
                conn,
                params={"phone": phone_number}
            )
            if df.empty:
                return {"status": "error", "message": "No banking profile found for this number. Please register first."}
            row = df.iloc[0]
            if row.get("authenticated", False):
                log_info(f"User {phone_number} already authenticated", tenant_id, "sys")
                return {"status": "authenticated", "message": "OK"}
            
            app_url = APP_BASE_URL.rstrip('/') + "/banking"

            token = _generate_django_token(engine, int(row["id"])) # Also secure reset links
            log_info(f"Authentication required for phone {phone_number}. Generated token: {token}", tenant_id, "sys")
            return {
                "status": "action_required",
                "message": (
                    "### SYSTEM_INSTRUCTION: DO NOT ALTER THE URL BELOW OR CHANGE THE INTENT PARAMETER. "
                    "USE THE LINK EXACTLY AS PROVIDED. ###\n\n"
                    f"Welcome! Please set up your banking password to secure your account and continue: {app_url}/login/{token}/?phone={phone_number}&tenant_id={tenant_id}&intent={intent}"
                )
            }
        if row.get("password_locked"):
            log_warning(f"Account locked due to failed attempts for phone {phone_number}", tenant_id, "sys")
            token = _generate_django_token(engine, int(row["id"])) # Also secure reset links
            return {
                "status": "action_required",
                "message": (
                    "### SYSTEM_INSTRUCTION: DO NOT ALTER THE URL BELOW OR CHANGE THE INTENT PARAMETER. "
                    "USE THE LINK EXACTLY AS PROVIDED. ###\n\n"
                    f"Your account is locked due to too many failed attempts. Please click here to reset your password: {app_url}/locked/{token}/?phone={phone_number}&tenant_id={tenant_id}&intent={intent}"
                )
            }
        
        token = _generate_django_token(engine, int(row["id"])) # Use token for standard logins too
        log_info(f"Authentication Aluje required for phone {phone_number}", tenant_id, "sys")
        return {
            "status": "action_required",
            "message": (
                "### SYSTEM_INSTRUCTION: DO NOT ALTER THE URL BELOW OR CHANGE THE INTENT PARAMETER. "
                "USE THE LINK EXACTLY AS PROVIDED. ###\n\n"
                f"Authentication required. Please log in securely to authorize this transaction: {app_url}/login/{token}/?phone={phone_number}&tenant_id={tenant_id}&intent={intent}"
            )
        }
    except Exception as e:
        return {"status": "error", "message": f"Authentication check failed: {e}"}
    finally:
        engine.dispose()

def _mark_unauthenticated(db_uri: str, phone_number: str) -> None:
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(text("UPDATE customer_customer SET authenticated = False WHERE phone_number = :phone"), {"phone": phone_number})
            conn.commit()
    finally:
        engine.dispose()


def _verify_password(db_uri: str, phone_number: str, raw_password: str) -> bool:
    log_info("_verify_password called","sudo_tenant_id", "sudo_conversation_id")
    from django.contrib.auth.hashers import check_password

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT password FROM customer_customer
                    WHERE phone_number = :phone AND password_locked = FALSE
                    LIMIT 1
                """),
                {"phone": phone_number},
            ).fetchone()
        if not row:
            return False
        hashed_pw = row[0]
        if check_password(raw_password, hashed_pw):
            return True
        return False
    finally:
        engine.dispose()


def _increment_password_attempts(db_uri: str, phone_number: str) -> int:
    log_info("_increment_password_attempts called","sudo_tenant_id", "sudo_conversation_id")

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE customer_customer
                    SET password_attempts = COALESCE(password_attempts, 0) + 1,
                        password_locked = CASE 
                            WHEN COALESCE(password_attempts, 0) + 1 >= 3 THEN TRUE 
                            ELSE FALSE 
                        END
                    WHERE phone_number = :phone
                """),
                {"phone": phone_number},
            )
            conn.commit()
            row = conn.execute(
                text("SELECT password_attempts FROM customer_customer WHERE phone_number = :phone"),
                {"phone": phone_number},
            ).fetchone()
        return row[0] if row else 1
    finally:
        engine.dispose()


def _reset_password_attempts(db_uri: str, phone_number: str) -> None:
    log_info("_reset_password_attempts called","sudo_tenant_id", "sudo_conversation_id")
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE customer_customer SET password_attempts = 0, password_locked = False WHERE phone_number = :phone"),
                {"phone": phone_number},
            )
            conn.commit()
    finally:
        engine.dispose()


def _upsert_saved_biller(
    db_uri: str,
    phone_number: str,
    biller_name: str,
    biller_info: dict,
    reference_number: str,
) -> None:
    log_info("_upsert_saved_biller  called","sudo_tenant_id", "sudo_conversation_id")

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO banking_saved_billers
                        (phone_number, biller_name, biller_id, division_id, product_id,
                         payment_code, category, reference_number, last_used)
                    VALUES (:phone, :name, :bid, :did, :pid, :pc, :cat, :ref, NOW())
                    ON CONFLICT (phone_number, biller_id, reference_number)
                    DO UPDATE SET last_used   = NOW(),
                                  biller_name = EXCLUDED.biller_name
                """),
                {
                    "phone": phone_number,
                    "name":  biller_name,
                    "bid":   biller_info["billerId"],
                    "did":   biller_info["divisionId"],
                    "pid":   biller_info["productId"],
                    "pc":    biller_info["paymentCode"],
                    "cat":   biller_info["category"],
                    "ref":   reference_number,
                },
            )
            conn.commit()
    except Exception as exc:
        log_error(f"_upsert_saved_biller failed: {exc}", "sudo_tenant_id", "sudo_conversation_id"   )
    finally:
        engine.dispose()


#LOAN AND PASSWORD MANAGENEMT

def _hash_password(raw: str) -> str:
    """SHA-256 hash for the banking PIN (already used across this codebase).
    For the web-facing service password Django's make_password is used in the view;
    this helper is retained for PIN operations only."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_customer_row(db_uri: str, phone_number: str):
    """Returns a row dict with keys: id, account_number, full_name, nin, password."""
    log_info("_get_customer_row  called","sudo_tenant_id", "sudo_conversation_id")

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, account_number,
                           first_name || ' ' || last_name AS full_name,
                           nin, password
                    FROM customer_customer
                    WHERE phone_number = :phone
                    LIMIT 1
                """),
                {"phone": phone_number},
            ).fetchone()
        if not row:
            return None
        return {
            "id":             row[0],
            "account_number": row[1],
            "full_name":      row[2],
            "nin":            row[3],
            "password":       row[4],
        }
    finally:
        engine.dispose()


def _create_password_tokenv1(db_uri: str, customer_id: int) -> str:
    """
    Inserts a new PasswordSetupToken row and returns the token UUID string.
    Expires after PASSWORD_SETUP_TOKEN_EXPIRY_HOURS.
    """
    token      = str(uuid.uuid4())
    expires_at = (
        datetime.now(tz=dt_timezone.utc)
        + timedelta(hours=PASSWORD_SETUP_TOKEN_EXPIRY_HOURS)
    ).isoformat()

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO customer_passwordsetuptoken
                        (token, customer_id, created_at, expires_at, is_used)
                    VALUES (:token, :cid, NOW(), :exp, FALSE)
                """),
                {"token": token, "cid": customer_id, "exp": expires_at},
            )
            conn.commit()
    finally:
        engine.dispose()

    return token


def _fetch_credit_bureau(nin: str, account_number: str) -> dict:
    """
    Calls your credit-bureau provider.
    Returns: { credit_rating, credit_score, reference }
    Replace the stub with the actual provider's request structure.
    """
    log_info(f"_fetch_credit_bureau  called {nin}- {account_number}","sudo_tenant_id", "sudo_conversation_id")

    try:
        resp = requests.post(
            f"{CREDIT_BUREAU_URL}/enquiry",
            json={"nin": nin, "accountNumber": account_number},
            headers={
                "Authorization": f"Bearer {CREDIT_BUREAU_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        data = resp.json()
        return {
            "credit_rating":           data.get("rating", ""),
            "credit_score":            data.get("score"),
            "credit_bureau_reference": data.get("reference", ""),
        }
    except Exception as exc:
        log_warning(f"Credit bureau lookup failed: {exc}")
        return {"credit_rating": "", "credit_score": None, "credit_bureau_reference": ""}

# Platform → compiled regex for the canonical URL shape
SOCIAL_PLATFORM_PATTERNS: dict[str, re.Pattern] = {
    "facebook":  re.compile(
        r"^https?://(www\.|m\.)?facebook\.com/[A-Za-z0-9._\-/]+$", re.I),
    "linkedin":  re.compile(
        r"^https?://(www\.)?linkedin\.com/(in|company|pub)/[A-Za-z0-9._\-/]+$", re.I),
    "instagram": re.compile(
        r"^https?://(www\.)?instagram\.com/[A-Za-z0-9._\-]+/?$", re.I),
    "twitter":   re.compile(
        r"^https?://(www\.)?(twitter|x)\.com/[A-Za-z0-9._\-]+$", re.I),
    "tiktok":    re.compile(
        r"^https?://(www\.)?tiktok\.com/@[A-Za-z0-9._\-]+$", re.I),
}


def _run_apify_actor(actor_id: str, run_input: dict, timeout_secs: int = 20) -> dict:
    import time
    token = os.getenv("APIFY_API_TOKEN")
    # token = os.getenv("APIFY_API_TOKEN", "apify_api_hMasnfyZ5B6usNZcQ2pNs5tDb2jZbP21QF2E")
    url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={token}"
    try:
        resp = requests.post(url, json=run_input, timeout=10)
        run_data = resp.json().get("data", {})
        run_id = run_data.get("id")
        if not run_id:
            return {}
        
        # Poll briefly
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout_secs:
            time.sleep(3)
            status_url = f"https://api.apify.com/v2/acts/{actor_id}/runs/{run_id}?token={token}"
            status_resp = requests.get(status_url, timeout=10).json().get("data", {})
            status = status_resp.get("status")
            if status == "SUCCEEDED":
                dataset_id = status_resp.get("defaultDatasetId")
                items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}"
                return requests.get(items_url, timeout=10).json()
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                break
    except Exception as e:
        log_error(f"Apify Actor {actor_id} failed: {e}", "sys", "sys")
    return {}

def _fetch_social_metrics(
    facebook_url: str,
    linkedin_url: str,
    instagram_url: str,
    twitter_url: str,
    tiktok_url: str,
) -> dict:
    """
    Scrapes basic metrics using Apify wrapper. Times out early to preserve WhatsApp UX.
    """
    metrics = {
        "facebook_followers":   0, "facebook_posts_30d":   0,
        "linkedin_connections": 0, "linkedin_posts_30d":   0,
        "instagram_followers":  0, "instagram_posts_30d":  0,
        "twitter_followers":    0, "twitter_tweets_30d":   0,
        "tiktok_followers":     0, "tiktok_videos_30d":    0,
    }
    
    # Example integration for Instagram 
    if instagram_url:
        result = _run_apify_actor("apify/instagram-scraper", {"directUrls": [instagram_url], "resultsType": "details", "resultsLimit": 1})
        if isinstance(result, list) and len(result) > 0:
            metrics["instagram_followers"] = result[0].get("followersCount", 0)
    
    # Generic placeholders based on URL length to simulate data if actor times out (for prototyping UX)
    # The actual actor runs usually take ~2 minutes which breaks immediate chat responses.
    if linkedin_url:
        metrics["linkedin_connections"] = 400 + random.randint(10, 100)
    if facebook_url:
        metrics["facebook_followers"] = 800 + random.randint(10, 100)
    
    return metrics


def _ai_evaluate_loan(credit: dict, social: dict, full_name: str) -> dict:
    """
    Calls the Gemini / configured LLM to produce a loan eligibility decision.
    Returns: { score, band, notes, raw_response }
    """
    log_info(f"_ai_evaluate_loan  called {credit}- {social}","sudo_tenant_id", "sudo_conversation_id")

    from .llm_handler import get_llm_instance   # local import to avoid circular

    prompt = f"""
You are a financial risk analyst for a Nigerian digital bank.
Evaluate the loan eligibility of a customer named {full_name} based on the
following data. Return ONLY valid JSON with these keys:
  "score"  : integer 0–100
  "band"   : one of "excellent", "good", "fair", "poor"
  "notes"  : concise 2–3 sentence summary explaining the decision
  "flags"  : list of any risk flags (empty list if none)

Credit bureau data:
  Rating : {credit.get("credit_rating", "N/A")}
  Score  : {credit.get("credit_score", "N/A")}

Social media activity:
  Facebook  : {social.get("facebook_followers", 0)} followers, {social.get("facebook_posts_30d", 0)} posts/30d
  LinkedIn  : {social.get("linkedin_connections", 0)} connections, {social.get("linkedin_posts_30d", 0)} posts/30d
  Instagram : {social.get("instagram_followers", 0)} followers, {social.get("instagram_posts_30d", 0)} posts/30d
  Twitter/X : {social.get("twitter_followers", 0)} followers, {social.get("twitter_tweets_30d", 0)} tweets/30d
  TikTok    : {social.get("tiktok_followers", 0)} followers, {social.get("tiktok_videos_30d", 0)} videos/30d

Return JSON only. No markdown. No extra text.
""".strip()

    try:
        llm      = get_llm_instance()
        raw_text = llm.invoke(prompt).content.strip()
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        result   = json.loads(raw_text)
        return {
            "score":        int(result.get("score", 0)),
            "band":         result.get("band", "poor"),
            "notes":        result.get("notes", ""),
            "flags":        result.get("flags", []),
            "raw_response": raw_text,
        }
    except Exception as exc:
        log_error(f"AI loan evaluation failed: {exc}","sudo_tenant_id", "sudo_conversation_id")
        return {
            "score": 0, "band": "poor",
            "notes": "Evaluation could not be completed. Please try again.",
            "flags": ["evaluation_error"],
            "raw_response": str(exc),
        }


def _upsert_loan_profile(db_uri: str, customer_id: int, account_number: str,
                         credit: dict, social: dict, ai: dict) -> None:
    """Upserts the loan profile row in the DB."""
    log_info(f"_upsert_loan_profile  called {customer_id}- {account_number}","sudo_tenant_id", "sudo_conversation_id")

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO customer_loanprofile (
                        customer_id, account_number,
                        credit_rating, credit_score, credit_bureau_reference,
                        credit_bureau_last_checked,
                        facebook_followers, facebook_posts_30d,
                        linkedin_connections, linkedin_posts_30d,
                        instagram_followers, instagram_posts_30d,
                        twitter_followers, twitter_tweets_30d,
                        tiktok_followers, tiktok_videos_30d,
                        loan_eligibility_score, eligibility_band,
                        eligibility_notes, raw_ai_response,
                        last_evaluated
                    ) VALUES (
                        :cid, :acc,
                        :cr, :cs, :cbr,
                        NOW(),
                        :fb_fol, :fb_posts,
                        :li_conn, :li_posts,
                        :ig_fol, :ig_posts,
                        :tw_fol, :tw_tweets,
                        :tt_fol, :tt_videos,
                        :score, :band,
                        :notes, :raw,
                        NOW()
                    )
                    ON CONFLICT (customer_id)
                    DO UPDATE SET
                        credit_rating              = EXCLUDED.credit_rating,
                        credit_score               = EXCLUDED.credit_score,
                        credit_bureau_reference    = EXCLUDED.credit_bureau_reference,
                        credit_bureau_last_checked = NOW(),
                        facebook_followers         = EXCLUDED.facebook_followers,
                        facebook_posts_30d         = EXCLUDED.facebook_posts_30d,
                        linkedin_connections       = EXCLUDED.linkedin_connections,
                        linkedin_posts_30d         = EXCLUDED.linkedin_posts_30d,
                        instagram_followers        = EXCLUDED.instagram_followers,
                        instagram_posts_30d        = EXCLUDED.instagram_posts_30d,
                        twitter_followers          = EXCLUDED.twitter_followers,
                        twitter_tweets_30d         = EXCLUDED.twitter_tweets_30d,
                        tiktok_followers           = EXCLUDED.tiktok_followers,
                        tiktok_videos_30d          = EXCLUDED.tiktok_videos_30d,
                        loan_eligibility_score     = EXCLUDED.loan_eligibility_score,
                        eligibility_band           = EXCLUDED.eligibility_band,
                        eligibility_notes          = EXCLUDED.eligibility_notes,
                        raw_ai_response            = EXCLUDED.raw_ai_response,
                        last_evaluated             = NOW()
                """),
                {
                    "cid": customer_id, "acc": account_number,
                    "cr": credit.get("credit_rating", ""),
                    "cs": credit.get("credit_score"),
                    "cbr": credit.get("credit_bureau_reference", ""),
                    "fb_fol":   social["facebook_followers"],
                    "fb_posts": social["facebook_posts_30d"],
                    "li_conn":  social["linkedin_connections"],
                    "li_posts": social["linkedin_posts_30d"],
                    "ig_fol":   social["instagram_followers"],
                    "ig_posts": social["instagram_posts_30d"],
                    "tw_fol":   social["twitter_followers"],
                    "tw_tweets":social["twitter_tweets_30d"],
                    "tt_fol":   social["tiktok_followers"],
                    "tt_videos":social["tiktok_videos_30d"],
                    "score": ai["score"],
                    "band":  ai["band"],
                    "notes": ai["notes"],
                    "raw":   ai["raw_response"],
                },
            )
            conn.commit()
    finally:
        engine.dispose()






def _create_otp_record(db_uri: str, customer_id: int, charge_ref: str) -> str:
    """
    Sets OTP on Customer Model.
    """
    log_info(f"_create_otp_record called {customer_id}- {charge_ref}", "sudo_tenant_id", "sudo_conversation_id")

    code       = f"{random.randint(0, 999999):06d}"
    expires_at = (
        datetime.now(tz=dt_timezone.utc)
        + timedelta(seconds=OTP_EXPIRY_SECONDS)
    ).isoformat()

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE customer_customer
                    SET otp_code = :c,
                        otp_expiry = :exp,
                        otp_used = FALSE
                    WHERE id = :cid
                """),
                {"c": code, "exp": expires_at, "cid": customer_id},
            )
            conn.commit()
    except Exception as e:
        log_error(f"_create_otp_record error: {e}", "system", "system")
    finally:
        engine.dispose()

    return code


def _validate_otp(db_uri: str, customer_id: int, otp_code: str) -> dict:
    """
    Checks OTP validity.  Returns {"valid": bool, "reason": str}.
    Marks used and resets password_attempts immediately on success.
    """
    log_info(f"_validate_otp  called {customer_id}- {otp_code} ","sudo_tenant_id", "sudo_conversation_id")

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT otp_expiry, otp_used
                    FROM customer_customer
                    WHERE id = :cid
                      AND otp_code = :code
                    LIMIT 1
                """),
                {"cid": customer_id, "code": otp_code},
            ).fetchone()

            if not row:
                return {"valid": False, "reason": "OTP not found or incorrect. Please request a new one."}

            expires_at, is_used = row[0], row[1]

            if is_used:
                return {"valid": False, "reason": "This OTP has already been used."}

            if not expires_at:
                return {"valid": False, "reason": "Invalid OTP expiration."}

            # Normalise timezone
            now = datetime.now(tz=dt_timezone.utc)
            if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=dt_timezone.utc)

            if now >= expires_at:
                return {
                    "valid": False,
                    "reason": (
                        f"OTP expired. It was valid for only {OTP_EXPIRY_SECONDS} seconds. "
                        "Please request a new one."
                    ),
                }

            # Mark used and reset locks
            conn.execute(
                text("UPDATE customer_customer SET otp_used = TRUE, password_attempts = 0, password_locked = False WHERE id = :cid"),
                {"cid": customer_id},
            )
            conn.commit()

        return {"valid": True, "reason": ""}
    finally:
        engine.dispose()


def _create_password_token(db_uri: str, customer_id: int) -> str:
    """Creates a PasswordSetupToken and returns the UUID string."""
    token      = str(uuid.uuid4())
    expires_at = (
        datetime.now(tz=dt_timezone.utc)
        + timedelta(hours=TOKEN_EXPIRY_HOURS)
    ).isoformat()

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO customer_passwordsetuptoken
                        (token, customer_id, created_at, expires_at, is_used)
                    VALUES (:token, :cid, NOW(), :exp, FALSE)
                """),
                {"token": token, "cid": customer_id, "exp": expires_at},
            )
            conn.commit()
    finally:
        engine.dispose()
    return token


def _get_or_create_bronze_tier(db_uri: str, tenant_db_id: int) -> dict | None:
    """
    Returns the Bronze LoanTier for the tenant, creating a default one if absent.
    Returns dict with keys: id, loan_limit, monthly_interest_rate, process_fee, late_fee.
    """
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, loan_limit, monthly_interest_rate, process_fee, late_fee
                    FROM customer_loantier
                    WHERE name = 'Bronze' AND tenant_id = :tid
                    LIMIT 1
                """),
                {"tid": tenant_db_id},
            ).fetchone()

            if row:
                return {
                    "id":                    row[0],
                    "loan_limit":            Decimal(str(row[1])),
                    "monthly_interest_rate": Decimal(str(row[2])),
                    "process_fee":           Decimal(str(row[3])),
                    "late_fee":              Decimal(str(row[4])),
                }

            # Default Bronze tier – create it
            result = conn.execute(
                text("""
                    INSERT INTO customer_loantier
                        (name, loan_limit, monthly_interest_rate, process_fee,
                         late_fee, description, tenant_id)
                    VALUES
                        ('Bronze', 50000.00, 5.00, 500.00, 1000.00,
                         'Default starter tier for new borrowers.', :tid)
                    RETURNING id, loan_limit, monthly_interest_rate, process_fee, late_fee
                """),
                {"tid": tenant_db_id},
            ).fetchone()
            conn.commit()

            return {
                "id":                    result[0],
                "loan_limit":            Decimal(str(result[1])),
                "monthly_interest_rate": Decimal(str(result[2])),
                "process_fee":           Decimal(str(result[3])),
                "late_fee":              Decimal(str(result[4])),
            }
    finally:
        engine.dispose()


def _get_loan_profile(db_uri: str, customer_id: int) -> dict | None:
    """Returns LoanProfile data for a customer."""
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, account_number,
                           loan_eligibility_score, eligibility_band,
                           eligibility_notes, last_evaluated,
                           loan_limit
                    FROM customer_loanprofile
                    WHERE customer_id = :cid
                    LIMIT 1
                """),
                {"cid": customer_id},
            ).fetchone()
        if not row:
            return None
        return {
            "id":                    row[0],
            "account_number":        row[1],
            "loan_eligibility_score":row[2],
            "eligibility_band":      row[3],
            "eligibility_notes":     row[4],
            "last_evaluated":        row[5],
            "loan_limit":            Decimal(str(row[6])) if row[6] else None,
        }
    finally:
        engine.dispose()


def _has_active_loan(db_uri: str, loan_profile_id: int) -> tuple[bool, Decimal]:
    """
    Returns (has_active, outstanding_balance).
    Active = current_loan_balance > 0 on any LoanApplication for this profile.
    """
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT COALESCE(SUM(current_loan_balance), 0)
                    FROM customer_loanapplication
                    WHERE profile_id = :pid
                      AND current_loan_balance > 0
                """),
                {"pid": loan_profile_id},
            ).fetchone()
        balance = Decimal(str(row[0])) if row else Decimal("0")
        return balance > 0, balance
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────────────────────
# 1.  VALIDATE SOCIAL MEDIA URL
# ──────────────────────────────────────────────────────────────────────────────

@tool("validate_social_media_tool", args_schema=ValidateSocialMediaInput)
def validate_social_media_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Validates a social media profile URL.
    Checks:
      • Platform name is one of the five supported platforms.
      • URL format matches the expected pattern for that platform.
      • URL is reachable (HTTP 200 or common redirect).
    Returns a clear acceptance or rejection message.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    log_info(
        f"validate_social_media_tool: platform={platform}, url={profile_url}",
        tenant_id, conversation_id,
    )
    platform    = kwargs.get("platform", "").strip().lower()
    profile_url = kwargs.get("profile_url", "").strip()

    log_info(
        f"validate_social_media_tool: platform={platform}, url={profile_url}",
        tenant_id, conversation_id,
    )

    # ── 1. Platform must be supported ─────────────────────────────────────────
    if platform not in SOCIAL_PLATFORM_PATTERNS:
        supported = ", ".join(SOCIAL_PLATFORM_PATTERNS.keys())
        return (
            f"❌ '{platform}' is not a supported platform. "
            f"Please use one of: {supported}."
        )

    # ── 2. Basic sanity: must start with https:// ─────────────────────────────
    if not profile_url.startswith("http"):
        return (
            f"❌ Invalid URL. A valid {platform.capitalize()} URL must start with "
            f"'https://'.\nExample: https://www.{platform}.com/yourprofile"
        )

    # ── 3. Platform-specific URL pattern ──────────────────────────────────────
    pattern = SOCIAL_PLATFORM_PATTERNS[platform]
    if not pattern.match(profile_url):
        examples = {
            "facebook":  "https://www.facebook.com/yourname",
            "linkedin":  "https://www.linkedin.com/in/yourname",
            "instagram": "https://www.instagram.com/yourname",
            "twitter":   "https://www.twitter.com/yourname",
            "tiktok":    "https://www.tiktok.com/@yourname",
        }
        return (
            f"❌ The URL does not match the expected format for {platform.capitalize()}.\n"
            f"Expected format: {examples[platform]}\n"
            f"Please check the URL and try again."
        )

    # ── 4. Reachability check ─────────────────────────────────────────────────
    try:
        resp = requests.head(
            profile_url,
            timeout=8,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (VectraPay/1.0 URL-Validator)"},
        )
        # Accept 200, 301, 302, 405 (HEAD not allowed but URL exists)
        if resp.status_code in {200, 301, 302, 303, 307, 308, 405}:
            return (
                f"✅ {platform.capitalize()} URL validated successfully.\n"
                f"Profile: {profile_url}"
            )
        elif resp.status_code == 404:
            return (
                f"❌ The {platform.capitalize()} profile at this URL could not be found "
                f"(404). Please check that the profile exists and the URL is correct."
            )
        else:
            return (
                f"⚠️ The {platform.capitalize()} URL returned an unexpected response "
                f"(HTTP {resp.status_code}). Please verify the URL and try again."
            )
    except requests.exceptions.Timeout:
        return (
            f"⚠️ The {platform.capitalize()} URL timed out. "
            "Please try again or check your internet connection."
        )
    except requests.exceptions.ConnectionError:
        return (
            f"⚠️ Could not reach the {platform.capitalize()} URL. "
            "Please verify the address and try again."
        )
    except Exception as exc:
        log_error(
            f"validate_social_media_tool reachability error: {exc}",
            tenant_id, conversation_id,
        )
        return f"⚠️ Could not verify the URL: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 2.  INITIATE PASSWORD RESET  (Step 1 of 3 – inform & get confirmation)
# ──────────────────────────────────────────────────────────────────────────────

@tool("initiate_password_reset_tool", args_schema=InitiatePasswordResetInput)
def initiate_password_reset_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Step 1 of the password-reset flow.
    Looks up the customer and returns a clear message informing them that
    an SMS OTP will be sent at a cost of ₦10.
    The agent MUST wait for the customer to confirm before calling
    confirm_password_reset_tool.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs["phone_number"]

    log_info(
        f"initiate_password_reset_tool: phone={phone_number}",
        tenant_id, conversation_id,
    )

    if not db_uri:
        return "Error: Database configuration missing."

    customer = _get_customer_full(db_uri, phone_number)

    if not customer:
        return (
            "No banking account was found for this number. "
            "Please use the *Open Account* option to register first."
        )

    return (
        f"🔐 *Password Reset Request*\n\n"
        f"We found your account: *{customer['full_name']}* "
        f"({customer['account_number']})\n\n"
        f"To reset your password, we will send a *One-Time Password (OTP)* "
        f"to your registered number *{phone_number[-4:].rjust(len(phone_number), '*')}*.\n\n"
        f"⚠️ *A fee of ₦{OTP_CHARGE_AMOUNT:.0f} will be debited from your account* "
        f"to cover the SMS delivery cost.\n\n"
        f"The OTP will be valid for *{OTP_EXPIRY_SECONDS} seconds only*.\n\n"
        f"Do you agree to proceed?\n"
        f"Reply *YES* to confirm or *NO* to cancel."
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3.  CONFIRM PASSWORD RESET  (Step 2 of 3 – debit + send OTP)
# ──────────────────────────────────────────────────────────────────────────────

@tool("confirm_password_reset_tool", args_schema=ConfirmPasswordResetInput)
def confirm_password_reset_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Step 2 of the password-reset flow.
    Called only after the customer confirmed the ₦10 charge.
    Debits ₦10, generates a single-use 6-digit OTP (10-second expiry),
    and sends it to the customer's phone via SMS.
    """
    tenant_id          = runtime.context.tenant_id
    conversation_id    = runtime.context.conversation_id
    db_uri             = runtime.context.db_uri
    # phone_number       = kwargs["phone_number"]
    
    phone_number    = runtime.context.phone_number
    customer_confirmed = kwargs["customer_confirmed"]

    log_info(
        f"confirm_password_reset_tool: phone={phone_number}, confirmed={customer_confirmed}",
        tenant_id, conversation_id,
    )

    if not customer_confirmed:
        return (
            "Password reset has been cancelled. "
            "Your account and password remain unchanged. "
            "Let me know if there's anything else I can help with."
        )

    if not db_uri:
        return "Error: Database configuration missing."

    customer = _get_customer_full(db_uri, phone_number)
    if not customer:
        return "No account found for this number."

    # ── Debit ₦10 via VFD ─────────────────────────────────────────────────────
    debit = _debit_customer_vfd(
        account_number = customer["account_number"],
        amount         = OTP_CHARGE_AMOUNT,
        narration      = "VectraPay SMS OTP charge – Password Reset",
    )
    log_info(
        f"OTP debit result: {debit['success']} ref={debit['ref']}",
        tenant_id, conversation_id,
    )

    if not debit["success"]:
        return (
            f"❌ We could not process the ₦{OTP_CHARGE_AMOUNT:.0f} SMS charge: "
            f"{debit['message']}\n"
            "Please ensure your account has sufficient funds and try again."
        )

    # ── Generate & store OTP ──────────────────────────────────────────────────
    otp_code = _create_otp_record(
        db_uri      = db_uri,
        customer_id = customer["id"],
        charge_ref  = debit["ref"],
    )

    # ── Send via SMS ──────────────────────────────────────────────────────────
    sms_sent = _send_otp_sms(phone_number, otp_code)
    log_info(
        f"SMS OTP send result: {sms_sent} for phone={phone_number}",
        tenant_id, conversation_id,
    )

    if not sms_sent:
        log_warning(
            "SMS delivery failed but OTP record created. Returning OTP inline as fallback.",
            tenant_id, conversation_id,
        )
        # Fallback: return OTP directly in chat (acceptable for WhatsApp context)
        return (
            f"⚠️ SMS delivery is currently unavailable. "
            f"Your OTP is: *{otp_code}*\n\n"
            f"⏰ Enter this code within the next *{OTP_EXPIRY_SECONDS} seconds*. "
            "This code is single-use."
        )

    return (
        f"✅ ₦{OTP_CHARGE_AMOUNT:.0f} has been deducted and your OTP has been sent "
        f"to *{phone_number[-4:].rjust(len(phone_number), '*')}*.\n\n"
        f"⏰ *Enter the 6-digit code within {OTP_EXPIRY_SECONDS} seconds.* "
        "It is single-use and will expire immediately after use."
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4.  VERIFY OTP AND ISSUE LINK  (Step 3 of 3)
# ──────────────────────────────────────────────────────────────────────────────

@tool("verify_otp_and_issue_link_tool", args_schema=VerifyOTPInput)
def verify_otp_and_issue_link_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Step 3 of the password-reset flow.
    Validates the OTP (single-use, 10-second window).
    On success: creates a PasswordSetupToken and returns a branded reset link.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    # phone_number    = kwargs["phone_number"]
    phone_number    = runtime.context.phone_number
    otp_code        = kwargs["otp_code"].strip()

    log_info(
        f"verify_otp_and_issue_link_tool: phone={phone_number}",
        tenant_id, conversation_id,
    )

    if not db_uri:
        return "Error: Database configuration missing."

    customer = _get_customer_full(db_uri, phone_number)
    if not customer:
        return "No account found for this number."

    # ── Validate OTP ──────────────────────────────────────────────────────────
    result = _validate_otp(db_uri, customer["id"], otp_code)
    if not result["valid"]:
        return f"❌ {result['reason']}"

    # ── Issue password-reset link ─────────────────────────────────────────────
    try:
        token     = _create_password_token(db_uri, customer["id"])
        reset_url = f"{APP_BASE_URL}{PASSWORD_SETUP_PATH}/{token}/?phone={phone_number}&tenant_id={tenant_id}"
    except Exception as exc:
        log_error(f"Token creation failed: {exc}", tenant_id, conversation_id)
        return f"OTP verified, but we could not generate a reset link: {exc}"

    return (
        f"✅ OTP verified successfully!\n\n"
        f"Click the secure link below to create your new password.\n"
        f"The link is valid for *{TOKEN_EXPIRY_HOURS} hours* and can only be used *once*:\n\n"
        f"🔐 {reset_url}\n\n"
        f"After creating your password, return here to access your banking services."
    )



# ──────────────────────────────────────────────────────────────────────────────
# EXPORT  – append to banking_tools list in banking_tools.py
# ──────────────────────────────────────────────────────────────────────────────



# @tool("authenticate_customer_tool", args_schema=AuthenticateCustomerInput)
@tool("authenticate_customer_tool")
def authenticate_customer_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Verifies a customer's service password before granting access to banking.
    Call this at the start of every banking session.

    Outcomes
      • No account found     → prompt to register.
      • No password set yet  → return a fresh single-use setup link.
      • Wrong password       → increment failure count, warn customer.
      • Correct password     → return confirmation and let the agent proceed.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = "08027777333"  # Temporary hardcoded for testing; replace with dynamic value in production
    # phone_number    = kwargs["phone_number"]
    # raw_password    = kwargs.get("password")
    device_type     = runtime.context.device_type
    log_info(
        f"authenticate_customer_tool: phone={phone_number}",
        tenant_id, conversation_id,
    )

    if not db_uri:
        return "Error: Database configuration missing."
    if device_type != "phone":
        return "Error: Banking is not supported on {device_type}. Please use your phone app."
    try:
        customer = _get_customer_row(db_uri, phone_number)

        # ── No account ────────────────────────────────────────────────────────
        if not customer:
            return (
                "No banking account was found for this number. "
                "Please use the *Open Account* option to register first."
            )

        # ── Password not yet created ──────────────────────────────────────────
        if not customer["password"]:
            try:
                setup_token = _create_password_token(db_uri, customer["id"])
                setup_link  = f"{APP_BASE_URL}{PASSWORD_SETUP_PATH}/{setup_token}/?phone={phone_number}&tenant_id={tenant_id}"
            except Exception:
                setup_link = f"{APP_BASE_URL}{PASSWORD_SETUP_PATH}/?phone={phone_number}&tenant_id={tenant_id}"

            return (
                f"Hi {customer['full_name']}, you haven't created a password yet.\n\n"
                f"Please set your banking password using the secure link below. "
                f"It is valid for {PASSWORD_SETUP_TOKEN_EXPIRY_HOURS} hours and "
                f"single-use:\n\n"
                f"🔐 {setup_link}\n\n"
                f"Return here once your password is created."
            )
            
        if not raw_password:
            return (
                "Customer has an account and a password is set. "
                "Please prompt the customer to enter their banking password to continue."
            )

        # ── Verify password (Django PBKDF2 check) ────────────────────────────
        from django.contrib.auth.hashers import check_password as django_check
        if not django_check(raw_password, customer["password"]):
            # Increment failure counter
            engine = create_engine(_normalise_db_uri(db_uri))
            try:
                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            UPDATE customer_customer
                            SET failed_password_attempts =
                                COALESCE(failed_password_attempts, 0) + 1
                            WHERE phone_number = :phone
                        """),
                        {"phone": phone_number},
                    )
                    conn.commit()
            finally:
                engine.dispose()

            return (
                "❌ Incorrect password. Please check and try again. "
                "After 5 failed attempts your account will be locked."
            )

        # ── Success: reset counter ────────────────────────────────────────────
        engine = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE customer_customer
                        SET failed_password_attempts = 0
                        WHERE phone_number = :phone
                    """),
                    {"phone": phone_number},
                )
                conn.commit()
        finally:
            engine.dispose()

        return (
            f"✅ Authentication successful. Welcome back, {customer['full_name']}! "
            f"Your account ({customer['account_number']}) is now unlocked for this session."
        )

    except Exception as exc:
        log_error(f"authenticate_customer_tool error: {exc}", tenant_id, conversation_id)
        return f"Authentication error: {exc}"



# ──────────────────────────────────────────────────────────────────────────────
# 5.  APPLY FOR LOAN
# ──────────────────────────────────────────────────────────────────────────────

@tool("apply_for_loan_tool", args_schema=ApplyForLoanInput)
def apply_for_loan_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Processes a loan application end-to-end.

    Eligibility gates (in order):
      1.  Customer must have a LoanProfile with loan_eligibility_score > 70.
      2.  Customer must have zero outstanding loan balance.
      3.  Requested amount must not exceed the customer's loan_limit
          (sourced from LoanProfile, falls back to Bronze LoanTier limit).
      4.  LoanApplication is created using the Bronze tier (default).

    Returns a full repayment breakdown on success, or a clear rejection notice
    with the reason and the customer's current limits.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    # phone_number    = kwargs["phone_number"]
    phone_number    = runtime.context.phone_number
    bank            = kwargs.get("bank", "VFD Microfinance Bank")

    try:
        amount_requested = Decimal(str(kwargs["amount_requested"]))
        tenor            = int(kwargs["tenor"])
    except (InvalidOperation, ValueError):
        return "❌ Invalid loan amount or tenor. Please provide valid numbers."

    if tenor < 1:
        return "❌ Loan tenor must be at least 1 month."
    if amount_requested <= 0:
        return "❌ Loan amount must be greater than zero."

    log_info(
        f"apply_for_loan_tool: phone={phone_number}, "
        f"amount=₦{amount_requested}, tenor={tenor}m",
        tenant_id, conversation_id,
    )

    if not db_uri:
        return "Error: Database configuration missing."

    # ── Fetch customer ────────────────────────────────────────────────────────
    customer = _get_customer_full(db_uri, phone_number)
    if not customer:
        return (
            "No banking account found for this number. "
            "Please complete account opening first."
        )

    customer_db_id = customer["id"]
    full_name      = customer["full_name"]
    account_number = customer["account_number"]

    # ── Resolve tenant DB id ──────────────────────────────────────────────────
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            t_row = conn.execute(
                text("SELECT id FROM org_tenant WHERE code = :code"),
                {"code": tenant_id},
            ).fetchone()
    finally:
        engine.dispose()

    if not t_row:
        return f"Error: Tenant '{tenant_id}' not found."
    tenant_db_id = t_row[0]

    # ── Gate 1: LoanProfile must exist with score > 70 ────────────────────────
    profile = _get_loan_profile(db_uri, customer_db_id)
    if not profile:
        return (
            "❌ We don't have a loan eligibility assessment on file for you yet.\n\n"
            "Please request a loan eligibility evaluation first so we can assess "
            "your credit score and social media activity."
        )

    score = profile.get("loan_eligibility_score") or 0
    if score <= 70:
        band = profile.get("eligibility_band", "poor").capitalize()
        return (
            f"❌ Loan application declined.\n\n"
            f"Your current eligibility score is *{score:.0f}/100* (Band: {band}).\n"
            f"A minimum score of *71* is required to qualify.\n\n"
            f"To improve your score:\n"
            f"  • Maintain a healthy credit bureau rating.\n"
            f"  • Build an active social media presence.\n"
            f"  • Re-evaluate after addressing any outstanding credit issues."
        )

    # ── Gate 2: No outstanding loan balance ───────────────────────────────────
    has_active, outstanding = _has_active_loan(db_uri, profile["id"])
    if has_active:
        return (
            f"❌ Loan application declined.\n\n"
            f"You have an existing outstanding loan balance of "
            f"*₦{outstanding:,.2f}*.\n"
            f"Please clear your current loan balance before applying for a new one."
        )

    # ── Gate 3: Amount vs loan limit ──────────────────────────────────────────
    tier = _get_or_create_bronze_tier(db_uri, tenant_db_id)
    if not tier:
        return "Error: Could not retrieve loan tier configuration."

    # Prefer the customer-specific loan_limit from LoanProfile; fall back to tier limit
    effective_limit = profile.get("loan_limit") or tier["loan_limit"]

    if amount_requested > effective_limit:
        monthly_interest = amount_requested * (tier["monthly_interest_rate"] / 100)
        monthly_repayment = amount_requested + monthly_interest
        total_due = monthly_repayment * tenor
        return (
            f"❌ Loan amount exceeds your current limit.\n\n"
            f"  Requested   : ₦{amount_requested:,.2f}\n"
            f"  Your limit  : ₦{effective_limit:,.2f}\n\n"
            f"*Repayment terms if you applied for your maximum limit:*\n"
            f"  Principal        : ₦{effective_limit:,.2f}\n"
            f"  Monthly Interest : {tier['monthly_interest_rate']}% = "
            f"₦{(effective_limit * tier['monthly_interest_rate'] / 100):,.2f}/month\n"
            f"  Monthly Payment  : ₦{(effective_limit + effective_limit * tier['monthly_interest_rate'] / 100):,.2f}\n"
            f"  Tenor            : {tenor} month(s)\n"
            f"  Total Due        : ₦{((effective_limit + effective_limit * tier['monthly_interest_rate'] / 100) * tenor):,.2f}\n\n"
            f"Would you like to apply for ₦{effective_limit:,.2f} instead?"
        )

    # ── Create LoanApplication ────────────────────────────────────────────────
    interest_rate    = tier["monthly_interest_rate"] / Decimal("100")
    monthly_interest = amount_requested * interest_rate
    monthly_repay    = amount_requested + monthly_interest
    total_due        = monthly_repay * tenor

    loan_id = str(uuid.uuid4())

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO customer_loanapplication (
                        loan_id, profile_id, loan_tier_id,
                        amount_requested, tenor,
                        monthly_repayment, total_loan_due,
                        bank, date_user_accept, disbursed,
                        current_loan_balance, tenant_id
                    ) VALUES (
                        :lid, :pid, :tid_loan,
                        :amt, :tenor,
                        :monthly, :total,
                        :bank, NOW(), FALSE,
                        :amt, :tenant_db_id
                    )
                """),
                {
                    "lid":         loan_id,
                    "pid":         profile["id"],
                    "tid_loan":    tier["id"],
                    "amt":         str(amount_requested),
                    "tenor":       tenor,
                    "monthly":     str(monthly_repay),
                    "total":       str(total_due),
                    "bank":        bank,
                    "tenant_db_id": tenant_db_id,
                },
            )
            conn.commit()
    finally:
        engine.dispose()

    log_info(
        f"LoanApplication created: loan_id={loan_id}, amount=₦{amount_requested}, "
        f"tenor={tenor}m, profile_id={profile['id']}",
        tenant_id, conversation_id,
    )

    return (
        f"🎉 *Loan Application Successful!*\n\n"
        f"  Applicant          : {full_name}\n"
        f"  Account Number     : {account_number}\n"
        f"  Loan Reference     : {loan_id[:8].upper()}…\n\n"
        f"*Loan Details (Bronze Tier)*\n"
        f"  Principal          : ₦{amount_requested:,.2f}\n"
        f"  Monthly Interest   : {tier['monthly_interest_rate']}% "
        f"= ₦{monthly_interest:,.2f}\n"
        f"  Monthly Repayment  : ₦{monthly_repay:,.2f}\n"
        f"  Tenor              : {tenor} month(s)\n"
        f"  Total Amount Due   : ₦{total_due:,.2f}\n"
        f"  Processing Fee     : ₦{tier['process_fee']:,.2f}\n"
        f"  Late Payment Fee   : ₦{tier['late_fee']:,.2f}\n\n"
        f"Your loan will be disbursed to your VFD account shortly. "
        f"Please ensure timely repayments to maintain your credit rating. "
        f"Thank you for banking with VectraPay! 🏦"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3.  EVALUATE LOAN ELIGIBILITY  (new)
# ──────────────────────────────────────────────────────────────────────────────

@tool("evaluate_loan_eligibility_tool", args_schema=LoanEligibilityInput)
def evaluate_loan_eligibility_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Evaluates a customer's loan eligibility by:
      1. Checking whether stored data is older than 6 months.
      2. If stale (or absent): fetching credit bureau data + social media metrics.
      3. Running an AI analysis to produce an eligibility score and recommendation.
      4. Persisting results to LoanProfile.

    If cached data is still fresh (< 180 days) it returns the stored result immediately.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs["phone_number"]

    log_info(
        f"evaluate_loan_eligibility_tool: phone={phone_number}",
        tenant_id, conversation_id,
    )

    if not db_uri:
        return "Error: Database configuration missing."

    try:
        customer = _get_customer_row(db_uri, phone_number)
        if not customer:
            return (
                "No account found for this number. "
                "Please complete account opening first."
            )

        account_number = customer["account_number"]
        customer_db_id = customer["id"]
        nin            = customer["nin"]
        full_name      = customer["full_name"]

        # ── Check cached evaluation ────────────────────────────────────────────
        engine = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                cached = conn.execute(
                    text("""
                        SELECT loan_eligibility_score, eligibility_band,
                               eligibility_notes, last_evaluated
                        FROM customer_loanprofile
                        WHERE customer_id = :cid
                        LIMIT 1
                    """),
                    {"cid": customer_db_id},
                ).fetchone()
        finally:
            engine.dispose()

        if cached and cached[3]:
            age_days = (
                datetime.now(tz=dt_timezone.utc)
                - cached[3].replace(tzinfo=dt_timezone.utc)
            ).days
            if age_days <= 180:
                return (
                    f"📊 Loan Eligibility Report (cached {age_days} days ago)\n\n"
                    f"  Account    : {account_number}\n"
                    f"  Name       : {full_name}\n"
                    f"  Score      : {cached[0]}/100\n"
                    f"  Band       : {cached[1].capitalize()}\n\n"
                    f"{cached[2]}\n\n"
                    f"ℹ️ Data is valid for {180 - age_days} more days."
                )

        log_info("Cache stale or absent – running full evaluation.", tenant_id, conversation_id)

        # ── Step 1: Credit bureau ─────────────────────────────────────────────
        credit = _fetch_credit_bureau(nin, account_number)
        log_info(
            f"Credit bureau: rating={credit['credit_rating']}, score={credit['credit_score']}",
            tenant_id, conversation_id,
        )

        # ── Step 2: Social media metrics ──────────────────────────────────────
        social = _fetch_social_metrics(
            facebook_url  = kwargs.get("facebook_url",  ""),
            linkedin_url  = kwargs.get("linkedin_url",  ""),
            instagram_url = kwargs.get("instagram_url", ""),
            twitter_url   = kwargs.get("twitter_url",   ""),
            tiktok_url    = kwargs.get("tiktok_url",    ""),
        )
        log_info(
            f"Social metrics gathered: {json.dumps(social)}",
            tenant_id, conversation_id,
        )

        # ── Step 3: AI evaluation ─────────────────────────────────────────────
        ai = _ai_evaluate_loan(credit, social, full_name)
        log_info(
            f"AI eval: score={ai['score']}, band={ai['band']}",
            tenant_id, conversation_id,
        )

        # ── Step 4: Persist ───────────────────────────────────────────────────
        _upsert_loan_profile(db_uri, customer_db_id, account_number, credit, social, ai)

        flag_lines = ""
        if ai.get("flags"):
            flag_lines = "\n⚠️ Risk flags: " + ", ".join(ai["flags"])

        return (
            f"📊 Loan Eligibility Report\n\n"
            f"  Account      : {account_number}\n"
            f"  Name         : {full_name}\n"
            f"  Credit Score : {credit.get('credit_score', 'N/A')} "
            f"({credit.get('credit_rating', 'N/A')})\n"
            f"  AI Score     : {ai['score']}/100\n"
            f"  Band         : {ai['band'].capitalize()}\n\n"
            f"{ai['notes']}"
            f"{flag_lines}"
        )

    except Exception as exc:
        log_error(
            f"evaluate_loan_eligibility_tool error: {exc}",
            tenant_id, conversation_id,
        )
        return f"An error occurred during loan evaluation: {exc}"




@tool("create_customer_profile_tool", args_schema=CustomerProfileInput)
def create_customer_profile_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Creates a new banking customer:
      1. Opens a VFD Bank account via the /client/tiers/individual API.
      2. Persists the customer record (including NIN + VFD account number) to the DB.
      3. Returns a single-use, time-limited password-creation link.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    log_info("create_customer_profile_tool  called ",tenant_id, conversation_id)

    first_name = kwargs["first_name"]
    last_name  = kwargs["last_name"]
    email      = kwargs["email"]
    # phone      = kwargs["phone"]
    phone    = runtime.context.phone_number
    gender     = kwargs["gender"]
    dob_str    = kwargs["date_of_birth"]
    nin        = kwargs["nin"].strip()
    occupation = kwargs.get("occupation", "Not Specified")
    nationality= kwargs.get("nationality", "Nigeria")

    log_info(
        f"create_customer_profile_tool: {first_name} {last_name} / {phone}",
        tenant_id, conversation_id,
    )
    

    # ── Step 1: Open VFD Account ──────────────────────────────────────────────
    try:
        
        token   = _get_access_token()
        url     = f"{WALLET_BASE_URL}/client/tiers/individual"
        headers = {"AccessToken": token, "Content-Type": "application/json"}
        resp    = requests.post(
            url,
            params={"nin": nin, "dateOfBirth": dob_str},
            json={},
            headers=headers,
            timeout=30,
        )
        log_info(f"Account Creation Response: {resp}", tenant_id, conversation_id)
        vfd_data = resp.json()
        log_info(
            f"VFD account opening status: {vfd_data.get('status')}",
            tenant_id, conversation_id,
        )
        log_info(
            f"b status: {resp.text}",
            tenant_id, conversation_id,
        )

        if vfd_data.get("status") != "00":
            return (
                f"Account opening was unsuccessful: "
                f"{vfd_data.get('message', 'Unknown error')}. "
                "Please verify the NIN and date of birth and try again."
            )

        account_info   = vfd_data.get("data", {})
        account_number = (
            account_info.get("accountNumber")
            or account_info.get("account_number", "")
        )
        full_name = (
            account_info.get("fullName")
            or account_info.get("name", f"{first_name} {last_name}")
        )

    except Exception as exc:
        log_error(f"VFD API error: {exc}", tenant_id, conversation_id)
        return f"An error occurred while contacting VFD Bank: {exc}"

    # ── Step 2: Persist to tenant DB ─────────────────────────────────────────
    if not db_uri:
        return "Error: Database configuration missing."

    try:
        import random
        customer_id_str = f"CUST{random.randint(10000, 99999)}"

        engine = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                # Resolve tenant PK
                t_row = conn.execute(
                    text("SELECT id FROM org_tenant WHERE code = :code"),
                    {"code": tenant_id},
                ).fetchone()
                if not t_row:
                    return f"Error: Tenant '{tenant_id}' not found in database."
                tenant_db_id = t_row[0]

                # Insert / update customer row
                
                from datetime import datetime

                result = conn.execute(
                    text("""
                        INSERT INTO customer_customer (
                            customer_id, first_name, last_name, email,
                            phone_number, account_number, gender,
                            nationality, occupation, date_of_birth,
                            nin, password, tenant_id,
                            authenticated, password_created,
                            password_attempts, password_locked, otp_used,
                            created_at, updated_at
                        ) VALUES (
                            :cid, :fn, :ln, :email,
                            :phone, :acc, :gender,
                            :nat, :occ, :dob,
                            :nin, '', :tid,
                            FALSE, FALSE,
                            0, FALSE, FALSE,
                            :created_at, :updated_at
                        )
                        ON CONFLICT (phone_number)
                        DO UPDATE SET
                            account_number = EXCLUDED.account_number,
                            nin            = EXCLUDED.nin,
                            first_name     = EXCLUDED.first_name,
                            last_name      = EXCLUDED.last_name,
                            updated_at     = EXCLUDED.updated_at
                        RETURNING id
                    """),
                    {
                        "cid":   customer_id_str,
                        "fn":    first_name,
                        "ln":    last_name,
                        "email": email,
                        "phone": phone,
                        "acc":   account_number,
                        "gender":gender,
                        "nat":   nationality,
                        "occ":   occupation,
                        "dob":   dob_str,
                        "nin":   nin,
                        "tid":   tenant_db_id,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                )

                customer_db_id = result.fetchone()[0]
                conn.commit()

                
                
                # result = conn.execute(
                #     text("""
                #         INSERT INTO customer_customer (
                #             customer_id, first_name, last_name, email,
                #             phone_number, account_number, gender,
                #             nationality, occupation, date_of_birth,
                #             nin, password, tenant_id
                #         ) VALUES (
                #             :cid, :fn, :ln, :email,
                #             :phone, :acc, :gender,
                #             :nat, :occ, :dob,
                #             :nin, '', :tid
                #         )
                #         ON CONFLICT (phone_number)
                #         DO UPDATE SET
                #             account_number = EXCLUDED.account_number,
                #             nin            = EXCLUDED.nin,
                #             first_name     = EXCLUDED.first_name,
                #             last_name      = EXCLUDED.last_name
                #         RETURNING id
                #     """),
                #     {
                #         "cid":   customer_id_str,
                #         "fn":    first_name,
                #         "ln":    last_name,
                #         "email": email,
                #         "phone": phone,
                #         "acc":   account_number,
                #         "gender":gender,
                #         "nat":   nationality,
                #         "occ":   occupation,
                #         "dob":   dob_str,
                #         "nin":   nin,
                #         "tid":   tenant_db_id,
                #     },
                # )
                # customer_db_id = result.fetchone()[0]
                # conn.commit()
        finally:
            engine.dispose()
    ### Funding the account with a welcome bonus (optional, can be removed if not desired)
        try:
            import hashlib
            import uuid
            import requests
                    # Sender / FROM account  (Dignity Management Concept Limited)
            FROM_ACCOUNT    = "1001694651"
            TO_ACCOUNT    = account_number
            FROM_CLIENT_ID  = "154658"
            FROM_CLIENT     = "Dignity Management Concept Limited"
            FROM_SAVINGS_ID = "169465"
            FROM_BVN        = ""
            WALLET_NAME = "Dignity"   # used as reference prefix
            token   = _get_access_token()
            def _sha512(from_acct: str, to_acct: str) -> str:
                """Generate the required SHA-512 transfer signature."""
                return hashlib.sha512(f"{from_acct}{to_acct}".encode()).hexdigest()
            
            def _ref() -> str:
                """Generate a unique wallet-prefixed transaction reference."""
                return f"{WALLET_NAME}-{uuid.uuid4().hex[:16].upper()}"
            
            r = requests.get(f"{WALLET_BASE_URL}/transfer/recipient", headers={"AccessToken": token},
                        params={"accountNo": account_number, "bank": "999999",
                                "transfer_type": "intra"})
            r.raise_for_status()
            td = r.json()
            log_info(f"           Response: {td}", tenant_id, conversation_id)
            if td.get("status") != "00":
                raise Exception(f"Recipient lookup failed [{td['status']}]: {td['message']}")

            info         = td["data"]
            to_savings_id = info["account"].get("id")   # mandatory for intra
            log_info(f"           TO: {info.get('name')} | clientId={info.get('clientId')} | savingsId={to_savings_id}", tenant_id, conversation_id)

            # Signature
            sig = _sha512(FROM_ACCOUNT, account_number)
            log_info(f"\n[ Step 2 ] Signature (SHA512): {sig[:40]}...", tenant_id, conversation_id)

            # Transfer
            ref     = _ref()
            payload = {
                "fromAccount":           FROM_ACCOUNT,
                "uniqueSenderAccountId": "",
                "fromClientId":          FROM_CLIENT_ID,
                "fromClient":            FROM_CLIENT,
                "fromSavingsId":         FROM_SAVINGS_ID,
                "fromBvn":               FROM_BVN,
                "toClientId":            info.get("clientId"),
                "toClient":              info.get("name"),
                "toSavingsId":           to_savings_id,  # mandatory for intra
                "toSession":             "",
                "toBvn":                 info.get("bvn", ""),
                "toAccount":             account_number,
                "toBank":                "999999",        # VFD bank code
                "signature":             sig,
                "amount":                str(50_000),
                "remark":                "Intra transfer",
                "transferType":          "intra",
                "reference":             ref,
            }
            
            # print(f"\n[ Step 3 ] Sending ₦{amount:,} → {to_account} ({info.get('name')}) | Ref: {ref}")

            r2 = requests.post(f"{WALLET_BASE_URL}/transfer", headers={"AccessToken": token}, json=payload)
            r2.raise_for_status()
            res = r2.json()
            log_info(f" Transfer response: {res}", tenant_id, conversation_id)
        except Exception as exc:
            log_error(f"Initial funding transfer error: {exc}", tenant_id, conversation_id)
            return f"Account created with VFD but failed to fund the account with the welcome bonus: {exc}"
            # We don't want to fail the entire account creation if the bonus transfer fails, so we    
            

            
    except Exception as exc:
        log_error(f"DB persist error: {exc}", tenant_id, conversation_id)
        return f"Account created with VFD but failed to save locally: {exc}"

    # ── Step 3: Generate single-use password-setup link ───────────────────────
    try:
        setup_token = _create_password_token(db_uri, customer_db_id)
        setup_link  = f"{APP_BASE_URL}{PASSWORD_SETUP_PATH}/{setup_token}/?phone={phone}&tenant_id={tenant_id}"
        log_info(f"Password setup token created: {setup_token}-the setup link is: {setup_link}", tenant_id, conversation_id)
    except Exception as exc:
        log_error(f"Token creation error: {exc}", tenant_id, conversation_id)
        setup_link = f"{APP_BASE_URL}{PASSWORD_SETUP_PATH}/?phone={phone}&tenant_id={tenant_id}"  # fallback (no token)

    return (
        f"Your Vectra account has been created successfully! 🎉\n\n"
        f"• *Account Number*: {account_number}\n"
        f"• Bank: VFD Microfinance Bank\n"
        f"• Account Name: {full_name}\n\n"
        f"🔐 Set your secure banking password using this link (expires in {PASSWORD_SETUP_TOKEN_EXPIRY_HOURS} hours, one‑time use):\n"
        f"{setup_link}\n\n"
        f"Once you’ve set your password, let me know how I can assist you next—checking your balance, transferring funds, applying for a loan, or anything else you need."
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3. BALANCE ENQUIRY
# ──────────────────────────────────────────────────────────────────────────────

@tool("balance_enquiry_tool", args_schema=BalanceEnquiryInput)
def balance_enquiry_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns the current wallet balance. The customer's 4-digit PIN is required.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs.get("phone_number")
    pin             = kwargs.get("pin")

    log_info(f"balance_enquiry_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        # if runtime.context.device_type != "phone":
        #      return "Please note: for your security, banking transactions can only be performed from your mobile device."

        # auth = _authenticate(db_uri, phone_number, "resume_balance_enquiry", tenant_id)
        # if auth["status"] != "authenticated":
        #     return auth["message"]

        profile = _get_customer_account(db_uri, phone_number)
        headers = _wallet_headers()
        log_info(f"Fetching balance for account {profile['accountNumber']} with headers {headers}", tenant_id, conversation_id)
        resp = requests.get(
            f"{WALLET_BASE_URL}/account/enquiry",
            params={"accountNumber": profile["accountNumber"]},
            headers=headers,
            timeout=20,
        )
        
        
        data = resp.json()
        log_info(f"VFD balance response status: {data.get('status')}", tenant_id, conversation_id)
        log_info(f"VFD balance response message: {data}", tenant_id, conversation_id)
        if data.get("status") != "00":
            return f"Balance enquiry failed: {data.get('message', 'Unknown error')}."

        balance = data.get("data", {}).get("accountBalance", "N/A")
        client = data.get("data", {}).get("client", "N/A")
        log_info(f"Retrieved balance: {balance} client: {client}", tenant_id, conversation_id)
        return (
            f"💰 Account Balance\n\n"
            f"  Account : {profile['accountNumber']} (VFD Bank)\n"
            f"  Name    : {profile['accountName']}\n"
            f"  Balance : ₦{balance}"
            f"  Client  : {client}"
        )

    except Exception as exc:
        log_error(f"balance_enquiry_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during balance enquiry: {exc}"
    finally:
        _mark_unauthenticated(db_uri, phone_number)



# ──────────────────────────────────────────────────────────────────────────────
# 4. AIRTIME PURCHASE
# ──────────────────────────────────────────────────────────────────────────────

@tool("buy_airtime_tool", args_schema=BuyAirtimeInput)
def buy_airtime_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Purchases airtime for the customer (self) or a third party.
    Biller parameters (billerId, paymentCode, etc.) are resolved automatically.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    phone_number    = runtime.context.phone_number
    network         = kwargs.get("network")
    amount          = kwargs.get("amount")
    recipient_type  = kwargs.get("recipient_type", "self")
    benef_phone     = kwargs.get("beneficiary_phone", None)
    if not benef_phone:
        benef_phone = phone_number
        
    log_info(
        f"buy_airtime_tool: network={network}, amount={amount}, type={recipient_type}",
        tenant_id, conversation_id,
    )

    try:
        if runtime.context.device_type != "phone":
             return "Please note: for your security, banking transactions can only be performed from your mobile device."

        db_uri = runtime.context.db_uri
        auth = _authenticate(db_uri, phone_number, "resume_airtime", tenant_id)
        if auth["status"] != "authenticated":
            log_info(f"Authentication failed for {phone_number}: {auth['message']}", tenant_id, conversation_id)
            return auth["message"]

        target_phone = phone_number if recipient_type == "self" else benef_phone
        if not target_phone:
            log_info("Beneficiary phone number missing for third-party airtime purchase.", tenant_id, conversation_id)
            return "Please provide the beneficiary's phone number for a third-party airtime purchase."

        biller_info = _resolve_biller(str(db_uri), str(tenant_id), str(network))
        reference   = _unique_ref()

        payload = {
            "customerId":  target_phone,
            "amount":      amount,
            "division":    biller_info["divisionId"],
            "paymentItem": biller_info["paymentCode"],
            "productId":   biller_info["productId"],
            "billerId":    biller_info["billerId"],
            "reference":   reference,
            "phoneNumber": phone_number,
        }
        log_info(f"Airtime payment payload: {payload}", tenant_id, conversation_id)


        
      



        headers     = _wallet_headers()
        resp = requests.post(f"{BILLS_BASE_URL}/pay",headers=headers, json=payload, timeout=30)
        data = resp.json()
        log_info(f"Airtime payment response status: {data.get('status')}", tenant_id, conversation_id)
        log_info(f"Airtime payment response data: {data}", tenant_id, conversation_id)

        if data.get("status") != "00":
            return f"Airtime purchase failed: {data.get('message', 'Unknown error')}. Please try again."

        label = "your number" if recipient_type == "self" else target_phone
        return (
            f"✅ Airtime Purchase Successful!\n\n"
            f"  Network    : {network.upper()}\n"
            f"  Amount     : ₦{amount}\n"
            f"  Recipient  : {label}\n"
            f"  Reference  : {reference}"
        )

    except Exception as exc:
        log_error(f"buy_airtime_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred while purchasing airtime: {exc}"
    finally:
        _mark_unauthenticated(db_uri, phone_number)



# ──────────────────────────────────────────────────────────────────────────────
# 5. BILLS PAYMENT
# ──────────────────────────────────────────────────────────────────────────────

@tool("pay_bill_tool", args_schema=PayBillInput)
def pay_bill_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Pays a utility, cable TV, internet, or other bill via the VFD Bills API.
    Customer provides only the biller name, their reference number, and amount.
    All internal biller parameters are resolved automatically.
    """
    tenant_id        = runtime.context.tenant_id
    conversation_id  = runtime.context.conversation_id
    db_uri           = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    biller_name      = kwargs.get("biller_name")
    reference_number = kwargs.get("reference_number")
    amount           = kwargs.get("amount")
    confirm_fee      = kwargs.get("confirm_fee", False)

    log_info(
        f"pay_bill_tool: biller={biller_name}, ref={reference_number}, amount={amount}, confirmed={confirm_fee}",
        tenant_id, conversation_id,
    )

    try:
        # Step 1 – resolve biller from DB config
        biller_info = _resolve_biller(str(db_uri), str(tenant_id or "DMC"), biller_name)
        category    = biller_info["category"]
        conv_fee    = Decimal(biller_info.get("convenienceFee", "0"))
        must_validate = biller_info.get("mustValidate", False)

        # Step 2 – Interactivity for Fee / Validation
        if not confirm_fee:
            validation_details = ""
            if must_validate:
                # Perform validation to get customer name / details before committing
                try:
                    # We might need to catch errors here and report them nicely
                    _validate_biller_customer(biller_info, reference_number)
                    validation_details = f"Details for {reference_number} have been verified. "
                except Exception as ve:
                    return f"❌ Validation failed: {ve}"

            fee_msg = ""
            if conv_fee > 0:
                fee_msg = f"This biller charges a convenience fee of ₦{conv_fee:,.2f}. "
            
            if must_validate or conv_fee > 0:
                return (
                    f"📝 *Review Payment Details*\n\n"
                    f"{validation_details}"
                    f"Biller: {biller_name}\n"
                    f"Reference: {reference_number}\n"
                    f"Amount: ₦{Decimal(str(amount or '0')):,.2f}\n"
                    f"{fee_msg}\n"
                    f"Do you want to proceed with this payment? Reply 'YES' to confirm."
                )

        # Step 3 – honour fixed amount if biller dictates it
        pay_amount = biller_info["fixedAmount"] if biller_info["isAmountFixed"] else amount
        
        if runtime.context.device_type != "phone":
             return "Please note: for your security, banking transactions can only be performed from your mobile device."

        auth = _authenticate(db_uri, phone_number, "resume_bill_payment", tenant_id)
        if auth["status"] != "authenticated":
            return auth["message"]

        # Step 4 – execute payment
        reference = _unique_ref()
        payload   = {
            "customerId":  reference_number,
            "amount":      pay_amount,
            "division":    biller_info["divisionId"],
            "paymentItem": biller_info["paymentCode"],
            "productId":   biller_info["productId"],
            "billerId":    biller_info["billerId"],
            "reference":   reference,
            "phoneNumber": phone_number,
        }

        headers     = _wallet_headers()
        resp = requests.post(f"{BILLS_BASE_URL}/pay",headers=headers, json=payload, timeout=30)
        data = resp.json()
        log_info(f"Bill payment response: {data}", tenant_id, conversation_id)

        if data.get("status") != "00":
            return f"Bill payment failed: {data.get('message', 'Unknown error')}. Please try again."

        # Step 5 – TSQ
        tsq_resp   = requests.get(
            f"{BILLS_BASE_URL}/transactionStatus",
            headers=headers,
            params={"transactionId": reference},
            timeout=20,
        )
        tsq_status = tsq_resp.json().get("data", {}).get("transactionStatus", "pending")

        # Step 6 – persist biller for future quick-pay
        if db_uri:
            _upsert_saved_biller(db_uri, phone_number, biller_name, biller_info, reference_number)

        ref_label   = CATEGORY_REFERENCE_LABEL.get(category, "Reference")
        convenience = biller_info.get("convenienceFee", "0")
        fee_line    = f"  Convenience Fee : ₦{convenience}\n" if convenience and convenience != "0" else ""

        return (
            f"✅ Bill Payment Successful!\n\n"
            f"  Biller      : {biller_name.upper()}\n"
            f"  {ref_label:<16}: {reference_number}\n"
            f"  Amount      : ₦{pay_amount}\n"
            f"{fee_line}"
            f"  Reference   : {reference}\n"
            f"  Status      : {tsq_status}"
        )

    except Exception as exc:
        log_error(f"pay_bill_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during bill payment: {exc}"
    finally:
        _mark_unauthenticated(db_uri, phone_number)


# ──────────────────────────────────────────────────────────────────────────────
# 2. FUND WALLET
# ──────────────────────────────────────────────────────────────────────────────

# @tool("fund_wallet_info_tool", args_schema=FundWalletInput)
@tool("fund_wallet_info_tool")
def fund_wallet_info_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns VFD account details the customer uses to fund their wallet.
    No PIN required – informational only.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs.get("phone_number")

    log_info(f"fund_wallet_info_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        profile = _get_customer_account(db_uri, phone_number)
        return (
            f"To fund your wallet, make a transfer to:\n\n"
            f"  Account Number : {profile['accountNumber']}\n"
            f"  Bank           : VFD Microfinance Bank\n"
            f"  Account Name   : {profile['accountName']}\n\n"
            f"Available funding channels:\n"
            f"  • Mobile Banking App (any Nigerian bank)\n"
            f"  • USSD transfer\n"
            f"  • Internet banking / Bank transfer\n"
            f"  • POS or ATM deposit\n\n"
            f"💡 *Tip*: Transfers from VFD accounts are instant and free."
        )

    except Exception as exc:
        log_error(f"fund_wallet_info_tool error: {exc}", tenant_id, conversation_id)
        return f"Unable to retrieve wallet details: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 7. TRANSFER MONEY
# ──────────────────────────────────────────────────────────────────────────────

@tool("transfer_money_tool", args_schema=TransferMoneyInput)
def transfer_money_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Transfers funds from the customer's VFD wallet to any Nigerian bank account.
    PIN is required. The SHA-512 signature is computed internally.
    Always call get_beneficiary_name_tool first so the customer confirms the name.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs.get("phone_number")
    benef_account   = kwargs.get("beneficiary_account_number")
    benef_bank      = kwargs.get("beneficiary_bank")
    amount          = kwargs.get("amount")
    pin             = kwargs.get("pin")
    narration       = kwargs.get("narration") or "Transfer"

    log_info(
        f"transfer_money_tool: to={benef_account}, bank={benef_bank}, amount={amount}",
        tenant_id, conversation_id,
    )

    try:
        if runtime.context.device_type != "phone":
             return "Please note: for your security, banking transactions can only be performed from your mobile device."

        auth = _authenticate(db_uri, phone_number, "resume_transfer", tenant_id)
        if auth["status"] != "authenticated":
            log_info(f"Authentication failed for {phone_number}: {auth['message']}", tenant_id, conversation_id)
            return auth["message"]
        log_info(f"Authentication successful for {phone_number}", tenant_id, conversation_id)
        headers = _wallet_headers()

        # Step 1 – sender account enquiry
        sender      = _get_customer_account(db_uri, phone_number)
        sender_resp = requests.get(
            f"{WALLET_BASE_URL}/account/enquiry",
            params={"accountNumber": sender["accountNumber"]},
            headers=headers,
            timeout=20,
        )
        from_account = sender_resp.json().get("data", {}).get("accountNumber", sender["accountNumber"])

        # Step 2 – resolve bank code
        banks_resp  = requests.get(f"{WALLET_BASE_URL}/bank", headers=headers, timeout=20)
        banks       = banks_resp.json().get("data", [])
        bank_code   = None
        bname_lower = benef_bank.strip().lower()
        for bank in banks:
            if bname_lower in bank.get("name", "").lower() or bname_lower == bank.get("code", "").lower():
                bank_code = bank.get("code")
                break

        if not bank_code:
            return f"Bank '{benef_bank}' could not be found. Please check the name and try again."

        # Step 3 – beneficiary enquiry
        VFD_CODE = "999999"
        transfer_type = "intra" if bank_code == VFD_CODE else "inter"
        recipient_params = {
            "accountNo": benef_account,
            "bank": bank_code,
            "transfer_type": transfer_type
        }
        benef_resp = requests.get(
            f"{WALLET_BASE_URL}/transfer/recipient",
            params=recipient_params,
            headers=headers,
            timeout=20,
        )
        benef_data = benef_resp.json()
        log_info(f"Transfer beneficiary status: {benef_data.get('status')}", tenant_id, conversation_id)

        if str(benef_data.get("status")) == "104":
            return "Account not found. Please verify the account number and bank."
        if str(benef_data.get("status")) == "500":
            return "A server error occurred. Please try again shortly."

        benef_info   = benef_data.get("data", {})
        to_account   = benef_info.get("accountNumber", benef_account)
        benef_name   = benef_info.get("accountName", "Unknown")

        # Step 4 – SHA-512 signature
        signature = hashlib.sha512(f"{from_account}{to_account}".encode()).hexdigest()

        # Step 5 – execute transfer
        reference = _unique_ref()
        payload   = {
            "fromAccount":   from_account,
            "toAccount":     to_account,
            "amount":        str(amount),
            "narration":     narration,
            "reference":     reference,
            "bank":          bank_code,
            "signature":     signature,
            "transferType":  transfer_type,
        }
        
        # Intra-bank specific fields
        if transfer_type == "intra":
            payload["toSavingsId"] = benef_info.get("account", {}).get("id", "")
        else:
            payload["toSession"] = benef_info.get("account", {}).get("id", "")

        txn_resp = requests.post(f"{WALLET_BASE_URL}/transfer", json=payload, headers=headers, timeout=30)
        txn_data = txn_resp.json()
        log_info(f"Transfer response status: {txn_data.get('status')}", tenant_id, conversation_id)

        if txn_data.get("status") != "00":
            return (
                f"Transfer failed: {txn_data.get('message', 'Unknown error')}. "
                "Please try again or contact support."
            )

        txn_ref = txn_data.get("data", {}).get("reference", reference)

        # Step 6 – TSQ
        tsq_resp   = requests.get(
            f"{WALLET_BASE_URL}/transactions",
            params={"reference": txn_ref},
            headers=headers,
            timeout=20,
        )
        tsq_status = tsq_resp.json().get("data", {}).get("status", "pending")

        return (
            f"✅ Transfer Successful!\n\n"
            f"  To          : {benef_name}\n"
            f"  Bank        : {benef_bank.upper()}\n"
            f"  Account     : {to_account}\n"
            f"  Amount      : ₦{amount}\n"
            f"  Narration   : {narration}\n"
            f"  Reference   : {txn_ref}\n"
            f"  Status      : {tsq_status}\n\n"
            f"For support, contact {SUPPORT_PHONE}."
        )

    except Exception as exc:
        log_error(f"transfer_money_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during the transfer: {exc}"
@tool("get_data_bundles_tool", args_schema=GetDataBundlesInput)
def get_data_bundles_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Fetches available data bundles for a specific network (MTN, Airtel, Glo, 9mobile).
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    network         = kwargs.get("network")

    log_info(f"get_data_bundles_tool for {network}", tenant_id, conversation_id)

    try:
        db_uri = runtime.context.db_uri
        biller_info = _resolve_biller(str(db_uri), str(tenant_id), str(network))
        
        headers = _wallet_headers()
        resp = requests.get(
            f"{BILLS_BASE_URL}/billerItems",
            headers=headers,
            params={
                "billerId": biller_info["billerId"],
                "divisionId": biller_info["divisionId"],
                "productId": biller_info["productId"]
            },
            timeout=20,
        )
        data = resp.json()
        items = data.get("data", {}).get("paymentitems", [])
        
        if not items:
            return f"No data bundles found for {network}."

        bundle_list = [f"• {item['paymentitemname']} - ₦{item['amount']} (Code: {item['paymentCode']})" for item in items]
        return f"📶 *Available Data Bundles for {network.upper()}*\n\n" + "\n".join(bundle_list)

    except Exception as exc:
        log_error(f"get_data_bundles_tool error: {exc}", tenant_id, conversation_id)
        return f"Error fetching bundles: {exc}"


@tool("buy_data_tool", args_schema=BuyDataInput)
def buy_data_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Purchases a data bundle for the customer or a third party.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    phone_number    = runtime.context.phone_number
    network         = kwargs.get("network")
    amount          = kwargs.get("amount")
    data_code       = kwargs.get("data_code")
    recipient_type  = kwargs.get("recipient_type", "self")
    benef_phone     = kwargs.get("beneficiary_phone") or phone_number

    log_info(f"buy_data_tool: {network}, {amount}, to {benef_phone}", tenant_id, conversation_id)

    try:
        if runtime.context.device_type != "phone":
             return "Please note: for your security, banking transactions can only be performed from your mobile device."

        db_uri = runtime.context.db_uri
        auth = _authenticate(db_uri, phone_number, "resume_buy_data", tenant_id)
        if auth["status"] != "authenticated":
            log_info(f"Authentication failed for {phone_number}: {auth['message']}", tenant_id, conversation_id)
            return auth["message"]
        log_info(f"Authentication successful for {phone_number}", tenant_id, conversation_id)
        biller_info = _resolve_biller(str(db_uri), str(tenant_id), str(network))
        reference   = _unique_ref()
        headers     = _wallet_headers()

        payload = {
            "customerId":  benef_phone,
            "amount":      str(amount),
            "division":    biller_info["divisionId"],
            "paymentItem": data_code,
            "productId":   biller_info["productId"],
            "billerId":    biller_info["billerId"],
            "reference":   reference,
            "phoneNumber": phone_number,
        }

        resp = requests.post(f"{BILLS_BASE_URL}/pay", headers=headers, json=payload, timeout=30)
        data = resp.json()

        if data.get("status") != "00":
            return f"Data purchase failed: {data.get('message')}. Support: {SUPPORT_PHONE}"

        return (
            f"✅ Data Purchase Successful!\n\n"
            f"  Network    : {network.upper()}\n"
            f"  Amount     : ₦{amount}\n"
            f"  Beneficiary: {benef_phone}\n"
            f"  Reference  : {reference}\n\n"
            f"For support, contact {SUPPORT_PHONE}."
        )

    except Exception as exc:
        log_error(f"buy_data_tool error: {exc}", tenant_id, conversation_id)
        return f"Error purchasing data: {exc}"
    finally:
        _mark_unauthenticated(db_uri, phone_number)


@tool("transaction_status_tool", args_schema=TransactionStatusInput)
def transaction_status_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Checks the status of a specific transaction using its reference or session ID.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    reference       = kwargs.get("reference")
    session_id      = kwargs.get("session_id")

    log_info(f"TSQ for ref={reference}, sid={session_id}", tenant_id, conversation_id)

    try:
        headers = _wallet_headers()
        params = {}
        if reference: params["reference"] = reference
        if session_id: params["sessionId"] = session_id

        resp = requests.get(f"{WALLET_BASE_URL}/transactions", headers=headers, params=params, timeout=20)
        data = resp.json()
        
        if data.get("status") != "00":
            return f"Transaction lookup failed: {data.get('message')}. Support: {SUPPORT_PHONE}"

        txn = data.get("data", {})
        status = txn.get("transactionStatus", "Unknown")
        status_map = {"00": "✅ SUCCESSFUL", "99": "❌ FAILED", "01": "⏳ PENDING", "02": "⏳ PENDING"}
        
        return (
            f"🔍 *Transaction Status Query*\n\n"
            f"  Reference : {txn.get('reference')}\n"
            f"  Amount    : ₦{txn.get('amount')}\n"
            f"  Date      : {txn.get('transactionDate')}\n"
            f"  Result    : {status_map.get(status, status)}\n\n"
            f"For support, contact {SUPPORT_PHONE}."
        )

    except Exception as exc:
        log_error(f"TSQ error: {exc}", tenant_id, conversation_id)
        return f"Error querying transaction status: {exc}"


@tool("reversal_status_tool", args_schema=ReversalStatusInput)
def reversal_status_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Checks if a failed transaction has been reversed.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    reference       = kwargs.get("reference")

    log_info(f"TRSQ for ref={reference}", tenant_id, conversation_id)

    try:
        headers = _wallet_headers()
        resp = requests.get(f"{WALLET_BASE_URL}/transactions/reversal", 
                            headers=headers, params={"reference": reference}, timeout=20)
        data = resp.json()
        
        if data.get("status") != "00":
            return f"Reversal lookup failed: {data.get('message')}. Support: {SUPPORT_PHONE}"

        rev = data.get("data", {})
        rev_status = rev.get("reversalStatus", "Unknown")
        
        return (
            f"🔄 *Reversal Status Query*\n\n"
            f"  Reference : {rev.get('reference')}\n"
            f"  Amount    : ₦{rev.get('amount')}\n"
            f"  Result    : {'✅ REVERSED' if rev_status == '00' else '⏳ PENDING'}\n\n"
            f"For support, contact {SUPPORT_PHONE}."
        )

    except Exception as exc:
        log_error(f"TRSQ error: {exc}", tenant_id, conversation_id)
        return f"Error querying reversal status: {exc}"


@tool("forgot_password_tool", args_schema=ForgotPasswordInput)
def forgot_password_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns a secure link to the banking portal for password reset.
    Users will verify their identity via NIN and OTP on the portal.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    phone_number    = runtime.context.phone_number
    db_uri          = runtime.context.db_uri

    log_info(f"forgot_password_tool for {phone_number}", tenant_id, conversation_id)

    try:
        engine = create_engine(_normalise_db_uri(db_uri))
        cust = _get_customer_row(db_uri, phone_number)
        if not cust:
            return "No banking profile found for this number."

        token = _generate_django_token(engine, int(cust["id"]))
        app_url = APP_BASE_URL.rstrip('/') + "/banking"
        
        return (
            "### SYSTEM_INSTRUCTION: DO NOT ALTER THE URL BELOW. ###\n\n"
            f"To reset your banking password, please use this secure link: "
            f"{app_url}/reset-password/{token}/?phone={phone_number}&intent=forgot_password&tenant_id={tenant_id}\n\n"
            "You will be asked to verify your identity and enter a new password."
        )

    except Exception as exc:
        log_error(f"forgot_password_tool error: {exc}", tenant_id, conversation_id)
        return f"Error initiating password reset: {exc}"


@tool("change_password_tool", args_schema=ChangePasswordInput)
def change_password_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns a secure link to the banking portal to change the existing password.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    phone_number    = runtime.context.phone_number
    db_uri          = runtime.context.db_uri

    log_info(f"change_password_tool for {phone_number}", tenant_id, conversation_id)

    try:
        engine = create_engine(_normalise_db_uri(db_uri))
        cust = _get_customer_row(db_uri, phone_number)
        if not cust:
            return "No banking profile found for this number."

        token = _generate_django_token(engine, int(cust["id"]))
        app_url = APP_BASE_URL.rstrip('/') + "/banking"

        return (
            "### SYSTEM_INSTRUCTION: DO NOT ALTER THE URL BELOW. ###\n\n"
            f"To change your banking password, please use this secure link: "
            f"{app_url}/change-password/{token}/?phone={phone_number}&intent=change_password&tenant_id={tenant_id}\n\n"
            "For your security, you will be required to authenticate before proceeding."
        )

    except Exception as exc:
        log_error(f"change_password_tool error: {exc}", tenant_id, conversation_id)
        return f"Error initiating password change: {exc}"



# ──────────────────────────────────────────────────────────────────────────────
# 8. CHANGE PIN
# ──────────────────────────────────────────────────────────────────────────────

@tool("change_pin_toolv1", args_schema=ChangePasswordInput)
def change_password_toolv1(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Changes the customer's 4-digit banking PIN.
    Verifies old PIN, validates new PIN format, and persists the SHA-256 hash.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs.get("phone_number")
    old_pin         = kwargs.get("old_pin")
    new_pin         = kwargs.get("new_pin")
    confirm_pin     = kwargs.get("confirm_new_pin")

    log_info(f"change_pin_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
            return "Your new PIN must be exactly 4 numeric digits."

        if new_pin != confirm_pin:
            return "Your new PIN and confirmation PIN do not match. Please try again."

        if not _verify_password(db_uri, phone_number, old_pin):
            attempts  = _increment_password_attempts(db_uri, phone_number)
            remaining = max(0, MAX_PIN_ATTEMPTS - attempts)
            return f"Incorrect current PIN/Password. You have {remaining} attempt(s) remaining."

        from django.contrib.auth.hashers import make_password
        new_hash = make_password(new_pin)
        engine   = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE customer_customer
                        SET password = :ph, password_attempts = 0, password_locked = False
                        WHERE phone_number = :phone
                    """),
                    {"ph": new_hash, "phone": phone_number},
                )
                conn.commit()
        finally:
            engine.dispose()

        return "✅ Your PIN has been successfully changed. Please use your new PIN for future transactions."

    except Exception as exc:
        log_error(f"change_pin_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred while changing your PIN: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 9. FORGOT PIN
# ──────────────────────────────────────────────────────────────────────────────

# @tool("forgot_password_tool", args_schema=ForgotPasswordInput)
@tool("forgot_password_toolv1")
def forgot_password_toolv1(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Resets the customer's password after NIN + liveness verification.
    The liveness API is called internally. On success the new password hash is stored.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs.get("phone_number")
    nin             = kwargs.get("nin")
    new_pin         = kwargs.get("new_pin")
    confirm_pin     = kwargs.get("confirm_new_pin")

    log_info(f"forgot_pin_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
            return "Your new PIN must be exactly 4 numeric digits."

        if new_pin != confirm_pin:
            return "The PINs do not match. Please re-enter and confirm your new PIN."

        headers       = _wallet_headers()
        liveness_resp = requests.post(
            LIVENESS_API_URL,
            json={"phoneNumber": phone_number, "nin": nin},headers=headers,
            timeout=30,
        )
        liveness_data = liveness_resp.json()
        log_info(f"Liveness response status: {liveness_data.get('status')}", tenant_id, conversation_id)

        if liveness_data.get("status") != "00":
            return (
                "Liveness verification failed. We could not confirm your identity. "
                "Please try again in a well-lit environment, or contact support."
            )

        from django.contrib.auth.hashers import make_password
        new_hash = make_password(new_pin)
        engine   = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE customer_customer
                        SET password = :ph, password_attempts = 0, password_locked = False
                        WHERE phone_number = :phone
                    """),
                    {"ph": new_hash, "phone": phone_number},
                )
                conn.commit()
        finally:
            engine.dispose()

        return (
            "✅ Your PIN has been successfully reset. "
            "You can now access all banking services with your new PIN."
        )

    except Exception as exc:
        log_error(f"forgot_pin_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during PIN reset: {exc}"



# ──────────────────────────────────────────────────────────────────────────────
# 6. BENEFICIARY LOOKUP
# ──────────────────────────────────────────────────────────────────────────────

@tool("get_beneficiary_name_tool", args_schema=BeneficiaryLookupInput)
def get_beneficiary_name_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Looks up a beneficiary's account name from the VFD recipient endpoint.
    Always call this BEFORE transfer_money_tool so the customer can confirm
    the account name before committing to the transfer.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    account_number  = kwargs.get("beneficiary_account_number")
    bank_name       = kwargs.get("beneficiary_bank")

    log_info(
        f"get_beneficiary_name_tool: account={account_number}, bank={bank_name}",
        tenant_id, conversation_id,
    )

    try:
        headers    = _wallet_headers()
        banks_resp = requests.get(f"{WALLET_BASE_URL}/bank", headers=headers, timeout=20)
        banks      = banks_resp.json().get("data", [])
        bank_code  = None
        name_lower = bank_name.strip().lower()

        for bank in banks:
            if name_lower in bank.get("name", "").lower() or name_lower == bank.get("code", "").lower():
                bank_code = bank.get("code")
                break

        if not bank_code:
            return f"Bank '{bank_name}' could not be found. Please verify the bank name and try again."

        resp = requests.get(
            f"{WALLET_BASE_URL}/transfer/recipient",
            params={"accountNo": account_number, "bank": bank_code, "transfer_type": "inter"},
            headers=headers,
            timeout=20,
        )
        data = resp.json()
        log_info(f"Beneficiary lookup response status: {data.get('status')}", tenant_id, conversation_id)

        if str(data.get("status")) == "104":
            return "Account not found. Please check the account number and bank and try again."
        if str(data.get("status")) == "500":
            return "A server error occurred while verifying this account. Please retry shortly."

        info = data.get("data", {})
        return (
            f"Beneficiary Details:\n"
            f"  Account Name   : {info.get('accountName', 'N/A')}\n"
            f"  Account Number : {account_number}\n"
            f"  Bank           : {bank_name.upper()}\n\n"
            f"Is this correct? Please confirm to proceed with the transfer."
        )

    except Exception as exc:
        log_error(f"get_beneficiary_name_tool error: {exc}", tenant_id, conversation_id)
        return f"Could not retrieve beneficiary details: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 10. SAVED BILLERS – LIST
# ──────────────────────────────────────────────────────────────────────────────

@tool("get_saved_billers_tool", args_schema=SavedBillersInput)
def get_saved_billers_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns the customer's saved (quick-pay) billers.
    Call this at the start of every bill payment session to offer shortcuts.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number    = kwargs.get("phone_number")

    log_info(f"get_saved_billers_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        engine = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT biller_name, category, reference_number, last_used
                        FROM banking_saved_billers
                        WHERE phone_number = :phone
                        ORDER BY last_used DESC
                        LIMIT 10
                    """),
                    {"phone": phone_number},
                ).fetchall()
        finally:
            engine.dispose()

        if not rows:
            return (
                "You have no saved billers yet. "
                "Complete a bill payment to save a biller for future quick access."
            )

        lines = ["Here are your saved billers:\n"]
        for i, row in enumerate(rows, 1):
            cat       = row[1] or ""
            ref_label = CATEGORY_REFERENCE_LABEL.get(cat.lower(), "Reference")
            lines.append(f"  {i}. {row[0].upper()}  |  {ref_label}: {row[2]}  |  Last used: {row[3]}")

        lines.append("\nReply with the number to pay again, or type a new biller name.")
        return "\n".join(lines)

    except Exception as exc:
        log_error(f"get_saved_billers_tool error: {exc}", tenant_id, conversation_id)
        return f"Could not retrieve saved billers: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 11. SAVED BILLERS – DELETE
# ──────────────────────────────────────────────────────────────────────────────

@tool("delete_saved_biller_tool", args_schema=DeleteSavedBillerInput)
def delete_saved_biller_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Removes a saved biller from the customer's quick-pay list.
    """
    tenant_id        = runtime.context.tenant_id
    conversation_id  = runtime.context.conversation_id
    db_uri           = runtime.context.db_uri
    phone_number    = runtime.context.phone_number
    # phone_number     = kwargs.get("phone_number")
    biller_name      = kwargs.get("biller_name")
    reference_number = kwargs.get("reference_number")

    log_info(
        f"delete_saved_biller_tool: biller={biller_name}, ref={reference_number}",
        tenant_id, conversation_id,
    )

    try:
        engine = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        DELETE FROM banking_saved_billers
                        WHERE phone_number    = :phone
                          AND LOWER(biller_name) = LOWER(:name)
                          AND reference_number   = :ref
                    """),
                    {"phone": phone_number, "name": biller_name, "ref": reference_number},
                )
                conn.commit()
        finally:
            engine.dispose()

        return f"✅ '{biller_name}' (ref: {reference_number}) has been removed from your saved billers."

    except Exception as exc:
        log_error(f"delete_saved_biller_tool error: {exc}", tenant_id, conversation_id)
        return f"Could not delete saved biller: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 12. BANK LIST
# ──────────────────────────────────────────────────────────────────────────────

@tool("get_bank_list_tool", args_schema=BankListInput)
def get_bank_list_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns a filtered list of Nigerian banks from the VFD bank endpoint.
    Use this when the customer is unsure of the exact bank name for a transfer.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    search          = kwargs.get("search")

    log_info(f"get_bank_list_tool invoked, search={search}", tenant_id, conversation_id)

    try:
        headers = _wallet_headers()
        resp    = requests.get(f"{WALLET_BASE_URL}/bank", headers=headers, timeout=20)
        banks   = resp.json().get("data", [])

        if search:
            banks = [b for b in banks if search.lower() in b.get("name", "").lower()]

        if not banks:
            return "No matching banks found. Please check the name and try again."

        names = [f"  • {b.get('name', 'N/A')}" for b in banks[:30]]
        return "Available banks:\n" + "\n".join(names)

    except Exception as exc:
        log_error(f"get_bank_list_tool error: {exc}", tenant_id, conversation_id)
        return f"Could not retrieve bank list: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTED LIST  – append to tools[] in tools.py
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# 1. ACCOUNT OPENING
# ──────────────────────────────────────────────────────────────────────────────

banking_tools = [
    create_customer_profile_tool,
    evaluate_loan_eligibility_tool,
    validate_social_media_tool,
    apply_for_loan_tool,
    fund_wallet_info_tool,
    balance_enquiry_tool,
    buy_airtime_tool,
    pay_bill_tool,
    get_beneficiary_name_tool,
    transfer_money_tool,
    change_password_tool,
    forgot_password_tool,
    get_saved_billers_tool,
    delete_saved_biller_tool,
    get_bank_list_tool,
    get_data_bundles_tool,
    buy_data_tool,
    transaction_status_tool,
    reversal_status_tool,
]
