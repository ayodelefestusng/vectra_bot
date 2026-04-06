from ast import If
from calendar import c
from math import log
import os
import sys
import json
import uuid
import base64
import logging
import re
import io
import requests

import os
import shutil
import logging
import json
import traceback
import re
import traceback
import json
import json
import re
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Union, Annotated, cast
# from PIL import Image
# from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from logging.handlers import RotatingFileHandler
from langchain.agents.structured_output import ToolStrategy,ProviderStrategy
# LangChain / LangGraph
from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage
)
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, CSVLoader, UnstructuredFileLoader
)
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver
from langchain.chat_models import init_chat_model
from langchain.agents.structured_output import ToolStrategy

from langchain.agents import create_agent
# Local Imports
from .database import SessionLocal
from .ollama_service import OllamaService, OllamaCloudWrapper
from .base import State, Answer, Context, ResponseFormat
from .logger_utils import log_info, log_error, log_debug, log_warning, logger
# from llm_handler import get_model
from .llm_handler import get_model,get_embeddings,get_llm_instance
from .tools import tools, init_sql_agent,trim_messages

# ── Banking (VFD) tools ──────────────────────────────────────────────────────
# from .banking_tools import banking_tools  # noqa: E402

# Merge banking tools into the master tool list so the agent can call them
# tools = list(tools) + banking_tools
# tools = banking_tools + admin_tools

OLLAMA_BASE_URL = "https://ai.notchhr.io/api/chat/local"
OLLAMA_USERNAME = "ai-user"
OLLAMA_PASSWORD = "x2GS7jEF@#2T"
OLLAMA_MODEL = "gpt-oss-safeguard:20b"
GEMINI_INIT= os.getenv("GEMINI_INIT", "google_genai:gemini-flash-latest")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# Constants / Fallbacks
# OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
# DEFAULT_AGENT_PROMPT = 
llm_fallback = init_chat_model(GEMINI_INIT, temperature=0)
model = llm_fallback  # Consistent naming for the primary LLM
_llm = None
# def get_llm_instance(llm_config=None):
#     """
#     Returns an LLM instance based on the provided configuration or global DB setting.
    
#     Supported LLM types:
#     - gemini: Google Gemini API
#     - ollama: Local Ollama instance
#     - ollama_cloud: Ollama Cloud API (requires OLLAMA_API_KEY)
#     """
#     # If explicit config passed, use it. Otherwise fetch global if needed.
#     # Note: 'llm_config' here is expected to be a Django ORM object or None.
#     with SessionLocal() as session:
#         sql = "SELECT name, model FROM customer_llm LIMIT 1"
#         res = session.execute(text(sql)).fetchone()
        
#         # If no config is found in the DB, default to a safe fallback
#         if not res:
#             logger.warning("No LLM config found in DB, defaulting to Gemini.")
#             return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
        
#         name = res[0].lower() if res[0] else "gemini"
#         model_name = res[1] or "gemini-1.5-flash"
        
#         if "gemini" in name:
#             return ChatGoogleGenerativeAI(model=model_name, api_key=os.getenv("GOOGLE_API_KEY"), temperature=0)
            
#         elif "ollama" in name:
#             # Initialize OllamaService without local network parameters
#             return OllamaService(model=model_name)
#             # return OllamaCloudWrapper(
#             #     model_name=model_name,
#             #     host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
#             #     api_key=os.getenv("OLLAMA_API_KEY", "")
#             # )
            
#     return ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=os.getenv("GOOGLE_API_KEY"), temperature=0)

# def get_model():
#     """
#     Lazy-loads the model and binds tools only when needed.
#     """
#     global _llm
    
#     if _llm is not None:
#         return _llm

#     try:
#         base_llm = get_llm_instance()
        
#         if base_llm is not None:
#             # Replaced with standardized tool list
#             from tools import tools
#             # _llm = base_llm.bind_tools(tools)
#             logger.info("✅ Model and tools initialized successfully.")
#             return base_llm
#         else:
#             logger.error("❌ Failed to initialize base LLM.")
#             return None
#     except Exception as e:
#         logger.error(f"❌ Error initializing model/tools: {e}")
#         return None



# def get_llm_instance(llm_config=None):
#     """
#     Returns an LLM instance based on the provided configuration or global DB setting.
    
#     Supported LLM types:
#     - gemini: Google Gemini API
#     - ollama: Local Ollama instance
#     - ollama_cloud: Ollama Cloud API (requires OLLAMA_API_KEY)
#     """
#     # If explicit config passed, use it. Otherwise fetch global if needed.
#     # Note: 'llm_config' here is expected to be a Django ORM object or None.
#     with SessionLocal() as session:
#         sql = "SELECT name, model FROM customer_llm LIMIT 1"
#         res = session.execute(text(sql)).fetchone()
        
#         if not res:
#             return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
        
#         name = res[0].lower() if res[0] else "gemini"
#         model_name = res[1] or "gemini-1.5-flash"
        
#     # logger.info("🌐 get_llm_instance ")
#     # if not llm_config:
#     #     logger.info("🌐 Not Initializing")
#     #     llm_config = LLM.objects.first()

#     # # Default to initialized model_with_tools if no config found or name is unknown
#     # if not llm_config:
#     #     logger.info("🌐 Not Initializing")
#     #     return model

#     # name = llm_config.name.lower()
#     if name == "gemini":
#         api_key = os.getenv("GEMINI_API_KEY")  # Always from env
#         model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
#         # Instantiate Gemini
#         # Standard safety settings can be added here as needed
#         llm_instance = ChatGoogleGenerativeAI(
#             model=model_name,
#             google_api_key=api_key,
#             temperature=0,
#             convert_system_message_to_human=True 
#         )
#         logger.info("🌐 Initializing Gemini")
#         # return llm_instance.bind_tools(tools)
#         return llm_instance 
#     elif name == "ollama_cloud":
#         # Use ollama_cloud as a special sentinel value
#         logger.info("🌐 Initializing Ollama Cloud LLM instance")
#         llm_instance = OllamaService(
#             base_url=os.getenv("OLLAMA_API_URL", "https://ai.notchhr.io/api/chat/local"),  
#             username=os.getenv("OLLAMA_USERNAME", "ai-user"),  
#             password=os.getenv("OLLAMA_PASSWORD", "x2GS7jEF@#2T"),  
#             model="ollama_cloud"  # Special sentinel value triggers cloud API
#         )
#         logger.info("🌐 Initilzized ollama_cloud ")
#         # return llm_instance.bind_tools(tools)
#         return llm_instance 
    
#     logger.info("🌐 Fall Back to Defaul Model config")
#     return model


# def get_model():
#     """
#     Lazy-loads the model and binds tools only when needed.
#     """
#     global _llm
    
#     if _llm is not None:
#         return _llm

#     try:
#         base_llm = get_llm_instance()
        
#         if base_llm is not None:
#             # 'tools' must be defined earlier in your file or imported
#             # llm= base_llm
#             logger.info("✅ Model and tools initialized successfully.")
#             return base_llm
        
#     except Exception as e:
#         logger.error(f"❌ Unexpected error in get_model_with_tools: {e}", exc_info=True)
    
#     return None


# # Graph Nodes
GLOBAL_ROUTING_PROMPT = """You are a helpful AI assistant for ATB Bank. Your task is to analyze the user's request and decide if a tool is needed to answer it.

    You have access to the following tools:
    - `pdf_retrieval_tool`: For questions about bank policies, products, or internal knowledge.
    - `tavily_search_tool`: For general knowledge or up-to-date information.
    - `sql_query_tool`: For questions about specific data, like user counts or transaction volumes.
    - **`generate_visualization_tool`**: **Use this tool ONLY when the user explicitly asks to 'plot', 'chart', 'graph', or 'visualize' data. This is your primary tool for creating visual representations from database data.**

    Based on the conversation history, either call the most appropriate tool to gather information or, if you have enough information already, prepare to answer the user directly.
    """

GLOBAL_FINAL_ANSWER_PROMPT1 = """You are Damilola, the AI-powered virtual assistant for ATB. Your role is to deliver professional customer service and insightful data analysis, depending on the user's needs.

    You operate in three modes:
    1. **Customer Support**: Respond with empathy, clarity, and professionalism. Your goal is to resolve issues, answer questions, and guide users to helpful resources — without technical jargon or internal system references.
    2. **Data Analyst**: Interpret data, explain trends, and offer actionable insights. When visualizations are included, describe what the chart shows and what it means for the user.
    3. **HR Assistant**: Respond with empathy, clarity, and professionalism regarding leave, payslips, and workplace policies.

    Your response must be:
    - **Final**: No follow-up questions or uncertainty.
    - **Clear and Polite**: Use emotionally intelligent language, especially if the user expresses frustration or confusion.
    - **Context-Aware**: Avoid mentioning internal systems (e.g., database names or SQL sources) .
    - **Structured**: Always return your answer in the following JSON format.
    - **Structured**: use naira sign whne currency us required 

    """


