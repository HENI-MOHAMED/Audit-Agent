from typing import TypedDict, Sequence, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.documents import Document
from operator import add as add_message
from langgraph.graph import StateGraph, START
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
import os
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

load_dotenv()

MAX_TOOL_ITERATIONS = 15  # Safety limit for helper agent tool loops

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"), base_url='https://api.openai.com/v1', temperature=0)
helper_llm = ChatDeepSeek(model="deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"), base_url='https://api.deepseek.com', temperature=0)
# helper_llm = llm

class invoice:
    def __init__(self, invoice_number: str, note: str, invoice_data: dict, state:str):
        self.invoice_number = invoice_number
        self.note = note
        self.state = state
        self.invoice_data = invoice_data
        self.audits_results = {'supplier_authenticity': None}
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_message]
    user_input: str
    invoces: list[invoice]
    local_db_files: list[str]
    db_source: str
    company_info: dict


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
    if isinstance(last_message, HumanMessage) and "/scan" in last_message.content.lower():
        return "scan_invoice_node"
    if isinstance(last_message, HumanMessage) and "/local_db" in last_message.content.lower():
        return "local_db_node"
    if isinstance(last_message, HumanMessage) and "/upload_docs" in last_message.content.lower():
        return "upload_docs"
    if isinstance(last_message, HumanMessage):
        return "main_ai_node"
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_node"
    return "end"

# Cache Chroma DB instances to avoid re-creating connections on every retrieval
_db_cache: dict[tuple, Chroma] = {}

def LoadDataBase(persist_directory: str = "./chroma_db", collection_name: str = "audit_documents_better_embeddings"):
    """Load the existing database from the persist directory (cached)."""
    cache_key = (persist_directory, collection_name)
    if cache_key not in _db_cache:
        _db_cache[cache_key] = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=persist_directory
        )
    return _db_cache[cache_key]

@tool
def retreave_information(query: str, persist_directory: str = "./chroma_db_multilingual", collection_name: str = "audit_documents_better_embeddings") -> str:
    """ Retreaving information from the database based on the query. It uses similarity search to find the most relevant chunks of information."""
    db = LoadDataBase(persist_directory=persist_directory, collection_name=collection_name)
    results = db.similarity_search(query, k=1)
    print(f"Retreaved Information for the query: '{query}': {[r.page_content for r in results]}")
    return "\n".join(r.page_content for r in results)

@tool
def search_web(query: str) -> str:
    """Performs a web search using DuckDuckGo, fetches full page content for each result."""
    import requests
    from bs4 import BeautifulSoup
    try:
        from ddgs import DDGS

        print(f"Searching web for: {query}")
        results = DDGS().text(query, max_results=2)

        if not results:
            return "No results found."

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

        def _fetch_page(i, result):
            """Fetch a single search result page in a thread."""
            title = result.get('title', 'N/A')
            link = result.get('href', 'N/A')
            full_text = result.get('body', '')
            try:
                page_response = requests.get(link, headers=headers, timeout=5)
                page_response.raise_for_status()
                page_soup = BeautifulSoup(page_response.text, 'html.parser')
                for tag in page_soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                paragraphs = page_soup.find_all('p')
                page_text = ' '.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                if page_text:
                    full_text = page_text[:2000]
            except Exception as fetch_err:
                print(f"  Could not fetch page {link}: {fetch_err}")
            return i, f"Result {i}:\nTitle: {title}\nLink: {link}\nContent: {full_text}\n"

        # Fetch all pages in parallel
        with ThreadPoolExecutor(max_workers=len(results)) as executor:
            futures = [executor.submit(_fetch_page, i, r) for i, r in enumerate(results, 1)]
            fetched = sorted((f.result() for f in as_completed(futures)), key=lambda x: x[0])

        output = "\n".join(text for _, text in fetched)
        print(f"Web search for '{query}' successful. Found {len(results)} results.")
        return output
    except Exception as e:
        print(f"Error during web search: {e}")
        return f"Error: {e}"
# Cache the DocumentConverter (heavy initialization)
_doc_converter = None

def _get_doc_converter():
    """Lazy singleton for docling DocumentConverter."""
    global _doc_converter
    if _doc_converter is None:
        from docling.document_converter import DocumentConverter
        _doc_converter = DocumentConverter()
    return _doc_converter

def Scan_PDF(file_path: str) -> str:
    """Scans a PDF file and returns its content as clean markdown text with tables."""
    try:
        converter = _get_doc_converter()
        result = converter.convert(file_path)
        markdown_content = result.document.export_to_markdown()
        print(f"Scanned PDF '{file_path}' successfully.")
        return markdown_content
    except Exception as e:
        print(f"Error scanning PDF: {e}")
        return f"Error: {e}"

_ocr_reader = None

