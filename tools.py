from typing_extensions import runtime


import os
import sys
import requests
import pandas as pd
import re
import io
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from matplotlib.ticker import FuncFormatter
from datetime import datetime, timedelta
from dateutil.parser import parse
from sqlalchemy import create_engine
from sqlalchemy import text
from typing import Any, Dict, List, Literal, Optional, Union, Annotated
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    AnyMessage,
)
from langchain_community.vectorstores import FAISS
from langchain_community.utilities import SQLDatabase
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.prebuilt import ToolNode, create_react_agent, tools_condition
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain.tools import tool
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.tools import tool, ToolRuntime
from dataclasses import dataclass
# from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from langchain.tools import tool
from langchain.agents.structured_output import ToolStrategy
from sqlalchemy import text
from langchain.agents.middleware import before_model
from langchain.agents import create_agent, AgentState
from langgraph.runtime import Runtime
from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from typing import Any
from datetime import datetime
from urllib.parse import urlparse
import json
from sqlalchemy import create_engine
import re
import json 

from sqlalchemy import text
from sqlalchemy import text
from datetime import datetime
import random
from sqlalchemy import text
import psycopg2
from sqlalchemy import text
from sqlalchemy import text
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langgraph.prebuilt import create_react_agent

# from myproject_revisit.org.management.commands import state
from .logger_utils import log_info, log_error, log_debug, log_warning, logger
from .llm_handler import get_model
# from .chat_bot import get_llm_instance
        
from .ollama_service import OllamaService
from .base import (MultiplicationInput,
PayslipQuery,LeaveBalanceRequest,PayslipListQuery,PayslipInfo,PayslipSummary,PayslipListResponse,
PayslipDownloadQuery,PayslipDownloadResponse,PayslipExplainQuery,PayslipExplainResponse,LeaveTypeRequest,
PrepareLeaveApplicationRequest,PreparedLeaveApplication,ValidateLeaveBalanceRequest,
ValidateLeaveBalanceResponse,CalculateDaysRequest,CalculateDaysResponse,SubmitLeaveApplicationRequest,SearchJobOpportunitiesRequest,
JobOpportunityResponse,LeaveStatusRequest,ExitPolicyRequest,TravelSearchRequest,ProfileUpdateInput,
CustomerProfileInput,CustomerDetailsInput,ToolInput,Answer,VisualizationInput,SQLQueryInput,Summary,State,UpdateCustomerProfileInput,Context,ResponseFormat,VisualizationAnalysis)
# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Logging and configuration - moved to logger_utils and shared modules

def log_exception_auto(msg, tenant_id, conversation_id):
    logger.error(
        f"[Tenant: {tenant_id} | Conversation: {conversation_id}] {msg}",
        exc_info=True,
    )


tavily_search = TavilySearch(max_results=2)
search_tool = TavilySearch(
    max_results=5,
    include_raw_content=True,
)


@tool("get_payslip_tool", args_schema=PayslipQuery, description="Useful for fetching payslip archives. Input dates can be in various formats (e.g., 'Jan 2025', '01/25', '2025-01', '012025'). Outputs a download URL for the specified period.")
def get_payslip_tool(runtime: ToolRuntime[Context], **kwargs) -> str:
    """Normalizes dates to MMYYYY and fetches payslip archive."""
    employee_id = runtime.context.employee_id  
    query = PayslipQuery(**kwargs)
        
    raw_start = kwargs.get('start_date')
    raw_end = kwargs.get('end_date')
    

    def normalize_to_mmyyyy(date_str: str) -> str:
        try:
            
            # Smart parsing: handles "Jan 2025", "01/25", "2025-01", etc.
            parsed_date = parse(date_str, fuzzy=True)
            return parsed_date.strftime("%m%Y")
        except:
            # Fallback for purely numeric strings like "012025"
            if len(date_str) == 6 and date_str.isdigit():
                return date_str
            raise ValueError(f"Could not understand date: {date_str}")

    try:
        clean_start = normalize_to_mmyyyy(raw_start)
        clean_end = normalize_to_mmyyyy(raw_end)
        
        # config_data = config.get("configurable", {})
        # employee_id = config_data.get("employee_id")
        download_url = f"https://hr.system/payslip/{employee_id}/{clean_start}-{clean_end}.pdf"

        # The data structure you requested for PayslipInfo
        payslip_data = {
            "start_date": clean_start, # Now guaranteed MMYYYY
            "end_date": clean_end,     # Now guaranteed MMYYYY
            "download_url": download_url
        }
        log_info(f"Generated payslip data: {payslip_data}", runtime.context.tenant_id, runtime.context.conversation_id)
        response =f"Your payslip for {clean_start} to {clean_end} has been sent to your email."
        return response
        # return Command(
        #     update={
        #         "sudo": payslip_data, # Added as child to State
        #         "messages": [
        #             ToolMessage(
        #                 content=f"Your payslip for {clean_start} to {clean_end} has been sent to your email.",
        #                 tool_call_id=tid
        #             )
        #         ]
        #     }
        # )
    except Exception as e:
        return f"I had trouble understanding the dates. Please use MMYYYY format. Error: {str(e)}"



@tool("fetch_available_leave_types_tool", args_schema=LeaveTypeRequest)
# def fetch_available_leave_types_tool(config: RunnableConfig, **kwargs):
def fetch_available_leave_types_tool(runtime: ToolRuntime[Context], **kwargs)  -> str:  
    """
    REQUIRED FIRST STEP for leave applications. 
    Fetches available leave types from the PostgreSQL tenant database.
    """
    # 1. Get the ID we injected in tool_node for the response message
  
    log_info(f"Invoked fetch_available_leave_types_tool with args: {kwargs}", runtime.context.tenant_id, runtime.context.conversation_id)
    
    emp_id = runtime.context.emp_id  
    query = LeaveTypeRequest(**kwargs)
    tenant_id = runtime.context.tenant_id
    db_uri = runtime.context.db_uri
 
    tid = kwargs.get('current_tool_id')
    if not tid:
        tid = "unknown_id" 
    
    # config_data = config.get("configurable", {})
    # emp_id = config_data.get("employee_id")
    # tenant_id = config_data.get("tenant_id")
    # db_uri = config_data.get("db_uri")
    
    log_info(f"Fetching available leave types for employee: {emp_id} from tenant: {tenant_id}", tenant_id, "unknown")

    try:
        # Validate db_uri is available
        if not db_uri:
            log_error(f"No database URI available for tenant {tenant_id}", tenant_id, "unknown")
            # return ToolMessage(content="Error: Database configuration missing.", tool_call_id=tid)
            return "Error: Database configuration missing."

        # Ensure PostgreSQL URI uses postgresql:// prefix
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        # Create engine and execute query
        

        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # Query the leave_leavetype table for available leave types for this tenant
                query = text("""
                    SELECT id, name, is_paid, base_entitlement 
                    FROM leave_leavetype 
                    WHERE tenant_id = (
                        SELECT id FROM org_tenant WHERE code = :tenant_code
                    )
                    ORDER BY name
                """)
                
                result = connection.execute(query, {"tenant_code": tenant_id})
                leave_types = result.fetchall()
                
                if leave_types:
                    # Extract leave type names
                    leave_names = [row[1] for row in leave_types]  # row[1] is the name column
                    result_text = f"The following leave types are available: {', '.join(leave_names)}. Which one would you like to apply for?"
                    log_info(f"The result text from the fetch_available_leave_types_tool: {result_text}", tenant_id, "unknown")
                    # return ToolMessage(content=result_text, tool_call_id=tid)
                    return result_text
                else:
                    # return ToolMessage(content="No leave types are currently configured for your tenant.", tool_call_id=tid)
                    return "No leave types are currently configured for your tenant."

        finally:    
            engine.dispose()

    except Exception as e:
        log_info(f"Failed to fetch leave types from database: {str(e)}", tenant_id, "unknown")
        # return ToolMessage(content=f"Error retrieving leave types: {str(e)}", tool_call_id=tid)
        return f"Error retrieving leave types: {str(e)}"



