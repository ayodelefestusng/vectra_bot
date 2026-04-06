from typing import Any, Dict, List, Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field, ValidationError
from langgraph.graph import END, START, MessagesState, StateGraph

# Define the input schema for the multiplication tool
class MultiplicationInput(BaseModel):
    """Input for the multiplication tool."""

    a: Union[int, float] = Field(description="The first number to multiply.")
    b: Union[int, float] = Field(description="The second number to multiply.")
    # Add a simple string field if you need context from the state
    context_message: str = Field(
        description=" The exact value of   llm_calls in the state message eg '2' "
    )
    model_provider: str = Field(
        description=" The name of the model being used eg   eg 'chatgpt' "
    )

class PayslipQuery(BaseModel):
    start_date: str = Field(..., description="Start month and year in MMYYYY format (e.g., 012025) or natural language (e.g., 'Jan 2025')")
    end_date: str = Field(..., description="End month and year in MMYYYY format (e.g., 122025) or natural language")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID") 
    
class LeaveBalanceRequest(BaseModel):
    employee_id: str = Field(..., description="Internal employee ID (email)")
    year: int = Field(..., description="Leave year to check (e.g., 2025)")
    leaveTypeName: str = Field(..., description="Name of the leave type to check")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
    
class PayslipListQuery(BaseModel):
    employee_id: str
    year: int



class PayslipInfo(BaseModel):
    period: str
    gross_pay: float
    net_pay: float
    currency: str
    download_url: str = ""

class PayslipSummary(BaseModel):
    period: str
    gross_pay: float
    net_pay: float
    currency: str
    download_url: str = ""


class PayslipListResponse(BaseModel):
    employee_id: str
    year: int
    payslips: List[PayslipSummary]
    
    
class PayslipDownloadQuery(BaseModel):
    employee_id: str
    year: int
    month: int


class PayslipDownloadResponse(BaseModel):
    period: str
    pdf_url: str
    
class PayslipExplainQuery(BaseModel):
    employee_id: str
    year: int
    month: int


class PayslipExplainResponse(BaseModel):
    period: str
    explanation: str
    

class LeaveTypeRequest(BaseModel):
    employee_id: Optional[str] = Field(None, description="The ID of the employee")
    # current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
class PrepareLeaveApplicationRequest(BaseModel):
    employeeID: str
    leaveTypeName: str
    leaveStartDate: str = Field(..., description="Start date in DDMMYYYY format")
    leaveEndDate: str = Field(..., description="End date in DDMMYYYY format")
    leaveReason: str
    workAssigneeRequest: str = Field(..., description="The reliever or person taking over tasks")
    addressWhileOnLeave: str = Field(..., description="Physical address during vacation")
    emailWhileOnLeave: str = Field(..., description="Personal/Alternative email for contact")
    contactNoWhileOnLeave: str = Field(..., description="Phone number while away")
    leaveYear: int = Field(..., description="The year the leave is being deducted from (Current or Previous)")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
    
    
class PreparedLeaveApplication(BaseModel):
    address: str
    allowLeaveAllowanceOption: str
    consentNeeded: str
    contactNo: str
    email: str
    employeeID: str
    files: list
    hasAssignee: str
    isPaid: bool
    leaveAllowanceApplied: str
    leaveEndDate: str
    leaveReason: str
    leaveStartDate: str
    leaveType: dict
    leaveTypeID: str
    numOfDays: int
    resumptionDate: str
    supervisorID: str
    workAssigneeCompulsory: str
    workAssigneeRequest: str
    year: int
    
class ValidateLeaveBalanceRequest(BaseModel):
    employeeID: str = Field(..., description="The ID of the employee")
    leaveTypeName: str = Field(..., description="The name of the leave type (e.g., Annual Leave)")
    leaveTypeID: Optional[str] = Field(None, description="Optional ID of the leave type if known")
    year: int = Field(..., description="The leave year (e.g., 2025)")
    numOfDays: int = Field(..., description="The number of days requested for validation")


class ValidateLeaveBalanceResponse(BaseModel):
    status: str
    message: str
    remainingDays: int = 0
  
  
class CalculateDaysRequest(BaseModel):
    startDate: str
    endDate: str
    holidays: List[str] = []  # optional list of YYYY-MM-DD strings


class CalculateDaysResponse(BaseModel):
    numOfDays: int  
    