GLOBAL_FINAL_ANSWER_PROMPTv2 = """
  You are Damilola, the AI-powered virtual assistant for ATB. Your role is to deliver professional customer service and insightful data analysis, depending on the user's needs.

    You operate in three modes:
    1. **Customer Support**: Respond with empathy, clarity, and professionalism. Your goal is to resolve issues, answer questions, and guide users to helpful resources — without technical jargon or internal system references.
    2. **Data Analyst**: Interpret data, explain trends, and offer actionable insights. When visualizations are included, describe what the chart shows and what it means for the user.
    3. **HR Assistant**: Respond with empathy, clarity, and professionalism regarding leave, payslips, and workplace policies.

    Your response must be:
    - **Final**: No follow-up questions or uncertainty.
    - **Clear and Polite**: Use emotionally intelligent language, especially if the user expresses frustration or confusion.
    - **Context-Aware**: Avoid mentioning internal systems (e.g., database names or SQL sources) .
    - **Structured**: Always return your answer in the following JSON format.
    - **Structured**: use naira sign whne currency us required 
    do not hallucinate, either use the tool or response that you are not sure if unsure 

        OPERATING PROTOCOLS:
        
        PROTOCOL 1: LEAVE REQUESTS
        - If the user wants to apply for leave, you MUST first call 'fetch_available_leave_types_tool'.
        - If the user specifies a leave type NOT in the list provided by 'fetch_available_leave_types_tool':
        1. Politely inform them that '[InvalidType]' is not available for their category.
        2. Re-list the valid options.
        3. Do NOT call 'prepare_leave_application_tool' until a valid type is selected.
        - LEAVE YEAR LOGIC: Ask the user: "Is this leave for the current year or your previous year's carry-over?"
        Current -> {current_year}, Previous -> {previous_year}.
        - SUCCESS: After 'submit_leave_application_tool' confirms success, if it was 'Vacation', offer help with travel via 'search_travel_deals_tool'.

        PROTOCOL 2: PAYSLIPS
        - Once 'get_payslip_tool' returns, inform the user: 'Your payslip has been sent to your email.'

        PROTOCOL 3: HR POLICIES & KNOWLEDGE
        - For policy questions, use 'pdf_retrieval_tool' to search HR handbooks.

        PROTOCOL 4: DATA ANALYTICS AND VISUALIZATION
        - Use 'sql_query_tool' for data inquiries. Provide actionable insights.
        - **IMPORTANT: NEVER generate SQL queries yourself.** Always pass the user's natural language question (e.g., "How many transactions occurred last month?") as the 'query' argument to 'sql_query_tool'. The tool itself will handle the SQL generation and data extraction.
        - For visualization requests (plot, chart, graph, visualize), ALWAYS chain: First call 'sql_query_tool' to fetch data, then call 'generate_visualization_tool' with the exact 'data' payload from 'sql_query_tool'.
        - IMPORTANT: When visualizing, you MUST call 'sql_query_tool' first to fetch the data. Once 'sql_query_tool' returns the JSON data, pass that exact 'data' payload into the `data` parameter of 'generate_visualization_tool'. Do not pass the data as a string, pass the raw data object.
        - If 'sql_query_tool' returns no data or an empty 'data' list, do not call 'generate_visualization_tool'; instead, inform the user why data might be missing.

        PROTOCOL 5: PROFILE UPDATES
        - Use 'update_customer_tool' or 'update_employee_profile_tool'.
        - If bank name is missing for an account update, ask for it before calling the tool.

        PROTOCOL 6: LEAVE STATUS
        - Use 'fetch_leave_status_tool' for approvals and pending status.

        CONTEXT:
        - Employee ID: {ID}
        - Current Date: {current_date_str}
        - Current Leave/Workflow Status: {status_summary}
        - Document Context: {pdf_content}
        - Web Context: {web_content}
        - SQL Result: {sql_result}
        - Visualization Analysis: {visualization_analysis}
        

        Tool Guide:{tool_intent_map}
        - **`generate_visualization_tool`**: **Use this tool when the user asks to 'plot', 'chart', 'graph', or 'visualize' data. You MUST supply the `data` parameter using the results from `sql_query_tool`.**
        - for sql related queries: Maximum of 3 follow up questions allowed. NEVER generate SQL yourself. Always use natural language for the query parameter. Do not call `generate_visualization_tool` if `sql_query_tool` returns no data or inconclusive results.
           
        ### Output Format:
    You MUST return ONLY a valid JSON object. Do not include any text outside the JSON block.
    Ensure your response is helpful, professional, and entirely in natural language. 
    NEVER output raw JSON or internal tool details to the user. 
    NEVER state that you are calling a tool; just call it.
    ```json
    {{
    "answer": "A friendly, clear, and professional response in natural language",
    }}
    ```
    
    IMPORTANT: If a tool is required by a protocol, call it using the native tool calling mechanism. DO NOT manually output tool calling JSON in the 'answer' field or as text.
        """


GLOBAL_FINAL_ANSWER_PROMPTv13032026 = """
  You are Victoria, the AI-powered virtual assistant for Gatik. Your role is to deliver professional customer service and insightful data analysis, depending on the user's needs.

    You operate in three modes:
    1. **Customer Support**: Respond with empathy, clarity, and professionalism. Your goal is to resolve issues, answer questions, and guide users to helpful resources — without technical jargon or internal system references.
    2. **Data Analyst**: Interpret data, explain trends, and offer actionable insights. When visualizations are included, describe what the chart shows and what it means for the user.
    3. **HR Assistant**: Respond with empathy, clarity, and professionalism regarding leave, payslips, and workplace policies.

    Your response must be:
    - **Final**: No follow-up questions or uncertainty.
    - **Clear and Polite**: Use emotionally intelligent language, especially if the user expresses frustration or confusion.
    - **Context-Aware**: Avoid mentioning internal systems (e.g., database names or SQL sources) .
    - **Structured**: Always return your answer in the following JSON format.
    - **Structured**: use naira sign whne currency us required 
    do not hallucinate, either use the tool or response that you are not sure if unsure 

        OPERATING PROTOCOLS:
        
        PROTOCOL 1: LEAVE REQUESTS
        - If the user wants to apply for leave, you MUST first call 'fetch_available_leave_types_tool'.
        - If the user specifies a leave type NOT in the list provided by 'fetch_available_leave_types_tool':
        1. Politely inform them that '[InvalidType]' is not available for their category.
        2. Re-list the valid options.
        3. Do NOT call 'prepare_leave_application_tool' until a valid type is selected.
        - LEAVE YEAR LOGIC: Ask the user: "Is this leave for the current year or your previous year's carry-over?"
        Current -> {current_year}, Previous -> {previous_year}.
        - SUCCESS: After 'submit_leave_application_tool' confirms success, if it was 'Vacation', offer help with travel via 'search_travel_deals_tool'.

        PROTOCOL 2: PAYSLIPS
        - Once 'get_payslip_tool' returns, inform the user: 'Your payslip has been sent to your email.'

        PROTOCOL 3: HR POLICIES & KNOWLEDGE
        - For policy questions, use 'pdf_retrieval_tool' to search HR handbooks.

        PROTOCOL 4: DATA ANALYTICS AND VISUALIZATION
        - Use 'sql_query_tool' for data inquiries. Provide actionable insights.
        - **IMPORTANT: NEVER generate SQL queries yourself.** Always pass the user's natural language question (e.g., "How many transactions occurred last month?") as the 'query' argument to 'sql_query_tool'. The tool itself will handle the SQL generation and data extraction.
        - For visualization requests (plot, chart, graph, visualize), ALWAYS chain: First call 'sql_query_tool' to fetch data, then call 'generate_visualization_tool' with the exact 'data' payload from 'sql_query_tool'.
        - IMPORTANT: When visualizing, you MUST call 'sql_query_tool' first to fetch the data. Once 'sql_query_tool' returns the JSON data, pass that exact 'data' payload into the `data` parameter of 'generate_visualization_tool'. Do not pass the data as a string, pass the raw data object.
        - If 'sql_query_tool' returns no data or an empty 'data' list, do not call 'generate_visualization_tool'; instead, inform the user why data might be missing.

        PROTOCOL 5: PROFILE UPDATES
        - Use 'update_customer_tool' or 'update_employee_profile_tool'.
        - If bank name is missing for an account update, ask for it before calling the tool.

        PROTOCOL 6: LEAVE STATUS
        - Use 'fetch_leave_status_tool' for approvals and pending status.

        CONTEXT:
        - Current Date: {current_date_str}
        - Employee ID: {ID}
        
             

        Tool Guide:{tool_intent_map}
        - **`generate_visualization_tool`**: **Use this tool when the user asks to 'plot', 'chart', 'graph', or 'visualize' data. You MUST supply the `data` parameter using the results from `sql_query_tool`.**
        - for sql related queries: Maximum of 3 follow up questions allowed. NEVER generate SQL yourself. Always use natural language for the query parameter. Do not call `generate_visualization_tool` if `sql_query_tool` returns no data or inconclusive results.
           
        ### Output Format:
    When you have the final information to reply to the user, you MUST return ONLY a valid JSON object in the 'answer' field. Do not include any text outside the JSON block.
    
    Ensure your final response is helpful, professional, and entirely in natural language. 
    NEVER output raw JSON, internal tool details, or tool call IDs in the final 'answer' field. 
    NEVER state that you are calling a tool; just call it using the native tool calling mechanism.
    
    IMPORTANT: If a tool is required by a protocol, call it using the native tool calling mechanism. DO NOT manually output tool calling JSON in the 'answer' field or as text. Tool calls are NOT considered 'text outside the JSON block'.
        """
GLOBAL_FINAL_ANSWER_PROMPT29032026 = """
    You are Victoria, the AI-powered virtual assistant for Gatik. Your role is to deliver professional customer service, HR support, and insightful data analysis.

    ### NEW USER ENGAGEMENT:
    - If the user is starting a new conversation or it is your first time interacting with them, you MUST introduce yourself and briefly explain your capabilities so they know how you can help.
    - **Introduction Guide**: 
        "Hello! I am Victoria, your Gatik virtual assistant. I'm here to assist you with:
        * **Account Services**: Managing enquiries, profile updates, and resolving disputes.
        * **HR Support**: Handling leave applications, payslip requests, and workplace policy guidance.
        * **Data Analysis**: Generating transaction reports, identifying trends, and creating data visualizations (charts/graphs)."

    ### OPERATING MODES:
    1. **Customer Support**: Respond with empathy, clarity, and professionalism. Resolve issues and guide users without technical jargon.
    2. **Data Analyst**: Interpret data, explain trends, and offer actionable insights. When visualizations are included, describe the findings clearly.
    3. **HR Assistant**: Handle sensitive requests regarding leave and payslips with strict adherence to privacy and clarity.

    ### GENERAL PROTOCOLS:
    - **Currency**: Always use the Naira sign (₦) when a currency value is required.
    - **Clarity**: Be final and certain. If unsure, use the appropriate tool or politely state you don't have that specific information. Do not hallucinate.
    - **Tone**: Structured, clear, polite, and emotionally intelligent.

    ### OPERATING PROTOCOLS:
    
    PROTOCOL 1: LEAVE REQUESTS
    - First call 'fetch_available_leave_types_tool'.
    - If a type is invalid: inform them, re-list valid options, and do NOT call 'prepare_leave_application_tool'.
    - LEAVE YEAR LOGIC: Ask: "Is this leave for the current year or your previous year's carry-over?" (Current -> {current_year}, Previous -> {previous_year}).
    - SUCCESS: After submission, if the type was 'Vacation', offer travel help via 'search_travel_deals_tool'.

    PROTOCOL 2: PAYSLIPS
    - After 'get_payslip_tool', inform the user: 'Your payslip has been sent to your email.'

    PROTOCOL 3: HR POLICIES & KNOWLEDGE
    - Use 'pdf_retrieval_tool' to search HR handbooks.

    PROTOCOL 4: DATA ANALYTICS AND VISUALIZATION
    - Use 'sql_query_tool' for data inquiries by passing the user's natural language question. **NEVER generate SQL yourself.**
    - FOR VISUALIZATION (plot, chart, graph): You MUST call 'sql_query_tool' first. Pass the resulting raw JSON 'data' object directly into 'generate_visualization_tool'.
    - If data is empty, do not call the visualization tool; explain why data might be missing.

    PROTOCOL 5: PROFILE UPDATES
    - Use 'update_customer_tool' or 'update_employee_profile_tool'.
    - Ensure bank names are present before updating account details.

    PROTOCOL 6: LEAVE STATUS
    - Use 'fetch_leave_status_tool' for status checks.

    ### CONTEXT:
    - Current Date: {current_date_str}
    - Employee ID: {ID}
    - Tool Guide: {tool_intent_map}

    ### OUTPUT FORMAT:
    Return ONLY a valid JSON object in the 'answer' field. 
    {
      "answer": "Your natural language response here"
    }
    NEVER output raw JSON, internal tool details, tool call IDs, or base64 strings in the 'answer' field.
"""

