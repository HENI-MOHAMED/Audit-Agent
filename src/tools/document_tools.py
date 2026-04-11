from langchain_core.tools import tool
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


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

def _resolve_file_path(file_path: str) -> str:
    """Return the full path to a file.

    If *file_path* already points to an existing file, return it unchanged.
    Otherwise assume only the filename was given and search the common
    upload/attachment directories so the caller always gets a resolvable path.
    """
    if os.path.isfile(file_path):
        return file_path
    filename = os.path.basename(file_path)
    search_dirs = [
        "storage/email_attachments",
        "data/uploads",
        "storage/Google_Drive_Retrete",
        "storage",
        "data"
    ]
    
    # Prefix absolute directory depending on script execution location
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    search_dirs = [os.path.join(root_dir, d) for d in search_dirs]
    
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, _dirs, files in os.walk(search_dir):
            if filename in files:
                found = os.path.join(root, filename)
                print(f"Resolved '{file_path}' → '{found}'")
                return found
    return file_path  # return as-is; the caller will surface the error


def _scan_documents_impl(file_path: str) -> str:
    """Internal implementation for document scanning (supports recursion for archives)."""
    file_path = _resolve_file_path(file_path)
    if file_path.lower().endswith(('.xlsx', '.xls', '.pdf', '.docx', '.doc','.csv')):
        return Scan_PDF(file_path)
    elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return Scan_image(file_path)
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
    elif file_path.lower().endswith('.zip'):
        try:
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
        except Exception as e:
            return f"Error processing zip file: {str(e)}"
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
    from src.utils.config import get_email_address, get_email_app_password

    EMAIL = get_email_address()
    PASSWORD = get_email_app_password()
    if not EMAIL or not PASSWORD:
        return "Error: EMAIL_ADDRESS or EMAIL_APP_PASSWORD not set in environment variables or settings."
    
    with MailBox("imap.gmail.com").login(EMAIL, PASSWORD) as mailbox:
        criteria = OR(subject=query, text=query, from_=query, to=query)
        messages = mailbox.fetch(criteria=criteria, limit=100, reverse=True)
        
        for msg in messages:
            print(f"Found relevant email: {msg.subject}")
            attachments_dir = f"storage/email_attachments/{msg.from_}"
            
            if msg.attachments:
                print(f"  Found {len(msg.attachments)} attachment(s):")
                for att in msg.attachments:
                    print(f"    - {att.filename} ({att.content_type}, {att.size} bytes)")
                    
                    if save_attachments:
                        os.makedirs(attachments_dir, exist_ok=True)
                        filename = att.filename if att.filename else f"attachment_{att.size}.bin"
                        att_file_path = os.path.join(attachments_dir, filename)
                        with open(att_file_path, 'wb') as f:
                            f.write(att.payload)
                        print(f"      Saved to: {att_file_path}")
            
            result = f"Subject: {msg.subject}\nFrom: {msg.from_}\nDate: {msg.date}\n\n{msg.text}"
            
            if msg.attachments:
                result += f"\n\nAttachments ({len(msg.attachments)}):\n"
                for att in msg.attachments:
                    filename = att.filename if att.filename else f"attachment_{att.size}.bin"
                    result += f"  - file_path: {os.path.join(attachments_dir, filename)} ({att.content_type})\n"
            
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
        # Construct absolute paths to storage/json_configs correctly
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        token_path = os.path.join(root_dir, "storage", "json_configs", "token.json")
        creds_path = os.path.join(root_dir, "storage", "json_configs", "credentials.json")
        json_configs_dir = os.path.join(root_dir, "storage", "json_configs")

        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    # Token has been revoked or expired, delete it and re-authenticate
                    os.remove(token_path)
                    creds = None
            
            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    creds_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                os.makedirs(json_configs_dir, exist_ok=True)
                with open(token_path, "w") as token:
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
            download_dir = f"storage/Google_Drive_Retrete/{query}"
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