class SubmitLeaveApplicationRequest(BaseModel):
    # Core Identification
    employeeID: str = Field(..., description="The employee ID (or email)")
    leaveTypeID: Optional[str] = Field(None, description="The unique ID for the leave type")
    leaveTypeName: str = Field(..., description="The human-readable name of the leave type")
    
    # Dates and Duration
    leaveStartDate: str = Field(..., description="Start date in DDMMYYYY format")
    leaveEndDate: str = Field(..., description="End date in DDMMYYYY format")
    resumptionDate: str = Field(..., description="Date the employee returns to work (DDMMYYYY)")
    year: int = Field(..., description="The calendar year for this leave deduction")
    numOfDays: int = Field(..., description="The total number of days being requested")
    
    # Contact and Handover
    leaveReason: str = Field(..., description="The reason for the leave request")
    workAssigneeRequest: Optional[str] = Field(None, description="The name or email of the relief officer")
    address: str = Field(..., description="Physical address while on leave")
    contactNo: str = Field(..., description="Phone number while on leave")
    email: str = Field(..., description="Alternative email while on leave")
    
    # Injected tracking
    state: Optional[dict] = Field(None, description="Injected workflow state")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
# 1. Update your Schema
class SearchJobOpportunitiesRequest(BaseModel):
    department: Optional[str] = Field(None, description="Filter by hiring department name")
    jobType: Optional[str] = Field(None, description="Filter by job type (e.g., Full-time, Contract)")
    location: Optional[str] = Field(None, description="Filter by work location")
    jobRoleType: Optional[str] = Field(None, description="Filter by role type")
    limit: int = Field(5, description="Number of results to return")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
    
    
class JobOpportunityResponse(BaseModel):
    """Structured response for a single job opportunity."""
    job_title: str
    department: str
    location: str
    salary_range: str
    experience_level: str
    description_snippet: str
    application_deadline: str

class LeaveStatusRequest(BaseModel):
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
class ExitPolicyRequest(BaseModel):
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")

class TravelSearchRequest(BaseModel):
    destination: str = Field(..., description="The vacation destination city")
    departureDate: str = Field(..., description="YYYY-MM-DD")
    returnDate: str = Field(..., description="YYYY-MM-DD")
    current_tool_id: Optional[str] = Field(None)

class ProfileUpdateInput(BaseModel):
    last_name: Optional[str] = Field(None, description="The new last name of the employee")
    pfa: Optional[str] = Field(None, description="The Pension Fund Administrator name")
    phone: Optional[str] = Field(None, description="The new phone number")
    personal_email: Optional[str] = Field(None, description="The personal email address")
    address: Optional[str] = Field(None, description="The residential address")
    city: Optional[str] = Field(None, description="The city of residence")
    state: Optional[str] = Field(None, description="The state of residence")
    country: Optional[str] = Field(None, description="The country of residence")
    account_number: Optional[str] = Field(None, description="The 10-digit bank account number")
    bank_name: Optional[str] = Field(None, description="The name of the bank")



class CustomerProfileInputvfd(BaseModel):
    first_name: str = Field(..., description="First name of the customer")
    last_name: str = Field(..., description="Last name of the customer")
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    gender: str = Field(..., description="Gender: male or female")
    date_of_birth: str = Field(..., description="Date of birth YYYY-MM-DD")
    occupation: Optional[str] = Field(None, description="Customer's occupation")
    nationality: Optional[str] = Field("Nigeria", description="Customer's nationality")
    nin: str = Field(..., description="National Identification Number (NIN) 11-digit number)")
    current_tool_id: Optional[str] = Field(None)

class CustomerProfileInput(BaseModel):
    """Schema for create_customer_profile_tool."""
    first_name:    str = Field(..., description="Customer's first name")
    last_name:     str = Field(..., description="Customer's last name")
    email:         str = Field(..., description="Customer's email address")
    phone:         str = Field(..., description="Nigerian phone number (e.g. 08012345678)")
    gender:        str = Field(..., description="'male' or 'female'")
    date_of_birth: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    nin:           str = Field(..., description="11-digit National Identification Number")
    occupation:    str = Field("Not Specified", description="Occupation")
    nationality:   str = Field("Nigeria", description="Nationality")
    current_tool_id: Optional[str] = Field(None)

# class AuthenticateCustomerInput(BaseModel):
#     """Schema for authenticate_customer_tool."""
#     phone_number: str = Field(..., description="Customer's registered phone number")
#     password:     Optional[str] = Field(None, description="Customer's service password")


