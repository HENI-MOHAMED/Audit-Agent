from typing import TypedDict, Sequence, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage, AIMessage
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
communications_manager = {
    "Retrever_Agent_Called_By": [],
    "Calculation_Agent_Called_By": [],
    "Main_AI_Agent_Called_By": [],
    "Audit_Agent_Called_By": [],
    "Tool_Node_Called_By": []
    }
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_message]
    retrever_messages: Annotated[Sequence[BaseMessage], add_message]
    calculation_messages: Annotated[Sequence[BaseMessage], add_message]
    audit_messages: Annotated[Sequence[BaseMessage], add_message]
# Main AI Node
def Main_AI(state: AgentState)-> AgentState:
    """Main AI Node that processes the conversation and generates responses."""
    system_message = SystemMessage(
        content="""You are a Tax and Audit expert in Tunisia. You are the Main agent here, 
you have others helper agents that you can assign tasks to. You can also use the tools at 
your disposal to retrieve information and data. You can also ask the helper agents by calling 
them by their name and giving them a query and instructions and they will retrieve the 
information for you and return it to you and then you can use it to answer the user question 
or to retrieve more information if needed.

For now you only have tow helper agent 'Retrever_Agent' and 'Calculation_Agent' that you can call by using the tool 'Agents_Manager' and giving it the name of the agent 'Retrever_Agent' or 'Calculation_Agent' and the query and instructions (add the instructions to the query argument) and the agent fild(in your case it should always be "messages").

The Retrever_Agent will retrieve the information for you and return it to you and then you 
can use it to answer the user question or to retrieve more information if needed.

The Calculation_Agent will preform all the calculation that you want, you just give it the query and instructions and this is cirtcal to give it detailed instructions about what you want to calculate and what information you want it to use in the calculation or you can let it decide.

90 percent of your information will come from the Retrever_Agent. Only use your tools if 
you are suspicious about the information you retrieve from the Retrever_Agent. Even if you 
want to look for something else to get more details, use Retrever_Agent.
Current year: 2026"""
    )
    if not any(isinstance(msg, SystemMessage) for msg in state["messages"]):
        state["messages"].insert(0, system_message)
    response = llm.invoke(state["messages"])
    state["messages"].append(response)
    print(f" \n \n Main AI Agent Response: {response.content} \n \n")
    return state
def sould_continue(state: AgentState) -> bool:
    """ A simple function to check if the agent should continue or not."""
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return False
    return True

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
    search_kwargs={"k": 5}  # K is the amount of chunks to return
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
        results = DDGS().text(query, max_results=5)

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
                    full_text = page_text[:3000]
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
                    results.append(scan_documents.func(extracted_file_path))
        
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
                        results.append(scan_documents.func(extracted_file_path))
            
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
        criteria = OR(subject=query, text=query, from_=query, to=query, cc=query, bcc=query, keyword=[q for q in query.split()])  # Search in multiple fields
        messages = mailbox.fetch(criteria=criteria, limit=100, reverse=True)
        
        for msg in messages:
            print(f"Found relevant email: {msg.subject}")
            
            # Process attachments
            attachment_paths = []
            if msg.attachments:
                print(f"  Found {len(msg.attachments)} attachment(s):")
                for att in msg.attachments:
                    print(f"    - {att.filename} ({att.content_type}, {att.size} bytes)")
                    
                    if save_attachments:
                        # Save attachment to disk
                        # Create attachments folder if it doesn't exist
                        attachments_dir = f"email_attachments/{msg.from_}"
                        os.makedirs(attachments_dir, exist_ok=True)
                        file_path = os.path.join(attachments_dir, att.filename)
                        with open(file_path, 'wb') as f:
                            f.write(att.payload)
                        print(f"      Saved to: {file_path}")
                        attachment_paths.append((att.filename, file_path, att.content_type))
            
            # Build response
            result = f"Subject: {msg.subject}\nFrom: {msg.from_}\nDate: {msg.date}\n\n{msg.text}"
            
            if attachment_paths:
                result += f"\n\nAttachments ({len(attachment_paths)}):\n"
                for filename, file_path, content_type in attachment_paths:
                    result += f"  - {filename}: {scan_documents.func(file_path)} \n ({content_type})\n"
            
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
                creds.refresh(Request())
            else:
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
@tool
def Agents_Manager(Agent_name: str, query: str, sender_fild: str) -> str:
    """A tool to manage the agents and assign tasks to them. it takes the name of the agent and the query and the sender_fild as input and then it calls the agent with the query and return the response from the agent."""
    return f"{Agent_name}: {query} (from {sender_fild})"