@tool("validate_leave_balance_tool", args_schema=ValidateLeaveBalanceRequest)
def validate_leave_balance_tool(runtime: ToolRuntime[Context], **kwargs)-> str:
    """
    Validates leave balance against the PostgreSQL tenant database.
    If numOfDays is 0, it calculates it using the dates provided in the workflow state.
    """
    
    
    emp_id = runtime.context.emp_id  
    query = LeaveTypeRequest(**kwargs)
    tenant_id = runtime.context.tenant_id
    db_uri = runtime.context.db_uri
 
    tid = kwargs.get('current_tool_id')
    if not tid:
        tid = "unknown_id" 
    
    # tid = kwargs.get('current_tool_id') or "unknown_id"
    emp_id = runtime.context.emp_id  
    leave_type_name = kwargs.get('leaveTypeName')
    leave_type_id = kwargs.get('leaveTypeID')
    year = kwargs.get('year')
    num_days = kwargs.get('numOfDays')
    
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri
    
    log_info(f"Validating leave balance for employee: {emp_id} (Type: {leave_type_name})", tenant_id, conversation_id)

    try:
        if not db_uri:
            return ToolMessage(content="Error: Database configuration missing.")

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        
        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # 1. Resolve leave_type_id if only name is provided
                if not leave_type_id and leave_type_name:
                    lt_query = text("""
                        SELECT id FROM leave_leavetype 
                        WHERE name ILIKE :name 
                        AND tenant_id = (SELECT id FROM org_tenant WHERE code = :tenant_code)
                    """)
                    lt_result = connection.execute(lt_query, {"name": leave_type_name, "tenant_code": tenant_id}).fetchone()
                    if lt_result:
                        leave_type_id = lt_result[0]
                    else:
                        return ToolMessage(content=f"Error: Leave type '{leave_type_name}' not found.", tool_call_id=tid)

                # 2. Fetch balance
                # Query leave_leavebalance table
#                 balance_query = text("""
#     SELECT lb.balance_days, lb.total_earned, lb.used 
#     FROM leave_leavebalance lb
#     JOIN employees_employee ee ON lb.employee_id = ee.id
#     JOIN auth_user au ON ee.user_id = au.id
#     WHERE au.email = :emp_id 
#     AND lb.leave_type_id = :lt_id 
#     AND lb.year = :year
# """)
                
                
                balance_query = text("""
                    SELECT lb.balance_days, lb.total_earned, lb.used 
                    FROM leave_leavebalance lb
                    JOIN employees_employee ee ON lb.employee_id = ee.id
                    WHERE ee.employee_email = :emp_id 
                    AND lb.leave_type_id = :lt_id 
                    AND lb.year = :year
                """)
                
                try:
                    bal_result = connection.execute(balance_query, {
                        "emp_id": emp_id, 
                        "lt_id": leave_type_id, 
                        "year": year
                    }).fetchone()
                except Exception as e:
                    # HERE IS WHERE YOU PUT THE LOGGING LOGIC
                    logger.error(f"DB Error validating balance for {emp_id}: {str(e)}")
                    return ToolMessage(
                        content="We encountered an issue checking your leave balance. Please try again or contact HR support.", 
                        tool_call_id=tid
                    )
                
                if not bal_result:
                    return ToolMessage(content=f"Error: No leave balance record found for {leave_type_name} in {year}.", tool_call_id=tid)
                
                remaining = float(bal_result[0])
                
                if remaining < num_days:
                    result_text = f"Insufficient balance. You requested {num_days} days but only have {remaining} days available for {leave_type_name}."
                else:
                    result_text = f"Validation successful. You have {remaining} days available for {leave_type_name}."
                
                return ToolMessage(content=result_text, tool_call_id=tid)
        finally:
            engine.dispose()

    except Exception as e:
        log_error(f"Failed to validate leave balance: {str(e)}", tenant_id, conversation_id)
        return ToolMessage(content=f"Error validating leave balance: {str(e)}", tool_call_id=tid)


@tool("submit_leave_application_tool", args_schema=SubmitLeaveApplicationRequest)
def submit_leave_application_tool(runtime: ToolRuntime[Context], **kwargs)-> str:
    """
    Finalizes the leave application and inserts the record into the PostgreSQL database.
    Resolves employee, leave type, and relief employee IDs from the database.
    """
    tid = kwargs.get('current_tool_id') or "unknown_id"
    emp_email = runtime.context.emp_id
    tenant_code = runtime.context.tenant_id
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri
    
    # Extract fields from kwargs
    lt_name = kwargs.get('leaveTypeName')
    start_str = kwargs.get('leaveStartDate')
    end_str = kwargs.get('leaveEndDate')
    reason = kwargs.get('leaveReason') or ""
    relief_name = kwargs.get('workAssigneeRequest')
    
    log_info(f"Submitting leave application for: {emp_email} (Type: {lt_name})", tenant_id, conversation_id)

    try:
        if not db_uri:
            log_error("Database configuration missing.", tenant_id, conversation_id)
            return ToolMessage(content="Error: Database configuration missing.", tool_call_id=tid)

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        
        # Parse dates DDMMYYYY
        try:
            start_date = datetime.strptime(start_str, "%d%m%Y").date()
            end_date = datetime.strptime(end_str, "%d%m%Y").date()
        except Exception as e:
            # return ToolMessage(content=f"Error parsing dates: {str(e)}. Use DDMMYYYY format.", tool_call_id=tid)
            return f"Error parsing dates: {str(e)}. Use DDMMYYYY format."

        # from sqlalchemy import text
        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # 1. Resolve Tenant ID
                t_query = text("SELECT id FROM org_tenant WHERE code = :code")
                t_res = connection.execute(t_query, {"code": tenant_code}).fetchone()
                if not t_res:
                    return ToolMessage(content=f"Error: Tenant '{tenant_code}' not found.", tool_call_id=tid)
                tenant_id = t_res[0]

                # 2. Resolve Main Employee ID
                e_query = text("SELECT id FROM employees_employee WHERE employee_email = :email AND tenant_id = :t_id")
                e_res = connection.execute(e_query, {"email": emp_email, "t_id": tenant_id}).fetchone()
                if not e_res:
                    return ToolMessage(content=f"Error: Employee profiling for '{emp_email}' not found.", tool_call_id=tid)
                employee_id = e_res[0]

                # 3. Resolve Leave Type ID
                lt_query = text("SELECT id FROM leave_leavetype WHERE name ILIKE :name AND tenant_id = :t_id")
                lt_res = connection.execute(lt_query, {"name": lt_name, "t_id": tenant_id}).fetchone()
                if not lt_res:
                    return ToolMessage(content=f"Error: Leave type '{lt_name}' not found.", tool_call_id=tid)
                leave_type_id = lt_res[0]

                # 4. Resolve Relief Employee ID (Optional)
                relief_id = None
                if relief_name and relief_name.strip():
                    r_query = text("""
                        SELECT id FROM employees_employee 
                        WHERE (first_name || ' ' || last_name ILIKE :name OR employee_email = :name)
                        AND tenant_id = :t_id
                    """)
                    r_res = connection.execute(r_query, {"name": relief_name, "t_id": tenant_id}).fetchone()
                    if r_res:
                        relief_id = r_res[0]

                # 5. Insert Leave Request
                # Using columns from LeaveRequest model: employee_id, leave_type_id, start_date, end_date, reason, approval_status, tenant_id, relief_employee_id
                insert_query = text("""
                    INSERT INTO leave_leaverequest (
                        employee_id, leave_type_id, start_date, end_date, 
                        reason, approval_status, tenant_id, relief_employee_id,
                        order_date
                    ) VALUES (
                        :e_id, :lt_id, :start, :end, 
                        :reason, 'pending', :t_id, :r_id,
                        NOW()
                    ) RETURNING id
                """)
                
                result = connection.execute(insert_query, {
                    "e_id": employee_id,
                    "lt_id": leave_type_id,
                    "start": start_date,
                    "end": end_date,
                    "reason": reason,
                    "t_id": tenant_id,
                    "r_id": relief_id
                })
                new_id = result.fetchone()[0]
                connection.commit()

                success_msg = f"Leave application submitted successfully! Reference ID: {new_id}."
                return success_msg
             
                # return Command(
                #     update={
                #         "leave_application": {
                #             "status": "success",
                #             "application_id": str(new_id)
                #         },
                #          "status_summary": success_msg,
                #         "messages": [
                #             ToolMessage(content=success_msg, tool_call_id=tid)
                #         ]
                #     },
                #     goto="assistant"
                # )
        finally:
            engine.dispose()

    except Exception as e:
        log_error(f"Failed to submit leave application: {str(e)}", tenant_id, conversation_id)
        return ToolMessage(content=f"Error submitting application: {str(e)}", tool_call_id=tid)