class LoanEligibilityInput(BaseModel):
    """Schema for evaluate_loan_eligibility_tool."""
    # phone_number:   str = Field(..., description="Customer's registered phone number")
    amount:   str = Field(..., description="Amount of loan requested")
    tenor:   str = Field(..., description="Tenor of loan requested in months")
    facebook_url:   str = Field("", description="Facebook profile URL (optional) to assist credit evaluation")
    linkedin_url:   str = Field("", description="LinkedIn profile URL (optional)")
    instagram_url:  str = Field("", description="Instagram profile URL (optional)")
    twitter_url:    str = Field("", description="Twitter / X profile URL (optional)")
    tiktok_url:     str = Field("", description="TikTok profile URL (optional)")


# ──────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class ValidateSocialMediaInput(BaseModel):
    platform:    str = Field(..., description="Platform name: facebook, linkedin, instagram, twitter, tiktok")
    profile_url: str = Field(..., description="Full profile URL to validate")


class InitiatePasswordResetInput(BaseModel):
    phone_number: str = Field(..., description="Customer's registered phone number")


class ConfirmPasswordResetInput(BaseModel):
    phone_number:      str  = Field(..., description="Customer's registered phone number")
    customer_confirmed: bool = Field(..., description="True if customer agreed to the ₦10 SMS charge")


class VerifyOTPInput(BaseModel):
    phone_number: str = Field(..., description="Customer's registered phone number")
    otp_code:     str = Field(..., description="6-digit OTP entered by the customer")


class ApplyForLoanInput(BaseModel):
    # phone_number:     str   = Field(..., description="Customer's registered phone number")
    amount_requested: float = Field(..., description="Loan amount requested in Naira")
    tenor:            int   = Field(..., description="Loan duration in months")
    # bank:             str   = Field("VFD Microfinance Bank", description="Customer's bank name")
    facebook_url:   str = Field("", description="Facebook profile URL (optional) to assist credit evaluation")
    linkedin_url:   str = Field("", description="LinkedIn profile URL (optional)")
    instagram_url:  str = Field("", description="Instagram profile URL (optional)")
    twitter_url:    str = Field("", description="Twitter / X profile URL (optional)")
    tiktok_url:     str = Field("", description="TikTok profile URL (optional)")




class CustomerDetailsInput(BaseModel):
    phone_or_email: Optional[str] = Field(None, description="Phone number or email address of the customer")
    account_number: Optional[str] = Field(None, description="The 10-digit bank account number")
    current_tool_id: Optional[str] = Field(None)

class UpdateCustomerProfileInput(BaseModel):
    phone_number: Optional[str] = Field(None, description="The new phone number")
    email: Optional[str] = Field(None, description="The new email address")
    occupation: Optional[str] = Field(None, description="The new occupation")
    town_of_residence_id: Optional[int] = Field(None, description="ID of the town of residence Location")
    branch_id: Optional[int] = Field(None, description="ID of the branch Location")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


# ==========================
# 📊 Pydantic Schemas (Revised for Clarity)
# ==========================
class ToolInput(BaseModel):
    """Input for the multiplication tool."""

    conversation_id: str = Field(
        description="The value  convassociatied with conversation_id key  in the state meessage eg 'ers1'."
    )
    query: str = Field(
        description="TThe search workd suitable for  the user message context  ."
    )
    tenant_id: str = Field(
        description="The value  convassociatied with conversation_id key  in the state meessage eg '111'."
    )

    # # Add a simple string field if you need context from the state
    # context_message: str = Field(description=" The intt value of   llm_calls in the state message ")


class Answer(BaseModel):
    """The final, structured answer for the user."""

    answer: str = Field(
        description="Clear, concise, polite response to the user's query."
    )
    sentiment: int = Field(description="User's sentiment score from -2 to +2.")
    confidence_score: int = Field(
        default=1, description="AI confidence level in the response from 0-100."
    )  # Added
    ticket: List[str] = Field(description="List of relevant service channels.")
    source: List[str] = Field(description="Names of the tools used.")
    human_assistant: bool = Field(description="True if human assistance is required.")
    source_type: List[str] = Field(description="Type of the source used to generate the answer")
    # source_type: str = Field(
    #     default="AI", description="Type of the source used to generate the answer."
    # )

class VisualizationInput(BaseModel):
    """Input schema for the generate_visualization_tool."""
    query: str = Field(description="The user's natural language request for a chart or visualization, e.g., 'Plot the total sales by region'.")
    data: Optional[Any] = Field(None, description="The raw data payload from sql_query_tool to visualize. MUST be provided if available.")
    state: Optional[dict] = Field(None, description="Injected workflow state")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