# Retrever Agent Node
def Retrever_Agent(state: AgentState) -> AgentState:
    """An helper AI Agent that Retreves information from where it decides based on the on the request of the Main AI Agent. The retreved information should be cheked by the Main AI Agent"""
    print(" \n \n Retrever Agent is processing the request... \n \n")
    system_prompt = SystemMessage(content="You are a helper Agent that work for the main AI agent so you answer should be clear, your mission is to retreve informations and data mainly about the financial laws, tax laws, audit procedures, and financial regulations in Tunisia. and info about the company and you can also retreve invoces and informations from email and google drive. All of that is base on the Main AI request. You should decide where to retreve the information based on the Main AI request and then retreave the information, process it, clean it, make sure to include all the law and sources and artecle and then return it to the Main AI Agent. Make sure of the info before returning it to the Main AI Agent, you can use the tools at your disposal to retreave the information, you can also use the web search tool to retreave information from the web if needed, but make sure to check the sources and the credibility of the information you retreave from the web. The google drive tool will return informations about all the documents and file it retreved if you want to see inside the files and documents you can take the file path that it retreve and use it in scan_documents. You don't chat or add any else, your output should be a clear and concise summary of the information you retreved and processed, no quations nothing else just inforamtaion. It's preferd if you use multiple sources to verify the information you retreved. Make your output ideal for an AI agent. Current year: 2026")
    if not any(isinstance(msg, SystemMessage) for msg in state["retrever_messages"]):
        state["retrever_messages"].insert(0, system_prompt)
    target = communications_manager["Retrever_Agent_Called_By"][-1] if communications_manager["Retrever_Agent_Called_By"] else "unknown"
    ai_msg = next(m for m in reversed(state[target]) if isinstance(m, AIMessage))
    agent_tc = next((ts for ts in ai_msg.tool_calls if ts["name"] == "Agents_Manager" and ts["args"]["Agent_name"] == "Retrever_Agent"), None)
    query = agent_tc["args"]["query"]
    state["retrever_messages"].append(HumanMessage(content=query))
    helper_llm_response = helper_llm.invoke(state["retrever_messages"])
    state["retrever_messages"].append(helper_llm_response)

    if not helper_llm_response.tool_calls:
        state[target].append(ToolMessage(content=f"Retrever_Agent: {helper_llm_response.content}", tool_call_id=agent_tc["id"]))
        for tc in ai_msg.tool_calls:
            if tc["name"] != "Agents_Manager":
                tool_fn = next((t for t in tools if t.name == tc["name"]), None)
                if tool_fn:
                    result = tool_fn.invoke(tc["args"])
                    state[target].append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                else:
                    state[target].append(ToolMessage(content="Tool not available", tool_call_id=tc["id"]))
        print(f"\n \n Retrever Agent Response: {helper_llm_response.content} \n \n")
    return state

def Tool_Node(state: AgentState) -> AgentState:
    """A Tool Node to call the Retrever Agent from the Main AI Agent and give it the query and instructions and then return the response from the Retrever Agent to the Main AI Agent."""
    target = communications_manager["Tool_Node_Called_By"][-1] if communications_manager["Tool_Node_Called_By"] else "unknown"
    ai_msg = next(m for m in reversed(state[target]) if isinstance(m, AIMessage))
    if ai_msg.tool_calls:
        # Execute each requested tool and add proper ToolMessage responses
        for tc in ai_msg.tool_calls:
            tool_fn = next(t for t in tools if t.name == tc["name"])
            result = tool_fn.invoke(tc["args"])
            state[target].append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )
    return state