GLOBAL_FINAL_ANSWER_PROMPT = """
    You are Theresa, the AI-powered virtual assistant for VectraPay / Gatik.
    Your role is to deliver professional customer service, banking services,
    HR support, and insightful data analysis.

    ═══════════════════════════════════════════════════════════════════════
    NEW USER ENGAGEMENT
    ═══════════════════════════════════════════════════════════════════════
    If the user is starting a new conversation, introduce yourself briefly:
    "Hello! I am Theresa, your VectraPay virtual assistant. I can help you with:
      • 🏦 Banking    – account opening, transfers, airtime, bills, balance enquiry, PIN & password management
      • 💰 Loans      – eligibility checks, loan applications, repayment information
      • 🧑‍💼 HR Support – leave applications, payslips, workplace policy guidance
      • 📊 Analytics  – transaction reports, trends, data visualizations"

    ═══════════════════════════════════════════════════════════════════════
    OPERATING MODES
    ═══════════════════════════════════════════════════════════════════════
    1. Banking Assistant  – guide customers through financial transactions securely.
    2. Loan Officer       – evaluate eligibility and process loan applications.
    3. Customer Support   – resolve issues with empathy and clarity.
    4. Data Analyst       – interpret data, explain trends, create visualizations.
    5. HR Assistant       – handle leave and payslips with privacy and clarity.

    ═══════════════════════════════════════════════════════════════════════
    GLOBAL SECURITY RULES  (apply to every interaction)
    ═══════════════════════════════════════════════════════════════════════
    - Currency: Always use the Naira sign (₦).
    - Do not hallucinate. If unsure, use a tool or say you don't have the info.
    - NEVER expose internal API parameters (billerId, divisionId, productId,
      paymentCode, SHA-512 signatures, token UUIDs) to the customer.
    - NEVER display, echo, or repeat a customer's PIN or password.
    - NEVER skip a confirmation step before any financial transaction.
    - After 5 consecutive wrong PINs, direct customer to 'Forgot PIN'.
    - After 5 consecutive wrong passwords, direct customer to 'Forgot Password'.
    - ALL banking service requests (except account opening) MUST begin with
      Protocol B0 (password authentication). Do not proceed without it.

    ═══════════════════════════════════════════════════════════════════════
    BANKING PROTOCOLS  (B0 – B10)
    ═══════════════════════════════════════════════════════════════════════

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B0 – CUSTOMER SECURE AUTHENTICATION
    ────────────────────────────────────────────────────────────────────────
    You DO NOT ask for passwords or PINs inside the chat anymore! All authentication
    is handled by our secure external web pages.
    Whenever a customer requests a banking transaction (balance enquiry, transfer, 
    airtime, bill payment), IMMEDIATELY CALL the corresponding tool for that service 
    (e.g., balance_enquiry_tool, transfer_money_tool) without asking for a password.

    If the customer is not authenticated, the tool will automatically return a 
    secure login URL (or setup URL if they have no password). You must display 
    the exact response provided by the tool to the user so they can click the link.

    NEVER invent your own authentication flow here or ask for a PIN/password.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B1 – ACCOUNT OPENING
    ────────────────────────────────────────────────────────────────────────
    - Collect: first name, last name, email, phone number, gender,
               date of birth (YYYY-MM-DD), NIN (11 digits),
               occupation, nationality (default: Nigeria).
    - Call 'create_customer_profile_tool'.
    - On success the tool returns:
        • VFD account number and account name.
        • A single-use password-creation link (valid 24 hours).
    - Display to customer:
        "🎉 Your account has been created!
         Account Number: [account_number] | Bank: VFD Microfinance Bank
         Please create your secure banking password using this secure link: [link]
         The link expires in 24 hours and can only be used once.
         Return to WhatsApp after creating your password to start banking."

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B2 – FUND WALLET
    ────────────────────────────────────────────────────────────────────────
    [Requires B0 first]
    - No PIN required. Call 'fund_wallet_info_tool' with customer's phone number.
    - Display: account number, bank name (VFD Bank), account name, and available
      funding channels (mobile app, USSD, bank transfer, POS/ATM).

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B3 – BALANCE ENQUIRY
    ────────────────────────────────────────────────────────────────────────
    - Call 'balance_enquiry_tool'. If you are asked to auth, display the link! 
    - Otherwise, display the balance.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B4 – AIRTIME PURCHASE
    ────────────────────────────────────────────────────────────────────────
    [Requires B0 first]
    Step 1 – Ask: "Is this for yourself or a third party?"
    Step 2 – Collect: network (MTN / Airtel / Glo / 9mobile) and amount.
             If third party: also collect beneficiary phone number.
    Step 3 – Show a confirmation summary before calling 'buy_airtime_tool'.
    Step 4 – Call 'buy_airtime_tool' and display the result.
    NOTE: Never ask for billerId or paymentCode — the tool resolves these.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B5 – BILLS PAYMENT  (INTELLIGENT FLOW)
    ────────────────────────────────────────────────────────────────────────
    [Requires B0 first]
    - Customer provides ONLY: biller name, amount, and reference number.
    - Reference label by biller type:
        Electricity (utility)  → "Meter Number"
        Cable TV (DSTV/GOTV)   → "Smart Card Number"
        Airtime / Data         → "Phone Number"
        Internet Subscription  → "Account Number / Username"
        Other                  → "Reference Number"
    - Before asking for details, call 'get_saved_billers_tool'.
      If saved billers exist, show list and offer quick-pay option.
    - Show a confirmation summary (including convenience fee) before paying.
    - Call 'pay_bill_tool'. Never mention billerId, divisionId, productId.
    - After a successful payment, inform the customer the biller is saved.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B6 – TRANSFER MONEY
    ────────────────────────────────────────────────────────────────────────
    Step 1 – Collect beneficiary bank (call 'get_bank_list_tool' if needed).
    Step 2 – Collect beneficiary account number.
    Step 3 – Call 'get_beneficiary_name_tool' → show account name for confirmation.
    Step 4 – Collect amount and optional narration.
    Step 5 – Call 'transfer_money_tool' and display the result (which might be an auth link).
    ERRORS:
      "Account Not Found"     → "We couldn't find that account. Please check and retry."
      "Internal Server Error" → "Something went wrong. Please try again shortly."

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B7 – CHANGE PIN
    ────────────────────────────────────────────────────────────────────────
    [Requires B0 first]
    - Collect old PIN, new PIN, confirm new PIN.
    - Call 'change_pin_tool'. Confirm success. Never reveal any PIN.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B8 – FORGOT PIN
    ────────────────────────────────────────────────────────────────────────
    [Does NOT require B0 — customer may be locked out]
    - Collect the customer's NIN.
    - Inform the customer a liveness check will be performed.
    - Once confirmed ready, call 'forgot_pin_tool' with NIN, new PIN, confirm PIN.
    - If liveness fails: advise the customer to retry in a well-lit area
      or contact support.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B9 – FORGOT PASSWORD  (3-Step OTP Flow)
    ────────────────────────────────────────────────────────────────────────
    [Does NOT require B0 — customer may be locked out]

    ⚠️ STRICT SEQUENCE — do not skip or reorder steps.

    STEP 1 – Initiate
      - Call 'initiate_password_reset_tool' with the customer's phone number.
      - The tool returns a message informing the customer that:
          • An OTP will be sent to their registered number.
          • A fee of ₦10 will be debited from their account.
          • The OTP is valid for only 10 seconds.
      - Present this message EXACTLY as returned by the tool ( phone,
        amount, expiry). Ask the customer to reply YES or NO.

    STEP 2 – Confirm & Send OTP
      - Only call 'confirm_password_reset_tool' after the customer replies YES.
      - Pass customer_confirmed=True.
      - If customer replies NO → cancel and inform: "Password reset cancelled.
        Your account remains unchanged."
      - If the tool reports an insufficient balance error: tell the customer to
        fund their account and try again.
      - On success: the tool sends the OTP via SMS. Prompt the customer to enter
        the 6-digit OTP immediately — it expires in 10 seconds.

    STEP 3 – Verify OTP & Issue Link
      - Call 'verify_otp_and_issue_link_tool' with the phone number and OTP.
      - On success: the tool returns a single-use password-reset link.
        Display: "✅ OTP verified! Create your new password using this secure
        link (valid 24 hours, single-use): [link]
        Return here once your password is set."
      - On failure ("expired" / "already used"): inform the customer and offer
        to restart from Step 1. Remind them the OTP window is only 10 seconds.

    ────────────────────────────────────────────────────────────────────────
    PROTOCOL B10 – LOAN SERVICES
    ────────────────────────────────────────────────────────────────────────
    [Requires B0 first]

    SUB-PROTOCOL L1 – LOAN ELIGIBILITY EVALUATION
      Step 1 – Ask the customer to provide their social media profile URLs
               (Facebook, LinkedIn, Instagram, Twitter/X, TikTok).
               Make clear these are optional but improve the evaluation.
      Step 2 – For each URL provided, call 'validate_social_media_tool'.
               • On validation failure: show the specific error returned by
                 the tool and ask the customer to correct or skip that platform.
               • Never accept a URL that the tool has rejected.
               • Only proceed once all submitted URLs have passed validation.
      Step 3 – Call 'evaluate_loan_eligibility_tool' with all validated URLs.
      Step 4 – Present the result:
               • Score, band (Excellent / Good / Fair / Poor), and notes.
               • If score ≤ 70: inform the customer they do not yet qualify and
                 share the improvement tips returned by the tool.
               • If score > 70: inform the customer they are eligible and ask
                 if they would like to apply for a loan now.
      NOTE: If stored data is < 180 days old the tool returns cached results.
            Inform the customer when cached results are being used and how
            many days remain before re-evaluation is required.

    SUB-PROTOCOL L2 – LOAN APPLICATION
      Step 1 – Confirm the customer's eligibility score is > 70 (run L1 if not done).
      Step 2 – Collect: loan amount (₦) and tenor (number of months).
      Step 3 – Call 'apply_for_loan_tool'.
      Step 4 – Evaluate the response:
        a) SUCCESS → display the full loan breakdown:
             Principal, monthly interest rate, monthly interest amount,
             monthly repayment, tenor, total amount due, processing fee,
             late payment fee.
           Inform the customer: "Please review your loan offer in full on the
           link provided and confirm with your banking password to receive
           disbursement."
        b) AMOUNT EXCEEDS LIMIT → the tool returns the customer's maximum
             limit plus a repayment illustration for that limit.
             Ask: "Would you like to apply for [limit] instead?"
        c) OUTSTANDING BALANCE → inform: "You currently have an outstanding
             loan balance of ₦[balance]. Please clear it before applying."
        d) SCORE TOO LOW → redirect to L1 for a fresh evaluation.
      Step 5 – Remind the customer: timely repayments improve their credit
               rating and unlock higher loan tiers (Silver, Gold).

    ═══════════════════════════════════════════════════════════════════════
    HR & DATA PROTOCOLS  (Protocols 1 – 6)  — unchanged
    ═══════════════════════════════════════════════════════════════════════

    PROTOCOL 1 – LEAVE REQUESTS
    - First call 'fetch_available_leave_types_tool'.
    - Invalid type → inform, re-list, do NOT call 'prepare_leave_application_tool'.
    - Ask: "Is this leave for {current_year} or your {previous_year} carry-over?"
    - After submission of Vacation leave → offer travel via 'search_travel_deals_tool'.

    PROTOCOL 2 – PAYSLIPS
    - After 'get_payslip_tool': inform the user their payslip has been sent to email.

    PROTOCOL 3 – HR POLICIES & KNOWLEDGE
    - Use 'pdf_retrieval_tool' to search HR handbooks.

    PROTOCOL 4 – DATA ANALYTICS AND VISUALIZATION
    - Pass natural language questions to 'sql_query_tool'. NEVER write SQL yourself.
    - For charts/plots: call 'sql_query_tool' first, then 'generate_visualization_tool'.
      Skip visualization if data is empty.

    PROTOCOL 5 – PROFILE UPDATES
    - Use 'update_customer_tool' or 'update_employee_profile_tool'.
    - Require bank name before updating account details.

    PROTOCOL 6 – LEAVE STATUS
    - Use 'fetch_leave_status_tool' for approval and pending status.

    ═══════════════════════════════════════════════════════════════════════
    CALL TO ACTION (POST-TASK ENGAGEMENT)
    ═══════════════════════════════════════════════════════════════════════
    After completing any major flow or when a user finishes inputting required
    information for an operation (e.g. account setup, password creation, loan
    inputs), you MUST proactively engage them with a contextual Call To Action.
    
    Examples:
    - If they just finished Account Opening: "Now that your account is ready, would you like to check your balance, transfer funds, or buy airtime?"
    - If they just checked their loan Eligibility: "Would you like me to guide you through submitting a loan application now, or would you prefer to explore our loan calculation tools?"
    - If they completed their HR setup/login: "Can I assist you in checking your leave balance or getting a copy of your recent payslip?"

    ═══════════════════════════════════════════════════════════════════════
    CONTEXT
    ═══════════════════════════════════════════════════════════════════════
    - Current Date : {current_date_str}
    - Employee ID  : {ID}
    - Tool Guide   : {tool_intent_map}

    ═══════════════════════════════════════════════════════════════════════
    OUTPUT FORMAT
    ═══════════════════════════════════════════════════════════════════════
    Return ONLY a valid JSON object.
    {{
      "answer": "Your natural language response here"
    }}
    NEVER output raw JSON, internal tool details, tool call IDs, base64 strings,
    API parameters (billerId, divisionId, paymentCode, token UUIDs), customer
    PINs, or passwords in the 'answer' field.
"""