class VisualizationAnalysis(BaseModel):
    """Structured analysis for a visualization."""
    summary: str = Field(description="A brief summary of the main trend or insight.")
    key_points: List[str] = Field(description="List of specific observations from the data.")
    recommendation: Optional[str] = Field(None, description="An actionable recommendation based on the data.")

class SQLQueryInput(BaseModel):
    """Input schema for the sql_query_tool."""
    query: str = Field(description="The user's natural language question (e.g., 'total sales per month'). NEVER generate SQL yourself; the tool handles that.")
    state: Optional[dict] = Field(None, description="Injected workflow state")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")
    
class Summary(BaseModel):
    """Conversation summary schema."""

    summary: str = Field(description="A concise summary of the entire conversation.")
    sentiment: int = Field(
        description="Overall sentiment of the conversation from -2 to +2."
    )
    unresolved_tickets: List[str] = Field(
        description="A list of channels with unresolved issues."
    )
    all_sources: List[str] = Field(
        description="All the tools used in the entire conversation ."
    )
    summary_human_assistant: bool = Field(
        description="Set to True ONLY if human assistance is required, otherwise False."
    )


class Context(BaseModel):
    """Context schema for the agent."""
    tenant_id: str = Field(description="The tenant or organization ID.") 
    conversation_id: str = Field(description="The unique ID for the conversation thread.")
    emp_id: Optional[str] = Field(description="The employee's email or ID, if available.")
    db_uri: Optional[str] = Field(description="Database connection URI, injected at runtime.")
    push_name: Optional[str] = Field(description="The name of the push notification, injected at runtime.")
    device_type: Optional[str] = Field("unknown", description="The device type of the user.")
    agent_prompt: str = Field(description="The original prompt given to the agent, injected at runtime.")
    final_answer_prompt: str = Field(description="The final prompt used to generate the answer, injected at runtime.")
    tool_intent_map: Optional[Dict[str, Any]] = Field(description="A mapping of tool categories to their intended tools and triggers.")
    # tenant_config: Optional[Dict[str, Any]] = Field(description="Configuration settings specific to the tenant, injected at runtime.")
    vector_store_path: Optional[str] = Field(description="The file path to the tenant's vector store, injected at runtime.")
    # summarization_request: bool = Field(description="Indicates if this is a summarization request, injected at runtime.")
    phone_number: Optional[str] = Field(description="The phone number of the user, injected at runtime.")
    # intent: Optional[str] = Field(description="The intent of the user, injected at runtime.")
class ResponseFormat(BaseModel):
    """Response schema for the agent."""
    # A punny response (always required)
    answer: str = Field(description="A concise response to the user's query.")
    # Any interesting information about the weather if available
    leave_application: Optional[dict]= Field(description="The leave approval status to be injected by tools if applicable, otherwise null.")
    visualization_image: Optional[str] = Field(None, description="Base64-encoded image string of the generated visualization, if applicable.")
    visualization_analysis:Optional[str] = Field(None, description="Amalysis  of the generated visualization, if applicable.")

 
# ══════════════════════════════════════════════════════════════════════════════
# BANKING (VFD) — Pydantic Input Schemas
# ══════════════════════════════════════════════════════════════════════════════

