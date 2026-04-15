from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated
from langgraph.prebuilt import InjectedState

from src.utils.config import get_helper_llm, MAX_TOOL_ITERATIONS, helper_llm_resoner
from src.tools.document_tools import search_web, scan_documents, Retreave_from_email, Retreave_from_google_drive, Retreave_from_whatsapp
from src.database.db_tools import retreave_information, db_connector
from src.api.models import AgentState
from src.utils.stream_utils import get_emitter

# ─── Base tools list (used internally by helper agents) ───
base_tools = [search_web, retreave_information, scan_documents, Retreave_from_email, Retreave_from_google_drive, Retreave_from_whatsapp, db_connector]
_base_tool_map = {t.name: t for t in base_tools}  # O(1) lookup


def _execute_tool_calls_parallel(tool_calls: list, tool_map: dict, agent_name: str = "agent") -> list[ToolMessage]:
    """Execute multiple tool calls in parallel using threads. Falls back to sequential for single calls."""
    emitter = get_emitter()
    if len(tool_calls) == 1:
        tc = tool_calls[0]
        if emitter: emitter.emit_agent_tool_call(agent_name, tc["name"], tc["args"])
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            err = f"Error: Unknown tool '{tc['name']}'"
            if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], err)
            return [ToolMessage(content=err, name=tc["name"], tool_call_id=tc["id"])]
        result = tool_fn.invoke(tc["args"])
        if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], str(result))
        return [ToolMessage(content=str(result), name=tc["name"], tool_call_id=tc["id"])]

    results = {}
    def _run(tc):
        if emitter: emitter.emit_agent_tool_call(agent_name, tc["name"], tc["args"])
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            err = f"Error: Unknown tool '{tc['name']}'"
            if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], err)
            return tc["id"], tc["name"], err
        res = str(tool_fn.invoke(tc["args"]))
        if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], res)
        return tc["id"], tc["name"], res

    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
        futures = {executor.submit(_run, tc): tc for tc in tool_calls}
        for future in as_completed(futures):
            tc_id, name, content = future.result()
            results[tc_id] = (name, content)

    # Return in original order
    return [ToolMessage(content=results[tc["id"]][1], name=results[tc["id"]][0], tool_call_id=tc["id"]) for tc in tool_calls]


