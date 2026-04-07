from typing import TypedDict, Sequence, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.documents import Document
from operator import add as add_message
from langgraph.graph import StateGraph, START, END
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import tool
from g4f.integration.langchain import ChatAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
import os 
from langgraph.prebuilt import ToolNode
import glob
from bs4 import BeautifulSoup
from polars import date
import requests
import easyocr

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
os.environ["OPENAI_API_KEY"] = "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"
os.environ["DEEPSEEK_API_KEY"] = "sk-c1604ea114b24b039cb20ddd50982f6b"
llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"), base_url='https://api.openai.com/v1', temperature=0)
# helper_llm = llm
helper_llm = ChatDeepSeek(model="deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"), base_url='https://api.deepseek.com', temperature=0)

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_message]
# Use input Node
def input_node(state: AgentState) -> AgentState:
    """Takes user input and adds it to the conversation history."""
    user_input = input("User: ")
    return {"messages": state["messages"] + [HumanMessage(content=user_input)]}
# Main AI Node
def Main_AI(state: AgentState)-> AgentState:
    """Main AI Node that processes the conversation and generates responses."""
    system_prompt = SystemMessage(
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
    if not any(isinstance(msg, SystemMessage) for msg in state["messages"]):
        state["messages"].insert(0, system_prompt)
    response = llm.invoke(state["messages"])
    print(f" \n \n Main AI Agent Response: {response.content} \n \n")
    return {"messages": state["messages"] + [response]}

def should_continue(state: AgentState) -> str:
    """Route to tools or end based on whether the LLM made tool calls."""
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage) and last_message.content.lower() in ["exit", "quit", "end"]:
        return "exit"
    if isinstance(last_message, HumanMessage):
        return "main_ai_node"
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_node"
    return "end"

def LoadDataBase(persist_directory: str = "./chroma_db", collection_name: str = "audit_documents_better_embeddings"):
    """Load the existing database from the persist directory."""
    db = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory
    )
    return db

@tool
def retreave_information(query: str, persist_directory: str = "./chroma_db_multilingual", collection_name: str = "audit_documents_better_embeddings") -> str:
    """ Retreaving information from the database based on the query. It uses similarity search to find the most relevant chunks of information."""
    retriver = LoadDataBase(persist_directory=persist_directory, collection_name=collection_name).as_retriever(
    search_type="similarity",
    search_kwargs={"k": 1}  # K is the amount of chunks to return
)
    results = retriver.invoke(query)
    print(f"Retreaved Information for the query: '{query}': {[result.page_content for result in results]} \n \n \n \n \n \n")
    return "\n".join([result.page_content for result in results])

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
        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get('title', 'N/A')
            link = result.get('href', 'N/A')
            snippet = result.get('body', '')

            # Fetch full page content
            full_text = snippet
            try:
                page_response = requests.get(link, headers=headers, timeout=5)
                page_response.raise_for_status()
                page_soup = BeautifulSoup(page_response.text, 'html.parser')
                # Remove scripts and styles
                for tag in page_soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                paragraphs = page_soup.find_all('p')
                page_text = ' '.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                if page_text:
                    full_text = page_text[:2000]
            except Exception as fetch_err:
                print(f"  Could not fetch page {link}: {fetch_err}")

            formatted_results.append(
                f"Result {i}:\n"
                f"Title: {title}\n"
                f"Link: {link}\n"
                f"Content: {full_text}\n"
            )

        output = "\n".join(formatted_results)
        print(f"Web search for '{query}' successful. Found {len(results)} results.")
        return output
    except Exception as e:
        print(f"Error during web search: {e}")
        return f"Error: {e}"
# def search_web(query):
#     """Performs a web search using DuckDuckGo and returns text from the top result."""
#     try:
#         search_url = f"https://html.duckduckgo.com/html/?q={query}"
#         headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
#         response = requests.get(search_url, headers=headers)
#         response.raise_for_status()
        
#         soup = BeautifulSoup(response.text, 'html.parser')
#         results = soup.find_all('a', class_='result__a')
        
#         if not results:
#             return "No results found."
            
#         top_result_url = results[0]['href']
        