@tool("prepare_leave_application_tool", args_schema=PrepareLeaveApplicationRequest)
def prepare_leave_application_tool(runtime: ToolRuntime[Context], **kwargs)-> str: 
    """Validates full leave details including contact info and year selection."""
    
    tid = kwargs.get('current_tool_id')
    
    # Extract fields from Assistant's tool call
    start_date = kwargs.get("leaveStartDate")
    end_date = kwargs.get("leaveEndDate")
    leave_year = kwargs.get("leaveYear")
    reliever = kwargs.get("workAssigneeRequest")
    address = kwargs.get("addressWhileOnLeave")
    contact = kwargs.get("contactNoWhileOnLeave")
    email = kwargs.get("emailWhileOnLeave")

    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    
    log_info(f"Preparing application for Year {leave_year}. Reliever: {reliever}", tenant_id, conversation_id)

    # 1. Date Format Validation (DDMMYYYY)
    date_fmt = "%d%m%Y"
    try:
        if not start_date or not end_date:
            raise ValueError("Start and End dates are mandatory.")
            
        start_dt_obj = datetime.strptime(start_date, date_fmt)
        end_dt_obj = datetime.strptime(end_date, date_fmt)
        
        # 2. Dynamic Resumption Calculation (End Date + 1)
        resumption_dt_obj = end_dt_obj + timedelta(days=1)
        resumption_str = resumption_dt_obj.strftime("%d-%m-%Y")
        
    except ValueError as e:
        content=f"Error: {str(e)}. Please ensure dates are in DDMMYYYY format (e.g., 22122025).",
        # return ToolMessage(
        #     content=f"Error: {str(e)}. Please ensure dates are in DDMMYYYY format (e.g., 22122025).",
        #     tool_call_id=tid
        # )
        return  content

    log_info(f"Calculated resumption date as {resumption_str}", tenant_id, conversation_id)

    # 3. Update State
    # return Command(
    #     update={
    #         "leave_application": {
    #             "status": "prepared",
    #             "details": {
    #                 **kwargs, 
    #                 "resumptionDate": resumption_str
    #             }
    #         },
    #         "messages": [
    #             ToolMessage(
    #                 content=(
    #                     f"I've prepared your application:\n"
    #                     f"* Resumption: {resumption_str}\n"
    #                     f"* Reliever: {reliever}\n"
    #                     f"* Address: {address}\n"
    #                     "Please confirm to **Submit**."
    #                 ),
    #                 tool_call_id=tid
    #             )
    #         ]
    #     }
    # )
    return (
        f"I've prepared your application:\n"
        f"* Resumption: {resumption_str}\n"
        f"* Reliever: {reliever}\n"
        f"* Address: {address}\n"
        "Please confirm to **Submit**."
    )

@tool("calculate_num_of_days_tool", args_schema=CalculateDaysRequest)
def calculate_num_of_days_tool(runtime: ToolRuntime[Context], **kwargs)-> int: 
    """
    Calculates the actual number of leave days by skipping weekends and 
    a provided list of public holidays.
    """
    startDate = kwargs.get('startDate')
    endDate = kwargs.get('endDate')
    holidays = kwargs.get('holidays', [])
    
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    log_info(f"Calculating business days between {startDate} and {endDate}", tenant_id, conversation_id)
    
    try:
        # 1. Parse string dates to date objects

        # To this:
        start = datetime.strptime(startDate, "%d%m%Y").date()
        end = datetime.strptime(endDate, "%d%m%Y").date()
        
        # 2. Convert holiday strings to a set of date objects for O(1) lookup
        holiday_set = {datetime.fromisoformat(h.replace("Z", "")).date() for h in holidays}
        
        total_days = 0
        current_day = start
        
        # 3. Iterate through the range
        while current_day <= end:
            # Check if it's a weekday (Monday=0, Friday=4) AND not a holiday
            if current_day.weekday() < 5 and current_day not in holiday_set:
                total_days += 1
            else:
                log_reason = "Weekend" if current_day.weekday() >= 5 else "Public Holiday"
                logger.warning(f"Skipping {current_day}: {log_reason}", config)
                
            current_day += timedelta(days=1)

        # logger.debug(f"Final calculation: {total_days} business days", "config")
        log_info(f"Calculated {total_days} business days between {startDate} and {endDate}", tenant_id, conversation_id)

        # 4. Return structured response
        return total_days
    
    except Exception as e:
        log_debug(f"Error calculating leave days: {e}", tenant_id, conversation_id)
        # Fallback to a standard diff if parsing fails, or return 0
        return 0

# 2. Update the Tool Function
@tool("search_job_opportunities_tool", args_schema=SearchJobOpportunitiesRequest)
def search_job_opportunities_tool(runtime: ToolRuntime[Context], **kwargs)-> str: 
    """Searches for internal job opportunities by querying the tenant's PostgreSQL database.

    This tool uses the `org_jobrole` table and related joins. Only roles marked `vacant = true`
    are considered. Additional filters (department, jobType, location, jobRoleType) map to
    corresponding columns/joined tables where possible.
    """
    tid = kwargs.get('current_tool_id')
    if not tid:
        tid = "unknown_id"
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri

    log_info(f"Searching jobs for tenant {tenant_id} using db_uri {db_uri}", tenant_id, conversation_id)

    try:
        if not db_uri:
            raise ValueError("No db_uri provided for tenant")
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        
        engine = create_engine(db_uri)
        try:
            with engine.connect() as conn:
                base_sql = [
                    "SELECT jr.id, jt.name AS job_title, ou.name AS org_unit, jr.vacant, jr.role_type, jr.status",
                    "FROM org_jobrole jr",
                    "LEFT JOIN org_jobtitle jt ON jr.job_title_id = jt.id",
                    "LEFT JOIN org_orgunit ou ON jr.org_unit_id = ou.id",
                    "WHERE jr.vacant = true",
                    "AND jr.tenant_id = (SELECT id FROM org_tenant WHERE code = :tenant_code)"
                ]
                params = {"tenant_code": tenant_id}

                # optional filters
                if kwargs.get("department"):
                    base_sql.append("AND ou.name ILIKE :department")
                    params["department"] = f"%{kwargs['department']}%"
                if kwargs.get("jobType"):
                    base_sql.append("AND jr.status = :jobType")
                    params["jobType"] = kwargs.get("jobType")
                if kwargs.get("location"):
                    base_sql.append("AND ou.name ILIKE :location")
                    params["location"] = f"%{kwargs['location']}%"
                if kwargs.get("jobRoleType"):
                    base_sql.append("AND jr.role_type = :jobRoleType")
                    params["jobRoleType"] = kwargs.get("jobRoleType")

                base_sql.append("ORDER BY jt.name")
                final_query = text("\n".join(base_sql))

                result = conn.execute(final_query, params)
                rows = result.fetchall()
                log_info(f"The rows from the search_job_opportunities_tool: {rows}", tenant_id, conversation_id)

                jobs_found = []
                for row in rows:
                    jobs_found.append({
                        "Role": row.job_title,
                        "OrgUnit": row.org_unit,
                        "Type": row.status,
                        "RoleType": row.role_type,
                    })

                if not jobs_found:
                    result_text = "No open internal positions match those criteria at the moment."
                    log_info(f"The result text from the search_job_opportunities_tool: {result_text}", tenant_id, conversation_id)
                else:
                    result_text = f"Found {len(jobs_found)} opportunities: {jobs_found}"
                    log_info(f"The result text from the search_job_opportunities_tool: {result_text}", tenant_id, conversation_id)
                return ToolMessage(content=result_text, tool_call_id=tid)
        finally:
            engine.dispose()
    except Exception as e:
        log_error(f"Job search failed: {str(e)}", tenant_id, conversation_id)
        return f"Error searching jobs: {str(e)}"
