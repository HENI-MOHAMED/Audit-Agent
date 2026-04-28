from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
import os
from dotenv import load_dotenv

from src.utils.config import helper_llm, get_llm, MAX_TOOL_ITERATIONS
from src.api.models import invoice, AgentState
from src.tools.document_tools import search_web, scan_documents, Retreave_from_email, Retreave_from_google_drive, Retreave_from_whatsapp
from src.database.db_tools import retreave_information, store_data
from src.agents.audit_agents import call_retriever_agent, call_audit_agent, call_calculation_agent, base_tools
from src.agents.invoice_nodes import  finalize_node, supplier_verification_node, purchase_order_verification_node, inventory_order_verification_node, tax_verification_node, payment_verification_node, audit_agent, ai_review_node
from src.agents.local_db_nodes import local_db, local_db_agent, local_db_terminology_agent, process_emails_agent

load_dotenv()

# ─── Global checkpointer (single instance) ───
checkpointer = MemorySaver()


# ─── Shared nodes ───




def Main_AI(state: AgentState) -> AgentState:
    """Main AI Node that processes the conversation and generates responses."""
    print(f"Main AI Agent processing with thinking mode: {state['thinking_mode']}...")
    print(f"Current conversation history: {[msg.content for msg in state['messages'] if not isinstance(msg, SystemMessage)] }")
    _MAIN_SYSTEM_PROMPT = SystemMessage(
content=f"""
You are the Main AI Agent – Tax and Audit Expert in Tunisia (Year: 2026).
{""" Limits (tools credits):
- scan_documents : as much as you want. only used when you have the file path.(you won't be using this often)
- Retreave_from_email : only 2 time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only 2 time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only 3 times.
 -db_connector : only 5 time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
- retreave_information : only 5 time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need. it take as input a query and the collection name to search in.
        . query is the information you want to retreave  and the collection_name is the name of the collection, you have tow collections you can search in, the first one is 'audit_documets_better_embeddings' use it to retreave the information about the law in tunisia,
        . the second collection is 'past_conversations_summaries' use it to retreave the information from the past conversations with the user, this can help you to have more context about the company and the user needs.
""" if state['thinking_mode'] == 'fast' else """ You coordinate helper agents and use tools when necessary.
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
Always provide structured, professional responses."""}



Execution Control & Anti-Loop Rules:
- Never call the same tool twice with the exact same query.
- Do not re-request information already retrieved unless new missing elements are clearly identified.
- Do not perform recursive verification of already validated data.
- Only trigger another tool if a specific data gap prevents completion.
- If the objective of the user request has been achieved, terminate execution.
- After producing the final structured response, STOP.
"""
)
    if state["thinking_mode"] == "fast":
        main_llm = get_llm().bind_tools(base_tools)
    elif state["thinking_mode"] in ["thinking", "deep_dive"]:
        main_llm = get_llm().bind_tools(all_tools)
        
    current_messages = list(state["messages"])
    if not any(isinstance(msg, SystemMessage) for msg in current_messages):
        current_messages.insert(0, _MAIN_SYSTEM_PROMPT)
        
    response = main_llm.invoke(current_messages)
    print(f" \n \n Main AI Agent Response: {response.content} \n \n")
    
    from src.utils.stream_utils import get_emitter
    emitter = get_emitter()
    if emitter and getattr(response, "tool_calls", None):
        for tc in response.tool_calls:
            emitter.emit_tool_call(tc["name"], tc["args"])
            
    return {"messages": [response]}


def exit_agent(state: AgentState) -> AgentState:
    """Saves the conversation history and deletes the current state to prepare for a new conversation."""
    print("Saving conversation summary and resetting state for new conversation...")
    system_message = SystemMessage(content="Create a very detailed summary of the conversation, including all the important information, insights, and conclusions." \
    "Then use the store_data tool to save the summary in the database. use the collection name 'past_conversations_summaries' and the persist directory './chroma_db_multilingual'. ")
    exit_llm = get_llm().bind_tools([store_data])
    
    # We create a local list of messages for the LLM to process without mutating the actual state.
    # Mutating `state["messages"]` here will trigger the reducer when we pass it back, causing duplicate history bugs.
    # We also remove messages with role "tool" since they might not have a matching AIMessage with tool_calls in the filtered history, which crashes OpenAI.
    chat_history = [
        msg for msg in state["messages"]
        if not isinstance(msg, SystemMessage) and not isinstance(msg, ToolMessage) and not (hasattr(msg, "tool_calls") and msg.tool_calls)
    ] + [HumanMessage(content="The conversation has ended. Please summarize the conversation and store it for future reference.")]
    
    print(f"Conversation history to summarize: {[msg.content for msg in chat_history]}")
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = exit_llm.invoke([system_message] + chat_history)
        print(f"Exit Agent Response: {response.content}")
        if not response.tool_calls:
            break
            
        chat_history.append(response)
        
        for tc in response.tool_calls:
            tool_fn = next((t for t in [store_data] if t.name == tc["name"]), None)
            if tool_fn is None:
                chat_history.append(ToolMessage(content=f"Error: Unknown tool '{tc['name']}'", tool_call_id=tc["id"]))
                continue
            result = tool_fn.invoke(tc["args"])
            chat_history.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
            
    # Do not return state["messages"] here, let the state persist normally. 
    # Or if you want to clear it, just return it in the format the reducer expects.
    return {"messages": []}


class StreamingToolNode(ToolNode):
    def invoke(self, input, config=None, **kwargs):
        results = super().invoke(input, config, **kwargs)
        from src.utils.stream_utils import get_emitter
        emitter = get_emitter()
        if emitter and "messages" in results:
            for msg in results["messages"]:
                if hasattr(msg, "name") and msg.name:
                    emitter.emit_tool_result(msg.name, msg.content)
        return results

# ─── All tools for Main AI ───
all_tools = base_tools + [call_retriever_agent, call_calculation_agent, call_audit_agent, store_data]


# ═══════════════════════════════════════════════════
#  SINGLE GRAPH with route-based conditional edges
# ═══════════════════════════════════════════════════
#
#  The `route` field in AgentState determines which branch to take.
#  Set by the API layer before calling graph.invoke().
#
#  START → router_node ─┬─ "chat"     → main_ai_node ↔ tools_node → END
#                        ├─ "audit"    → audit_agent → supplier → PO → inventory → tax → payment → END
#                        ├─ "local_db" → local_db → local_db_terminology_node → END
#                        ├─ "upload"   → local_db_agent → END
#                        └─ "exit"     → exit_agent → END


def scan_invoices_node(state: AgentState) -> AgentState:
    """Wrapper node for simple extraction without verification."""
    # This runs the standard audit_agent which parses docs and updates state["invoces"]
    return audit_agent(state)


def router_node(state: AgentState) -> AgentState:
    """Pass-through node that sets up state for routing.
    The actual routing is done by the conditional edge reading state['route'].
    """
    return state


def _route_by_field(state: AgentState) -> str:
    """Read state['route'] and return the next node name."""
    route = state.get("route", "chat")
    route_map = {
        "chat": "main_ai_node",
        "audit": "audit_agent",
        "scan_invoice": "scan_invoices_node",
        "local_db": "local_db",
        "terminology": "local_db_terminology_node",
        "upload": "local_db_agent",
        "exit": "exit_agent",
        "email_sync": "process_emails_agent",
    }
    return route_map.get(route, "main_ai_node")


def _chat_should_continue(state: AgentState) -> str:
    """Route inside chat branch: tools loop or finish."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_node"
    return "end"


# ─── Build the single graph ───
graph = StateGraph(AgentState)

# Nodes
graph.add_node("router_node", router_node)
graph.add_node("main_ai_node", Main_AI)
graph.add_node("tools_node", StreamingToolNode(tools=all_tools))
graph.add_node("audit_agent", audit_agent)
graph.add_node("supplier_verification_node", supplier_verification_node)
graph.add_node("purchase_order_verification_node", purchase_order_verification_node)
graph.add_node("inventory_order_verification_node", inventory_order_verification_node)
graph.add_node("tax_verification_node", tax_verification_node)
graph.add_node("payment_verification_node", payment_verification_node)
graph.add_node("local_db", local_db)
graph.add_node("local_db_terminology_node", local_db_terminology_agent)
graph.add_node("local_db_agent", local_db_agent)
graph.add_node("exit_agent", exit_agent)
graph.add_node("process_emails_agent", process_emails_agent)
graph.add_node("ai_verification_node", ai_review_node)
graph.add_node("finalize_node", finalize_node)
graph.add_node("scan_invoices_node", scan_invoices_node)

# START → router
graph.add_edge(START, "router_node")

# Router → conditional branch based on state["route"]
graph.add_conditional_edges(
    "router_node",
    _route_by_field,
    {
        "main_ai_node": "main_ai_node",
        "audit_agent": "audit_agent",
        "scan_invoices_node": "scan_invoices_node",
        "local_db": "local_db",
        "local_db_terminology_node": "local_db_terminology_node",
        "local_db_agent": "local_db_agent",
        "exit_agent": "exit_agent",
        "process_emails_agent": "process_emails_agent",
    },
)

# ── Chat branch: main_ai ↔ tools loop → END
graph.add_conditional_edges(
    "main_ai_node",
    _chat_should_continue,
    {"tools_node": "tools_node", "end": END},
)
graph.add_edge("tools_node", "main_ai_node")

# ── Scan invoices branch: standalone → END
graph.add_edge("scan_invoices_node", END)

# ── Audit branch: linear pipeline → END
graph.add_edge("audit_agent", "supplier_verification_node")
graph.add_edge("supplier_verification_node", "purchase_order_verification_node")
graph.add_edge("purchase_order_verification_node", "inventory_order_verification_node")
graph.add_edge("inventory_order_verification_node", "tax_verification_node")
graph.add_edge("tax_verification_node", "payment_verification_node")
graph.add_edge("payment_verification_node", "ai_verification_node")
graph.add_edge("ai_verification_node", "finalize_node")
graph.add_edge("finalize_node", END)

# ── Local DB branch: sync → terminology → END
graph.add_edge("local_db", "local_db_terminology_node")
graph.add_edge("local_db_terminology_node", END)

# ── Upload branch: local_db_agent → END
graph.add_edge("local_db_agent", END)

# ── Exit branch: exit_agent → END
graph.add_edge("exit_agent", END)

# ── Email sync branch: process_emails_agent → END
graph.add_edge("process_emails_agent", END)

# ─── Compile single graph with checkpointer ───

app = graph.compile(checkpointer=checkpointer)


# ═══════════════════════════════════════════════════
#  CLI entry point (only runs when executed directly)
# ═══════════════════════════════════════════════════

def _cli_input_node(state: AgentState) -> AgentState:
    """Takes user input and adds it to the conversation history (CLI only)."""
    user_input = input("User: ")
    state["user_input"] = user_input
    state["messages"].append(HumanMessage(content=user_input))
    if "invoces" not in state or state["invoces"] is None:
        state["invoces"] = []
    return state


def _cli_should_continue(state: AgentState) -> str:
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


def _cli_get_local_db_documents(state: AgentState) -> AgentState:
    """CLI-only node that reads file paths from stdin."""
    doc = str(input("Enter the file path of the document to process for the local database (or 'done' to finish): "))
    files = []
    while doc.lower() != 'done':
        if os.path.exists(doc):
            files.append(doc)
            print(f"Added '{doc}' for processing.")
        else:
            print(f"File '{doc}' not found. Please enter a valid file path.")
        doc = str(input("Enter the file path of the document to process for the local database (or 'done' to finish): "))
    state["local_db_files"] = files
    return state


if __name__ == "__main__":
    # Build the full CLI graph with input() loops
    cli_graph = StateGraph(AgentState)
    cli_graph.add_node("user_input_node", _cli_input_node)
    cli_graph.add_node("main_ai_node", Main_AI)
    cli_graph.add_node("tools_node", StreamingToolNode(tools=all_tools))
    cli_graph.add_node("exit_agent", exit_agent)
    cli_graph.add_node("audit_agent", audit_agent)
    cli_graph.add_node("supplier_verification_node", supplier_verification_node)
    cli_graph.add_node("local_db", local_db)
    cli_graph.add_node("get_local_db_documents", _cli_get_local_db_documents)
    cli_graph.add_node("local_db_agent", local_db_agent)
    cli_graph.add_node("local_db_terminology_node", local_db_terminology_agent)
    cli_graph.add_node("purchase_order_verification_node", purchase_order_verification_node)
    cli_graph.add_node("inventory_order_verification_node", inventory_order_verification_node)
    cli_graph.add_node("tax_verification_node", tax_verification_node)
    cli_graph.add_node("payment_verification_node", payment_verification_node)
    cli_graph.add_edge(START, "user_input_node")
    cli_graph.add_conditional_edges(
        "main_ai_node",
        _cli_should_continue,
        {"tools_node": "tools_node", "end": "user_input_node"},
    )
    cli_graph.add_conditional_edges(
        "user_input_node",
        _cli_should_continue,
        {
            "main_ai_node": "main_ai_node",
            "audit_node": "audit_agent",
            "local_db_node": "local_db",
            "upload_docs": "get_local_db_documents",
            "exit": "exit_agent",
        },
    )
    cli_graph.add_edge("exit_agent", "user_input_node")
    cli_graph.add_edge("tools_node", "main_ai_node")
    cli_graph.add_edge("audit_agent", "supplier_verification_node")
    cli_graph.add_edge("supplier_verification_node", "purchase_order_verification_node")
    cli_graph.add_edge("purchase_order_verification_node", "inventory_order_verification_node")
    cli_graph.add_edge("inventory_order_verification_node", "tax_verification_node")
    cli_graph.add_edge("tax_verification_node", "payment_verification_node")
    cli_graph.add_edge("payment_verification_node", "user_input_node")
    cli_graph.add_edge("local_db", "local_db_terminology_node")
    cli_graph.add_edge("local_db_terminology_node", "user_input_node")
    cli_graph.add_edge("get_local_db_documents", "local_db_agent")
    cli_graph.add_edge("local_db_agent", "user_input_node")
    cli_app = cli_graph.compile()

    result = cli_app.invoke({"messages": [], "user_input": "", "invoces": [], "local_db_files": [], "db_source": "odoo", "company_info": {'company_name': 'my company'}, "route": "chat"})
    print("Final Response from Main AI Agent:")
    print(result["messages"][-1].content)