golden_rules = (
    "\n\nSTRICT OPERATING RULES:\n"
    "1. AUTHENTICATION GATE: ALWAYS call the requested banking service tool directly without asking for passwords. "
    "   If the customer needs to authenticate, the tool itself will return a secure link.\n"
    "2. FINAL RESPONSE: ALWAYS provide your final response to the user in "
    "   natural, friendly, and professional language within the JSON 'answer' field.\n"
    "3. NO SYSTEM LEAKAGE: NEVER output raw JSON, tool call IDs, token UUIDs, "
    "   or internal structural artifacts to the user's view.\n"
    "4. NATIVE TOOL CALLING: Adhere to protocols by calling tools natively. "
    "   Do not simulate a tool call by writing JSON text. Only provide the "
    "   JSON 'answer' block once you have the tool result you need.\n"
    "5. TOOL-FIRST: If you need a tool, execute the tool call immediately. "
    "   Do not provide a final JSON response until the tool has returned its result.\n"
    "6. NO BASE64 IN TEXT: NEVER include base64-encoded image data or "
    "   'data:image/...' strings in the 'answer' field.\n"
    "7. OTP URGENCY: When waiting for an OTP (Protocol B9 Step 3), remind "
    "   the customer the code expires in 10 seconds. Do not delay.\n"
    "8. LOAN SEQUENCE: Never call 'apply_for_loan_tool' without first confirming "
    "   the customer has a loan_eligibility_score > 70 from 'evaluate_loan_eligibility_tool'.\n"
    "9. SOCIAL MEDIA VALIDATION: Never pass an unvalidated social media URL to "
    "   'evaluate_loan_eligibility_tool'. Every URL must first pass "
    "   'validate_social_media_tool'.\n"
    "10. PASSWORD MASKING: Never repeat, display, or confirm any password or PIN "
    "    entered by the customer."
)


tool_guide = {
    # ── BANKING SERVICES ─────────────────────────────────────────────────────
    "account_opening": {
        "tools": ["create_customer_profile_tool"],
        "triggers": [
            "open account", "create account", "new account", "register",
            "sign up", "onboard", "account opening", "get an account",
        ],
        "note": "B0 authentication NOT required for this step.",
    },
    "fund_wallet": {
        "tools": ["fund_wallet_info_tool"],
        "triggers": [
            "fund wallet", "top up", "deposit", "add money",
            "fund my account", "how to fund", "bank details",
        ],
    },
    "balance_enquiry": {
        "tools": ["balance_enquiry_tool"],
        "triggers": [
            "balance", "check balance", "account balance",
            "how much do i have", "wallet balance",
        ],
    },
    "airtime_purchase": {
        "tools": ["buy_airtime_tool"],
        "triggers": [
            "airtime", "buy airtime", "recharge", "top up phone", "data",
            "mtn", "airtel", "glo", "9mobile", "etisalat",
        ],
    },
    "bills_payment": {
        "tools": [
            "pay_bill_tool",
            "get_saved_billers_tool",
            "delete_saved_biller_tool",
        ],
        "triggers": [
            "pay bill", "bills", "electricity", "dstv", "gotv", "startimes",
            "cable tv", "nepa", "ekedc", "ikedc", "meter", "smart card",
            "internet subscription", "betting", "waec",
        ],
    },
    "money_transfer": {
        "tools": [
            "transfer_money_tool",
            "get_beneficiary_name_tool",
            "get_bank_list_tool",
        ],
        "triggers": [
            "transfer", "send money", "wire", "pay someone", "bank transfer",
            "inter-bank", "intra-bank", "beneficiary",
        ],
    },
    "change_pin": {
        "tools": ["change_pin_tool"],
        "triggers": [
            "change pin", "update pin", "new pin", "change my pin", "update my pin",
        ],
    },
    "forgot_pin": {
        "tools": ["forgot_pin_tool"],
        "triggers": [
            "forgot pin", "lost pin", "can't remember pin",
            "recover pin", "reset pin", "liveness", "nin verification",
        ],
        "note": "B0 authentication NOT required — customer may be locked out.",
    },
    # ── PASSWORD MANAGEMENT ───────────────────────────────────────────────────
    "forgot_password": {
        "tools": [
            "initiate_password_reset_tool",
            "confirm_password_reset_tool",
            "verify_otp_and_issue_link_tool",
        ],
        "triggers": [
            "forgot password", "reset password", "lost password",
            "can't login", "locked out", "password reset",
            "otp", "one time password", "sms code",
        ],
        "note": (
            "3-step flow: initiate → confirm (₦10 debit + OTP) → verify OTP → issue link. "
            "OTP expires in 10 seconds. B0 NOT required."
        ),
    },
    # ── LOAN SERVICES ─────────────────────────────────────────────────────────
    "loan_eligibility": {
        "tools": [
            "validate_social_media_tool",
            "evaluate_loan_eligibility_tool",
        ],
        "triggers": [
            "loan eligibility", "can i get a loan", "check eligibility",
            "credit check", "credit score", "social media check",
            "qualify for loan", "am i eligible",
        ],
        "note": (
            "Social media URLs must pass 'validate_social_media_tool' before "
            "being passed to 'evaluate_loan_eligibility_tool'. "
            "Cached results used if < 180 days old."
        ),
    },
    "loan_application": {
        "tools": ["apply_for_loan_tool"],
        "triggers": [
            "apply for loan", "get a loan", "borrow money", "take a loan",
            "loan application", "request loan", "need a loan",
            "how much can i borrow",
        ],
        "note": (
            "Requires eligibility score > 70. "
            "Default tier is Bronze. "
            "Loan amount must not exceed customer loan limit. "
            "Customer must have zero outstanding loan balance."
        ),
    },
    "social_media_validation": {
        "tools": ["validate_social_media_tool"],
        "triggers": [
            "validate url", "check profile", "verify social media",
            "facebook link", "linkedin link", "instagram link",
            "twitter link", "tiktok link",
        ],
        "note": "Can also be called standalone if a customer wants to check a URL.",
    },
    # ── HR & ANALYTICS ────────────────────────────────────────────────────────
    "leave_management": {
        "tools": [
            "fetch_available_leave_types_tool",
            "prepare_leave_application_tool",
            "submit_leave_application_tool",
            "fetch_leave_status_tool",
            "calculate_num_of_days_tool",
        ],
        "triggers": [
            "leave", "vacation", "sick leave", "day off", "approve",
            "leave balance", "resumption",
        ],
    },
    "payslip_services": {
        "tools": ["get_payslip_tool"],
        "triggers": ["payslip", "salary", "pay statement", "earnings", "payroll"],
    },
    "hr_policy": {
        "tools": ["pdf_retrieval_tool"],
        "triggers": ["policy", "handbook", "benefits", "hr guide", "rules"],
    },
    "data_visualization": {
        "tools": ["sql_query_tool", "generate_visualization_tool"],
        "triggers": [
            "plot", "chart", "graph", "visualize", "show as a bar chart",
            "report", "count", "average", "total", "statistics", "data",
        ],
    },
    "profile_updates": {
        "tools": [
            "update_employee_profile_tool",
            "create_customer_profile_tool",
            "get_customer_details_tool",
        ],
        "triggers": ["update", "profile", "phone number", "bank account", "details"],
    },
    "recruitment": {
        "tools": ["search_job_opportunities_tool"],
        "triggers": ["job", "vacancy", "career", "hiring", "position"],
    },
    "travel_concierge": {
        "tools": ["search_travel_deals_tool"],
        "triggers": ["flight", "hotel", "travel", "booking", "trip"],
    },
    "general_inquiry": {
        "tools": ["web_search_tool"],
        "triggers": ["what is", "how to", "who is", "search"],
    },
}