def _get_ocr_reader():
    """Lazy singleton for easyocr.Reader to avoid reloading models on every call."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en", "ar"], gpu=False)
    return _ocr_reader

def Scan_image(file_path: str) -> str:
    """Scan an image file and returns its content as text."""
    from img2table.document import Image as Img2TableImage
    from img2table.ocr import EasyOCR as Img2TableEasyOCR

    reader = _get_ocr_reader()
    text_lines = reader.readtext(file_path, detail=0, paragraph=True)

    ocr = Img2TableEasyOCR(lang=["en", "ar"])
    doc = Img2TableImage(file_path)
    tables = doc.extract_tables(ocr=ocr, borderless_tables=True)
    table_markdowns = [table.df.to_markdown(index=False) for table in tables]
    return "\n".join(text_lines) + "\n" + "\n".join(table_markdowns)

def _scan_documents_impl(file_path: str) -> str:
    """Internal implementation for document scanning (supports recursion for archives)."""
    if file_path.lower().endswith('.pdf'):
        return Scan_PDF(file_path)
    elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return Scan_image(file_path)
    elif file_path.lower().endswith(('.xlsx', '.xls')):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheets_output = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    sheets_output.append(f"### Sheet: {sheet_name}\n(empty)")
                    continue
                # Use first row as headers if available
                headers = [str(c) if c is not None else '' for c in rows[0]]
                lines = ["| " + " | ".join(headers) + " |",
                         "| " + " | ".join(['---'] * len(headers)) + " |"]
                for row in rows[1:]:
                    lines.append("| " + " | ".join(str(c) if c is not None else '' for c in row) + " |")
                sheets_output.append(f"### Sheet: {sheet_name}\n" + "\n".join(lines))
            print(f"Scanned Excel '{file_path}' successfully.")
            return "\n\n".join(sheets_output)
        except ImportError:
            return "Error: openpyxl not installed. Run: pip install openpyxl"
    elif file_path.lower().endswith('.zip'):
        import zipfile
        import tempfile
        
        results = []
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    extracted_file_path = os.path.join(root, file)
                    results.append(_scan_documents_impl(extracted_file_path))
        
        return "\n\n--- Next File ---\n\n".join(results)
    elif file_path.lower().endswith('.rar'):
        try:
            import rarfile
            import tempfile
            
            results = []
            with tempfile.TemporaryDirectory() as temp_dir:
                with rarfile.RarFile(file_path, 'r') as rar_ref:
                    rar_ref.extractall(temp_dir)
                
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        extracted_file_path = os.path.join(root, file)
                        results.append(_scan_documents_impl(extracted_file_path))
            
            return "\n\n--- Next File ---\n\n".join(results)
        except ImportError:
            return "Error: rarfile library not installed. Run: pip install rarfile"
    else:
        return f"Unsupported file type: {file_path}"

@tool
def scan_documents(file_path: str) -> str:
    """Scans a document (PDF, image, Excel or archive) and returns its content as text. Supports PDF, image (png, jpg, jpeg), xlsx/xls, zip and rar files."""
    return _scan_documents_impl(file_path)

@tool
def Retreave_from_email(query: str, save_attachments: bool = True) -> str:
    """Retreave information about the company transaction and invoices from emails based on the query. the query can be the name of the company or the invoice number or the transaction details or the date or the sender or the receiver."""
    from imap_tools import MailBox, AND
    from imap_tools.query import OR
    
    EMAIL = os.getenv("EMAIL_ADDRESS")
    PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
    if not EMAIL or not PASSWORD:
        return "Error: EMAIL_ADDRESS or EMAIL_APP_PASSWORD not set in environment variables."
    
    with MailBox("imap.gmail.com").login(EMAIL, PASSWORD) as mailbox:
        criteria = OR(subject=query, text=query, from_=query, to=query)
        messages = mailbox.fetch(criteria=criteria, limit=100, reverse=True)
        
        for msg in messages:
            print(f"Found relevant email: {msg.subject}")
            attachments_dir = f"email_attachments/{msg.from_}"
            
            if msg.attachments:
                print(f"  Found {len(msg.attachments)} attachment(s):")
                for att in msg.attachments:
                    print(f"    - {att.filename} ({att.content_type}, {att.size} bytes)")
                    
                    if save_attachments:
                        os.makedirs(attachments_dir, exist_ok=True)
                        att_file_path = os.path.join(attachments_dir, att.filename)
                        with open(att_file_path, 'wb') as f:
                            f.write(att.payload)
                        print(f"      Saved to: {att_file_path}")
            
            result = f"Subject: {msg.subject}\nFrom: {msg.from_}\nDate: {msg.date}\n\n{msg.text}"
            
            if msg.attachments:
                result += f"\n\nAttachments ({len(msg.attachments)}):\n"
                for att in msg.attachments:
                    result += f"  - file_path: {os.path.join(attachments_dir, att.filename)} ({att.content_type})\n"
            
            return result
        
        return "No relevant emails found."
    
@tool
def Retreave_from_google_drive(query: str) -> str:
        """Search for files in Google Drive based on query. Returns the names and ids of matching files."""
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
        import os.path
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.auth.exceptions import RefreshError
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    # Token has been revoked or expired, delete it and re-authenticate
                    os.remove("token.json")
                    creds = None
            
            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open("token.json", "w") as token:
                    token.write(creds.to_json())

        try:
            import io
            from googleapiclient.http import MediaIoBaseDownload
            
            service = build("drive", "v3", credentials=creds)

            # Search with priority: exact phrase first, then individual words
            words = query.split()
            all_items = []
            seen_ids = set()
            
            if len(words) > 1:
                # First: search for exact phrase
                exact_results = (
                    service.files()
                    .list(q=f"fullText contains '{query}'", pageSize=10, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)")
                    .execute()
                )
                exact_items = exact_results.get("files", [])
                for item in exact_items:
                    all_items.append(item)
                    seen_ids.add(item['id'])
                
                # Second: search for individual words (excluding already found files)
                word_queries = " or ".join([f"fullText contains '{word}'" for word in words])
                word_results = (
                    service.files()
                    .list(q=word_queries, pageSize=20, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)")
                    .execute()
                )
                word_items = word_results.get("files", [])
                for item in word_items:
                    if item['id'] not in seen_ids:
                        all_items.append(item)
                        seen_ids.add(item['id'])
            else:
                # Single word search
                results = (
                    service.files()
                    .list(q=f"fullText contains '{query}'", pageSize=20, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)")
                    .execute()
                )
                all_items = results.get("files", [])

            if not all_items:
                return f"No files found matching '{query}'."
            
            # Create download directory
            download_dir = f"Google_Drive_Retrete/{query}"
            os.makedirs(download_dir, exist_ok=True)
            
            # Google Workspace MIME types and their export formats
            google_mime_types = {
                'application/vnd.google-apps.document': ('application/pdf', '.pdf'),
                'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
                'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
                'application/vnd.google-apps.drawing': ('application/pdf', '.pdf'),
            }
            
            result_text = f"Files matching '{query}':\n"
            for item in all_items:
                file_name = item['name']
                file_id = item['id']
                mime_type = item.get('mimeType', 'unknown')
                created_time = item.get('createdTime', 'N/A')
                modified_time = item.get('modifiedTime', 'N/A')
                
                result_text += f"  - {file_name} (ID: {file_id})\n"
                result_text += f"    Type: {mime_type}\n"
                result_text += f"    Created: {created_time}\n"
                result_text += f"    Modified: {modified_time}\n"
                
                # Download or export the file
                try:
                    # Check if it's a Google Workspace file that needs export
                    if mime_type in google_mime_types:
                        export_mime, extension = google_mime_types[mime_type]
                        # Add extension if not present
                        if not any(file_name.endswith(ext) for ext in ['.pdf', '.xlsx', '.pptx', '.docx']):
                            file_name_with_ext = file_name + extension
                        else:
                            file_name_with_ext = file_name
                        
                        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
                        file_path = os.path.join(download_dir, file_name_with_ext)
                        
                        with io.FileIO(file_path, 'wb') as fh:
                            downloader = MediaIoBaseDownload(fh, request)
                            done = False
                            while not done:
                                status, done = downloader.next_chunk()
                        
                        result_text += f"    Exported to: {file_path}\n\n"
                    else:
                        # Regular binary file download
                        request = service.files().get_media(fileId=file_id)
                        file_path = os.path.join(download_dir, file_name)
                        
                        with io.FileIO(file_path, 'wb') as fh:
                            downloader = MediaIoBaseDownload(fh, request)
                            done = False
                            while not done:
                                status, done = downloader.next_chunk()
                        
                        result_text += f"    Downloaded to: {file_path}\n\n"
                except Exception as download_error:
                    result_text += f"    Download/Export failed: {download_error}\n\n"
            
            return result_text
        except HttpError as error:
            return f"An error occurred: {error}"
        
@tool
def Retreave_from_whatsapp(query: str) -> str:
    """Retreave information about the company transaction and invoices from whatsapp messages based on the query. the query can be the name of the company or the invoice number or the transaction details or the date or the sender or the receiver."""
    #Comming soon, I am currently working on a solution to retreave information from whatsapp messages based on the query. I will update this function as soon as I have a working solution. The main idea is to use the whatsapp web interface to search for messages containing the query and then extract the relevant information from those messages. I will also try to extract any attachments related to those messages and process them using the scan_documents function.
    return "This feature is coming soon. I am currently working on a solution to retreave information from whatsapp"

# ─── Base tools list (used internally by helper agents) ───
base_tools = [search_web, retreave_information, scan_documents, Retreave_from_email, Retreave_from_google_drive, Retreave_from_whatsapp]
_base_tool_map = {t.name: t for t in base_tools}  # O(1) lookup

# ─── Helper Agent: Retriever (as a tool) ───
@tool
def call_retriever_agent(query: str) -> str:
    """A helper AI agent that retrieves information from the database, web, email, Google Drive and other sources.
    Give it a detailed query with instructions about what information to retrieve. It will decide the best sources,
    retrieve the information, verify it, and return a clear summary. Use this for tax laws, audit procedures,
    financial regulations, company info, invoices, etc.
    NOTE: This tool does not accept a file_path — if the task does not need file retrieval, write 'this query does not need a file path'."""
    print(" \n \n Retrever Agent is processing the request... wtih the query: " + query + "\n \n")
    system_prompt = SystemMessage(
content="""
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
- Retreave_from_email : only 0 time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only 0 time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only 5 times.
- retreave_information : only 2 time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.