@tool("fetch_leave_status_tool", args_schema=LeaveStatusRequest)
def fetch_leave_status_tool(runtime: ToolRuntime[Context], **kwargs)-> str: 
    """Checks the current status of the employee's leave requests and identifies the pending approver and latest comments."""
    
    tid = kwargs.get('current_tool_id') or "unknown_id"
    emp_email = runtime.context.emp_id
    tenant_id = runtime.context.tenant_id
    tenant_code = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri

    log_info(f"Fetching leave status for: {emp_email}", tenant_id, conversation_id)

    try:
        if not db_uri:
            return ToolMessage(content="Error: Database configuration missing.", tool_call_id=tid)

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        
        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # 1. Resolve Tenant ID
                t_query = text("SELECT id FROM org_tenant WHERE code = :code")
                tenant_res = connection.execute(t_query, {"code": tenant_code}).fetchone()
                if not tenant_res:
                    return ToolMessage(content=f"Error: Tenant '{tenant_code}' not found.", tool_call_id=tid)
                tenant_db_id = tenant_res[0]

                # 2. Query Leave Requests with Workflow data
                # We need to find the ContentType ID for leave.leaverequest
                ct_query = text("SELECT id FROM django_content_type WHERE app_label = 'leave' AND model = 'leaverequest'")
                ct_res = connection.execute(ct_query).fetchone()
                ct_id = ct_res[0] if ct_res else None

                sql = """
                    SELECT 
                        lr.id, 
                        lt.name as leave_type, 
                        lr.start_date, 
                        lr.end_date, 
                        lr.approval_status,
                        wi.id as workflow_id,
                        (
                            SELECT wa.comment 
                            FROM workflow_workflowaction wa 
                            WHERE wa.instance_id = wi.id 
                            ORDER BY wa.created_at DESC LIMIT 1
                        ) as last_comment,
                        (
                            SELECT STRING_AGG(ee.first_name || ' ' || ee.last_name, ', ')
                            FROM workflow_workflowinstance_current_approvers wica
                            JOIN employees_employee ee ON wica.employee_id = ee.id
                            WHERE wica.workflowinstance_id = wi.id
                        ) as current_approvers
                    FROM leave_leaverequest lr
                    JOIN leave_leavetype lt ON lr.leave_type_id = lt.id
                    JOIN employees_employee emp ON lr.employee_id = emp.id
                    LEFT JOIN workflow_workflowinstance wi ON lr.id = wi.object_id AND wi.content_type_id = :ct_id
                    WHERE emp.employee_email = :email AND lr.tenant_id = :t_id
                    ORDER BY lr.order_date DESC
                    LIMIT 5
                """
                
                result = connection.execute(text(sql), {"email": emp_email, "t_id": tenant_db_id, "ct_id": ct_id})
                rows = result.fetchall()
                
                if not rows:
                    return ToolMessage(content="You have no recent leave requests.", tool_call_id=tid)
                
                reports = []
                for row in rows:
                    status_line = f"**{row.leave_type}** ({row.start_date} to {row.end_date}): **{row.approval_status.upper()}**"
                    if row.current_approvers:
                        status_line += f"\n   - Pending with: {row.current_approvers}"
                    if row.last_comment:
                        status_line += f"\n   - Last Comment: \"{row.last_comment}\""
                    reports.append(status_line)
                
                result_text = "Here is the status of your recent leave requests:\n\n" + "\n\n".join(reports)
                # return ToolMessage(content=result_text, tool_call_id=tid)
                return result_text
        finally:
            engine.dispose()

    except Exception as e:
        log_error(f"Failed to fetch leave status: {str(e)}", tenant_id, conversation_id)
        # return ToolMessage(content=f"Error fetching leave status: {str(e)}", tool_call_id=tid)
        return f"Error fetching leave status: {str(e)}"



@tool("search_travel_deals_tool", args_schema=TravelSearchRequest)
def search_travel_deals_tool(runtime: ToolRuntime[Context], **kwargs)-> str: 
    """Uses Tavily to search for the best flight and hotel deals for a vacation."""
    
    tid = kwargs.get('current_tool_id')
    dest = kwargs.get('destination')
    start = kwargs.get('departureDate')
    end = kwargs.get('returnDate')

    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    
    # Construct a high-quality search query for Tavily
    query = f"cheapest flights and top rated hotels in {dest} from {start} to {end} for vacation"
    
    log_info(f"Tavily searching travel deals: {query}", tenant_id, conversation_id)

    try:
        # Execute Tavily Search
        search_results = search_tool.invoke({"query": query})
        
        # Format the output for the AI Assistant
        formatted_results = []
        for res in search_results:
            formatted_results.append({
                "source": res.get("url"),
                "content": res.get("content")[:500] # Snippet for context
            })

        # return ToolMessage(
        #     content=f"Found these travel options in {dest}:\n{str(formatted_results)}",
        #     tool_call_id=tid
        # )
        return f"Found these travel options in {dest}:\n{str(formatted_results)}"
    except Exception as e:
        return f"Travel search failed: {str(e)}"   



@tool("create_customer_profile_tool", args_schema=CustomerProfileInput)
def create_customer_profile_tool(runtime: ToolRuntime[Context], **kwargs)-> str:
    """
    Creates a new customer profile in the PostgreSQL database.
    Generates a unique 10-digit account number and returns it.
    """
    tid = kwargs.get('current_tool_id') or "unknown_id"
    tenant_code = runtime.context.tenant_id  # Assuming tenant_code is same as tenant_id for lookup
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri
    
    first_name = kwargs.get('first_name')
    last_name = kwargs.get('last_name')
    email = kwargs.get('email')
    phone = kwargs.get('phone')
    gender = kwargs.get('gender')
    dob_str = kwargs.get('date_of_birth')
    occupation = kwargs.get('occupation') or "Not Specified"
    nationality = kwargs.get('nationality') or "Nigeria"
    nin = kwargs.get('nin') or "Not Provided"
    
    log_info(f"Creating customer profile for: {first_name} {last_name}", tenant_id, conversation_id)

    try:
        if not db_uri:
            log_error("Database configuration missing.", tenant_id, conversation_id)
            return ToolMessage(content="Error: Database configuration missing.", tool_call_id=tid)

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

       
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        except:
            return ToolMessage(content="Error: Invalid date format for date_of_birth. Use YYYY-MM-DD.", tool_call_id=tid)

        
        # Generate 10-digit account number
        account_num = "".join([str(random.randint(0, 9)) for _ in range(10)])
        # Generate customer ID
        cust_id = f"CUST{random.randint(10000, 99999)}"

        
        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # 1. Resolve Tenant ID
                t_query = text("SELECT id FROM org_tenant WHERE code = :code")
                tenant_res = connection.execute(t_query, {"code": tenant_code}).fetchone()
                if not tenant_res:
                    return ToolMessage(content=f"Error: Tenant '{tenant_code}' not found.", tool_call_id=tid)
                tenant_db_id = tenant_res[0]

                # 2. Insert Customer
                sql = """
                    INSERT INTO customer_customer (
                        customer_id, first_name, last_name, email, phone_number,
                        account_number, gender, nationality, occupation, date_of_birth,
                        tenant_id
                    ) VALUES (
                        :cid, :fn, :ln, :email, :phone,
                        :acc, :gender, :nat, :occ, :dob,
                        :tid
                    ) RETURNING id
                """
                
                result = connection.execute(text(sql), {
                    "cid": cust_id, "fn": first_name, "ln": last_name, "email": email, "phone": phone,
                    "acc": account_num, "gender": gender, "nat": nationality, "occ": occupation, "dob": dob,
                    "tid": tenant_db_id
                })
                connection.commit()
                
                msg = f"Successfully created customer profile for {first_name} {last_name}.\nAccount Number: **{account_num}**\nCustomer ID: {cust_id}"
                # return ToolMessage(content=msg, tool_call_id=tid)
                return msg
        finally:
            engine.dispose()

    except Exception as e:
        log_error(f"Failed to create customer profile: {str(e)}", tenant_id, conversation_id)
        # return ToolMessage(content=f"Error creating customer profile: {str(e)}", tool_call_id=tid)
        return f"Error creating customer profile: {str(e)}"