current_year = datetime.now().year
previous_year = current_year - 1
current_date_str = datetime.now().strftime("%Y-%m-%d")

# DEFAULT_TOOL_INTENT_MAP = {
#     "leave_management": {"tools": ["fetch_available_leave_types_tool", "prepare_leave_application_tool"], "triggers": ["leave", "vacation"]},
#     "data_analysis": {"tools": ["sql_query_tool"], "triggers": ["report", "count", "average"]},
#     "visualization": {"tools": ["generate_visualization_tool"], "triggers": ["plot", "chart", "graph"]}
# }



# DEFAULT_FINAL_ANSWER_PROMPT = """You are Damilola, the AI-powered virtual assistant. Deliver professional customer service and insightful data analysis."""

DEFAULT_EMPLOYEE_ID = "obinna.kelechi.adewale@dignityconcept.tech"

embeddings = None

def get_embeddings():
    global embeddings
    if embeddings is None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("❌ GEMINI_API_KEY or GOOGLE_API_KEY not found in environment.")
            raise ValueError("No API key found for embeddings. Set GEMINI_API_KEY or GOOGLE_API_KEY.")
        
        try:
            # Fixing lint error: some versions use 'api_key', others 'google_api_key'. 
            # Trying to be compatible or letting it fall back to environment.
            embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001") 
            logger.info("✅ Embeddings model initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Embeddings: {e}")
            raise
    return embeddings



 

def ingest_pdf_for_tenant(tenant_id: str, file_path: str):
    """
    Load a PDF, split into chunks, create a FAISS index.
    If an index already exists for the tenant, it is removed and replaced.
    """
    tenant_id = str(tenant_id)
    persist_directory = os.path.join("faiss_dbs", tenant_id)
    
    logger.info(f"[VectorStore | Tenant: {tenant_id}] Starting ingestion for {file_path}")
    
    try:
        # 1. Clean up existing index (Remove and Ingest logic)
        if os.path.exists(persist_directory):
            logger.info(f"[VectorStore | Tenant: {tenant_id}] Existing index found. Removing {persist_directory}...")
            shutil.rmtree(persist_directory)
        
        # 2. Path Validation
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at: {file_path}")
            
        # 3. Load PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Loaded {len(documents)} pages.")
        
        # 4. Split
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Split into {len(chunks)} chunks.")
        
        # 5. Embed and Create FAISS
        emb = get_embeddings()
        vector_store = FAISS.from_documents(chunks, emb)
        
        # 6. Save to Disk (Fresh directory)
        os.makedirs(persist_directory, exist_ok=True)
        vector_store.save_local(persist_directory)
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Successfully replaced index at {persist_directory}")
        
        return {"status": "success", "chunk_count": len(chunks), "path": persist_directory}
        
    except Exception as e:
        logger.error(f"[VectorStore | Tenant: {tenant_id}] Ingestion failed: {e}")
        return {"status": "error", "message": str(e)}

def ingest_pdf_for_tenantv1(tenant_id: str, file_path: str):
    """
    Load a PDF, split into chunks, create a FAISS index, and save to disk.
    """
    tenant_id = str(tenant_id)
    persist_directory = os.path.join("faiss_dbs", tenant_id)
    
    logger.info(f"[VectorStore | Tenant: {tenant_id}] Starting ingestion for {file_path}")
    
    try:
        # 1. Load PDF
        abs_path = os.path.abspath(file_path)
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Checking path: {file_path} (Absolute: {abs_path})")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at: {file_path}")
            
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Loaded {len(documents)} pages.")
        
        # 2. Split
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Split into {len(chunks)} chunks.")
        
        # 3. Embed and Create FAISS
        emb = get_embeddings()
        vector_store = FAISS.from_documents(chunks, emb)
        
        # 4. Save to Disk
        os.makedirs(persist_directory, exist_ok=True)
        vector_store.save_local(persist_directory)
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Saved index to {persist_directory}")
        
        return {"status": "success", "chunk_count": len(chunks), "path": persist_directory}
        
    except Exception as e:
        logger.error(f"[VectorStore | Tenant: {tenant_id}] Ingestion failed: {e}")
        return {"status": "error", "message": str(e)}


def initialize_vector_store(tenant_id: str):
    """
    Fetch and return a FAISS vector store for the given tenant.
    Loads ONLY from disk cache (faiss_dbs/<tenant_id>/).
    """
    tenant_id = str(tenant_id)
    persist_directory = os.path.join("faiss_dbs", tenant_id)

    logger.info(f"[VectorStore | Tenant: {tenant_id}] Initializing from disk (read-only).")

    # --- Step 1: Embeddings ---
    try:
        emb = get_embeddings()
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Embeddings ready.")
    except Exception as e:
        logger.error(f"[VectorStore | Tenant: {tenant_id}] Embeddings init failed: {e}")
        return None, {"status": "error", "message": f"Embeddings init failed: {e}"}

    # --- Step 2: Try to load from disk cache ---
    try:
        if not os.path.exists(persist_directory):
            raise FileNotFoundError(f"Directory {persist_directory} does not exist.")
            
        vector_store = FAISS.load_local(persist_directory, emb, allow_dangerous_deserialization=True)
        doc_count = vector_store.index.ntotal if hasattr(vector_store, "index") else "unknown"
        logger.info(f"[VectorStore | Tenant: {tenant_id}] Loaded successfully. index_size={doc_count}")
        return vector_store, {"status": "success", "source": "disk", "doc_count": doc_count}
    except FileNotFoundError:
        logger.warning(
            f"[VectorStore | Tenant: {tenant_id}] No disk index found at {persist_directory}. "
            "Use /load_pdf to ingest documents for this tenant."
        )
    except Exception as e:
        logger.error(f"[VectorStore | Tenant: {tenant_id}] Failed to load local index: {e}")

    return None, {"status": "not_found", "message": "No vector store index found on disk."}


# Model/Service Name Variables - Moved to llm_handler.py
# OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
_llm = None


GLOBAL_SCOPE = "GLOBAL"
NO_CONVO = "N/A"
def should_continue(state: State) -> Literal["tool_node", "__end__"]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    if state is None:
        return END
    tenant_config = state.get("tenant_config", {}) or {}
    tenant_id = tenant_config.get("tenant_id", "unknown")
    conversation_id = state.get("conversation_id", "unknown")
    log_info("Evaluating whether to continue or stop.", tenant_id, conversation_id)

    messages = state.get("messages", [])
    if not messages:
        return END
    # last_message = messages[-1]
    # FIX: Find the last AIMessage specifically
    last_message = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)), None
    )
    log_debug(f"Last LLM message: {last_message}", tenant_id, conversation_id)

    if last_message and getattr(last_message, "tool_calls", None):
        log_info(f"LLM made tool calls: {[tc.get('name', 'unknown') for tc in last_message.tool_calls]}. Continuing to tool node.", tenant_id, conversation_id)
        return "tool_node"
    
    if last_message and "parsed_json" in last_message.additional_kwargs:
        parsed = last_message.additional_kwargs["parsed_json"]
    else:
        # Try parsing from content if missing
        
        try:
            if last_message:
                content_str = last_message.content if isinstance(last_message.content, str) else str(getattr(last_message, "content", ""))
                parsed = json.loads(content_str)
            else:
                parsed = {}
        except:
            parsed = {}

    tool_name = parsed.get("tool", "none")
    if not last_message or str(tool_name).lower() == "none" or not tool_name:
        log_info("LLM requested 'none' or no valid tool. Ending workflow.", tenant_id, conversation_id)
        return END

    log_info(
        f"LLM requested tool: {tool_name}. Continuing to tool node.", tenant_id, conversation_id
    )
    return "tool_node"

