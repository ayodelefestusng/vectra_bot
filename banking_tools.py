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

import hashlib
import os
import uuid
from datetime import datetime

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
    ChangePinInput,
    ForgotPinInput,
    SavedBillersInput,
    DeleteSavedBillerInput,
    BankListInput,
)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

WALLET_BASE_URL = os.getenv(
    "VFD_WALLET_BASE_URL",
    "https://api-devapps.vfdbank.systems/vtech-wallet/api/v2/wallet2",
)
BILLS_BASE_URL = os.getenv(
    "VFD_BILLS_BASE_URL",
    "https://api-devapps.vfdbank.systems/vtech-bills/api/v2/billspaymentstore",
)
AUTH_URL = os.getenv(
    "VFD_AUTH_URL",
    "https://api-devapps.vfdbank.systems/vfd-tech/baas-portal/v1.1/baasauth/token",
)
LIVENESS_API_URL = os.getenv("LIVENESS_API_URL", "https://yourapp.com/api/liveness")
CONSUMER_KEY     = os.getenv("VFD_CONSUMER_KEY",    "mL1dqaMcB760EP3fR18Vc23qUSZy")
CONSUMER_SECRET  = os.getenv("VFD_CONSUMER_SECRET", "ohAWPpabbj0UmMppmOgAFTazkjQt")
WALLET_PREFIX    = os.getenv("VFD_WALLET_PREFIX",   "rosapay")

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


def _wallet_headers() -> dict:
    return {"AccessToken": _get_access_token(), "Content-Type": "application/json"}


def _unique_ref() -> str:
    ts  = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:6].upper()
    return f"{WALLET_PREFIX}-{ts}-{uid}"


def _normalise_db_uri(db_uri: str) -> str:
    """Mirrors the same fix used throughout tools.py."""
    if db_uri and db_uri.startswith("postgres://"):
        return db_uri.replace("postgres://", "postgresql://", 1)
    return db_uri


def _resolve_biller(biller_name: str) -> dict:
    """
    Silently resolves a human biller name to all internal VFD parameters.
    Returns: billerId, divisionId, productId, paymentCode,
             isAmountFixed, fixedAmount, convenienceFee, category.
    """
    resp    = requests.get(f"{BILLS_BASE_URL}/billerlist", timeout=20)
    billers = resp.json().get("data", [])
    name_lower = biller_name.strip().lower()

    matched = None
    for b in billers:
        if name_lower in b.get("name", "").lower() or name_lower in b.get("id", "").lower():
            matched = b
            break

    if not matched:
        raise ValueError(
            f"Biller '{biller_name}' could not be found. "
            "Please check the name and try again."
        )

    biller_id   = matched["id"]
    division_id = matched["division"]
    product_id  = matched["product"]
    category    = matched.get("category", "").lower()
    convenience = matched.get("convenienceFee", "0")

    items_resp    = requests.get(
        f"{BILLS_BASE_URL}/billerItems",
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

    return {
        "billerId":       biller_id,
        "divisionId":     division_id,
        "productId":      product_id,
        "paymentCode":    payment_code,
        "isAmountFixed":  is_fixed,
        "fixedAmount":    fixed_amount,
        "convenienceFee": convenience,
        "category":       category,
    }


def _validate_biller_customer(biller_info: dict, customer_id: str) -> None:
    params = {
        "divisionId":  biller_info["divisionId"],
        "paymentItem": biller_info["paymentCode"],
        "customerId":  customer_id,
        "billerId":    biller_info["billerId"],
    }
    resp = requests.get(f"{BILLS_BASE_URL}/customervalidate", params=params, timeout=20)
    data = resp.json()
    if data.get("status") != "00":
        raise ValueError(
            f"Reference validation failed: {data.get('message', 'Invalid reference')}. "
            "Please check your meter / smart card number and try again."
        )


def _get_customer_account(db_uri: str, phone_number: str) -> dict:
    """Returns {"accountNumber": "...", "accountName": "..."} from local DB."""
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT account_number, full_name
                    FROM banking_customer_profile
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
        return {"accountNumber": row[0], "accountName": row[1]}
    finally:
        engine.dispose()


def _verify_pin(db_uri: str, phone_number: str, pin: str) -> bool:
    hashed = hashlib.sha256(pin.encode()).hexdigest()
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT 1 FROM banking_customer_profile
                    WHERE phone_number = :phone AND pin_hash = :ph
                    LIMIT 1
                """),
                {"phone": phone_number, "ph": hashed},
            ).fetchone()
        return row is not None
    finally:
        engine.dispose()


def _increment_pin_attempts(db_uri: str, phone_number: str) -> int:
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE banking_customer_profile
                    SET failed_pin_attempts = COALESCE(failed_pin_attempts, 0) + 1
                    WHERE phone_number = :phone
                """),
                {"phone": phone_number},
            )
            conn.commit()
            row = conn.execute(
                text("SELECT failed_pin_attempts FROM banking_customer_profile WHERE phone_number = :phone"),
                {"phone": phone_number},
            ).fetchone()
        return row[0] if row else 1
    finally:
        engine.dispose()


