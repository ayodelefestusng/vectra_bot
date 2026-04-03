"""
banking_tools_extended.py
────────────────────────────────────────────────────────────────────────────────
New LangChain tools — append to banking_tools list in banking_tools.py.

Tools added
  1.  validate_social_media_tool         – URL format + platform + reachability
  2.  initiate_password_reset_tool       – Step 1: warn of ₦10 charge, ask confirm
  3.  confirm_password_reset_tool        – Step 2: debit ₦10, send OTP via SMS
  4.  verify_otp_and_issue_link_tool     – Step 3: validate OTP → issue reset link
  5.  apply_for_loan_tool                – Full loan eligibility check + creation

Convention mirrors the rest of the codebase.
"""

import os
import re
import uuid
import random
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

import requests
from langchain.tools import tool, ToolRuntime
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from .logger_utils import log_info, log_error, log_warning
from .base import Context

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

WALLET_BASE_URL  = os.getenv("VFD_WALLET_BASE_URL",
    "https://api-devapps.vfdbank.systems/vtech-wallet/api/v2/wallet2")
AUTH_URL         = os.getenv("VFD_AUTH_URL",
    "https://api-devapps.vfdbank.systems/vfd-tech/baas-portal/v1.1/baasauth/token")
CONSUMER_KEY     = os.getenv("VFD_CONSUMER_KEY",    "mL1dqaMcB760EP3fR18Vc23qUSZy")
CONSUMER_SECRET  = os.getenv("VFD_CONSUMER_SECRET", "ohAWPpabbj0UmMppmOgAFTazkjQt")
APP_BASE_URL     = os.getenv("APP_BASE_URL",    "https://yourapp.com")
SMS_API_URL      = os.getenv("SMS_API_URL",     "https://mock-sms.yourapp.com/send")
SMS_API_KEY      = os.getenv("SMS_API_KEY",     "mock-key")
WALLET_PREFIX    = os.getenv("VFD_WALLET_PREFIX", "rosapay")

OTP_CHARGE_AMOUNT      = Decimal("10.00")   # ₦10 debit before OTP is sent
OTP_EXPIRY_SECONDS     = 10                 # tight 10-second window
PASSWORD_SETUP_PATH    = "/banking/set-password"
TOKEN_EXPIRY_HOURS     = 24

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

_create_password_token

# ──────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _normalise_db_uri(uri: str) -> str:
    if uri and uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