def init_sql_agent(state: State, llm):
    """Initialize SQLDatabase and SQL Agent using db_uri from state."""
    tenant_id = state.get("tenant_id", "default")
    conversation_id = state.get("conversation_id", "unknown")
    db_uri = state.get("db_uri")  # <-- fetch db_uri from state
    if db_uri == "ayuladb":
        db_uri = DB_URI # Fixed legacy reference
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)

    log_info(f"The ule of sql {db_uri} ", tenant_id, conversation_id)

    if not db_uri:
        log_error(f"[{tenant_id}] No db_uri found in state.", tenant_id, conversation_id)
        return None

    try:
        # Import psycopg2 if using PostgreSQL to ensure dialect is available
        if "postgresql" in db_uri:
            try:
                import psycopg2
            except ImportError:
                log_error(f"[{tenant_id}] psycopg2 not installed. Cannot connect to PostgreSQL. {db_uri}", tenant_id, conversation_id)
                return None
        
        db = SQLDatabase.from_uri(db_uri)
        log_info(f"[{tenant_id}] SQLDatabase connected to RE {db_uri} successfully.",tenant_id, conversation_id,)
        # --- Log dialect ---
        log_info(f"[{tenant_id}] Dialect RE: {db.dialect}", tenant_id, conversation_id)

        # --- Log usable tables ---
        try:
            usable_tables = db.get_usable_table_names()
            log_info(f"[{tenant_id}] Available tables RE: {usable_tables}",tenant_id,conversation_id,)
        
        except Exception as e:
            log_warning( f"[{tenant_id}] Could not retrieve usable tables: {e}",tenant_id,conversation_id,)
            usable_tables = []

        # --- Initialize toolkit and agent ---

        # Use a LangChain-compatible OllamaService for the SQL toolkit
        # ollama_llm = OllamaService(
        #     base_url=OLLAMA_BASE_URL,
        #     username=OLLAMA_USERNAME,
        #     password=OLLAMA_PASSWORD,
        #     model=OLLAMA_MODEL
        # )
        from .chat_bot import get_model
        llm =get_model()  # Use the existing get_model function to maintain consistency and leverage any caching or configuration it provides
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools = toolkit.get_tools()
        for tool_item in tools:
            log_info(
                f"[{tenant_id}] Tool {tool_item.name}: {tool_item.description}",
                tenant_id,
                conversation_id,
            )
        SQL_SYSTEM_PROMPT = """
            You are an agent designed to interact with a SQL database. Given an input question,
            create a syntactically correct {dialect} query, execute it, and return the answer.

            Guidelines:
            - Query only the necessary columns.
            - DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP).
            - CRITICAL: ONLY query columns that contain simple text or numerical data.
            Avoid querying columns with complex types (JSON, JSONB, Arrays) to prevent errors.
            - Double-check your query before execution.
            - ALWAYS inspect the tables first to understand the schema.

            CRITICAL SCHEMAS TO REFERENCE:
            - customer_account, customer_branchperformance, customer_contact, customer_conversation,
            - customer_crmuser, customer_customer, customer_lead, customer_loanreport,
            - customer_message, customer_opportunity, customer_transaction, org_location,
            - ats_jobposting, ats_application, org_jobrole, employees_employee,
            - leave_leavetype, leave_leavebalance.

            Special Instructions:
            - For customer-related info (e.g., transaction count, customer details), focus on `customer_transaction`.
            - Use these tables to perform deep data analysis and visualizations.
            - Limit query results to at most 5 rows.
            """

        SQL_SYSTEM_PROMPTv1 = """
            You are an agent designed to interact with a SQL database. Given an input question,
            create a syntactically correct {dialect} query, execute it, and return the answer.

            - Query only necessary columns.
            - DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP).
            - **CRITICAL**: ONLY query columns that contain simple text or numerical data. Avoid querying columns that contain complex types like JSON, JSONB, or Arrays, as they cause internal errors.
            - Double-check your query before execution.
            - ALWAYS look at the tables first to understand the schema.
            - **CRITICAL SCHEMAS TO REFERENCE**: 
                - customer_account, customer_branchperformance, customer_contact, customer_conversation, 
                - customer_crmuser, customer_customer, customer_lead, customer_loanreport, 
                - customer_message, customer_opportunity, customer_transaction, org_location,
                - ats_jobposting, ats_application, org_jobrole, employees_employee, 
                - leave_leavetype, leave_leavebalance.
            - for customer reqlated info or data such as transaction count, customer details  focus on customer_transaction 
            - Use these tables to perform deep data analysis and visualizations.
            - Limit your query to at most 5 results.
            """
        
        # agent = create_agent(llm, tools, system_prompt=SQL_SYSTEM_PROMPT)
        # Use create_react_agent for better compatibility with LangGraph and stream/invoke methods
        agent = create_react_agent(
            llm,
            tools,
            prompt=SQL_SYSTEM_PROMPT.format(dialect=db.dialect),
        )
        log_info(
            f"[{tenant_id}] SQL Agent initialized successfully.",
            tenant_id,
            conversation_id,
        )
      
        
        TENANT_SQL_AGENTS[tenant_id] = agent
        TENANT_DBS[tenant_id] = db
        log_info(" SQL Agent initialized successfully.", tenant_id, conversation_id)
        return agent    

    except Exception as e:
        log_error(
            f"[{tenant_id}] Error initializing SQL Agent: {e}",
            tenant_id,
            conversation_id,
        )
        return None

@tool("get_customer_details_tool", args_schema=CustomerDetailsInput)
def get_customer_details_tool(runtime: ToolRuntime[Context], **kwargs)-> str:
    """
    Retrieves a customer's details from the PostgreSQL database using phone number, email, or account number.
    """
    tenant_code = runtime.context.tenant_id
    tenant_id = tenant_code if tenant_code else "unknown"
    conversation_id = runtime.context.conversation_id
    val = kwargs.get('phone_or_email')
    acc_num = kwargs.get('account_number')
    log_info(f"get_customer_details_tool invoked with args: {val}, {acc_num}", tenant_id, conversation_id)
    tid = kwargs.get('current_tool_id') or "unknown_id"
    db_uri = runtime.context.db_uri
    
    
    if not val and not acc_num:
        return ToolMessage(content="Please provide an email, phone number, or account number.", tool_call_id=tid)

    try:
        if not db_uri:
            return ToolMessage(content="Error: Database configuration missing.", tool_call_id=tid)

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        
        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # 1. Resolve Tenant ID
                t_query = text("SELECT id FROM org_tenant WHERE code = :code")
                tenant_res = connection.execute(t_query, {"code": tenant_code}).fetchone()
                tenant_db_id = tenant_res[0] if tenant_res else None

                sql = """
                    SELECT customer_id, first_name, last_name, email, phone_number, account_number, gender, occupation, nationality
                    FROM customer_customer
                    WHERE (email = :val OR phone_number = :val OR account_number = :acc)
                    AND tenant_id = :tid
                """
                
                res = connection.execute(text(sql), {"val": val, "acc": acc_num, "tid": tenant_db_id}).fetchone()
                
                if not res:
                    return ToolMessage(content="No customer found with the provided details.", tool_call_id=tid)
                
                details = (
                    f"Customer Found:\n"
                    f"- Name: {res.first_name} {res.last_name}\n"
                    f"- Email: {res.email}\n"
                    f"- Phone: {res.phone_number}\n"
                    f"- Account Number: **{res.account_number}**\n"
                    f"- Occupation: {res.occupation}\n"
                    f"- Nationality: {res.nationality}"
                )
                # return ToolMessage(content=details, tool_call_id=tid)
                return details
        finally:
            engine.dispose()

    except Exception as e:
        log_error(f"Failed to retrieve customer details: {str(e)}", tenant_id, conversation_id)
        # return ToolMessage(content=f"Error retrieving customer details: {str(e)}", tool_call_id=tid)
        return f"Error retrieving customer details: {str(e)}"

