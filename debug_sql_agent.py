import os
import sys
import dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from chat_bot import get_model

def run_debug():
    db_uri = "postgresql+psycopg://vectra:vectra_agoba@147.182.194.8:5433/vectra?sslmode=disable"
    engine = create_engine(db_uri)
    db = SQLDatabase(engine)
    llm = get_model()
    
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    sql_tools = toolkit.get_tools()
    
    SQL_SYSTEM_PROMPT = """
You are an expert data analyst assistant. Your task is to:
1. Search the database schema to find the MOST relevant tables (e.g., payroll_payslip, employees_employee).
2. Create a syntactically correct {dialect} query to answer the question.
3. Execute the query and capture the results.
4. Return your final answer EXCLUSIVELY as a JSON object inside a code block.

CRITICAL INSTRUCTIONS TO PREVENT LOOPS:
- DO NOT call `sql_db_list_tables` more than once!
- After receiving the list of tables, immediately pick the 1-3 most relevant tables and call `sql_db_schema` to see their columns.
- DO NOT hallucinate column names.

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
"""

    agent = create_react_agent(
        llm,
        sql_tools,
        prompt=SQL_SYSTEM_PROMPT.format(dialect=db.dialect),
    )

    print("Starting agent stream. We will pass a recurring error back if we hit strange behavior.")
    # Set recursion limit low to prevent getting completely frozen
    config = {"recursion_limit": 10}
    
    messages = [HumanMessage(content="Give me the count of transactions per month for the last three months.")]
    step_count = 0
    try:
        for step in agent.stream({"messages": messages}, config=config):
            step_count += 1
            print(f"\n======== STEP {step_count} ========")
            if "agent" in step:
                msg = step["agent"]["messages"][-1]
                print(f"AGENT TOOL CALLS: [{len(getattr(msg, 'tool_calls', []))} calls]")
                for tc in getattr(msg, 'tool_calls', []):
                    print(f"  -> {tc['name']}({tc.get('args')})")
                print(f"AGENT CONTENT: {repr(msg.content[:500])}")
            elif "tools" in step:
                for tool_msg in step["tools"]["messages"]:
                    print(f"TOOLS OUTPUT [{tool_msg.name}]: {repr(tool_msg.content[:500])}")
            else:
                print(step)
    except Exception as e:
        print("\n=== FATAL GRAPH ERROR ===")
        print(e)

if __name__ == "__main__":
    run_debug()