#         page_response = requests.get(top_result_url, headers=headers)
#         page_response.raise_for_status()
#         page_soup = BeautifulSoup(page_response.text, 'html.parser')
        
#         paragraphs = page_soup.find_all('p')
#         page_text = "\n".join([p.get_text() for p in paragraphs])
        
#         print(f"Web search for '{query}' successful.")
#         print(f"Top result URL: {page_text[:100]}")
#         return page_text[:2000]
#     except Exception as e:
#         print(f"Error during web search: {e}")
#         return f"Error: {e}"
    
def Scan_PDF(file_path: str) -> str:
    """Scans a PDF file and returns its content as clean markdown text with tables."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown_content = result.document.export_to_markdown()
        print(f"Scanned PDF '{file_path}' successfully.")
        return markdown_content
    except Exception as e:
        print(f"Error scanning PDF: {e}")
        return f"Error: {e}"

def Scan_image(file_path: str) -> str:
    """Scan an image file and returns its content as text."""
    from typing import List

    import easyocr
    from img2table.document import Image as Img2TableImage
    from img2table.ocr import EasyOCR as Img2TableEasyOCR


    def scan_image_text(file_path: str) -> List[str]:
        """Scan an image file and return its content as text lines."""
        reader = easyocr.Reader(["en", "ar"], gpu=False)
        return reader.readtext(file_path, detail=0, paragraph=True)


    def recognize_tables(file_path: str) -> list:
        """Detect tables in an image and return them as a list of DataFrames."""
        ocr = Img2TableEasyOCR(lang=["en", "ar"])
        doc = Img2TableImage(file_path)
        tables = doc.extract_tables(ocr=ocr, borderless_tables=True)
        print('Raw Table Data:', tables)
        return [table.df.to_markdown(index=False) for table in tables]
    return "\n".join(scan_image_text(file_path)) + "\n" + "\n".join(recognize_tables(file_path))

@tool
def scan_documents(file_path: str) -> str:
    """Scans a document (PDF or image or rar or zip) and returns its content as text. it take the path of the document as input and return the content of the document as text. it support PDF, image (png, jpg, jpeg), zip and rar files."""
    if file_path.lower().endswith('.pdf'):
        return Scan_PDF(file_path)
    elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return Scan_image(file_path)
    elif file_path.lower().endswith('.zip'):
        import zipfile
        import os
        import tempfile
        
        results = []
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Process all extracted files
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    extracted_file_path = os.path.join(root, file)
                    results.append(scan_documents(extracted_file_path))
        
        return "\n\n--- Next File ---\n\n".join(results)
    elif file_path.lower().endswith('.rar'):
        try:
            import rarfile
            import os
            import tempfile
            
            results = []
            with tempfile.TemporaryDirectory() as temp_dir:
                with rarfile.RarFile(file_path, 'r') as rar_ref:
                    rar_ref.extractall(temp_dir)
                
                # Process all extracted files
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        extracted_file_path = os.path.join(root, file)
                        results.append(scan_documents(extracted_file_path))
            
            return "\n\n--- Next File ---\n\n".join(results)
        except ImportError:
            return "Error: rarfile library not installed. Run: pip install rarfile"
    else:
        return f"Unsupported file type: {file_path}"

@tool
def Retreave_from_email(query: str, save_attachments: bool = True) -> str:
    """Retreave information about the company transaction and invoices from emails based on the query. the query can be the name of the company or the invoice number or the transaction details or the date or the sender or the receiver."""
    from imap_tools import MailBox, AND
    from imap_tools.query import OR
    import os
    
    EMAIL = "mohamedsuper27@gmail.com"
    PASSWORD = "wfdd npyq ugpk cbuf"
    
    
    with MailBox("imap.gmail.com").login(EMAIL, PASSWORD) as mailbox:
        # Search for emails containing the query in subject or body
        # Limit to last 100 emails to avoid freezing
        criteria = OR(subject=query, text=query, from_=query, to=query)  # Search in multiple fields
        messages = mailbox.fetch(criteria=criteria, limit=100, reverse=True)
        
        for msg in messages:
            print(f"Found relevant email: {msg.subject}")
            
            # Process attachments
            if msg.attachments:
                print(f"  Found {len(msg.attachments)} attachment(s):")
                for att in msg.attachments:
                    print(f"    - {att.filename} ({att.content_type}, {att.size} bytes)")
                    
                    if save_attachments:
                        # Save attachment to disk
                        # Create attachments folder if it doesn't exist
                        attachments_dir = f"email_attachments/{msg.from_}"
                        if save_attachments:
                            os.makedirs(attachments_dir, exist_ok=True)
                        file_path = os.path.join(attachments_dir, att.filename)
                        with open(file_path, 'wb') as f:
                            f.write(att.payload)
                        print(f"      Saved to: {file_path}")
            
            # Build response
            result = f"Subject: {msg.subject}\nFrom: {msg.from_}\nDate: {msg.date}\n\n{msg.text}"
            
            if msg.attachments:
                result += f"\n\nAttachments ({len(msg.attachments)}):\n"
                for att in msg.attachments:
                    result += f"  - file_path: {os.path.join(attachments_dir, att.filename)} \n ({att.content_type})\n"
            
            return result
        
        return "No relevant emails found."
    
@tool
def Retreave_from_google_drive(query: str) -> str:
        """Search for files in Google Drive based on query."""
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
        import os.path
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.auth.exceptions import RefreshError
        """Search for files in Google Drive based on query.
        Returns the names and ids of matching files.
        """
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
    retriever_llm = helper_llm.bind_tools(base_tools)
    msgs = [system_prompt, HumanMessage(content=query)]
    # Internal tool loop: let helper_llm call tools until it gives a final answer
    while True:
        response = retriever_llm.invoke(msgs)
        print(f"Retriever Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        for tc in response.tool_calls:
            tool_fn = next(t for t in base_tools if t.name == tc["name"])
            result = tool_fn.invoke(tc["args"])
            msgs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
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
    audit_tools = base_tools + [call_retriever_agent, call_calculation_agent]
    audit_llm = helper_llm.bind_tools(audit_tools)
    msgs = [system_prompt, HumanMessage(content=f"{query} (file path: {file_path})")]
    # Internal tool loop: let audit_llm call tools until it gives a final answer
    while True:
        response = audit_llm.invoke(msgs)
        print(f"Audit Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        for tc in response.tool_calls:
            tool_fn = next(t for t in audit_tools if t.name == tc["name"])
            result = tool_fn.invoke(tc["args"])
            msgs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
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
3. Retrieve missing data if necessary (prefer call_retriever_agent).
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
- call_retriever_agent : you can use this tool only 1 time, so use it wisely to retreave all the information.
- scan_documents : as much as you want.
- Retreave_from_email : only 0 time, so use it wisely to retreave all the information you need from the emails about the company or depend on what you need.
- Retreave_from_google_drive : only 0 time, so use it wisely to retreave all the information you need from the google drive about the company or depend on what you need.
- web_search : only 1 times.
- retreave_information : only 0 time, so use it wisely to retreave all the information you need from the database about the company or depend on what you need.
"""
)
    calc_tools = base_tools + [call_retriever_agent]
    calc_llm = helper_llm.bind_tools(calc_tools)
    msgs = [system_prompt, HumanMessage(content=query)]
    # Internal tool loop: let helper_llm call tools until it gives a final answer
    while True:
        response = calc_llm.invoke(msgs)
        print(f"Calculation Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        for tc in response.tool_calls:
            tool_fn = next(t for t in calc_tools if t.name == tc["name"])
            result = tool_fn.invoke(tc["args"])
            msgs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
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
    retriever_llm = llm.bind_tools([store_data])
    state["messages"] = [msg for msg in state["messages"] if not isinstance(msg, SystemMessage)] 
    while True:
        response = retriever_llm.invoke([system_message] + state["messages"])
        if not response.tool_calls:
            break
        for tc in response.tool_calls:
            tool_fn = next(t for t in [store_data] if t.name == tc["name"])
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
graph.add_edge(START, "user_input_node")
graph.add_edge("user_input_node", "main_ai_node")
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
        "exit": "exit_agent"
    }
)
graph.add_edge("exit_agent", "user_input_node")
graph.add_edge("tools_node", "main_ai_node")
app = graph.compile()

result = app.invoke({"messages": []})

print("Final Response from Main AI Agent:")
print(result["messages"][-1].content)