def _get_access_token() -> str:
    resp = requests.post(
        AUTH_URL,
        json={
            "consumerKey":    CONSUMER_KEY,
            "consumerSecret": CONSUMER_SECRET,
            "validityTime":   "-1",
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") == "00":
        return data["data"]["access_token"]
    raise RuntimeError(f"VFD auth failed: {data}")


def _wallet_headers() -> dict:
    return {"AccessToken": _get_access_token(), "Content-Type": "application/json"}


def _unique_ref() -> str:
    ts  = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:6].upper()
    return f"{WALLET_PREFIX}-{ts}-{uid}"


def _get_customer_full(db_uri: str, phone_number: str) -> dict | None:
    """
    Returns customer row including id, account_number, full_name, nin, password.
    """
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id,
                           account_number,
                           first_name || ' ' || last_name AS full_name,
                           nin,
                           password
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


def _debit_customer_vfd(account_number: str, amount: Decimal, narration: str) -> dict:
    """
    Debits the customer's VFD wallet.
    Returns {"success": bool, "ref": str, "message": str}.
    """
    ref     = _unique_ref()
    headers = _wallet_headers()
    payload = {
        "amount":        str(amount),
        "accountNumber": account_number,
        "narration":     narration,
        "transactionRef": ref,
    }
    try:
        resp = requests.post(
            f"{WALLET_BASE_URL}/account/debit",
            json=payload,
            headers=headers,
            timeout=30,
        )
        data = resp.json()
        if data.get("status") == "00":
            return {"success": True,  "ref": ref, "message": "Debit successful."}
        return {"success": False, "ref": ref, "message": data.get("message", "Debit failed.")}
    except Exception as exc:
        return {"success": False, "ref": ref, "message": str(exc)}


def _send_otp_sms(phone_number: str, otp_code: str) -> bool:
    """
    Sends OTP via the configured SMS gateway.
    Returns True on success.  Replace the payload structure with your real provider.
    """
    try:
        resp = requests.post(
            SMS_API_URL,
            json={
                "api_key":     SMS_API_KEY,
                "to":          phone_number,
                "message":     (
                    f"Your RosaPay password reset OTP is: {otp_code}. "
                    f"Valid for {OTP_EXPIRY_SECONDS} seconds. Do not share this code."
                ),
                "sender_id":   "RosaPay",
            },
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _create_otp_record(db_uri: str, customer_id: int, charge_ref: str) -> str:
    """
    Inserts a PasswordResetOTP row and returns the raw 6-digit code.
    Expires in OTP_EXPIRY_SECONDS seconds.
    """
    code       = f"{random.randint(0, 999999):06d}"
    expires_at = (
        datetime.now(tz=dt_timezone.utc)
        + timedelta(seconds=OTP_EXPIRY_SECONDS)
    ).isoformat()

    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            # Invalidate any existing unused OTPs for this customer first
            conn.execute(
                text("""
                    UPDATE customer_passwordresetotp
                    SET is_used = TRUE
                    WHERE customer_id = :cid AND is_used = FALSE
                """),
                {"cid": customer_id},
            )
            conn.execute(
                text("""
                    INSERT INTO customer_passwordresetotp
                        (id, customer_id, otp_code, expires_at, is_used, charge_ref,
                         created_at)
                    VALUES
                        (:uid, :cid, :code, :exp, FALSE, :ref, NOW())
                """),
                {
                    "uid":  str(uuid.uuid4()),
                    "cid":  customer_id,
                    "code": code,
                    "exp":  expires_at,
                    "ref":  charge_ref,
                },
            )
            conn.commit()
    finally:
        engine.dispose()

    return code


def _validate_otp(db_uri: str, customer_id: int, otp_code: str) -> dict:
    """
    Checks OTP validity.  Returns {"valid": bool, "reason": str}.
    Marks used immediately on success.
    """
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, expires_at, is_used
                    FROM customer_passwordresetotp
                    WHERE customer_id = :cid
                      AND otp_code   = :code
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"cid": customer_id, "code": otp_code},
            ).fetchone()

            if not row:
                return {"valid": False, "reason": "OTP not found. Please request a new one."}

            otp_id, expires_at, is_used = row[0], row[1], row[2]

            if is_used:
                return {"valid": False, "reason": "This OTP has already been used."}

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

            # Mark used
            conn.execute(
                text("UPDATE customer_passwordresetotp SET is_used = TRUE WHERE id = :oid"),
                {"oid": otp_id},
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
            headers={"User-Agent": "Mozilla/5.0 (RosaPay/1.0 URL-Validator)"},
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
    phone_number    = kwargs["phone_number"]

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
    phone_number       = kwargs["phone_number"]
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
        narration      = "RosaPay SMS OTP charge – Password Reset",
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
    phone_number    = kwargs["phone_number"]
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
        reset_url = f"{APP_BASE_URL}{PASSWORD_SETUP_PATH}/{token}/"
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
    phone_number    = kwargs["phone_number"]
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
        f"Thank you for banking with RosaPay! 🏦"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EXPORT  – append to banking_tools list in banking_tools.py
# ──────────────────────────────────────────────────────────────────────────────

extended_banking_tools = [
    validate_social_media_tool,
    initiate_password_reset_tool,
    confirm_password_reset_tool,
    verify_otp_and_issue_link_tool,
    apply_for_loan_tool,
]
