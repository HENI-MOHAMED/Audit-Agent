from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode
import os
from dotenv import load_dotenv

from config import helper_llm, MAX_TOOL_ITERATIONS
from models import invoice, AgentState
from document_tools import search_web, scan_documents, Retreave_from_email, Retreave_from_google_drive, Retreave_from_whatsapp
from DataBase.db_tools import retreave_information, store_data
from audit_agents import call_retriever_agent, call_audit_agent, call_calculation_agent, base_tools
from invoice_nodes import  supplier_verification_node, purchase_order_verification_node, inventory_order_verification_node, tax_verification_node, payment_verification_node, audit_agent
from local_db_nodes import local_db, local_db_agent, get_local_db_documents, local_db_terminology_agent

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"), base_url='https://api.openai.com/v1', temperature=0)

# Use input Node
def input_node(state: AgentState) -> AgentState:
    """Takes user input and adds it to the conversation history."""
    user_input = input("User: ")
    state["user_input"] = user_input
    state["messages"].append(HumanMessage(content=user_input))
    if "invoces" not in state or state["invoces"] is None:
        state["invoces"] = []
    return state

# Pre-build the system prompt once (avoid recreating every call)
_MAIN_SYSTEM_PROMPT = SystemMessage(
content="""
You are the Main AI Agent – Tax and Audit Expert in Tunisia (Year: 2026).

You coordinate helper agents and use tools when necessary.

Available helper tools:
- call_retriever_agent
- call_calculation_agent
- call_audit_agent

General Responsibilities:
- Analyze the user request.
- Decide which helper agent to call. 
- Provide clear, detailed instructions.
- Use returned information to produce the final response.

Tool Usage Guidelines:
- Use call_retriever_agent to retrieve laws, regulations, company data, invoices, email data, or Google Drive data.
- Use call_calculation_agent for financial or tax calculations.
- Use call_audit_agent when an invoice file_path is provided and a full audit is required.

The retriever agent is the primary source of external information.
Other tools may also use additional tools internally if needed.

Do not repeat the same request unnecessarily.
If sufficient information is available, provide the final answer.
Always provide structured, professional responses.

Execution Control & Anti-Loop Rules:
- Never call the same tool twice with the exact same query.
- Do not re-request information already retrieved unless new missing elements are clearly identified.
- Do not perform recursive verification of already validated data.
- Only trigger another tool if a specific data gap prevents completion.
- If the objective of the user request has been achieved, terminate execution.
- After producing the final structured response, STOP.
"""
)

# Main AI Node
def Main_AI(state: AgentState)-> AgentState:
    """Main AI Node that processes the conversation and generates responses."""
    if not any(isinstance(msg, SystemMessage) for msg in state["messages"]):
        state["messages"].insert(0, _MAIN_SYSTEM_PROMPT)
    response = llm.invoke(state["messages"])
    print(f" \n \n Main AI Agent Response: {response.content} \n \n")
    return {"messages": state["messages"] + [response]}

def should_continue(state: AgentState) -> str:
    """Route to tools or end based on whether the LLM made tool calls."""
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage) and last_message.content.lower() in ["exit", "quit", "end"]:
        return "exit"
    if isinstance(last_message, HumanMessage) and "/audit" in last_message.content.lower():
        return "audit_node"
    if isinstance(last_message, HumanMessage) and "/local_db" in last_message.content.lower():
        return "local_db_node"
    if isinstance(last_message, HumanMessage) and "/upload_docs" in last_message.content.lower():
        return "upload_docs"
    if isinstance(last_message, HumanMessage):
        return "main_ai_node"
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_node"
    return "end"


# Save and Restart Node
def exit_agent(state: AgentState) -> AgentState:
    """Saves the conversation history and deletes the current state to prepare for a new conversation."""
    print("Saving conversation summary and resetting state for new conversation...")
    system_message = SystemMessage(content="Create a very detailed summary of the conversation, including all the important information, insights, and conclusions." \
    "Then use the store_data tool to save the summary in the database. use the collection name 'past_conversations_summaries' and the persist directory './chroma_db_multilingual'. ")
    exit_llm = llm.bind_tools([store_data])
    state["messages"] = [msg for msg in state["messages"] if not isinstance(msg, SystemMessage)] 
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = exit_llm.invoke([system_message] + state["messages"])
        if not response.tool_calls:
            break
        for tc in response.tool_calls:
            tool_fn = next((t for t in [store_data] if t.name == tc["name"]), None)
            if tool_fn is None:
                state["messages"].append(ToolMessage(content=f"Error: Unknown tool '{tc['name']}'", tool_call_id=tc["id"]))
                continue
            result = tool_fn.invoke(tc["args"])
            state["messages"].append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    # Clear the state for a new conversation
    state["messages"] = []
    return state

# ─── All tools for Main AI (includes helper agents as tools) ───
all_tools = base_tools + [call_retriever_agent, call_calculation_agent, call_audit_agent, store_data]
llm = llm.bind_tools(all_tools)

# ─── Graph: Simple Main_AI → ToolNode → Main_AI loop ───
graph = StateGraph(AgentState)
graph.add_node("user_input_node", input_node)
graph.add_node("main_ai_node", Main_AI)
graph.add_node("tools_node", ToolNode(tools=all_tools))
graph.add_node("exit_agent", exit_agent)
graph.add_node("audit_agent", audit_agent)
graph.add_node("supplier_verification_node", supplier_verification_node)
graph.add_node("local_db", local_db)
graph.add_node("get_local_db_documents", get_local_db_documents)
graph.add_node("local_db_agent", local_db_agent)
graph.add_node("local_db_terminology_node", local_db_terminology_agent)
graph.add_node("purchase_order_verification_node", purchase_order_verification_node)
graph.add_node("inventory_order_verification_node", inventory_order_verification_node)
graph.add_node("tax_verification_node", tax_verification_node)
graph.add_node("payment_verification_node", payment_verification_node)
graph.add_edge(START, "user_input_node")
graph.add_conditional_edges(
    "main_ai_node",
    should_continue,
    {
        "tools_node": "tools_node",
        "end": 'user_input_node'
    }
)
graph.add_conditional_edges(
    "user_input_node",
    should_continue,
    {
        "main_ai_node": "main_ai_node",
        "audit_node": "audit_agent",
        "local_db_node": "local_db",
        "upload_docs": "get_local_db_documents",
        "exit": "exit_agent"
    }
)
graph.add_edge("exit_agent", "user_input_node")
graph.add_edge("tools_node", "main_ai_node")
graph.add_edge("audit_agent", "supplier_verification_node")
graph.add_edge("supplier_verification_node", "purchase_order_verification_node")
graph.add_edge("purchase_order_verification_node", "inventory_order_verification_node")
graph.add_edge("inventory_order_verification_node", "tax_verification_node")
graph.add_edge("tax_verification_node", "payment_verification_node")
graph.add_edge("payment_verification_node", "user_input_node")
graph.add_edge("local_db", "local_db_terminology_node")
graph.add_edge("local_db_terminology_node", "user_input_node")
graph.add_edge("get_local_db_documents", "local_db_agent")
graph.add_edge("local_db_agent", "user_input_node")
app = graph.compile()

result = app.invoke({"messages": [], "user_input": "", "invoces": [], "local_db_files": [], "db_source": "odoo", "company_info": {'company_name': 'my company'}})

print("Final Response from Main AI Agent:")
print(result["messages"][-1].content)