class VFDAccountOpeningInput(BaseModel):
    """Input schema for opening a VFD bank account via NIN."""
    nin: str = Field(..., description="Customer's 11-digit National Identification Number (NIN).")
    date_of_birth: str = Field(..., description="Customer's date of birth in YYYY-MM-DD format (e.g. 1994-04-05).")
    # phone_number: str = Field(..., description="Customer's registered phone number used to link their banking profile.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class FundWalletInput(BaseModel):
    """Input schema for retrieving wallet funding details."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class BalanceEnquiryInput(BaseModel):
    """Input schema for wallet balance enquiry. PIN is required."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class BuyAirtimeInput(BaseModel):
    """Input schema for purchasing airtime for self or a third party."""
    # phone_number: str = Field(..., description="Customer's registered phone number (the payer).")
    network: str = Field(..., description="Telecom network name, e.g. MTN, Airtel, Glo, 9mobile.")
    amount: str = Field(..., description="Airtime amount in Naira (e.g. '500').")
    recipient_type: str = Field(
        "self",
        description="Who is receiving the airtime: 'self' for the customer's own number, 'third_party' for someone else.",
    )
    beneficiary_phone: Optional[str] = Field(
        None,
        description="Beneficiary phone number. Required only when recipient_type is 'third_party'.",
    )
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class PayBillInput(BaseModel):
    """Input schema for bill payment. Customer provides only biller name, reference, and amount."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    biller_name: str = Field(
        ...,
        description=(
            "Human-readable biller name, e.g. DSTV, GOTV, EKEDC, IKEDC, Startimes, MTN Data. "
            "All internal biller IDs are resolved automatically."
        ),
    )
    reference_number: str = Field(
        ...,
        description=(
            "The customer's reference identifier for this biller. "
            "Meter Number for electricity, Smart Card Number for cable TV, "
            "Phone Number for airtime/data, Account/Username for internet."
        ),
    )
    amount: str = Field(..., description="Amount to pay in Naira.")
    confirm_fee: bool = Field(default=False, description="True if the customer has already confirmed the convenience fee and validated details.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class BeneficiaryLookupInput(BaseModel):
    """Input schema for looking up a transfer beneficiary's account name before confirming."""
    beneficiary_account_number: str = Field(..., description="The recipient's bank account number.")
    beneficiary_bank: str = Field(..., description="The recipient's bank name (e.g. Access Bank, GTBank).")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class TransferMoneyInput(BaseModel):
    """Input schema for executing a funds transfer. PIN is required to authorise."""
    # phone_number: str = Field(..., description="Sender's registered phone number.")
    beneficiary_account_number: str = Field(..., description="Recipient's bank account number.")
    beneficiary_bank: str = Field(..., description="Recipient's bank name (e.g. Access Bank, Zenith Bank).")
    amount: str = Field(..., description="Transfer amount in Naira.")
    narration: Optional[str] = Field(None, description="Optional transfer remark / description.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class ChangePinInput(BaseModel):
    """Input schema for changing the customer's 4-digit banking PIN."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    old_pin: str = Field(..., description="Current 4-digit PIN.")
    new_pin: str = Field(..., description="New 4-digit PIN the customer wishes to set.")
    confirm_new_pin: str = Field(..., description="Must match new_pin exactly.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class ForgotPinInput(BaseModel):
    """Input schema for resetting the PIN via NIN + liveness verification."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    nin: str = Field(..., description="Customer's National Identification Number (NIN).")
    new_pin: str = Field(..., description="New 4-digit PIN to set after identity verification.")
    confirm_new_pin: str = Field(..., description="Must match new_pin exactly.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class SavedBillersInput(BaseModel):
    """Input schema for retrieving a customer's list of saved (quick-pay) billers."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class DeleteSavedBillerInput(BaseModel):
    """Input schema for removing a saved biller from the customer's quick-pay list."""
    # phone_number: str = Field(..., description="Customer's registered phone number.")
    biller_name: str = Field(..., description="Name of the biller to remove.")
    reference_number: str = Field(..., description="Reference (meter number / smart card) associated with the saved biller.")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class BankListInput(BaseModel):
    """Input schema for fetching the list of Nigerian banks, optionally filtered by name."""
    search: Optional[str] = Field(None, description="Optional partial bank name to filter results (e.g. 'access').")
    current_tool_id: Optional[str] = Field(None, description="Injected tool call ID")


class State(MessagesState):
    """Manages the conversation state. Uses Pydantic models for structured data."""

    user_query: str
    attached_content: Optional[str]

    # Core identifiers
    conversation_id: str
    tenant_id: str

    # Tenant configuration and vector store
    tenant_config: Optional[Dict[str, Any]]
    vector_store_path: Optional[str]  # ✅ ADD THIS LINE

    summarization_request: bool
    # ✅ add this

    # vector_store: Optional[VectorStore]

    # Tool outputs
    pdf_content: Optional[str]
    web_content: Optional[str]
    ql_result: Optional[str]
    type: Optional[str]  # To indicate the type of last tool output

    # --- FINAL OUTPUTS ---
    # According to instructions, use leave_application for the structured result
    current_answer: Optional[Answer]
    conversation_summary: Optional[Summary]
    metadata: Optional[Dict[str, Any]]
    human_assistant_required: bool

    # Utility

    next_node: Optional[str]
    tool_usage_log: Optional[List[str]]  # Optional tracking
    llm_calls: int
    
    source_documents: Optional[List[str]]  # Optional tracking
    employee_id: str
    leave_application: Optional[dict]
    payslip_application: Optional[dict]
    payslip_info: Optional[dict]
    update_info: Optional[dict]
    job_opportunities: Optional[List[dict]]
    leave_status: Optional[dict]
    visualization_image: Optional[str]
    visualization_analysis: Optional[str]

    phone_number: str
    event: str
    tenant_id: str
    employee_id: str
    customer_name: str