@tool("update_customer_tool", args_schema=UpdateCustomerProfileInput)
def update_customer_tool(runtime: ToolRuntime[Context], **kwargs)-> str:
    """
    Updates the customer's profile details (phone, email, occupation, etc.) in the PostgreSQL database.
    """
    tenant_code = runtime.context.tenant_id
    tenant_id = tenant_code if tenant_code else "unknown"
    conversation_id = runtime.context.conversation_id
    target_email = kwargs.get('email') or runtime.context.emp_id
    target_phone = kwargs.get('phone_number')
    log_info(f"update_customer_tool invoked with args: {target_email}, {target_phone}", tenant_id, conversation_id)

    tid = kwargs.get('current_tool_id') or "unknown_id"
    db_uri = runtime.context.db_uri
    
    # We need a way to identify which customer to update. 
    # Since this is likely the current user, we assume their email/phone is in the context or provided.
    # For now, we'll use the provided email or phone if available, or fall back to the config employee_id (email).
    

    update_data = {k: v for k, v in kwargs.items() if v is not None and k != 'current_tool_id'}
    
    if not update_data:
        return ToolMessage(content="No update information was provided.", tool_call_id=tid)

    log_info(f"Updating customer profile for: {target_email or target_phone}", tenant_id, conversation_id)

    try:
        if not db_uri:
            log_error("Database configuration missing.", tenant_id, conversation_id)
            return ToolMessage(content="Error: Database configuration missing.", tool_call_id=tid)

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        
        engine = create_engine(db_uri)
        
        try:
            with engine.connect() as connection:
                # 1. Resolve Tenant ID
                t_query = text("SELECT id FROM org_tenant WHERE code = :code")
                tenant_res = connection.execute(t_query, {"code": tenant_code}).fetchone()
                tenant_db_id = tenant_res[0] if tenant_res else None

                # 2. Build Dynamic Update SQL
                set_clauses = []
                params = {"tid": tenant_db_id, "target_email": target_email, "target_phone": target_phone}
                
                for key, val in update_data.items():
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = val
                
                sql = f"""
                    UPDATE customer_customer 
                    SET {', '.join(set_clauses)}
                    WHERE (email = :target_email OR phone_number = :target_phone)
                    AND tenant_id = :tid
                """
                
                result = connection.execute(text(sql), params)
                connection.commit()
                
                if result.rowcount == 0:
                    return ToolMessage(content="No customer record found to update.", tool_call_id=tid)
                
                msg = f"Successfully updated your profile: {', '.join(update_data.keys())}."
                # return ToolMessage(content=msg, tool_call_id=tid)
                return msg
        finally:
            engine.dispose()

    except Exception as e:
       log_error(f"Failed to update customer profile: {str(e)}", tenant_id, conversation_id)
       return f"Error updating customer profile: {str(e)}"
       
    #    return ToolMessage(content=f"Error updating customer profile: {str(e)}", tool_call_id=tid)
    # 
      




@tool("sql_query_tool", args_schema=SQLQueryInput)
def sql_query_tool(runtime: ToolRuntime[Context], **kwargs) -> dict:
    """
    Useful for answering questions requiring data from a SQL database.
    **CRITICAL**: Pass ONLY a natural language question (e.g., 'List all employees hired in January') as the 'query' argument. 
    NEVER generate SQL yourself; the tool handles schema discovery and SQL generation internally.
    """
    query = kwargs.get('query')
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri
    tenant_name = tenant_id  # Assuming tenant_name is same as tenant_id for prompt purposes
    tenant_code = tenant_id  # Assuming tenant_code is same as tenant_id for prompt purposes
    log_info(f"sql_query_tool invoked with query: {query}", tenant_id, conversation_id)

    try:
       
        if not db_uri:
            return {"sql_result": "Error: Database configuration missing."}

        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        VECTRA_TABLE_LIST = [
    # Customer & CRM Tables
    "customer_account", 
    "customer_branchperformance", 
    "customer_contact", 
    "customer_conversation", 
    "customer_crmuser", 
    "customer_customer", 
    "customer_lead", 
    "customer_loanreport", 
    "customer_message", 
    "customer_opportunity", 
    "customer_transaction",
    
    # Organization & HR Tables
    "org_location",
    "org_jobrole", 
    "employees_employee", 
    
    # Recruitment (ATS) Tables
    "ats_jobposting", 
    "ats_application", 
    
    # Leave Management Tables
    "leave_leavetype", 
    "leave_leavebalance"
]
        engine = create_engine(db_uri)
        import warnings
        from sqlalchemy.exc import SAWarning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SAWarning)
            db = SQLDatabase(engine, 
        include_tables=VECTRA_TABLE_LIST,
        sample_rows_in_table_info=2)
        
        from .chat_bot import get_model
        llm = get_model()

        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        sql_tools = toolkit.get_tools()

        SQL_SYSTEM_PROMPT = """
You are an expert data analyst assistant for the tenant '{tenant_name}' (Code: {tenant_code}). Your task is to:
1. Search the database schema to find the MOST relevant tables for the user's question.
2. Create a syntactically correct {dialect} query to answer the question. Only query data relevant to `tenant_id={tenant_id}` if the table has a `tenant_id` column.
3. Execute the query and capture the results.
4. Return your final answer EXCLUSIVELY as a JSON object inside a code block.

CRITICAL INSTRUCTIONS TO PREVENT LOOPS:
- DO NOT call `sql_db_list_tables` more than once!
- After receiving the list of tables, immediately pick the 1-3 most relevant tables and call `sql_db_schema` to see their columns.
- DO NOT hallucinate column names. Verify them first.
           - **CRITICAL SCHEMAS TO REFERENCE**: 
                - customer_account, customer_branchperformance, customer_contact, customer_conversation, 
                - customer_crmuser, customer_customer, customer_lead, customer_loanreport, 
                - customer_message, customer_opportunity, customer_transaction, org_location,
                - ats_jobposting, ats_application, org_jobrole, employees_employee, 
                - leave_leavetype, leave_leavebalance.
            Special Instructions:
            - For customer-related info (e.g., transaction count, customer details), focus on `customer_transaction`.
            - Use these tables to perform deep data analysis and visualizations.
            - Limit query results to at most 5 rows.
Format:
```json
{{
  "analysis": "A brief summary of what you found.",
  "data": [
    {{"column1": "val1", "column2": "val2"}},
    ...
  ]
}}
```

- If no data is found, set "data" to [].
- DO NOT make any DML statements (INSERT, UPDATE, DELETE).
- NEVER output anything other than the JSON block.
- Ensure column names in "data" are descriptive and clean.
"""
      

        agent = create_react_agent(
            llm,
            sql_tools,
            prompt=SQL_SYSTEM_PROMPT.format(dialect=db.dialect, tenant_name=tenant_name, tenant_code=tenant_code, tenant_id=tenant_id),
        )

        agent_response = agent.invoke({"messages": [HumanMessage(content=str(query))]})
        agent_msgs = agent_response.get("messages", [])
        result = agent_msgs[-1].content if agent_msgs else "No response from SQL agent."
        log_info(f"SQL Tool Response: {result}", tenant_id, conversation_id)

        analysis_text = result
        parsed_data = None
        try:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", result, re.DOTALL)
            json_str = match.group(1) if match else result
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                parsed_data = parsed.get('data')
                analysis_text = parsed.get('analysis', result)
        except:
            pass
        log_info(f"SQL Tool Response: {parsed_data}", tenant_id, conversation_id)
        return {"sql_result": analysis_text, "data": parsed_data}

    except Exception as e:
        log_error(f"SQL Tool Error: {str(e)}", tenant_id, conversation_id)
        return {"sql_result": f"Error executing SQL query: {e}"}