# This node is responsible of all that calculation that the main AI Agent want to preform like calculating the tax based on the information that the Retrever Agent retreave or calculating the audit risk or any other calculation that the main AI Agent want to preform based on the information that the Retrever Agent retreave, this node is important because it will take care of all the calculation and make sure that the information is accurate and reliable before returning it to the main AI Agent.
def Calculation_Agent(state: AgentState) -> AgentState:
    """An helper AI Agent that work for the main AI agent, it will preform all the calculation that the main AI Agent want to preform"""
    print(" \n \n Calculation Agent is processing the request... \n \n")
    system_prompt = SystemMessage(content="""You are a helper Agent that work for the main AI agent so you answer should be clear,
                                   your mission is to preform calculations based on the information that the Retrever Agent retreave and based on the request of the Main AI Agent.
                                   you take the request from the Main AI Agent about what it want you to calculate and base on that request you will decide what information you need to preform the calculation,
                                   should your tools to get the informations that you diceded that you need like invoices details or financial data of a spicific year of a spicific company or person or provider or email... any other information that you need to preform the calculation
                                   moste of the time you can relay on the 'Retrever_Agent' to retreave the info form web, database, email, google drive , all you need to do to use the 'Agents_Manager' tool and call the 'Retrever_Agent' and give it the query and instructions in details ( and the instructions in detail with the query arg) and the agent filde(in your its always 'calculation_messages').
                                    But you can also use your own tools that are in your disposal to retreave the information you need if the 'Retrever_Agent' response is not enough or did not satisfy you and you still need more information to preform the calculations
                                   Don't forget to add a detailed explanation of the calculation steps and the final result in your response to the Main AI Agent.
                                   Current year: 2026""")
    if not any(isinstance(msg, SystemMessage) for msg in state["calculation_messages"]):
        state["calculation_messages"].insert(0, system_prompt)
    target = communications_manager["Calculation_Agent_Called_By"][-1] if communications_manager["Calculation_Agent_Called_By"] else "unknown"
    ai_msg = next(m for m in reversed(state[target]) if isinstance(m, AIMessage))
    agent_tc = next((ts for ts in ai_msg.tool_calls if ts["name"] == "Agents_Manager" and ts["args"]["Agent_name"] == "Calculation_Agent"), None)
    query = agent_tc["args"]["query"]
    state["calculation_messages"].append(HumanMessage(content=query))
    clac_tools = tools + [Agents_Manager]
    calculations_llm = helper_llm.bind_tools(clac_tools)
    res = calculations_llm.invoke(state["calculation_messages"])
    state["calculation_messages"].append(res)
    if not res.tool_calls:
        state[target].append(ToolMessage(content=f"Calculation_Agent: {res.content}", tool_call_id=agent_tc["id"]))

        for tc in ai_msg.tool_calls:
            if tc["name"] != "Agents_Manager":
                tool_fn = next((t for t in tools if t.name == tc["name"]), None)
                if tool_fn:
                    result = tool_fn.invoke(tc["args"])
                    state[target].append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                else:
                    state[target].append(ToolMessage(content="Tool not available", tool_call_id=tc["id"]))
        print(f"\n \n Calculation Agent Response: {res.content} \n \n")
    return state