# Graph Nodes
def tool_node29032026(state: State) -> dict:
    # Use the 'tools' list imported from tools.py
    from tools import tools as tool_list
    tools_by_name = {t.name: t for t in tool_list}
    
    tenant_config = state.get("tenant_config", {})
    tenant_id = tenant_config.get("tenant_id", "unknown")
    conversation_id = state.get("conversation_id", "unknown")
    
    log_info("Entered tool_node for execution.", tenant_id, conversation_id)
    
    try:
        last_ai_message = state["messages"][-1]
        tool_calls = getattr(last_ai_message, "tool_calls", [])
        log_debug(f"Tool calls to execute: {tool_calls}", tenant_id, conversation_id)
        
        if not tool_calls:
            return {"messages": []}

        new_messages = []
        state_updates = {}
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            
            # Handle nested 'arguments' key if present (LLM sometimes wraps args)
            if "arguments" in tool_args:
                tool_args = tool_args["arguments"]
            
            # Inject context
            tool_args["state"] = {k: v for k, v in state.items() if k != "messages"}
            
            tool = tools_by_name.get(tool_name)
            if not tool:
                log_error(f"Tool {tool_name} not found in {list(tools_by_name.keys())}", tenant_id, conversation_id)
                new_messages.append(ToolMessage(
                    content=f"Error: Tool {tool_name} not found.",
                    tool_call_id=tool_call.get("id"),
                    name=tool_name
                ))
                continue

            # Execution
            observation = tool.invoke(tool_args)
            
            # State Update Logic
            if tool_name == "pdf_retrieval_tool":
                state_updates["pdf_content"] = observation.get("pdf_content")
            
            if tool_name == "generate_visualization_tool":
                if isinstance(observation, dict) and "visualization_result" in observation:
                    viz_result = observation["visualization_result"]
                    state_updates["visualization_image"] = viz_result.get("image_base64")
                    state_updates["visualization_analysis"] = viz_result.get("analysis")
            
            new_messages.append(ToolMessage(
                content=json.dumps(observation) if isinstance(observation, dict) else str(observation),
                tool_call_id=tool_call.get("id"),
                name=tool_name
            ))
            
        log_info(f"Tool node executed successfully.", tenant_id, conversation_id)
        return {"messages": new_messages, **state_updates}

    except Exception as e:
        log_error(f"Critical failure in tool_node: {str(e)}", tenant_id, conversation_id)
       
        log_error(traceback.format_exc(), tenant_id, conversation_id)
        return {"messages": [ToolMessage(content=f"Error executing tool: {e}", tool_call_id="error", name="error_handler")]}
# Graph Nodes
def tool_node(state: State) -> dict:
    # Combine base tools + banking tools into a single lookup
    from tools import tools as base_tools
    from banking_tools import banking_tools as b_tools
    all_tools = list(base_tools) + list(b_tools)
    tools_by_name = {t.name: t for t in all_tools}
    
    tenant_config = state.get("tenant_config", {})
    tenant_id = tenant_config.get("tenant_id", "unknown")
    conversation_id = state.get("conversation_id", "unknown")
    
    log_info("Entered tool_node for execution.", tenant_id, conversation_id)
    
    try:
        last_ai_message = state["messages"][-1]
        tool_calls = getattr(last_ai_message, "tool_calls", [])
        log_debug(f"Tool calls to execute: {tool_calls}", tenant_id, conversation_id)
        
        if not tool_calls:
            return {"messages": []}

        new_messages = []
        state_updates = {}
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            
            # Handle nested 'arguments' key if present (LLM sometimes wraps args)
            if "arguments" in tool_args:
                tool_args = tool_args["arguments"]
            
            # Inject context
            tool_args["state"] = {k: v for k, v in state.items() if k != "messages"}
            
            tool = tools_by_name.get(tool_name)
            if not tool:
                log_error(f"Tool {tool_name} not found in {list(tools_by_name.keys())}", tenant_id, conversation_id)
                new_messages.append(ToolMessage(
                    content=f"Error: Tool {tool_name} not found.",
                    tool_call_id=tool_call.get("id"),
                    name=tool_name
                ))
                continue

            # Execution
            observation = tool.invoke(tool_args)
            
            # State Update Logic
            if tool_name == "pdf_retrieval_tool":
                state_updates["pdf_content"] = observation.get("pdf_content")
            
            if tool_name == "generate_visualization_tool":
                if isinstance(observation, dict) and "visualization_result" in observation:
                    viz_result = observation["visualization_result"]
                    state_updates["visualization_image"] = viz_result.get("image_base64")
                    state_updates["visualization_analysis"] = viz_result.get("analysis")
            
            new_messages.append(ToolMessage(
                content=json.dumps(observation) if isinstance(observation, dict) else str(observation),
                tool_call_id=tool_call.get("id"),
                name=tool_name
            ))
            
        log_info(f"Tool node executed successfully.", tenant_id, conversation_id)
        return {"messages": new_messages, **state_updates}

    except Exception as e:
        log_error(f"Critical failure in tool_node: {str(e)}", tenant_id, conversation_id)
       
        log_error(traceback.format_exc(), tenant_id, conversation_id)
        return {"messages": [ToolMessage(content=f"Error executing tool: {e}", tool_call_id="error", name="error_handler")]}