# ─── Helper Agent: Retriever (as a tool) ───
@tool
def call_retriever_agent(query: str, state: Annotated[AgentState, InjectedState]) -> str:
    """A helper AI agent that retrieves information from the database, web, email, Google Drive and other sources.
    Give it a detailed query with instructions about what information to retrieve. It will decide the best sources,
    retrieve the information, verify it, and return a clear summary. Use this for tax laws, audit procedures,
    financial regulations, company info, invoices, etc.
    NOTE: This tool does not accept a file_path — if the task does not need file retrieval, write 'this query does not need a file path'."""
    print(" \n \n Retrever Agent is processing the request... wtih the query: " + query + "\n \n")
    emitter = get_emitter()
    if emitter: emitter.emit_agent_start("Retriever Agent")
    system_prompt = SystemMessage(
content=f"""
You are a Retrieval Agent supporting the Main AI (Year: 2026).

Your mission:
Retrieve and process information related to:
- Tunisian tax laws
- Financial laws
- Audit procedures
- Financial regulations
- Company information
- Invoices
- Email data
- Google Drive documents

Process:
1. Determine the best source (database, web, email, drive).
2. Retrieve relevant information.
3. Verify credibility (prefer multiple reliable sources when possible).
4. Clean and structure the information.
5. Include law names, articles, and official sources when applicable.
6. Return a concise and structured summary.

Rules:
- No conversation.
- No questions.
- No commentary.
- No unnecessary explanation.
- Only relevant verified information.
- Output must be clear and structured for AI consumption.
- If you used all your tools credits or you have 0 to begin with, don't use that tool at all even if the main ai asked you just use what you have nothing else.so be wise with your tools querys.

Execution Control & Anti-Loop Rules:
- Do not repeat the same search query.
- Do not broaden the scope unless explicitly required by the Main AI request.
- If sufficient verified information is found, STOP. There is no need to use all your tools and credits, if the information you have are enough, stop and return the information. don't use all you got just for simple information.THIS IS VERY IMPORTANT.
- If information cannot be verified, clearly state limitations and STOP.
- Do not perform recursive or continuous searching.

Limits (tools credits):
- scan_documents : as much as you want. only used when you have the file path.(you won't be using this often)
- Retreave_from_email : only {"2" if state['thinking_mode'] == "thinking" else "4"} time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only {"2" if state["thinking_mode"] == "thinking" else "4"} time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only {"2" if state["thinking_mode"] == "thinking" else "7"} times.
- retreave_information : only {"2" if state["thinking_mode"] == "thinking" else "5"} time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
- db_connector : only {"3" if state["thinking_mode"] == "thinking" else "5"} time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
"""
)
    
    msgs = [system_prompt, HumanMessage(content=query)]
    # Internal tool loop: let helper_llm call tools until it gives a final answer
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = retriever_llm.invoke(msgs)
        print(f"Retriever Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        # Execute independent tool calls in parallel
        tool_results = _execute_tool_calls_parallel(response.tool_calls, _base_tool_map, agent_name="Retriever Agent")
        msgs.extend(tool_results)
    else:
        print("WARNING: Retriever Agent reached maximum tool iterations.")
    print(f"\n \n Retrever Agent Response: {response.content} \n \n RETRIEVED INFORMATION END \n \n")
    if emitter: emitter.emit_agent_done("Retriever Agent", response.content)
    return response.content


# ─── Helper Agent: Calculation (as a tool) ───
@tool
def call_calculation_agent(query: str, state: Annotated[AgentState, InjectedState]) -> str:
    """A helper AI agent that performs tax, audit, and financial calculations.
    Give it detailed instructions about what to calculate and what information to use.
    It can also retrieve information on its own using the retriever agent or other tools if needed.
    It returns a detailed explanation of the calculation steps and the final result.
    NOTE: This tool does not accept a file_path — if the task does not need a file, write 'this query does not need a file path'."""
    print(" \n \n Calculation Agent is processing the request...with query: " + query + "\n \n")
    emitter = get_emitter()
    if emitter: emitter.emit_agent_start("Calculation Agent")
    system_prompt = SystemMessage(
content=f"""
You are a Financial Calculation Agent supporting the Main AI (Year: 2026).

Your mission:
Perform calculations based on the Main AI request.

Process:
1. Analyze the calculation request.
2. Determine required data.
3. Retrieve the necessary data (prefer call_retriever_agent).
4. Perform accurate calculations.
5. Provide detailed step-by-step explanation.
6. Present final result clearly.

You may use available tools if needed.
You may rely on retriever_agent for financial data, invoice data, tax rates, or regulations.

Rules:
- No conversation.
- No questions.
- No unrelated commentary.
- Clearly show formulas used.
- Provide final numerical result.
- If you used all your tools credits or you have 0 to begin with, don't use that tool at all even if the main ai asked you just use what you have nothing else.so be wise with your tools querys. NEVER USE TOOLS WITHOUT CREDITS.

Execution Control & Anti-Loop Rules:
- Do not re-calculate unless new input data is introduced.
- If sufficient data is available, proceed directly to calculation.
- Once the final calculation result is produced, STOP.

Limits:
- call_retriever_agent : you can use this tool only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information. (it's not made for calculations, that your job)
- scan_documents : as much as you want.
- Retreave_from_email : only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only {"1" if state['thinking_mode'] == "thinking" else "3"} times.
- retreave_information : only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
"""
)
    retriever_llm = get_helper_llm().bind_tools(base_tools)
    calc_llm = get_helper_llm().bind_tools(calc_tools)
    msgs = [system_prompt, HumanMessage(content=query)]
    # Internal tool loop: let helper_llm call tools until it gives a final answer
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = calc_llm.invoke(msgs)
        print(f"Calculation Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, _calc_tool_map, agent_name="Calculation Agent")
        msgs.extend(tool_results)
    else:
        print("WARNING: Calculation Agent reached maximum tool iterations.")
    print(f"\n \n Calculation Agent Response: {response.content} \n \n CALCULATION END \n \n")
    if emitter: emitter.emit_agent_done("Calculation Agent", response.content)
    return response.content


# ─── Helper Agent: Audit (as a tool) ───
@tool
def call_audit_agent(query: str, file_path: str, state: Annotated[AgentState, InjectedState]) -> str:
    """A helper AI agent that performs invoice audit procedures, fraud detection, tax compliance checks, and tax optimization.
    'query': instructions and context about what to audit.
    'file_path': REQUIRED - the exact path to the invoice file (e.g. 'email_attachments/sender/invoice.pdf').
    It will scan the invoice at file_path, cross-check with the database, email, and Google Drive,
    verify compliance with Tunisian tax laws, detect fraud indicators, and produce a full audit report
    with optimization recommendations."""
    print(" \n \n Audit Agent is processing the request... with the query: \n \n", query, "\n file_path:", file_path, "\n \n")
    emitter = get_emitter()
    if emitter: emitter.emit_agent_start("Audit Agent")
    system_prompt = SystemMessage(
content=f"""
You are the Audit Agent – Tunisian Invoice Audit & Tax Optimization Specialist (Year: 2026).

Mission:
Perform a full audit of the invoice provided via file_path.

Procedure:

1. Use scan_documents to extract invoice data.
2. Retrieve company database information.(no need for this if the invoice is personal, but if the invoice is for a company, then you need to retreave information about the company from the database to verify the authenticity of the transaction and the compliance of the invoice with the tax laws and regulations).
3. Retrieve related email records.
4. Retrieve related Google Drive documents.
5. Verify transaction authenticity:
   - Confirm supplier existence.
   - Confirm customer existence.
   - Confirm transaction legitimacy.
   - Detect inconsistencies (price, quantity, date, duplication).

6. Retrieve All the data you need using call_retriever_agent.(use your own tools if you need to retreave more information, but prefer call_retriever_agent to retreave information from the database and web, email and google drive).

7. Verify compliance with:
   - Direction Générale des Impôts
   - Code de la TVA
   - Code de l'IRPP et de l'IS
8. Identify:
   - Missing legal mentions
   - VAT errors
   - Deductibility issues
   - Accounting misclassification
   - Fraud indicators

9. If calculations are required, use call_calculation_agent.
10. Provide correction steps if non-compliant.
11. Identify tax optimization opportunities.
12. Produce a complete structured audit report.

Report must include:
- Header Section
- Executive Summary
- Legal Compliance Verification
- VAT Validation
- Accounting Classification Review
- Tax Optimization Opportunities
- Fraud & Risk Indicators
- Financial Impact Summary
- Final Recommendation

Rules:
- Be precise and structured.
- Do not repeat retrieval unnecessarily.
- Base conclusions on verified data.
- Do not include internal reasoning.
- Output only the final audit report.
- Don't just copy paste retrieved information — analyze and synthesize it into insights.and compare the info with the invoice.
- If you used all your tools credits or you have 0 to begin with, don't use that tool at all even if the main ai asked you just use what you have nothing else.

Execution Control & Anti-Loop Rules:
- Scan the invoice only once.
- Do not retrieve the same database, email, drive, or legal information more than once unless new inconsistencies are detected.
- Do not continuously re-verify already confirmed elements.
- If enough information exists to complete the audit, proceed directly to report generation.
- Do not restart the audit cycle.
- After generating the final audit report, STOP execution completely.

Limits:
- call_retriever_agent : you can use this tool only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information so the query must be fully specified and and contain every single thing you need or your going to need, try not to use it the scend time at all, only if you are sure that you need to retreave more information that you did not retreave the first time and that is essential for the audit, so use it wisely to retreave all the information you need from the database, web, email and google drive about the company or depend on what you need.
- call_calculation_agent : you can use this tool only 1 time, so use it wisely to perform all the calculations you need.
- scan_documents : as much as you want.
- Retreave_from_email : only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only {"1" if state['thinking_mode'] == "thinking" else "5"} times.
- retreave_information : only {"1" if state['thinking_mode'] == "thinking" else "2"} time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
"""
)
    msgs = [system_prompt, HumanMessage(content=f"{query} (file path: {file_path})")]
    # Internal tool loop: let audit_llm call tools until it gives a final answer
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = audit_llm.invoke(msgs)
        print(f"Audit Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, _audit_tool_map, agent_name="Audit Agent")
        msgs.extend(tool_results)
    else:
        print("WARNING: Audit Agent reached maximum tool iterations.")
    print(f"\n \n Audit Agent Response: {response.content} \n \n AUDIT REPORT END \n \n")
    if emitter: emitter.emit_agent_done("Audit Agent", response.content)
    return response.content



# ─── Pre-bind helper LLMs once (avoid re-binding on every agent call) ───
# _retriever_llm = ...
retriever_llm = get_helper_llm().bind_tools(base_tools)

audit_tools = base_tools + [call_retriever_agent, call_calculation_agent]
_audit_tool_map = {t.name: t for t in audit_tools}
audit_llm = get_helper_llm().bind_tools(audit_tools)
# _audit_llm = ...

calc_tools = base_tools + [call_retriever_agent]
_calc_tool_map = {t.name: t for t in calc_tools}
# _calc_llm = ...
calc_llm = helper_llm_resoner.bind_tools(calc_tools)