def Audit_Agent(state: AgentState) -> AgentState:
    """An helper AI Agent that work for the main AI agent, it will preform all the audit procedures and risk assessment that the main AI Agent want to preform"""
    system_prompt = SystemMessage(content="""
                You are a helper Agent that work for the main AI agent so you answer should be clear,
                your mission is to preform audit procedures and risk assessment based on the information that you retreave,
                you will be given a request from the Main AI containing the invoce file_path that you need to check (use scan_documents tool), for every invoice you need to create a Report that look like this, but before i give the example of the report you should know that for every invoice you need to check first the company database(via 'retreave_information' tool), email (via 'Retreave_from_email' tool) and google drive (via 'Retreave_from_google_drive' tool) for any information about the invoice,
                to check if the invoice is real (the company really bought something from this provider and the invoice is for a real transaction) or if it is a fraud (the company did not buy anything from this provider or the quantity or the price in the invoice are not correct, the date of the invoice is not correct,).
                after you check that the invoice is real or fraud you need to check if the invoice is compliant with the tax laws and regulations in Tunisia and if it is not compliant you need to explain why, you can get informations about the tax laws and regulations in Tunisia from the 'Retreaver_Agent' using the 'Agents_Manager' tool by giving it the query and detailed instraction to retereave the informations(you can use as much as you want), you can also use the web search tool if you need to veryfy the informations if you suspect tha the retreaver agent made a mistake or if you want to get more details.
                and finaly you need to find a way to fix the invoice if it is not compliant and explain the steps to fix it, you can also use the 'Calculation_Agent' via 'Agents_Manager' if you need to preform any calculation to find a way to fix the invoice or to explain why it is not compliant.
                and find a way to optimize the tax for the company based on the invoice details and the tax laws and the company informations.
                Here is an example of the report you need to create for every invoice: '
                                  📄 INVOICE AUDIT & TAX OPTIMIZATION REPORT
1️⃣ Header Section

Client Name: XYZ SARL

MF (Matricule Fiscal): 1234567/A/M/000

Audit Period: January 2026

Invoice Reference: INV-2026-0145

Invoice Date: 15/01/2026

Supplier Name: ABC Services SARL

Supplier MF: 9876543/B/N/000

Audit Conducted By: Autonomous Fiscal Guardian v1.0

Date of Audit: 20/01/2026

2️⃣ Executive Summary

The invoice has been analyzed for compliance with Tunisian tax law, VAT correctness, accounting integrity, and optimization opportunities.

✅ VAT calculation is mathematically correct
⚠️ Missing mandatory legal mention
❌ Expense category misclassified
💡 Optimization opportunity detected: deductible expense reclassification

3️⃣ Legal Compliance Verification

Based on:

Direction Générale des Impôts

Code de la TVA

Code de l'IRPP et de l'IS

✅ Mandatory Invoice Elements Check
Element Required	Present	Status
Supplier MF	✔	Compliant
Client MF	✔	Compliant
VAT Rate	✔	Compliant
Unique Invoice Number	✔	Compliant
Description of Goods	✔	Compliant
Legal VAT Mention	❌	Non-Compliant

⚠️ Missing mention: “TVA collectée selon le régime réel”

Risk Level: Medium
Potential Fine: Administrative penalty under Tunisian tax procedure rules

4️⃣ VAT Validation
VAT Breakdown:

Net Amount (HT): 10,000 TND

VAT (19%): 1,900 TND

Total TTC: 11,900 TND

✔ Calculation verified
✔ VAT rate compliant with standard 19% rate
✔ Supplier VAT status valid

Input VAT Deductibility Check

Expense Nature: Consulting Service

Business Purpose: Operational

Deductible: ✅ Yes

5️⃣ Accounting Classification Review

Current Classification:

Account: 613 – External Services

⚠ Issue Detected:
The service relates to software development and qualifies as:

Recommended Classification:

Account: 218 – Immobilisations incorporelles

Impact:

Reclassification allows amortization over 3 years
This improves tax smoothing strategy

6️⃣ Tax Optimization Opportunities
💡 Optimization #1: Capitalization Instead of Expense

If treated as an asset:

Annual amortization: 3,333 TND

Reduces taxable income gradually

Improves EBITDA presentation

💡 Optimization #2: VAT Timing Optimization

If invoice payment delayed to next fiscal period:

VAT credit timing advantage possible

7️⃣ Fraud & Risk Indicators

AI Risk Analysis:

✔ Supplier exists in tax registry

✔ No duplicate invoice detected

✔ No abnormal VAT rate

❌ Slight rounding anomaly detected (0.200 TND difference)

Fraud Risk Score: 12% (Low)

8️⃣ Financial Impact Summary
Scenario	Taxable Income Impact	Cash Flow Impact
Current Treatment	-10,000 TND	-11,900 TND
Optimized Treatment	-3,333 TND/year	-11,900 TND

Projected Tax Savings Over 3 Years: 2,533 TND

9️⃣ Final Recommendation

✔ Correct missing legal mention
✔ Reclassify expense as intangible asset
✔ Maintain documentation for tax inspection
✔ Monitor amortization schedule
                                  
'        
                                  
you are the most importent agent in this system so every think you say and do is critical that why you should be very careful and make sure that the informations you retreave are accurate and reliable and from trusted sources.
                                  
                                                            
""")
    if not any(isinstance(msg, SystemMessage) for msg in state["audit_messages"]):
        state["audit_messages"].insert(0, system_prompt)
    target = communications_manager["Audit_Agent_Called_By"][-1] if communications_manager["Audit_Agent_Called_By"] else "unknown"
    ai_msg = next(m for m in reversed(state[target]) if isinstance(m, AIMessage))
    agent_tc = next((ts for ts in ai_msg.tool_calls if ts["name"] == "Agents_Manager" and ts["args"]["Agent_name"] == "Audit_Agent"), None)
    query = agent_tc["args"]["query"]
    state["audit_messages"].append(HumanMessage(content=query))
    audit_tools = tools + [Agents_Manager]
    audit_llm =llm.bind_tools(audit_tools)
    # Internal tool loop: let audit_llm call tools until it gives a final answer
    res = audit_llm.invoke(state["audit_messages"])
    state["audit_messages"].append(res)
    if not res.tool_calls:
        state[target].append(ToolMessage(content=f"Audit_Agent: {res.content}", tool_call_id=agent_tc["id"]))
        for tc in ai_msg.tool_calls:
            if tc["name"] != "Agents_Manager":
                tool_fn = next((t for t in tools if t.name == tc["name"]), None)
                if tool_fn:
                    result = tool_fn.invoke(tc["args"])
                    state[target].append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                else:
                    state[target].append(ToolMessage(content="Tool not available", tool_call_id=tc["id"]))
        print(f"\n \n Audit Agent Response: {res.content} \n \n")
    return state