def extract_final_answer(response):
    """
    Robustly extract the final text answer from an LLM response or structured object.
    """
    try:
        # Case 1: Structured Answer or dict
        if isinstance(response, dict):
            return response.get("answer") or json.dumps(response)
        
        # Case 2: AIMessage or object with .content
        if hasattr(response, "content") and response.content:
            content = response.content
        else:
            # Fallback if content is empty or response is not a message object
            if hasattr(response, "tool_calls") and response.tool_calls:
                return "Executing tools..."
            content = str(response) if response is not None else "LLM did not return a response"

        # Clean up markdown and extract JSON blocks if present
        content_clean = re.sub(r"^```json\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
        
        # Try direct parse
        try:
            parsed = json.loads(content_clean)
            if isinstance(parsed, dict) and "answer" in parsed:
                return parsed["answer"]
        except json.JSONDecodeError:
            pass

        # Try matching the largest possible JSON object first (greedy)
        greedy_match = re.search(r"(\{.*\})", content_clean, re.DOTALL)
        if greedy_match:
            try:
                obj = json.loads(greedy_match.group(1))
                if isinstance(obj, dict) and "answer" in obj:
                    return obj["answer"]
            except json.JSONDecodeError:
                pass

        # Try searching for JSON-like blocks as a fallback (non-greedy)
        json_blocks = re.findall(r"(\{.*?\})", content_clean, flags=re.DOTALL)
        for block in json_blocks:
            try:
                obj = json.loads(block)
                if isinstance(obj, dict) and "answer" in obj:
                    return obj["answer"]
            except json.JSONDecodeError:
                continue

        return content_clean or "LLM returned empty response"
    except Exception as e:
        logger.error(f"Error in extract_final_answer: {e}")
        return "Error extracting answer"

def clean_message_history(messages):
    """
    Strips additional_kwargs and serialized state from messages 
    to prevent LLM confusion and circular reference errors.
    """
    cleaned = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            # Keep only the content and tool_calls, discard the state-heavy additional_kwargs
            cleaned.append(AIMessage(
                content=msg.content, 
                tool_calls=msg.tool_calls
            ))
        elif isinstance(msg, ToolMessage):
            # Keep only the tool result
            cleaned.append(ToolMessage(
                content=msg.content, 
                tool_call_id=msg.tool_call_id, 
                name=msg.name
            ))
        else:
            # HumanMessage and SystemMessage are usually safe
            cleaned.append(msg)
    return cleaned

def normalize_tool_calls(response):
    logger.info("Starting normalization of tool calls.")
    
    # 1. Check if tool calls already exist
    if hasattr(response, "tool_calls") and response.tool_calls:
        logger.info("Tool calls already present in response.")
        return response

    if not isinstance(response.content, str):
        logger.info("Response content is not a string, skipping.")
        return response

    content = response.content.strip()
    if not content:
        logger.info("Response content is empty.")
        return response

    tool_calls = []
    decoder = json.JSONDecoder()
    pos = 0
    
    # 2. Iterate through content to find and parse multiple JSON objects
    # Attempt a regex extraction first to handle common LLM formatting issues like trailing quotes
   
    # Match everything between the first '{' and last '}'
    match = re.search(r"(\{.*\})", content, re.DOTALL)
    if match:
        content = match.group(1)

    while pos < len(content):
        try:
            # Find the next potential JSON object
            pos = content.find('{', pos)
            if pos == -1:
                break
            
            obj, index = decoder.raw_decode(content[pos:])
            pos += index
            
            # Check if this object is a tool call
            if isinstance(obj, dict) and ("tool" in obj or "name" in obj):
                logger.info(f"Successfully extracted tool call: {obj.get('tool') or obj.get('name')}")
                
                # Extract args, falling back to all other keys if not explicitly nested
                extracted_args = obj.get("parameters") or obj.get("args")
                if not extracted_args or not isinstance(extracted_args, dict):
                    extracted_args = {k: v for k, v in obj.items() if k not in ("tool", "name")}
                elif not extracted_args:
                    extracted_args = {}

                tool_calls.append({
                    "name": obj.get("tool") or obj.get("name"),
                    "args": extracted_args,
                    "id": f"call_{uuid.uuid4().hex[:12]}",
                    "type": "tool_call"
                })
            elif isinstance(obj, dict) and "visualization" in obj and isinstance(obj["visualization"], dict):
                 viz = obj["visualization"]
                 v_name = viz.get("tool") or viz.get("name")
                 if v_name:
                    logger.info(f"Successfully extracted tool call from visualization key: {v_name}")
                    v_args = viz.get("tool_input") or viz.get("args") or viz.get("parameters")
                    if not v_args or not isinstance(v_args, dict):
                        v_args = {k: v for k, v in viz.items() if k not in ("tool", "name")}
                    
                    tool_calls.append({
                        "name": v_name,
                        "args": v_args,
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "type": "tool_call"
                    })
            elif isinstance(obj, dict) and "tool_call" in obj and isinstance(obj["tool_call"], dict):
                logger.info(f"Successfully extracted tool_call: {obj['tool_call'].get('name')}")
                tc = obj["tool_call"]
                args = tc.get("arguments") or tc.get("args", {})
                tool_calls.append({
                    "name": tc["name"],
                    "args": args,
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                    "type": tc.get("type", "tool_call")
                })
            elif isinstance(obj, dict) and "tool_calls" in obj and isinstance(obj["tool_calls"], list):
                logger.info(f"Successfully extracted tool_calls array with {len(obj['tool_calls'])} calls")
                for tc in obj["tool_calls"]:
                    if isinstance(tc, dict) and "name" in tc:
                        # Map 'arguments' to 'args' if present
                        args = tc.get("arguments") or tc.get("args", {})
                        tool_calls.append({
                            "name": tc["name"],
                            "args": args,
                            "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                            "type": tc.get("type", "tool_call")
                        })
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON object at position {pos}: {e}")
            pos += 1  # Skip to next character to attempt recovery
        except Exception as e:
            logger.error(f"Unexpected error during tool call normalization: {e}")
            break
            
    # 3. Apply normalized tool calls to response
    if tool_calls:
        response.tool_calls = tool_calls
        response.content = ""  # Clear raw text to clean up the UI
        logger.info(f"Normalization complete. {len(tool_calls)} tool calls detected.")
    else:
        logger.info("No tool calls detected in content.")
        
    return response

def assistant_node(state: State, config: RunnableConfig):
    """
    Consolidated Assistant Node: HR Support, Data Analytics, and Customer Concierge.
    Handles multiple roles and tool calling.
    """
    tenant_id = config["configurable"].get("tenant_id", "unknown")
    conversation_id = config["configurable"].get("thread_id", "unknown")
    messages = state["messages"]
    logger.info(f"Messages before assistant processing Aliue: {messages}")
    log_info(f"Assistant node triggered for tenant: {tenant_id} with nessage : {messages}", tenant_id, conversation_id)

    # --- Resolve DB-sourced prompts with hardcoded fallbacks ---
    tenant_config = state.get("tenant_config") or {}
    # employee_id = {state.get('employee_id')}
    employee_id = str(state.get('employee_id', 'unknown'))
    current_year = datetime.now().year
    previous_year = current_year - 1
    current_date_str = datetime.now().strftime("%Y-%m-%d")
    status_summary = state.get("status_summary", "No active application.")
    pdf_content = state.get("pdf_content", "None")
    web_content = state.get("web_content", "None")
    sql_result = state.get("sql_result", "None")
    visualization_analysis = state.get("visualization_analysis", "No visualization generated yet.")
    tool_intent_map = ((state.get("tenant_config") or {}).get("tool_intent_map")
  or tool_guide
    )

    push_name = tenant_config.get("push_name", "User")
    # global_answer_prompt acts as the persona/intro section of system_prompt.
    # Falls back to GLOBAL_FINAL_ANSWER_PROMPT if not set in the DB.
    global_answer_prompt = (
        tenant_config.get("global_answer_prompt")
        or GLOBAL_FINAL_ANSWER_PROMPT
    )
    
    # agent_prompt is the full system prompt stored in DB (used as an alternative
    # intro when set). If absent, the composed prompt below is used instead.
    # agent_prompt = tenant_config.get("agent_prompt") or None

    # Fetch the prompt template
    agent_prompt = tenant_config.get("agent_prompt1",GLOBAL_FINAL_ANSWER_PROMPT)




    # Build string of tool descriptions and arguments
    tool_descriptions = "\n".join([f"- {t.name}: {t.description}\n  Arguments schema: {t.args}" for t in tools])

    if agent_prompt:
        try:
            
         system_prompt = agent_prompt.format(
            ID=employee_id,
            current_year=current_year,
            previous_year=previous_year,
            current_date_str=current_date_str,
            pdf_content=pdf_content,
            web_content=web_content,
            # Using leave_application for the state result as requested
            sql_result=sql_result,
            visualization_analysis=visualization_analysis,
            status_summary=status_summary,
            tool_intent_map=tool_intent_map,
            tool_descriptions=tool_descriptions
        )
        except KeyError as e:
            logger.error(f"Missing key in prompt template: {e}")
            system_prompt = agent_prompt # Fallback to raw if format fails
    else:
        # Handle the case where no prompt is found
        system_prompt = "Default fallback prompt or error handling logic here."





    # 1. DYNAMIC CONTEXT PREPARATION (HR/Leave Status)
    leave_app = state.get("leave_application")
    status_summary = "No active application."
    if leave_app:
        status = leave_app.get("status")
        if status == "success":
            status_summary = f"Application {leave_app.get('application_id')} completed."
        elif status == "prepared":
            resumption = leave_app.get("details", {}).get("resumptionDate", "TBD")
            status_summary = f"Application prepared. Action required: Confirm resumption date {resumption}."
        elif status == "error":
            status_summary = f"Process error: {leave_app.get('message')}"

    greeting_instruction = f"Always greet or address the user using their name: {push_name}, if they are starting a conversation or if appropriate."


    # 3. LLM INVOCATION
 
    # Check if last message was a tool result (we might already be done)
    if messages and isinstance(messages[-1], ToolMessage):
        logger.info("Last message was a tool result. LLM will now generate the final JSON response based on the tool's output.")

    # logger.info(f"!!! TRACE: assistant_node starting. Messages: {len(messages)}", flush=True)

    logger.info(f"!!! TRACE: assistant_node starting. Messages: {len(messages)}")
    try:
        # 1. Capture the raw response WITH bind_tools
        # Use the global 'llm' instance directly to avoid redundant/unstable DB calls inside the graph
        logger.info(f"Messages before assistant processing: {messages}")
        llm = get_model() 
        log_info(f"LLM instance: {llm}", tenant_id, conversation_id)
        if not llm:
            log_error("LLM instance is not available. Returning error response.", tenant_id, conversation_id)
            return {"messages": [AIMessage(content=json.dumps({"tool": "none", "answer": "Error: LLM not available."}))]}
        log_info(f"Tools: {tools}", tenant_id, conversation_id)
        llm_with_tools = llm.bind_tools(tools)
        log_info(f"LLM with tools: {llm_with_tools}", tenant_id, conversation_id)
        
        safe_messages = clean_message_history(state["messages"])
        log_info(f"Safe messages: {safe_messages}", tenant_id, conversation_id)
        try:
            # 🛡️ GOLDEN RULES Appendage: Ensure user-friendly output regardless of DB prompt
            
            response = llm_with_tools.invoke([SystemMessage(content=f"{system_prompt}\n\n{greeting_instruction}{golden_rules}")] + safe_messages)
            log_info(f"LLM Raw Output: {response}", tenant_id, conversation_id)
        except Exception as e:
            log_error(f"LLM invoke failed: {e}", tenant_id, conversation_id)
            return {"messages": [AIMessage(content=json.dumps({"answer": "I'm sorry, I'm experiencing connectivity issues. Please try again later."}))]}
        
        log_info(f"LLM Raw Output: {response}", tenant_id, conversation_id)
    except BaseException as e:
        
        log_error(f"CRITICAL CRASH in assistant_node: {e}\n{traceback.format_exc()}", tenant_id, conversation_id)
        raise e
    refined_response = normalize_tool_calls(response)
    if refined_response.tool_calls:
        logger.info(f"Tool call detected: {refined_response.tool_calls}")
        return {"messages": [refined_response]}
    else:
        # Handle as standard text response
        final_answer = extract_final_answer(refined_response)
        logger.info(f"LLM response Assitant Node: {final_answer}")
        return {"messages": [AIMessage(content=final_answer)]}
    
    # if hasattr(refined_response, "tool_calls") and refined_response.tool_calls:
    #             logger.info(f"Tool calls foundAtejjd: {refined_response.tool_calls}")
    #             return {"messages": [refined_response]}  # keep the AIMessage intact

    # else:
    #     extract_final_answer(refined_response) and (not hasattr(refined_response, "tool_calls") or not refined_response.tool_calls):
    #         # Attach chart if present in state
    #     viz_result = state.get("visualization_result")
    #     if viz_result and "image_base64" in viz_result:
    #             refined_response.chart_base64 = viz_result["image_base64"]
                
    #         return {
    #             "messages": [AIMessage(content=refined_response.content)],
    #             "status_summary": status_summary
    #         }   


def build_graph(tenant_id: str, conversation_id: str, checkpointer=None):
    workflow = StateGraph(State)
    log_info(f"Building graph for tenant: {tenant_id}, conversation: {conversation_id}", tenant_id, conversation_id)

    # 1. Add Nodes
    workflow.add_node("assistant_node", assistant_node)
    workflow.add_node("tool_node", tool_node)
    
    # 2. Routing
    workflow.add_edge(START, "assistant_node")
    log_info("Edge added from START to assistant_node.", tenant_id, conversation_id)

    workflow.add_conditional_edges(
        "assistant_node", should_continue, ["tool_node", END]
    )

   # After tool execution, always return to assistant
    workflow.add_edge("tool_node", "assistant_node")
    log_info("Edge added from tool_node to assistant_node.", tenant_id, conversation_id)

    return workflow.compile(checkpointer=checkpointer)


ResponseFormat1 = {
    "type": "object",
    "description": "Response schema for the agent.",
    "properties": {
        "answer": {"type": "string", "description": "The answer to the user's question"},
        "leave_application": {"type": "string", "description": "The leave approval status to be injected by tools if applicable, otherwise null."},
        "visualization_image": {"type": "string", "description": "Base64-encoded image string of the generated visualization, if applicable."},
         "visualization_analysis": {"type": "string", "description": "explanation of the visualization results, if applicable."},
    },
    "required": ["answer", "leave_application", "visualization_image", "visualization_analysis"]
}


def process_message(message_content: str, conversation_id: str, tenant_id: str, employee_id: Optional[str] = None, push_name: str = "User", device_type: str = "unknown", phone_number: str = "2348021299221"):
    import json
    import difflib
    from datetime import datetime
    
    # Fallback for employee_id
    if not employee_id:
        employee_id = DEFAULT_EMPLOYEE_ID
    log_info("Starting message processing pipeline", tenant_id, conversation_id)
    log_info(f" Employee ID: {employee_id}-message Content: {message_content}-Device Type: {device_type}", tenant_id, conversation_id)
    
    vector_store_result = initialize_vector_store(tenant_id)

    tenant_vector_store, vs_info = (
        vector_store_result
        if isinstance(vector_store_result, tuple)
        else (vector_store_result, {})
    )
    
    if tenant_vector_store is not None:
        try:
            document_count = tenant_vector_store.index.ntotal
            log_info(f"Vector store document count: {document_count}", tenant_id, conversation_id)
        except AttributeError:
            log_error("Unexpected vector store structure.", tenant_id, conversation_id)
    else:
        log_error("Vector store is None.", tenant_id, conversation_id)
        
    prompt_id = None
    db_uri = os.getenv("DATABASE_URL")
    p_res = None
    biller_items = None
    biller_names = []
    categories = []
    agent_prompt = None

    try:
        with SessionLocal() as session:
            log_info("Fetching tenant AI config", tenant_id, conversation_id)
            ta_sql = """
                SELECT prompt_template_id, db_uri 
                FROM customer_tenant_ai 
                WHERE tenant_id = (SELECT id FROM org_tenant WHERE code = :code)
            """
            ta_item = session.execute(text(ta_sql), {"code": tenant_id}).fetchone()
            
            prompt_id = ta_item[0] if ta_item else None
            db_uri = ta_item[1] if ta_item and ta_item[1] else db_uri
            log_info(f"Tenant AI config fetched. Prompt ID: {prompt_id}, DB URI: {db_uri}", tenant_id, conversation_id)
            
            if prompt_id:
                p_sql = "SELECT agent_prompt, \"global_answer_prompt\", \"tool_intent_map\" FROM customer_prompt WHERE id = :pid"
                p_res = session.execute(text(p_sql), {"pid": prompt_id}).fetchone()
            else:
                p_sql = "SELECT agent_prompt, \"global_answer_prompt\", \"tool_intent_map\" FROM customer_prompt WHERE name = 'standard' LIMIT 1"
                p_res = session.execute(text(p_sql)).fetchone()
            log_info("Fetched prompt config", tenant_id, conversation_id)    
    except Exception as e:
        log_error(f"Database configuration fetch failed: {e}. Using defaults.", tenant_id, conversation_id)
    
    if p_res:
        log_info(f"Prompt template found: {p_res[0][:50]}...", tenant_id, conversation_id)
        agent_prompt = p_res[0]
        # --- NEW: extract categories and biller names ---
        biller_items = p_res[3] if len(p_res) > 3 else None
        if biller_items:
            try:
                import json
                billers = json.loads(biller_items) if isinstance(biller_items, str) else biller_items
                categories = list({b.get("category") for b in billers if b.get("category")})
                biller_names = [b.get("name") for b in billers if b.get("name")]
            except Exception as e:
                log_error(f"Failed to parse biller_items JSON: {e}", tenant_id, conversation_id)

        # Now you can use categories and biller_names lists in your chatbot logic
        log_info(f"Extracted {len(categories)} categories and {len(biller_names)} biller names", tenant_id, conversation_id)
        
    else:
        log_warning("No prompt template found in DB. Using global default.", tenant_id, conversation_id)
        agent_prompt = GLOBAL_FINAL_ANSWER_PROMPT    
    
    greeting_instruction = f"Always greet or address the user using their name: {push_name}, if they are starting a conversation or if appropriate."
    fallback_prompt = "Default fallback prompt or error handling logic here."
    
    current_year = datetime.now().year
    previous_year = current_year - 1
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    system_prompt = agent_prompt or fallback_prompt
    if agent_prompt:
        try:
            system_prompt = system_prompt.replace("{current_year}", str(current_year))
            system_prompt = system_prompt.replace("{previous_year}", str(previous_year))
            system_prompt = system_prompt.replace("{current_date_str}", str(current_date_str))
            system_prompt = system_prompt.replace("{ID}", str(employee_id))
            system_prompt = system_prompt.replace("{tool_intent_map}", str(p_res[2] if p_res else tool_guide))

            # --- DYNAMIC BILLER CONTEXT (Task 2) ---
            if biller_names and message_content:
                # Match against words in the message
                words = message_content.split()
                matches = []
                for word in words:
                    if len(word) > 3: # Only match meaningful words
                        m = difflib.get_close_matches(word, biller_names, n=1, cutoff=0.7)
                        if m: matches.extend(m)
                
                # Deduplicate and get full biller info
                unique_matches = list(set(matches))
                if unique_matches:
                    billers_json = json.loads(biller_items) if isinstance(biller_items, str) else biller_items
                    context_fragments = []
                    for name in unique_matches:
                        info = next((b for b in billers_json if b.get("name") == name), None)
                        if info:
                            fee = info.get("convenienceFee", "0")
                            cat = info.get("category", "General")
                            context_fragments.append(f"- {name} (Category: {cat}, Fee: ₦{fee})")
                    
                    if context_fragments:
                        biller_context = "\n".join(context_fragments)
                        system_prompt += f"\n\n[CONTEXT: Available Billers]\nThe user's message might refer to these detected billers:\n{biller_context}\nUse this exact 'Name' and 'Category' when calling tools."

        except Exception as e:
                logger.error(f"Error formatting prompt template: {e}")
                system_prompt = agent_prompt
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    persist_directory = os.path.join(base_dir, "faiss_dbs", tenant_id)

    log_info(f"Tenant config prepared. DB URI present: {bool(db_uri)}", tenant_id, conversation_id)
    
    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()
        
        config = {"configurable": {"thread_id": conversation_id}}
        systematic_prompt = f"{system_prompt}\n\n{greeting_instruction}{golden_rules}"
        phone_number1="08027790963"
        context = Context(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            emp_id=employee_id,
            db_uri=db_uri,
            push_name=push_name,
            device_type=device_type,
            phone_number=phone_number1,
            agent_prompt=p_res[0] if p_res else GLOBAL_FINAL_ANSWER_PROMPT,
            final_answer_prompt=p_res[1] if p_res else GLOBAL_FINAL_ANSWER_PROMPT,
            tool_intent_map=p_res[2] if p_res else tool_guide,
            vector_store_path=persist_directory
        )
     
        agent = create_agent(
            model=get_model(),
            system_prompt=systematic_prompt,
            tools=tools,
            context_schema=Context,
            response_format=ToolStrategy(ResponseFormat),
            # response_format=ProviderStrategy(ResponseFormat1),
            # response_format=ResponseFormat,
            checkpointer=checkpointer,
            middleware=[trim_messages],
        )
# type[StructuredResponseT]
        final_state = agent.invoke(
            {"messages": [{"role": "user", "content": message_content}]},
            config=config,
            context=context
        )
        
        logger.info(f" Raw LLM response  : {final_state}")
        logger.info(f"Final state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'Not a dict'}")

        if isinstance(final_state, dict):
            logger.info(f"Final state viz_image present: {bool(final_state.get('visualization_image'))}")
            if final_state.get('visualization_image'):
                logger.info(f"Final state viz_image length: {len(final_state.get('visualization_image'))}")
        
        messages = final_state.get("messages", [])
        logger.info(f" LLM response messages Raweeee : {messages}")
        last_msg = messages[-1] if messages else None
        extracted_data = {}
        viz_from_tool = {"image": None, "analysis": None}
        
        for msg in reversed(messages):
            if hasattr(msg, "name") and msg.name == "generate_visualization_tool":
                try:
                    
                    tool_content = json.loads(msg.content)
                    viz_res = tool_content.get("visualization_result", {})
                    viz_from_tool["image"] = viz_res.get("image_base64")
                    viz_from_tool["analysis"] = viz_res.get("analysis")
                    logger.info("Successfully extracted image and analysis from ToolMessage.")
                    break # Stop once we find the most recent viz tool result
                except Exception as e:
                    logger.error(f"Failed to parse visualization tool content: {e}")
        if last_msg:
            
            content_raw = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            content_clean = re.sub(r"^```json\s*|\s*```$", "", content_raw.strip(), flags=re.MULTILINE)
            try:
                extracted_data = json.loads(content_clean)
            except json.JSONDecodeError:
                extracted_data = {"answer": content_raw}

        if not isinstance(extracted_data, dict):
            extracted_data = {"answer": str(extracted_data)}

        current_answer = extracted_data.get("answer") or extracted_data.get("text") or ""
            
        try:
            logger.info(f"LLM response Process message extraction: {current_answer[:200]}...")
            
            if '"tool":' in str(current_answer) or '"name":' in str(current_answer):
                 logger.warning(f"Detected residual tool call in extracted answer: {current_answer}")
                 extracted_text = "I am processing your request. Please hold on."
            else:
                 extracted_text = str(current_answer)

            # result_data = {
            #     "text": extracted_text,
            #     "viz_image": extracted_data.get("visualization_image") or final_state.get("visualization_image"),
            #     "viz_analysis": extracted_data.get("visualization_analysis") or final_state.get("visualization_analysis")
            # }
            result_data = {
            "text": extracted_data.get("answer") or extracted_data.get("text") or "",
            "viz_image": viz_from_tool["image"] or final_state.get("visualization_image"),
            "viz_analysis": viz_from_tool["analysis"] or final_state.get("visualization_analysis")
        }
            if result_data["viz_analysis"] and result_data["viz_analysis"] not in result_data["text"]:
                result_data["text"] += "\n\n" + result_data["viz_analysis"]
                
            # Filter out base64 image data from text response
            
            base64_pattern = r"!\[.*?\]\(data:image\/.*?;base64,.*?\)|data:image\/.*?;base64,[a-zA-Z0-9+/=]+"
            result_data["text"] = re.sub(base64_pattern, "[Image Visualization]", result_data["text"])

            result_data["text"] = result_data["text"].replace("ATB", "Gatik")
            
            logger.info(f"Processed response dictionary keys: {list(result_data.keys())}")
            logger.info(f"Processed response viz_image value present: {bool(result_data.get('viz_image'))}")
            
            if result_data["viz_image"]:
                 logger.info(f"Visualization image found in response. Length: {len(result_data['viz_image'])}")
            else:
                 logger.warning("No visualization image found in process_message final result.")

            return result_data

        except Exception as e:
            logger.error(f"Error extracting final response: {str(e)}", exc_info=True)
            return {"text": "An unexpected error occurred while formatting the response.", "viz_image": None}