@tool("pdf_retrieval_tool", args_schema=ToolInput)
def pdf_retrieval_tool(runtime: ToolRuntime[Context], **kwargs) -> dict:
    """
    Performs a document query using the pre-initialized FAISS vector store.
    """
    query = kwargs.get('query')
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    vector_store_path = runtime.context.vector_store_path
    
    log_info(f"pdf_retrieval_tool invoked with query: {query}", tenant_id, conversation_id)

    if not query:
        return {"pdf_content": "!!ERROR!! CODE:PDF-4002 MESSAGE:No user query provided for PDF search."}

    if not vector_store_path:
        return {"pdf_content": "!!ERROR!! CODE:PDF-4003 MESSAGE:Vector store path not provided in configuration."}

    try:
        from .chat_bot import get_embeddings
        vector_store = FAISS.load_local(
            folder_path=vector_store_path,
            embeddings=get_embeddings(),
            allow_dangerous_deserialization=True,
        )

        docs = vector_store.similarity_search(query, k=3)
        log_info(f"PDF Retrieval found {len(docs)} relevant documents.", tenant_id, conversation_id)
        results_text = []
        sources = set()
        for doc in docs:
            results_text.append(doc.page_content)
            source_file = os.path.basename(doc.metadata.get("source", "General Document"))
            sources.add(source_file)

        formatted_result = "\n\n".join(results_text)
        return {"pdf_content": formatted_result, "source_documents": list(sources)}

    except Exception as e:
        log_error(f"PDF Retrieval Error: {str(e)}", tenant_id, conversation_id)
        return {"pdf_content": f"!!ERROR!! CODE:PDF-5001 MESSAGE: {str(e)}"}

@tool("web_search_tool", args_schema=ToolInput)
def web_search_tool(runtime: ToolRuntime[Context], **kwargs) -> dict:
    """
    Performs web search using Tavily.
    """
    query = kwargs.get('query')
    # tenant_config = config["configurable"].get("tenant_config", {}) # Not in Context
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id

    log_info(f"web_search_tool invoked with query: {query}", tenant_id, conversation_id)
    

    # 1. Collect priority domains from context if available
    priority_domains = []
    # Note: Context doesn't currently expose tenant_knowledge_base or tenant_website
    # We might need to fetch this from elsewhere or update Context definition.
    # For now, we'll skip priority domains if not available.

    # 2. Targeted Search
    search_results = []
    source_label = "GENERAL SEARCH"
    if priority_domains:
        kb_tool = TavilySearch(max_results=5, include_domains=priority_domains, search_depth="advanced")
        try:
            search_results = kb_tool.invoke({"query": query})
            if search_results:
                source_label = "TENANT WEBSITE/KNOWLEDGE_BASE"
        except Exception as e:
            log_warning(f"Priority search failed: {e}", tenant_id, conversation_id)

    # 3. Fallback to general search
    if not search_results:
        general_tool = TavilySearch(max_results=5, search_depth="advanced")
        try:
            search_results = general_tool.invoke({"query": query})
            source_label = "GENERAL"
        except Exception as e:
            log_error(f"Fallback search failed: {e}", tenant_id, conversation_id)

    # 4. Format Output
    results_list = []
    if isinstance(search_results, dict) and "results" in search_results:
        results_list = search_results["results"]
    elif isinstance(search_results, list):
        results_list = search_results
    
    formatted_parts = []
    for res in results_list:
        if isinstance(res, dict) and 'url' in res and 'content' in res:
            part = f"--- SOURCE TYPE: {source_label} ---\nURL: {res['url']}\nCONTENT: {res['content']}\n"
            formatted_parts.append(part)
    
    return {
        "web_content": "\n".join(formatted_parts) if formatted_parts else "!!ERROR!! CODE:WEB-4002 MESSAGE:No valid search results found.",
        "type": "web_search",
        "source_documents": source_label.lower(),
        "source_labels": [f"web_search_{source_label.lower()}"],
    }



# sql_query_tool = Tool(
#     name="sql_query_tool",
#     description="Useful for answering questions requiring data from a SQL database (e.g., 'How many users are there?'). Input should be a natural language question.",
#     func=execute_sql_query_func,
#     args_schema=SQLQueryInput,
# )

# --- HELPER FUNCTIONS ---
def get_column_types(df: pd.DataFrame):
    """Helper function to identify column types for plotting."""
    # Attempt to convert object columns to datetime to identify "hidden" date columns
    for col in df.select_dtypes(include=['object']).columns:
        try:
            # Try parsing with a set threshold to avoid false positives on random strings
            # If it parses, convert the column permanently for plotting benefits
            df[col] = pd.to_datetime(df[col], errors='raise')
        except (ValueError, TypeError):
            pass

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    date_cols = df.select_dtypes(include=['datetime', 'datetimetz']).columns.tolist()
    return numeric_cols, categorical_cols, date_cols