# def where_to_go_next_audit(state: AgentState) -> str:

def where_to_go_next_main(state: AgentState) -> str:    
    mes = state["messages"][-1]
    for ts in mes.tool_calls:
        if ts["name"] == "Agents_Manager":
            if ts["args"]["Agent_name"] == "Retrever_Agent":
                communications_manager["Retrever_Agent_Called_By"].append("messages")
                return "retrever_agent_node"
            elif ts["args"]["Agent_name"] == "Calculation_Agent":
                communications_manager["Calculation_Agent_Called_By"].append("messages")
                return "calculation_agent_node"
            elif ts["args"]["Agent_name"] == "Audit_Agent":
                communications_manager["Audit_Agent_Called_By"].append("messages")
                return "audit_agent_node"
    if mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append("messages")
        return "tools_node"
    return 'end'
def where_to_go_next_retrever(state: AgentState) -> str: 
    entry_point = communications_manager["Retrever_Agent_Called_By"][-1] if communications_manager["Retrever_Agent_Called_By"] else "unknown"   
    mes = state[entry_point][-1]
    local_mes = state["retrever_messages"][-1] if "retrever_messages" in state and state["retrever_messages"] else mes
    if local_mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append("retrever_messages")
        return "tools_node"
    if mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append(entry_point)
        return "tools_node"
    if entry_point == 'calculation_messages':
        return "calculation_agent_node"
    if entry_point == 'audit_messages':
        return "audit_agent_node"
    return 'main_ai_node'
def where_to_go_next_calculation(state: AgentState) -> str:
    entry_point = communications_manager["Calculation_Agent_Called_By"][-1] if communications_manager["Calculation_Agent_Called_By"] else "unknown"   
    mes = state[entry_point][-1]
    local_mes = state["calculation_messages"][-1] if "calculation_messages" in state and state["calculation_messages"] else mes
    if "Agents_Manager" in [tc["name"] for tc in local_mes.tool_calls]:
        agent_tc = next(tc for tc in local_mes.tool_calls if tc["name"] == "Agents_Manager")
        #TODO: i can optimize this part to get rid of the if statements, figure out a way to do that future me
        if agent_tc["args"]["Agent_name"] == "Audit_Agent":
            communications_manager["Audit_Agent_Called_By"].append("calculation_messages")
            return "audit_agent_node"
        elif agent_tc["args"]["Agent_name"] == "Retrever_Agent":
            communications_manager["Retrever_Agent_Called_By"].append("calculation_messages")
            return "retrever_agent_node"
    if local_mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append("calculation_messages")
        return "tools_node"
    if mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append(entry_point)
        return "tools_node"
    if entry_point == 'retrever_messages':
        return "retrever_agent_node"
    if entry_point == 'audit_messages':
        return "audit_agent_node"
    return 'main_ai_node'