def _reset_pin_attempts(db_uri: str, phone_number: str) -> None:
    engine = create_engine(_normalise_db_uri(db_uri))
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE banking_customer_profile SET failed_pin_attempts = 0 WHERE phone_number = :phone"),
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
        log_error(f"_upsert_saved_biller failed: {exc}")
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────────────────────
# 1. ACCOUNT OPENING
# ──────────────────────────────────────────────────────────────────────────────

@tool("create_vfd_account_tool", args_schema=VFDAccountOpeningInput)
def create_vfd_account_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Opens a new VFD bank account using the customer's NIN and date of birth.
    On success, returns the account number, bank name, and a PIN setup link.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri

    nin          = kwargs.get("nin")
    dob          = kwargs.get("date_of_birth")
    phone_number = kwargs.get("phone_number")

    log_info(f"create_vfd_account_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        token   = _get_access_token()
        url     = f"{WALLET_BASE_URL}/client/tiers/individual"
        headers = {"AccessToken": token, "Content-Type": "application/json"}
        resp    = requests.post(
            url,
            params={"nin": nin, "dateOfBirth": dob},
            json={},
            headers=headers,
            timeout=30,
        )
        data = resp.json()
        log_info(f"VFD account opening response status: {data.get('status')}", tenant_id, conversation_id)

        if data.get("status") != "00":
            return (
                f"Account opening was unsuccessful: {data.get('message', 'Unknown error')}. "
                "Please verify your NIN and date of birth and try again."
            )

        account_info   = data.get("data", {})
        account_number = account_info.get("accountNumber") or account_info.get("account_number", "N/A")
        full_name      = account_info.get("fullName") or account_info.get("name", "")

        # Persist to tenant DB (same pattern as create_customer_profile_tool)
        if db_uri:
            engine = create_engine(_normalise_db_uri(db_uri))
            try:
                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO banking_customer_profile
                                (phone_number, account_number, full_name, failed_pin_attempts)
                            VALUES (:phone, :acct, :name, 0)
                            ON CONFLICT (phone_number)
                            DO UPDATE SET account_number = EXCLUDED.account_number,
                                          full_name      = EXCLUDED.full_name
                        """),
                        {"phone": phone_number, "acct": account_number, "name": full_name},
                    )
                    conn.commit()
            finally:
                engine.dispose()

        create_pin_link = f"https://yourapp.com/banking/create-pin?phone={phone_number}"

        return (
            f"🎉 Account successfully created!\n\n"
            f"  Account Number : {account_number}\n"
            f"  Bank           : VFD Bank\n"
            f"  Account Name   : {full_name}\n\n"
            f"To complete your setup and access all banking services, please create "
            f"your 4-digit PIN using the link below:\n"
            f"👉 {create_pin_link}"
        )

    except Exception as exc:
        log_error(f"create_vfd_account_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during account opening: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 2. FUND WALLET
# ──────────────────────────────────────────────────────────────────────────────

@tool("fund_wallet_info_tool", args_schema=FundWalletInput)
def fund_wallet_info_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Returns VFD account details the customer uses to fund their wallet.
    No PIN required – informational only.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = kwargs.get("phone_number")

    log_info(f"fund_wallet_info_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        profile = _get_customer_account(db_uri, phone_number)
        return (
            f"To fund your wallet, make a transfer to:\n\n"
            f"  Account Number : {profile['accountNumber']}\n"
            f"  Bank           : VFD Bank\n"
            f"  Account Name   : {profile['accountName']}\n\n"
            f"Available funding channels:\n"
            f"  • Mobile Banking App (any Nigerian bank)\n"
            f"  • USSD transfer\n"
            f"  • Internet banking / Bank transfer\n"
            f"  • POS or ATM deposit\n\n"
            f"Funds are usually credited within minutes. "
            f"Contact support if your balance is not updated after 10 minutes."
        )

    except Exception as exc:
        log_error(f"fund_wallet_info_tool error: {exc}", tenant_id, conversation_id)
        return f"Unable to retrieve wallet details: {exc}"


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
    phone_number    = kwargs.get("phone_number")
    pin             = kwargs.get("pin")

    log_info(f"balance_enquiry_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        if not _verify_pin(db_uri, phone_number, pin):
            attempts  = _increment_pin_attempts(db_uri, phone_number)
            remaining = max(0, MAX_PIN_ATTEMPTS - attempts)
            if remaining == 0:
                return (
                    "Your account has been locked due to too many incorrect PIN attempts. "
                    "Please use the 'Forgot PIN' option to reset your PIN."
                )
            return f"Incorrect PIN. You have {remaining} attempt(s) remaining before your account is locked."

        _reset_pin_attempts(db_uri, phone_number)
        profile = _get_customer_account(db_uri, phone_number)
        headers = _wallet_headers()

        resp = requests.get(
            f"{WALLET_BASE_URL}/account/enquiry",
            params={"accountNumber": profile["accountNumber"]},
            headers=headers,
            timeout=20,
        )
        data = resp.json()
        log_info(f"VFD balance response status: {data.get('status')}", tenant_id, conversation_id)

        if data.get("status") != "00":
            return f"Balance enquiry failed: {data.get('message', 'Unknown error')}."

        balance = data.get("data", {}).get("balance", "N/A")
        return (
            f"💰 Account Balance\n\n"
            f"  Account : {profile['accountNumber']} (VFD Bank)\n"
            f"  Name    : {profile['accountName']}\n"
            f"  Balance : ₦{balance}"
        )

    except Exception as exc:
        log_error(f"balance_enquiry_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during balance enquiry: {exc}"


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
    phone_number    = kwargs.get("phone_number")
    network         = kwargs.get("network")
    amount          = kwargs.get("amount")
    recipient_type  = kwargs.get("recipient_type", "self")
    benef_phone     = kwargs.get("beneficiary_phone")

    log_info(
        f"buy_airtime_tool: network={network}, amount={amount}, type={recipient_type}",
        tenant_id, conversation_id,
    )

    try:
        target_phone = phone_number if recipient_type == "self" else benef_phone
        if not target_phone:
            return "Please provide the beneficiary's phone number for a third-party airtime purchase."

        biller_info = _resolve_biller(network)
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

        resp = requests.post(f"{BILLS_BASE_URL}/pay", json=payload, timeout=30)
        data = resp.json()
        log_info(f"Airtime payment response status: {data.get('status')}", tenant_id, conversation_id)

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
    phone_number     = kwargs.get("phone_number")
    biller_name      = kwargs.get("biller_name")
    reference_number = kwargs.get("reference_number")
    amount           = kwargs.get("amount")

    log_info(
        f"pay_bill_tool: biller={biller_name}, ref={reference_number}, amount={amount}",
        tenant_id, conversation_id,
    )

    try:
        # Step 1 – resolve biller silently
        biller_info = _resolve_biller(biller_name)
        category    = biller_info["category"]

        # Step 2 – mandatory customer validation for utility / cable TV
        if category in MANDATORY_VALIDATE_CATEGORIES:
            _validate_biller_customer(biller_info, reference_number)

        # Step 3 – honour fixed amount if biller dictates it
        pay_amount = biller_info["fixedAmount"] if biller_info["isAmountFixed"] else amount

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

        resp = requests.post(f"{BILLS_BASE_URL}/pay", json=payload, timeout=30)
        data = resp.json()
        log_info(f"Bill payment response status: {data.get('status')}", tenant_id, conversation_id)

        if data.get("status") != "00":
            return f"Bill payment failed: {data.get('message', 'Unknown error')}. Please try again."

        # Step 5 – TSQ
        tsq_resp   = requests.get(
            f"{BILLS_BASE_URL}/transactionStatus",
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
    phone_number    = kwargs.get("phone_number")
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
        # PIN verification (same guard pattern as balance_enquiry_tool)
        if not _verify_pin(db_uri, phone_number, pin):
            attempts  = _increment_pin_attempts(db_uri, phone_number)
            remaining = max(0, MAX_PIN_ATTEMPTS - attempts)
            if remaining == 0:
                return (
                    "Your account has been locked due to too many incorrect PIN attempts. "
                    "Please use 'Forgot PIN' to reset your PIN."
                )
            return f"Incorrect PIN. You have {remaining} attempt(s) remaining."

        _reset_pin_attempts(db_uri, phone_number)
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
        benef_resp = requests.get(
            f"{WALLET_BASE_URL}/transfer/recipient",
            params={"accountNo": benef_account, "bank": bank_code, "transfer_type": "inter"},
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
            "amount":        amount,
            "narration":     narration,
            "reference":     reference,
            "bank":          bank_code,
            "signature":     signature,
            "transfer_type": "inter",
        }

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
            f"  Status      : {tsq_status}"
        )

    except Exception as exc:
        log_error(f"transfer_money_tool error: {exc}", tenant_id, conversation_id)
        return f"An error occurred during the transfer: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# 8. CHANGE PIN
# ──────────────────────────────────────────────────────────────────────────────

@tool("change_pin_tool", args_schema=ChangePinInput)
def change_pin_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Changes the customer's 4-digit banking PIN.
    Verifies old PIN, validates new PIN format, and persists the SHA-256 hash.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = kwargs.get("phone_number")
    old_pin         = kwargs.get("old_pin")
    new_pin         = kwargs.get("new_pin")
    confirm_pin     = kwargs.get("confirm_new_pin")

    log_info(f"change_pin_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
            return "Your new PIN must be exactly 4 numeric digits."

        if new_pin != confirm_pin:
            return "Your new PIN and confirmation PIN do not match. Please try again."

        if not _verify_pin(db_uri, phone_number, old_pin):
            attempts  = _increment_pin_attempts(db_uri, phone_number)
            remaining = max(0, MAX_PIN_ATTEMPTS - attempts)
            return f"Incorrect current PIN. You have {remaining} attempt(s) remaining."

        new_hash = hashlib.sha256(new_pin.encode()).hexdigest()
        engine   = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE banking_customer_profile
                        SET pin_hash = :ph, failed_pin_attempts = 0
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

@tool("forgot_pin_tool", args_schema=ForgotPinInput)
def forgot_pin_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """
    Resets the customer's PIN after NIN + liveness verification.
    The liveness API is called internally. On success the new PIN hash is stored.
    """
    tenant_id       = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri          = runtime.context.db_uri
    phone_number    = kwargs.get("phone_number")
    nin             = kwargs.get("nin")
    new_pin         = kwargs.get("new_pin")
    confirm_pin     = kwargs.get("confirm_new_pin")

    log_info(f"forgot_pin_tool invoked for phone: {phone_number}", tenant_id, conversation_id)

    try:
        if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
            return "Your new PIN must be exactly 4 numeric digits."

        if new_pin != confirm_pin:
            return "The PINs do not match. Please re-enter and confirm your new PIN."

        liveness_resp = requests.post(
            LIVENESS_API_URL,
            json={"phoneNumber": phone_number, "nin": nin},
            timeout=30,
        )
        liveness_data = liveness_resp.json()
        log_info(f"Liveness response status: {liveness_data.get('status')}", tenant_id, conversation_id)

        if liveness_data.get("status") != "00":
            return (
                "Liveness verification failed. We could not confirm your identity. "
                "Please try again in a well-lit environment, or contact support."
            )

        new_hash = hashlib.sha256(new_pin.encode()).hexdigest()
        engine   = create_engine(_normalise_db_uri(db_uri))
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE banking_customer_profile
                        SET pin_hash = :ph, failed_pin_attempts = 0
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
    phone_number    = kwargs.get("phone_number")

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
    phone_number     = kwargs.get("phone_number")
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

banking_tools = [
    create_vfd_account_tool,
    fund_wallet_info_tool,
    balance_enquiry_tool,
    buy_airtime_tool,
    pay_bill_tool,
    get_beneficiary_name_tool,
    transfer_money_tool,
    change_pin_tool,
    forgot_pin_tool,
    get_saved_billers_tool,
    delete_saved_biller_tool,
    get_bank_list_tool,
]