@tool("generate_visualization_tool", args_schema=VisualizationInput)
def generate_visualization_tool(runtime: ToolRuntime[Context], **kwargs) -> dict:
    """
    Generates a data visualization based on a natural language query.
    """
    query = kwargs.get('query')
    data = kwargs.get('data')
    # tenant_config = config["configurable"].get("tenant_config", {}) # Not in Context
    tenant_id = runtime.context.tenant_id
    conversation_id = runtime.context.conversation_id
    db_uri = runtime.context.db_uri
    tid = kwargs.get('current_tool_id') or "unknown_id"

    log_info(f"Generating Visualization for query: '{query}'", tenant_id, conversation_id)
    analysis_text = "" 
   
    try:
        from .chat_bot import get_model
        llm = get_model()

        if data:
            log_info("Data provided directly to visualization tool. Bypassing SQL generation.", tenant_id, conversation_id)
            
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass
            df = pd.DataFrame(data)
            sql_query = "Data provided directly via tool chaining"
            if df.empty:
                return {"visualization_result": {"analysis": "No data available to visualize.", "image_base64": None}}
        else:
            if not db_uri:
                return {"visualization_result": {"analysis": "Error: Database configuration missing.", "image_base64": None}}
            
            if db_uri.startswith("postgres://"):
                db_uri = db_uri.replace("postgres://", "postgresql://", 1)

            
            db = SQLDatabase.from_uri(db_uri)

            # Step 1: Generate SQL from the natural language query
            sql_generation_prompt = f"""Given the user's question {query}, create a single, syntactically correct SQL query to retrieve the data needed for a chart.
                    Do not include any other text or explanation, just the SQL query itself.

                    Tables available: {db.get_table_info()}

                    User question: "{query}"
                    SQL Query:
                    """
            raw_sql_query = llm.invoke(sql_generation_prompt).content.strip()
            
            match = re.search(r"```(?:sql)?\s*(.*?)\s*```", raw_sql_query, re.DOTALL)
            sql_query = match.group(1).strip() if match else raw_sql_query
            
            log_info(f"Generated SQL: {sql_query}", tenant_id, conversation_id)

            # Step 2: Execute the query with Pandas
            
            engine = create_engine(db_uri)
            df = pd.read_sql_query(sql_query, con=engine)
            
        if df.empty:
            log_warning("Query returned no data.", tenant_id, conversation_id)
            return {"visualization_result": {"analysis": "I found no data to visualize for your request.", "image_base64": None}}

        # --- ENHANCED LOGGING: Log DataFrame details ---
        buffer = io.StringIO()
        df.info(buf=buffer)
        df_info_str = buffer.getvalue()
        log_info(f"--- DataFrame Details ---\nHead:\n{df.head().to_string()}\nInfo:\n{df_info_str}", tenant_id, conversation_id)

        # Step 3: Determine the best chart type
        df_info_for_prompt = f"Data Columns: {df.columns.tolist()}\nData Head:\n{df.head().to_string()}"
        chart_selection_prompt = f"""
        Given the user's original query '{query}' and the following data summary, what is the best chart type to use?
        Your answer must be a single word from this list: 'bar', 'line', 'scatter', 'pie'.

        Data Summary:\n{df_info_for_prompt}
        """
        chart_type = llm.invoke(chart_selection_prompt).content.strip().lower()
        log_info(f"LLM chose chart type: '{chart_type}'", tenant_id, conversation_id)

        # Step 4: Get structured textual analysis from the LLM
        # from .base import VisualizationAnalysis
        analysis_prompt = f"Analyze this data and provide a brief, insightful summary based on the user's original request: '{query}'.\n\nData:\n{df.to_csv(index=False)}"        
        
        try:
            structured_llm = llm.with_structured_output(VisualizationAnalysis)
            analysis_obj = structured_llm.invoke(analysis_prompt)
            
            # Format analysis_text for downstream use
            analysis_text = f"**Summary**: {analysis_obj.summary}\n\n**Key Points**:\n- " + "\n- ".join(analysis_obj.key_points)
            if analysis_obj.recommendation:
                analysis_text += f"\n\n**Recommendation**: {analysis_obj.recommendation}"
        except Exception as e:
            log_warning(f"Structured analysis failed: {e}. Falling back to standard output.", tenant_id, conversation_id)
            analysis_text = llm.invoke(analysis_prompt).content
            
        log_info(f"Generated Analysis: {analysis_text[:200]}...", tenant_id, conversation_id) # Log a snippet

        # Step 5: Generate the plot using intelligent chart selection
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(10, 6))
        numeric, categorical, dates = get_column_types(df)
        
        if chart_type == 'bar' and (categorical or dates) and numeric:
            x_col = dates[0] if dates else categorical[0]
            y_cols = [c for c in numeric if c != x_col]
            if not y_cols: y_cols = [numeric[0]] # Fallback
            
            if len(y_cols) > 1: # Handle multi-series bar charts
                df.set_index(x_col)[y_cols].plot(kind='bar', ax=ax, figsize=(12, 7))
                ax.set_ylabel("Values")
                ax.legend(title='Metrics')
            else: # Handle single-series bar charts
                y_col = y_cols[0]
                df.plot(kind='bar', x=x_col, y=y_col, ax=ax, legend=False)
                ax.set_ylabel(y_col.replace('_', ' ').title())
            ax.set_xlabel(x_col.replace('_', ' ').title())
            plt.xticks(rotation=45, ha='right')

        elif chart_type == 'line' and (dates or categorical or numeric):
            # Prioritize Date -> Categorical -> First Numeric for X axis
            x_col = dates[0] if dates else (categorical[0] if categorical else numeric[0])
            y_cols = [c for c in numeric if c != x_col]
            if not y_cols: y_cols = [numeric[0]] # Fallback if everything is numeric and x picked the first one
            
            df.plot(kind='line', x=x_col, y=y_cols, ax=ax, marker='o')
            ax.set_xlabel(x_col.replace('_', ' ').title())
            ax.set_ylabel("Value")
            plt.xticks(rotation=45, ha='right')

        elif chart_type == 'scatter' and len(numeric) >= 2:
            x_col, y_col = numeric[0], numeric[1]
            df.plot(kind='scatter', x=x_col, y=y_col, ax=ax)
            ax.set_xlabel(x_col.replace('_', ' ').title())
            ax.set_ylabel(y_col.replace('_', ' ').title())

        elif chart_type == 'pie' and categorical and numeric:
            df.set_index(categorical[0])[numeric[0]].plot(
                kind='pie', ax=ax, autopct='%1.1f%%', startangle=90
            )
            ax.set_ylabel('')
        
        else: # Fallback
            log_warning(f"Could not find a perfect chart match for type '{chart_type}'. Using generic plot.", tenant_id, conversation_id)
            df.plot(ax=ax)
       
        # Formatting common to all charts
        ax.set_title(query.title())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:,.0f}'))
        plt.tight_layout()
        
        # Step 6: Convert plot to base64
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close(fig)
        log_info(f"Successfully generated plot image (Base64 length: {len(image_base64)}).", tenant_id, conversation_id)
    except Exception as e:
        # --- ENHANCED LOGGING: Log the full exception traceback ---
        log_error(f"Error in visualization tool: {e}", tenant_id, conversation_id)
        analysis_text_on_error = analysis_text if analysis_text else f"Sorry, I encountered an unrecoverable error: {e}"
        return {"visualization_result": {"analysis": analysis_text_on_error, "image_base64": None}}
     
    # return {"visualization_result": {"analysis": analysis_text, "image_base64": image_base64}}   
    return {"visualization_result": {"analysis": analysis_text, "image_base64": image_base64}}
    # return Command(
    #     update={
    #         "visualization_image": image_base64,
    #         "visualization_analysis": analysis_text,
    #         "messages": [
    #             ToolMessage(
    #                 content=f"Visualization generated successfully. Analysis: {analysis_text}",
    #                 tool_call_id=tid,
    #                 name="generate_visualization_tool"
    #             )
    #         ]
    #     }
    # )

        
       
   


# --- FULLY ENHANCED VISUALIZATION TOOL ---



# --- END OF VISUALIZATION TOOLS ---

@before_model
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Keep only the last few messages to fit context window and trim base64 content."""
    messages = state["messages"]
    
    # 1. Trim base64 content from all messages to save memory/context
    
    base64_pattern = r"data:image\/.*?;base64,[a-zA-Z0-9+/=]{100,}"
    
    modified = False
    processed_messages = []
    for msg in messages:
        if hasattr(msg, "content") and isinstance(msg.content, str) and re.search(base64_pattern, msg.content):
            new_content = re.sub(base64_pattern, "[IMAGE_DATA_TRIMMED]", msg.content)
            # Reconstruct message to keep metadata but update content
            msg_type = type(msg)
            kwargs = {}
            for attr in ["tool_calls", "tool_call_id", "name", "id", "additional_kwargs"]:
                if hasattr(msg, attr):
                    kwargs[attr] = getattr(msg, attr)
            processed_messages.append(msg_type(content=new_content, **kwargs))
            modified = True
        else:
            processed_messages.append(msg)

    # 2. Trim message count if needed
    if len(processed_messages) <= 2:
        if modified:
            return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + processed_messages}
        return None  # No changes needed

    first_msg = processed_messages[0]
    recent_messages = processed_messages[-3:] if len(processed_messages) % 2 == 0 else processed_messages[-4:]
    final_messages = [first_msg] + recent_messages

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *final_messages
        ]
    }

from .banking_tools import banking_tools
admin_tools = [
    get_payslip_tool,
    fetch_available_leave_types_tool,
    validate_leave_balance_tool,
    prepare_leave_application_tool,
    calculate_num_of_days_tool,
    submit_leave_application_tool,
    search_job_opportunities_tool,
    fetch_leave_status_tool,
    search_travel_deals_tool,
    create_customer_profile_tool,
    get_customer_details_tool,
    generate_visualization_tool,
    sql_query_tool,
    pdf_retrieval_tool,
    web_search_tool,
]
tools = admin_tools + banking_tools