def where_to_go_next_audit(state: AgentState) -> str:
    entry_point = communications_manager["Audit_Agent_Called_By"][-1] if communications_manager["Audit_Agent_Called_By"] else "unknown"   
    mes = state[entry_point][-1]
    local_mes = state["audit_messages"][-1] if "audit_messages" in state and state["audit_messages"] else mes
    if "Agents_Manager" in [tc["name"] for tc in local_mes.tool_calls]:
        agent_tc = next(tc for tc in local_mes.tool_calls if tc["name"] == "Agents_Manager")
        #TODO: i can optimize this part to get rid of the if statements, figure out a way to do that future me
        if agent_tc["args"]["Agent_name"] == "Calculation_Agent":
            communications_manager["Calculation_Agent_Called_By"].append("audit_messages")
            return "calculation_agent_node"
        elif agent_tc["args"]["Agent_name"] == "Retrever_Agent":
            communications_manager["Retrever_Agent_Called_By"].append("audit_messages")
            return "retrever_agent_node"
    if local_mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append("audit_messages")
        return "tools_node"
    if mes.tool_calls:
        communications_manager["Tool_Node_Called_By"].append(entry_point)
        return "tools_node"
    if entry_point == 'retrever_messages':
        return "retrever_agent_node"
    if entry_point == 'calculation_messages':
        return "calculation_agent_node"
    return 'main_ai_node'
def where_to_go_next_tools(state: AgentState) -> str:
    entry_point = communications_manager["Tool_Node_Called_By"][-1] if communications_manager["Tool_Node_Called_By"] else "unknown"   
    mes = state[entry_point][-1]
    if isinstance(mes, AIMessage) and mes.tool_calls:
        return "tools_node"
    if entry_point == 'retrever_messages':
        return "retrever_agent_node"
    if entry_point == 'calculation_messages':
        return "calculation_agent_node"
    if entry_point == 'audit_messages':
        return "audit_agent_node"
    return 'main_ai_node'
tools = [search_web, retreave_information, scan_documents, Retreave_from_email, Retreave_from_google_drive, Retreave_from_whatsapp]
llm = llm.bind_tools(tools+[Agents_Manager])
helper_llm = helper_llm.bind_tools(tools)
graph = StateGraph(AgentState)
graph.add_node("main_ai_node", Main_AI)
graph.add_node("retrever_agent_node", Retrever_Agent)
graph.add_node("calculation_agent_node", Calculation_Agent)
graph.add_node("audit_agent_node", Audit_Agent)
graph.add_node("tools_node", Tool_Node)
graph.add_edge(START, "main_ai_node")
graph.add_conditional_edges(
    "main_ai_node", 
    where_to_go_next_main,
    {
        "tools_node": "tools_node",
        "retrever_agent_node": "retrever_agent_node",
        "calculation_agent_node": "calculation_agent_node",
        "audit_agent_node": "audit_agent_node",
        "end": END
    }
)
graph.add_edge("tools_node", "main_ai_node")
graph.add_conditional_edges(
    "retrever_agent_node",
    where_to_go_next_retrever,
    {
        "tools_node": "tools_node",
        "main_ai_node": "main_ai_node",
        "calculation_agent_node": "calculation_agent_node"
    }
)
graph.add_conditional_edges(
    "calculation_agent_node",
    where_to_go_next_calculation,
    {
        "tools_node": "tools_node",
        "main_ai_node": "main_ai_node",
        "retrever_agent_node": "retrever_agent_node"
    })
graph.add_conditional_edges(
    "audit_agent_node",
    where_to_go_next_audit,
    {
        "tools_node": "tools_node",
        "main_ai_node": "main_ai_node",
        "retrever_agent_node": "retrever_agent_node",
        "calculation_agent_node": "calculation_agent_node"
    }
)
graph.add_conditional_edges(
    "tools_node",
    where_to_go_next_tools,
    {
        "main_ai_node": "main_ai_node",
        "retrever_agent_node": "retrever_agent_node",
        "calculation_agent_node": "calculation_agent_node",
        "audit_agent_node": "audit_agent_node"
    }
)
app = graph.compile()

result = app.invoke({"messages": [HumanMessage(content="can you check the email if i have an invoice from Microsoft and check if it is real or fraud?")], "retrever_messages": []})

print("Final Response from Main AI Agent:")
print(result["messages"][-1].content)