"""
)
    msgs = [system_prompt, HumanMessage(content=query)]
    # Internal tool loop: let helper_llm call tools until it gives a final answer
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = _retriever_llm.invoke(msgs)
        print(f"Retriever Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        # Execute independent tool calls in parallel
        tool_results = _execute_tool_calls_parallel(response.tool_calls, _base_tool_map)
        msgs.extend(tool_results)
    else:
        print("WARNING: Retriever Agent reached maximum tool iterations.")
    print(f"\n \n Retrever Agent Response: {response.content} \n \n RETRIEVED INFORMATION END \n \n")
    return response.content


# ─── Helper Agent: Audit (as a tool) ───
@tool
def call_audit_agent(query: str, file_path: str) -> str:
    """A helper AI agent that performs invoice audit procedures, fraud detection, tax compliance checks, and tax optimization.
    'query': instructions and context about what to audit.
    'file_path': REQUIRED - the exact path to the invoice file (e.g. 'email_attachments/sender/invoice.pdf').
    It will scan the invoice at file_path, cross-check with the database, email, and Google Drive,
    verify compliance with Tunisian tax laws, detect fraud indicators, and produce a full audit report
    with optimization recommendations."""
    print(" \n \n Audit Agent is processing the request... with the query: \n \n", query, "\n file_path:", file_path, "\n \n")
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
   - Confirm transaction legitimacy.
   - Detect inconsistencies (price, quantity, date, duplication).

6. Retrieve All the data you need using call_retriever_agent.(use your own tools if you need to retreave more information, but prefer call_retriever_agent to retreave information from the database and web, email and google drive).

7. Verify compliance with:
   - Direction Générale des Impôts
   - Code de la TVA
   - Code de l’IRPP et de l’IS
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
- call_retriever_agent : you can use this tool only 1 time, so use it wisely to retreave all the information so the query must be fully specified and and contain every single thing you need or your going to need, try not to use it the scend time at all, only if you are sure that you need to retreave more information that you did not retreave the first time and that is essential for the audit, so use it wisely to retreave all the information you need from the database, web, email and google drive about the company or depend on what you need.
- call_calculation_agent : you can use this tool only 1 time, so use it wisely to perform all the calculations you need.
- scan_documents : as much as you want.
- Retreave_from_email : only 0 time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only 0 time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only 1 times.
- retreave_information : only 0 time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
"""
)
    msgs = [system_prompt, HumanMessage(content=f"{query} (file path: {file_path})")]
    # Internal tool loop: let audit_llm call tools until it gives a final answer
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = _audit_llm.invoke(msgs)
        print(f"Audit Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, _audit_tool_map)
        msgs.extend(tool_results)
    else:
        print("WARNING: Audit Agent reached maximum tool iterations.")
    print(f"\n \n Audit Agent Response: {response.content} \n \n AUDIT REPORT END \n \n")
    return response.content




# ─── Helper Agent: Calculation (as a tool) ───
@tool
def call_calculation_agent(query: str) -> str:
    """A helper AI agent that performs tax, audit, and financial calculations.
    Give it detailed instructions about what to calculate and what information to use.
    It can also retrieve information on its own using the retriever agent or other tools if needed.
    It returns a detailed explanation of the calculation steps and the final result.
    NOTE: This tool does not accept a file_path — if the task does not need a file, write 'this query does not need a file path'."""
    print(" \n \n Calculation Agent is processing the request...with query: " + query + "\n \n")
    system_prompt = SystemMessage(
content="""
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
- call_retriever_agent : you can use this tool only 1 time, so use it wisely to retreave all the information. (it's not made for calculations, that your job)
- scan_documents : as much as you want.
- Retreave_from_email : only 0 time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only 0 time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only 1 times.
- retreave_information : only 0 time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
"""
)
    msgs = [system_prompt, HumanMessage(content=query)]
    # Internal tool loop: let helper_llm call tools until it gives a final answer
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = _calc_llm.invoke(msgs)
        print(f"Calculation Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, _calc_tool_map)
        msgs.extend(tool_results)
    else:
        print("WARNING: Calculation Agent reached maximum tool iterations.")
    print(f"\n \n Calculation Agent Response: {response.content} \n \n CALCULATION END \n \n")
    return response.content

@tool
def store_data(info: str, persist_directory: str = "./chroma_db_multilingual", collection_name: str = "default_collection") -> str:
    """Store new information in the database. This can be used to update the database with new findings or insights. it takes the information to store as a string, the persist directory and the collection name as input. it returns a success message with the collection name and the length of the stored information."""
    # Convert string to Document object
    doc = Document(page_content=info, metadata={"source": "stored_data"})
    
    db = Chroma.from_documents(
        [doc],
        collection_name=collection_name,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    print(f"Stored information in collection '{collection_name}' successfully. Content length: {len(info)} characters.")
    return f"Successfully stored information in collection '{collection_name}'. Content length: {len(info)} characters."
    
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
# ─── Pre-bind helper LLMs once (avoid re-binding on every agent call) ───
_retriever_llm = helper_llm.bind_tools(base_tools)

audit_tools = base_tools + [call_retriever_agent, call_calculation_agent]
_audit_tool_map = {t.name: t for t in audit_tools}
_audit_llm = helper_llm.bind_tools(audit_tools)

calc_tools = base_tools + [call_retriever_agent]
_calc_tool_map = {t.name: t for t in calc_tools}
_calc_llm = helper_llm.bind_tools(calc_tools)

def _execute_tool_calls_parallel(tool_calls: list, tool_map: dict) -> list[ToolMessage]:
    """Execute multiple tool calls in parallel using threads. Falls back to sequential for single calls."""
    if len(tool_calls) == 1:
        tc = tool_calls[0]
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            return [ToolMessage(content=f"Error: Unknown tool '{tc['name']}'", tool_call_id=tc["id"])]
        result = tool_fn.invoke(tc["args"])
        return [ToolMessage(content=str(result), tool_call_id=tc["id"])]

    results = {}
    def _run(tc):
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            return tc["id"], f"Error: Unknown tool '{tc['name']}'"
        return tc["id"], str(tool_fn.invoke(tc["args"]))

    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
        futures = {executor.submit(_run, tc): tc for tc in tool_calls}
        for future in as_completed(futures):
            tc_id, content = future.result()
            results[tc_id] = content

    # Return in original order
    return [ToolMessage(content=results[tc["id"]], tool_call_id=tc["id"]) for tc in tool_calls]

import psycopg2
import os
import json
from decimal import Decimal
from datetime import date, datetime
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import psycopg2
import re
@tool
def read_odoo_db(query: str) -> str:
    """Execute a SQL query against the Odoo PostgreSQL database and return the results as a JSON string."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("ODOO_DB_HOST", "localhost"),
            port=os.getenv("ODOO_DB_PORT", 5432),
            dbname=os.getenv("ODOO_DB_NAME"),
            user=os.getenv("ODOO_DB_USER", "odoo"),
            password=os.getenv("ODOO_DB_PASSWORD")
        )
        cursor = conn.cursor()
        cursor.execute(query)
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        def serialize(v):
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            return v

        result = [dict(zip(cols, (serialize(v) for v in row))) for row in rows]
        print(f"Executed Odoo DB query: {query}\nResult: {result} \n \n")
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error querying Odoo database: {e}")
        return json.dumps({"error": str(e)})

@tool
def write_odoo_db(query: str) -> str:
    """Execute a write SQL query (INSERT, UPDATE, DELETE) against the Odoo PostgreSQL database and return the result as a JSON string."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("ODOO_DB_HOST", "localhost"),
            port=os.getenv("ODOO_DB_PORT", 5432),
            dbname=os.getenv("ODOO_DB_NAME"),
            user=os.getenv("ODOO_DB_USER", "odoo"),
            password=os.getenv("ODOO_DB_PASSWORD")
        )
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return json.dumps({"status": "success", "rows_affected": affected})
    except Exception as e:
        print(f"Error writing to Odoo database: {e}")
        return json.dumps({"error": str(e)})

def db_connector(query: str, type: str = "read", source: str = "odoo") -> str:
    """A generic database connector that can route queries to different databases based on the source parameter. Currently supports Odoo PostgreSQL database."""
    if source == "odoo":
        if type == "read":
            return read_odoo_db.invoke(query)
        elif type == "write":
            return write_odoo_db.invoke(query)
        else:
            return json.dumps({"error": f"Unsupported query type: {type}"})
    elif source == "local_db":
        if type == "read":
            if local_db_exists() :
                return read_local_db.invoke(query)
            else:
                return json.dumps({"error": "Local database not found. Please initialize the local database before running this query."})
        elif type == "write":
            if local_db_exists() :
                return write_local_db.invoke(query)
            else:
                return json.dumps({"error": "Local database not found. Please initialize the local database before running this query."})
    else:
        return json.dumps({"error": f"Unsupported database source: {source}"})
  
def local_db_exists() -> bool:
    """Check if the local SQLite database exists."""
    return os.path.exists("local_data.db")

#Create local database Node
# def local_db(state: AgentState) -> AgentState:
#     """Initializes a local SQLite database for storing information."""
#     import sqlite3
#     db_path = "local_data.db"
#     if os.path.exists(db_path):
#         print("Local database already exists at 'local_data.db'.")
#         return state
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         # executescript handles multiple statements and issues an implicit COMMIT
#         cursor.executescript("""
# CREATE TABLE IF NOT EXISTS companies (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT NOT NULL,
#     tax_id TEXT,
#     address TEXT,
#     email TEXT,
#     phone TEXT,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# CREATE TABLE IF NOT EXISTS contacts (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     company_id INTEGER REFERENCES companies(id),
#     name TEXT NOT NULL,
#     type TEXT CHECK (type IN ('customer','supplier','employee','other')),
#     tax_number TEXT,
#     email TEXT,
#     phone TEXT,
#     address TEXT,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# CREATE TABLE IF NOT EXISTS products (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     company_id INTEGER REFERENCES companies(id),
#     name TEXT NOT NULL,
#     description TEXT,
#     price REAL,
#     cost REAL,
#     type TEXT CHECK (type IN ('product','service')),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# CREATE TABLE IF NOT EXISTS taxes (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT,
#     rate REAL,
#     description TEXT
# );

# CREATE TABLE IF NOT EXISTS invoices (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     company_id INTEGER REFERENCES companies(id),
#     contact_id INTEGER REFERENCES contacts(id),
#     invoice_number TEXT,
#     type TEXT CHECK (type IN ('sale','purchase')),
#     invoice_date DATE,
#     due_date DATE,
#     total_untaxed REAL,
#     total_tax REAL,
#     total_amount REAL,
#     status TEXT CHECK (status IN ('draft','posted','paid','cancelled')),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# CREATE TABLE IF NOT EXISTS invoice_lines (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
#     product_id INTEGER REFERENCES products(id),
#     description TEXT,
#     quantity REAL,
#     unit_price REAL,
#     tax_id INTEGER REFERENCES taxes(id),
#     subtotal REAL
# );

# CREATE TABLE IF NOT EXISTS payments (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     invoice_id INTEGER REFERENCES invoices(id),
#     payment_date DATE,
#     amount REAL,
#     payment_method TEXT,
#     reference TEXT
# );

# CREATE TABLE IF NOT EXISTS attachments (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     invoice_id INTEGER REFERENCES invoices(id),
#     file_name TEXT,
#     file_path TEXT,
#     uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# CREATE TABLE IF NOT EXISTS audit_results (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     invoice_id INTEGER REFERENCES invoices(id),
#     risk_level TEXT,
#     issue_detected TEXT,
#     recommendation TEXT,
#     ai_confidence REAL,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# CREATE TABLE IF NOT EXISTS audit_logs (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     entity_type TEXT,
#     entity_id INTEGER,
#     action TEXT,
#     details TEXT,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# INSERT INTO taxes (name, rate, description) VALUES
# ('TVA 19%', 19, 'Standard Tunisian VAT'),
# ('TVA 13%', 13, 'Reduced VAT'),
# ('TVA 7%', 7, 'Special VAT'),
# ('TVA Exempt', 0, 'No VAT applied');
#         """)
#         cursor.close()
#         conn.close()
#         print("Local database initialized successfully at 'local_data.db'.")
#     except Exception as e:
#         print(f"Error initializing local database: {e}")
#     return state

def local_db(state: "AgentState") -> "AgentState":

    mapping_file = "mapping_cache.json"

    # ------------------------------------------------
    # CREATE OR CONNECT TO AI AUDIT DATABASE
    # ------------------------------------------------

    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "ai_audit_db.sqlite")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    cursor = conn.cursor()

    # ------------------------------------------------
    # CREATE CANONICAL TABLES
    # ------------------------------------------------

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        tax_id TEXT,
        address TEXT,
        email TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        name TEXT,
        type TEXT,
        tax_number TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        source_system TEXT,
        source_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        name TEXT,
        description TEXT,
        price REAL,
        cost REAL,
        type TEXT,
        source_system TEXT,
        source_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        contact_id INTEGER REFERENCES contacts(id),
        invoice_number TEXT,
        type TEXT,
        currency TEXT,
        exchange_rate REAL,
        invoice_date TEXT,
        due_date TEXT,
        total_untaxed REAL,
        total_tax REAL,
        total_amount REAL,
        status TEXT,
        source_system TEXT,
        source_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS invoice_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
        product_id INTEGER,
        description TEXT,
        quantity REAL,
        unit_price REAL,
        tax_id INTEGER,
        subtotal REAL
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
        payment_date TEXT,
        amount REAL,
        payment_method TEXT,
        reference TEXT,
        source_system TEXT,
        source_id TEXT
    );
    """)

    conn.commit()
    print("Canonical schema ready")

    # ------------------------------------------------
    # LOAD OR GENERATE MAPPING
    # ------------------------------------------------

    if os.path.exists(mapping_file):

        with open(mapping_file) as f:
            mapping = json.load(f)

        print("Loaded mapping_cache.json")

    else:

        print("Generating mapping using DeepSeek")

        tables_json = read_odoo_db.invoke("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        """)

        tables = json.loads(tables_json)

        schema = {}

        for t in tables:

            table = t["table_name"]

            cols_json = read_odoo_db.invoke(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='{table}'
            """)

            cols = json.loads(cols_json)

            schema[table] = [c["column_name"] for c in cols]


        prompt = f"""
Map this Odoo schema to the canonical audit schema.

Odoo schema:
{json.dumps(schema,indent=2)}

Canonical tables and their columns:
companies: name, tax_id, address, email, phone
contacts: company_id, name, type, tax_number, email, phone, address, source_system, source_id
products: company_id, name, description, price, cost, type, source_system, source_id
invoices: company_id, contact_id, invoice_number, type, currency, exchange_rate, invoice_date, due_date, total_untaxed, total_tax, total_amount, status, source_system, source_id
invoice_lines: invoice_id, product_id, description, quantity, unit_price, tax_id, subtotal
payments: invoice_id, payment_date, amount, payment_method, reference, source_system, source_id

Return ONLY a JSON object in this exact format (no extra text):
{{
  "canonical_table_name": {{
    "source_table": "odoo_table_name",
    "field_mapping": {{
      "canonical_column": "odoo_column"
    }}
  }}
}}
"""

        response = helper_llm.invoke([HumanMessage(content=prompt)])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        mapping = json.loads(raw)

        # Validate mapping against actual Odoo schema: remove non-existent columns
        for canon, cfg in list(mapping.items()):
            src = cfg.get("source_table", "")
            if src not in schema:
                print(f"Warning: source table '{src}' not found, removing '{canon}'")
                del mapping[canon]
                continue
            valid_cols = set(schema[src])
            bad = [k for k, v in cfg["field_mapping"].items() if v not in valid_cols]
            for k in bad:
                print(f"Warning: column '{cfg['field_mapping'][k]}' not in '{src}', dropping mapping for '{k}'")
                del cfg["field_mapping"][k]

        with open(mapping_file,"w") as f:
            json.dump(mapping,f,indent=2)

        print("Saved mapping_cache.json")

    # ------------------------------------------------
    # DATA TRANSFER
    # ------------------------------------------------

    for canonical_table, config in mapping.items():

        source_table = config["source_table"]
        field_map = config["field_mapping"]

        if not field_map:
            print(f"Skipping {canonical_table}: no valid field mappings")
            continue

        source_fields = ",".join(field_map.values())

        rows_json = read_odoo_db.invoke(
            f"SELECT {source_fields} FROM {source_table}"
        )

        rows = json.loads(rows_json)

        if not isinstance(rows, list):
            print(f"Skipping {canonical_table}: query error – {rows}")
            continue

        for row in rows:

            columns = []
            values = []

            for c_field, s_field in field_map.items():

                val = row.get(s_field)
                # SQLite can't bind dict/list — serialize to JSON string
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                columns.append(c_field)
                values.append(val)

            placeholders = ",".join(["?"] * len(values))

            query = f"""
            INSERT INTO {canonical_table}
            ({",".join(columns)})
            VALUES ({placeholders})
            """

            cursor.execute(query, values)

        print(f"Imported {len(rows)} rows into {canonical_table}")

    conn.commit()
    conn.close()

    print("Odoo data imported successfully")

    return state




@tool
def read_local_db(query: str) -> str:
    """Execute a read SQL query against the local SQLite database and return the results as a JSON string."""
    import sqlite3
    try:
        conn = sqlite3.connect("ai_audit_db.sqlite", timeout=30)
        cursor = conn.cursor()
        cursor.execute(query)
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        result = [dict(zip(cols, row)) for row in rows]
        print(f"Executed local DB query: {query}\nResult: {result} \n \n")
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error querying local database: {e}")
        return json.dumps({"error": str(e)})
@tool
def write_local_db(query: str) -> str:
    """Execute a write SQL query (INSERT, UPDATE, DELETE) against the local SQLite database and return the result as a JSON string."""
    import sqlite3
    try:
        conn = sqlite3.connect("ai_audit_db.sqlite", timeout=30)
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        print(f"Executed local DB write query: {query}\nRows affected: {affected} \n \n")
        return json.dumps({"status": "success", "rows_affected": affected})
    except Exception as e:
        print(f"Error writing to local database: {e}")
        return json.dumps({"error": str(e)})

#Local database AI Agent Node
def local_db_agent(state: AgentState) -> AgentState:
    """An AI agent that can read from and write to the local SQLite database based on the user's query."""
    system_prompt = SystemMessage(content=""" You are a Local Database Agent.
                                   Your mission is to take a docmument content as input and decide where to store it and how you store it in the local database.
                                   you can also retreave informations form the local database if you need it to store the document content.
                                   you can use these tools to interact with the local database:
                                    1. read_local_db : to execute a read SQL query against the local SQLite database and return the result as a JSON string.
                                    2. write_local_db : to execute a write SQL query (INSERT, UPDATE, DELETE) against the local SQLite database and return the result as a JSON string.
                                    Here is the database schema you have to work with:
                                  DATABASE_SCHEMA:
                                    companies(id PK, name, tax_id, address, email, phone, created_at);

                                    contacts(id PK, company_id FK->companies.id, name, type[customer|supplier|employee|other], tax_number, email, phone, address, created_at);

                                    products(id PK, company_id FK->companies.id, name, description, price, cost, type[product|service], created_at);

                                    taxes(id PK, name, rate, description);

                                    invoices(id PK, company_id FK->companies.id, contact_id FK->contacts.id, invoice_number, type[sale|purchase], invoice_date, due_date, total_untaxed, total_tax, total_amount, status[draft|posted|paid|cancelled], created_at);

                                    invoice_lines(id PK, invoice_id FK->invoices.id, product_id FK->products.id, description, quantity, unit_price, tax_id FK->taxes.id, subtotal);

                                    payments(id PK, invoice_id FK->invoices.id, payment_date, amount, payment_method, reference);

                                    attachments(id PK, invoice_id FK->invoices.id, file_name, file_path, uploaded_at);

                                    audit_results(id PK, invoice_id FK->invoices.id, risk_level, issue_detected, recommendation, ai_confidence, created_at);

                                    audit_logs(id PK, entity_type, entity_id, action, details, created_at);

                                    RELATIONSHIPS:
                                    companies -> contacts
                                    companies -> products
                                    companies -> invoices
                                    contacts -> invoices
                                    invoices -> invoice_lines
                                    invoices -> payments
                                    invoices -> attachments
                                    invoices -> audit_results
                                    products -> invoice_lines
                                    taxes -> invoice_lines

                                    IMPORTANT RULES:
                                    -if a write_local_db return a dublication error, skip that row.
                                    - No need to store data in all the tables, just store the relevant information in the relevant tables.
                                    
                                                                                                       """)
    docs = state["local_db_files"]
    db_llm = helper_llm.bind_tools([read_local_db, write_local_db])
    db_tool_map = {"read_local_db": read_local_db, "write_local_db": write_local_db}
    for d in docs:
        doc_content = scan_documents.invoke(d)
        msgs = [system_prompt, HumanMessage(content=doc_content)]
        for _iteration in range(100):  # allow more iterations for complex document processing
            response = db_llm.invoke(msgs)
            msgs.append(response)
            if not response.tool_calls:
                break
            tool_results = _execute_tool_calls_parallel(response.tool_calls, db_tool_map)
            msgs.extend(tool_results)
        else:
            print("WARNING: Local DB Agent reached maximum tool iterations.")
        print(f"Local Database Agent processed document '{d}' with response: {response.content} \n \n")
    return state

#Get documents for the local database Node
def get_local_db_documents(state: AgentState) -> AgentState:
    """A node that retrieves the file paths of documents that need to be processed and stored in the local database. It updates the state with a list of file paths under the key 'local_db_files'."""
    # For demonstration, we will just use a hardcoded list of file paths. In a real implementation, this could be dynamic based on user input or a directory scan.
    # i will create a better one that takes the files paths from the frontend that the user selected but for now this will do the job.
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

#invoce Scanning Agent Node
def invoice_scanning_agent(state: AgentState) -> AgentState:
    """Scans the invoice document and extracts relevant data."""
    company_name = state.get("company_info", {}).get("company_name", "Unknown")
    system_prompt="""You are an Invoice Scanning Agent. Your task is to extract all relevant data from the invoice given by the user, the company you are working for called """ + company_name + """.
    "There is 3 senarios for the user request: 
    1. the user give you the invoce Number, in this case you use the read_odoo_db tool giving it a SQL query to retreave the invoice data from the table 'account_move' in the Odoo database, here are the columns of the 'account_move' table: [
    "id", "sequence_number", "message_main_attachment_id", "journal_id", "company_id", "origin_payment_id", "statement_line_id", "tax_cash_basis_rec_id", "tax_cash_basis_origin_move_id", "auto_post_origin_id", "secure_sequence_number", "invoice_payment_term_id", "partner_id", "commercial_partner_id", "partner_shipping_id", "partner_bank_id", "fiscal_position_id", "preferred_payment_method_line_id", "currency_id", "reversed_entry_id", "invoice_user_id", "invoice_incoterm_id", "invoice_cash_rounding_id", "create_uid", "write_uid", "sequence_prefix", "access_token", "name", "ref", "state", "move_type", "auto_post", "inalterable_hash", "payment_reference", "qr_code_method", "payment_state", "invoice_source_email", "invoice_partner_display_name", "invoice_origin", "incoterm_location", "date", "auto_post_until", "invoice_date", "invoice_date_due", "delivery_date", "taxable_supply_date", "sending_data", "narration", "invoice_currency_rate", "amount_untaxed", "amount_tax", "amount_total", "amount_residual", "amount_untaxed_signed", "amount_untaxed_in_currency_signed", "amount_tax_signed", "amount_total_signed", "amount_total_in_currency_signed", "amount_residual_signed", "quick_edit_total_amount", "always_tax_exigible", "checked", "posted_before", "made_sequence_gap", "is_manually_modified", "is_move_sent", "create_date", "write_date", "campaign_id", "source_id", "medium_id", "team_id
    2. the user give you the file path of the invoice, in this case you use the scan_documents tool to scan the invoice and extract the data, 
    3. the user give you some information about the invoice but not the file path or the invoice number, in this case you try to retreave the invoice data using the read_odoo_db tool with a SQL query that search for the invoice based on the information given by the user, if you can't find the invoice using the read_odoo_db tool, then you ask the user for more information or for the file path or the invoice number.
    \n\n
    After you extract the invoice data, your output will have two formats base on the seccess of the extraction: 
    1. if the extraction is successful, The output will be a JSON string with the EXACT following format (the output must be exactly in this format): 
    {'invoice_number': 'Number of the invoice' ,'state': 'waiting', 'note': 'if you have any notes put them here or anything you want', 'invoice_data':{'type': 'in_invoice|out_invoice|in_refund|out_refund|external', 'supplier_name': 'Name of the supplier', 'amount': 'Amount of the invoice', 'customer_name': 'Name of the customer', 'VAT': 'VAT amount', 'address': 'Address of the supplier', 'creation_date': 'Creation date of the invoice', 'product_name': 'Name of the product', 'cost': 'Cost of the product', 'price': 'Price of the product', 'category': 'Category of the product', VAT_class: 'VAT class', total: 'Total amount', ... (all other data if available) } }
    2. if the extraction fails, you output an error message exactly in this format: 
    {'error': 'Error message'}"""
    scanner_llm = helper_llm.bind_tools([read_odoo_db, scan_documents])
    msgs = [SystemMessage(content=system_prompt)] + [state["user_input"]]
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = scanner_llm.invoke(msgs)
        print(f"Invoice Scanning Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, {"read_odoo_db": read_odoo_db, "scan_documents": scan_documents})
        msgs.extend(tool_results)
    else:
        print("WARNING: Invoice Scanning Agent reached maximum tool iterations.")
    print(f"\n \n Invoice Scanning Agent Response: {response.content} \n \n INVOICE SCANNING END \n \n")
    json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
    try:
        json_response = json.loads(json_match.group()) if json_match else {}
    except json.JSONDecodeError:
        import ast
        try:
            json_response = ast.literal_eval(json_match.group()) if json_match else {}
        except Exception:
            json_response = {}
    if "error" in json_response:
        print(f"Invoice scanning failed with error: {json_response['error']}")
        state["invoces"].append(invoice("unknown", json_response["error"], {}, "error"))
    else:
        state['invoces'].append(invoice(json_response["invoice_number"], json_response["note"], json_response["invoice_data"], "waiting"))
    return state

    

def check_supplier_authenticity(supplier_info: dict) -> dict: 
    """
    Interactively asks the user whether a supplier is real or fake.
    If real, prompts the user to fill in supplier data.
    Returns: {"is_authentic": bool, "details": {"columns": [...], "data": [...]}}
    """
    # Whitelist of allowed column names to prevent SQL injection via column names
    ALLOWED_COLUMNS = {
        "name", "email", "phone", "website", "vat", "company_registry",
        "is_company", "street", "street2", "zip", "city", "country_id",
        "state_id", "lang", "tz", "function", "comment", "ref", "barcode",
        "supplier_rank", "customer_rank", "autopost_bills", "type",
        "company_name", "active", "group_on", "group_rfq"
    }

    print("\n" + "="*50)
    print("  SUPPLIER AUTHENTICITY CHECK")
    print("="*50)
    print(f"  Supplier Name : {supplier_info.get('name', 'Unknown')}")
    print(f"  Address       : {supplier_info.get('address', 'Unknown')}")
    print("="*50 + "\n")

    while True:
        answer = input("Is this supplier REAL or FAKE? (real/fake): ").strip().lower()
        if answer in ("real", "fake"):
            break
        print("  Please type 'real' or 'fake'.")

    if answer == "fake":
        print("\nSupplier marked as fake. Audit will flag this invoice.\n")
        return {"is_authentic": False, "details": {}}

    # ── Collect supplier data ──────────────────────────────────────────────
    print("\nPlease provide the supplier details.")
    print("  (*) = mandatory field    |    press Enter to skip optional fields\n")

    # (column, display label, mandatory, data_type)
    fields = [
        ("name",             "Full Name",                               True,  "str"),
        ("email",            "Email Address",                           False, "str"),
        ("phone",            "Phone Number",                            False, "str"),
        ("website",          "Website URL",                             False, "str"),
        ("vat",              "VAT / Tax Number",                        False, "str"),
        ("company_registry", "Company Registry Number",                 False, "str"),
        ("is_company",       "Is this a company? (true/false)",          False, "bool"),
        ("company_name",     "Company Name (if individual, parent co.)", False, "str"),
        ("street",           "Street",                                  False, "str"),
        ("street2",          "Street (line 2)",                         False, "str"),
        ("zip",              "ZIP / Postal Code",                       False, "str"),
        ("city",             "City",                                    False, "str"),
        ("country_id",       "Country ID (numeric Odoo ID)",            False, "int"),
        ("state_id",         "State / Recion ID (numeric Odoo ID)",     False, "int"),
        ("lang",             "Language code (e.g. en_US, fr_FR)",       False, "str"),
        ("tz",               "Timezone (e.g. Africa/Tunis)",            False, "str"),
        ("function",         "Job Position / Function",                 False, "str"),
        ("ref",              "Internal Reference",                      False, "str"),
        ("barcode",          "Barcode",                                 False, "str"),
        ("comment",          "Notes / Comment",                         False, "str"),
        ("supplier_rank",    "Supplier Rank (integer, default 1)",      False, "int"),
        ("customer_rank",    "Customer Rank (integer, default 0)",      False, "int"),
        ("autopost_bills",   "Auto-post bills (ask/always/never)",      True, "str"),
        ("active",           "Active? (true/false, default true)",      False, "bool"),
        ("group_on",         "Group On",                                True, "str"),
        ("group_rfq",        "Group RFQ",                               True, "str"),
    ]

    columns: list[str] = []
    data: list[str] = []

    for col, label, mandatory, dtype in fields:
        # Safety: skip if column not in whitelist (should not happen, but defensive)
        if col not in ALLOWED_COLUMNS:
            continue

        # Pre-fill hint from supplier_info when available
        prefill = supplier_info.get(col) or (supplier_info.get("name") if col == "name" else None)

        hint = f" [{prefill}]" if prefill else ""

        if mandatory:
            while True:
                prompt = f"  (*) {label}{hint}: "
                raw = input(prompt).strip()
                if not raw and prefill:
                    raw = str(prefill)
                if raw:
                    break
                print(f"      '{label}' is mandatory — please enter a value.")
        else:
            prompt = f"      {label}{hint} (optional): "
            raw = input(prompt).strip()
            if not raw and prefill:
                raw = str(prefill)
            if not raw:
                continue  # user skipped

        # Type coercion + value formatting for SQL literal
        if dtype == "int":
            try:
                sql_val = str(int(raw))
            except ValueError:
                print(f"      Invalid integer for '{label}' — skipping.")
                continue
        elif dtype == "bool":
            sql_val = "TRUE" if raw.strip().lower() in ("true", "1", "yes") else "FALSE"
        else:
            # Escape single quotes to prevent SQL injection in the value
            escaped = raw.replace("'", "''")
            sql_val = f"'{escaped}'"

        columns.append(col)
        data.append(sql_val)

    print("\nSupplier data collected successfully.\n")
    return {
        "is_authentic": True,
        "details": {
            "columns": columns,
            "data": data
        }
    }
    


#Supplier Verification Node
def supplier_verification_node(state: AgentState) -> AgentState:
    """Verifies the supplier Authenticity and Legitimacy."""
    invoice = state["invoces"][-1]  # Get the most recently scanned invoice
    s_v_score = 10
    state["invoces"][-1].status = "verifying_supplier"  # Update status to indicate supplier verification in progress
    supplier_info = {
        "name": invoice.invoice_data.get("supplier_name"),
        "address": invoice.invoice_data.get("address", "unknown"),
    }
    results = db_connector(f"SELECT id FROM {'res_partner' if state['db_source'] == 'odoo' else 'contacts'} WHERE name = '{supplier_info['name'].replace('\'', '\'\'')}' AND {'is_company = TRUE' if state['db_source'] == 'odoo' else 'type = \"supplier\"'};", type="read", source=state["db_source"])
    

    if results == "[]":
        s_v_score -= 5
        print(f"Supplier '{supplier_info['name']}' not found in {state['db_source']} database. Marking as 'unverified'.")
        check_result = check_supplier_authenticity(supplier_info) # must return a dict with the format {"is_authentic": True/False, "details":{ 'columns': ['column1', 'column2', ...], 'data': [ 'value1', 'value2', ...] } } }
        if check_result.get("is_authentic"):
            print(f"Supplier '{supplier_info['name']}' passed external authenticity check. Marking as 'verified'.")
            invoice.audits_results['supplier_authenticity'] = True
            # Augment with required Odoo system fields that are not collected from the user
            print("Make sure to add the supplier to the database as soon as possible to avoid having unverified suppliers in the system.")
            if supplier_info["address"] != invoice.invoice_data.get("address", ""):
                print(f"WARNING: Supplier address '{supplier_info['address']}' does not match the address in the invoice '{invoice.invoice_data.get('address', '')}'. This may indicate a potential issue with the supplier's legitimacy. Please verify the supplier's information and consider flagging this invoice for further review.")
                s_v_score -= 2
            invoice.state = f"verified_supplier_score: {s_v_score}"
            state["invoces"][-1] = invoice    
            
        else:
            s_v_score -= 5
            print(f"Supplier '{supplier_info['name']}' failed external authenticity check. Marking as 'unverified'.")
            invoice.audits_results['supplier_authenticity'] = False
            invoice.state = f"unverified_supplier_score: {s_v_score}"
            state["invoces"][-1] = invoice
            
    else:
        print(f"Supplier '{supplier_info['name']}' found in {state['db_source']} database. Marking as 'verified'.")
        invoice.audits_results['supplier_authenticity'] = True
        invoice.state = f"verified_supplier_score: {s_v_score}"
        state["invoces"][-1] = invoice
    return state


def purchase_order_verification_node(state: AgentState) -> AgentState:
    """Verifies the purchase order details and consistency."""
    







# ─── All tools for Main AI (includes helper agents as tools) ───
all_tools = base_tools + [call_retriever_agent, call_calculation_agent, call_audit_agent, store_data]
llm = llm.bind_tools(all_tools)

# ─── Graph: Simple Main_AI → ToolNode → Main_AI loop ───
graph = StateGraph(AgentState)
graph.add_node("user_input_node", input_node)
graph.add_node("main_ai_node", Main_AI)
graph.add_node("tools_node", ToolNode(tools=all_tools))
graph.add_node("exit_agent", exit_agent)
graph.add_node("invoice_scanning_agent", invoice_scanning_agent)
graph.add_node("supplier_verification_node", supplier_verification_node)
graph.add_node("local_db", local_db)
graph.add_node("get_local_db_documents", get_local_db_documents)
graph.add_node("local_db_agent", local_db_agent)
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
        "scan_invoice_node": "invoice_scanning_agent",
        "local_db_node": "local_db",
        "upload_docs": "get_local_db_documents",
        "exit": "exit_agent"
    }
)
graph.add_edge("exit_agent", "user_input_node")
graph.add_edge("tools_node", "main_ai_node")
graph.add_edge("invoice_scanning_agent", "supplier_verification_node")
graph.add_edge("supplier_verification_node", "user_input_node")
graph.add_edge("local_db", "user_input_node")
graph.add_edge("get_local_db_documents", "local_db_agent")
graph.add_edge("local_db_agent", "user_input_node")
app = graph.compile()

result = app.invoke({"messages": [], "user_input": "", "invoces": [], "local_db_files": [], "db_source": "local_db", "company_info": {'company_name': 'my company'}})

print("Final Response from Main AI Agent:")
print(result["messages"][-1].content)