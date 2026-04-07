# from __future__ import annotations

# from typing import List

# import easyocr
# from img2table.document import Image as Img2TableImage
# from img2table.ocr import EasyOCR as Img2TableEasyOCR
# from langchain_community.document_loaders import PyPDFLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter

# def scan_image_text(file_path: str) -> List[str]:
#     """Scan an image file and return its content as text lines."""
#     reader = easyocr.Reader(["en", "ar"], gpu=False)
#     return reader.readtext(file_path, detail=0, paragraph=True)


# def recognize_tables(file_path: str) -> list:
#     """Detect tables in an image and return them as a list of DataFrames."""
#     ocr = Img2TableEasyOCR(lang=["en", "ar"])
#     doc = Img2TableImage(file_path)
#     tables = doc.extract_tables(ocr=ocr, borderless_tables=True)
#     print('Raw Table Data:', tables)
#     return [table.df.to_markdown(index=False) for table in tables]

# def Scan_PDF(file_path: str) -> str:
#     """Scans a PDF file and returns its content as clean markdown text with tables."""
#     try:
#         from docling.document_converter import DocumentConverter
#         converter = DocumentConverter()
#         result = converter.convert(file_path)
#         markdown_content = result.document.export_to_markdown()
#         print(f"Scanned PDF '{file_path}' successfully.")
#         return markdown_content
#     except Exception as e:
#         print(f"Error scanning PDF: {e}")
#         return f"Error: {e}"

# def Scan_image(file_path: str) -> str:
#     """Scan an image file and returns its content as text."""
#     from typing import List

#     import easyocr
#     from img2table.document import Image as Img2TableImage
#     from img2table.ocr import EasyOCR as Img2TableEasyOCR


#     def scan_image_text(file_path: str) -> List[str]:
#         """Scan an image file and return its content as text lines."""
#         reader = easyocr.Reader(["en", "ar"], gpu=False)
#         return reader.readtext(file_path, detail=0, paragraph=True)


#     def recognize_tables(file_path: str) -> list:
#         """Detect tables in an image and return them as a list of DataFrames."""
#         ocr = Img2TableEasyOCR(lang=["en", "ar"])
#         doc = Img2TableImage(file_path)
#         tables = doc.extract_tables(ocr=ocr, borderless_tables=True)
#         print('Raw Table Data:', tables)
#         return [table.df.to_markdown(index=False) for table in tables]
#     return "\n".join(scan_image_text(file_path)) + "\n" + "\n".join(recognize_tables(file_path))



# def scan_documents(file_path: str) -> str:
#     """Scans a document (PDF or image or rar or zip) and returns its content as text."""
#     if file_path.lower().endswith('.pdf'):
#         return Scan_PDF(file_path)
#     elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
#         return Scan_image(file_path)
#     elif file_path.lower().endswith('.zip'):
#         import zipfile
#         import os
#         import tempfile
        
#         results = []
#         with tempfile.TemporaryDirectory() as temp_dir:
#             with zipfile.ZipFile(file_path, 'r') as zip_ref:
#                 zip_ref.extractall(temp_dir)
            
#             # Process all extracted files
#             for root, dirs, files in os.walk(temp_dir):
#                 for file in files:
#                     extracted_file_path = os.path.join(root, file)
#                     results.append(scan_documents(extracted_file_path))
        
#         return "\n\n--- Next File ---\n\n".join(results)
#     elif file_path.lower().endswith('.rar'):
#         try:
#             import rarfile
#             import os
#             import tempfile
            
#             results = []
#             with tempfile.TemporaryDirectory() as temp_dir:
#                 with rarfile.RarFile(file_path, 'r') as rar_ref:
#                     rar_ref.extractall(temp_dir)
                
#                 # Process all extracted files
#                 for root, dirs, files in os.walk(temp_dir):
#                     for file in files:
#                         extracted_file_path = os.path.join(root, file)
#                         results.append(scan_documents(extracted_file_path))
            
#             return "\n\n--- Next File ---\n\n".join(results)
#         except ImportError:
#             return "Error: rarfile library not installed. Run: pip install rarfile"
#     else:
#         return f"Unsupported file type: {file_path}"

# def Retreave_from_email(query: str, save_attachments: bool = True) -> str:
#     """Retreave information about the company transaction and invoices from emails based on the query. the query can be the name of the company or the invoice number or the transaction details or the date or the sender or the receiver."""
#     from imap_tools import MailBox, AND
#     from imap_tools.query import OR
#     import os
    
#     EMAIL = "mohamedsuper27@gmail.com"
#     PASSWORD = "wfdd npyq ugpk cbuf"
    
    
#     with MailBox("imap.gmail.com").login(EMAIL, PASSWORD) as mailbox:
#         # Search for emails containing the query in subject or body
#         # Limit to last 100 emails to avoid freezing
#         criteria = OR(subject=query, text=query, from_=query, to=query, cc=query, bcc=query date=query)
#         messages = mailbox.fetch(criteria=criteria, limit=100, reverse=True)
        
#         for msg in messages:
#             print(f"Found relevant email: {msg.subject}")
            
#             # Process attachments
#             if msg.attachments:
#                 print(f"  Found {len(msg.attachments)} attachment(s):")
#                 for att in msg.attachments:
#                     print(f"    - {att.filename} ({att.content_type}, {att.size} bytes)")
                    
#                     if save_attachments:
#                         # Save attachment to disk
#                         # Create attachments folder if it doesn't exist
#                         attachments_dir = f"email_attachments/{msg.from_}"
#                         if save_attachments:
#                             os.makedirs(attachments_dir, exist_ok=True)
#                         file_path = os.path.join(attachments_dir, att.filename)
#                         with open(file_path, 'wb') as f:
#                             f.write(att.payload)
#                         print(f"      Saved to: {file_path}")
            
#             # Build response
#             result = f"Subject: {msg.subject}\nFrom: {msg.from_}\nDate: {msg.date}\n\n{msg.text}"
            
#             if msg.attachments:
#                 result += f"\n\nAttachments ({len(msg.attachments)}):\n"
#                 for att in msg.attachments:
#                     result += f"  - {scan_document(file_path)} \n ({att.content_type})\n"
            
#             return result
        
#         return "No relevant emails found."
# print(Retreave_from_email("Your Microsoft invoice"))

#TODO: make sure that the ai agents focus on the data and the sender deepseekv3 





# def Retreave_from_google_drive(query: str) -> str:
#         SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
#         import os.path
#         from google.auth.transport.requests import Request
#         from google.oauth2.credentials import Credentials
#         from google_auth_oauthlib.flow import InstalledAppFlow
#         from googleapiclient.discovery import build
#         from googleapiclient.errors import HttpError
#         """Search for files in Google Drive based on query.
#         Returns the names and ids of matching files.
#         """
#         creds = None
#         # The file token.json stores the user's access and refresh tokens, and is
#         # created automatically when the authorization flow completes for the first
#         # time.
#         if os.path.exists("token.json"):
#             creds = Credentials.from_authorized_user_file("token.json", SCOPES)
#         # If there are no (valid) credentials available, let the user log in.
#         if not creds or not creds.valid:
#             if creds and creds.expired and creds.refresh_token:
#                 creds.refresh(Request())
#             else:
#                 flow = InstalledAppFlow.from_client_secrets_file(
#                     "credentials.json", SCOPES
#                 )
#                 creds = flow.run_local_server(port=0)
#                 # Save the credentials for the next run
#                 with open("token.json", "w") as token:
#                     token.write(creds.to_json())

#         try:
#             import io
#             from googleapiclient.http import MediaIoBaseDownload
            
#             service = build("drive", "v3", credentials=creds)

#             # Search with priority: exact phrase first, then individual words
#             words = query.split()
#             all_items = []
#             seen_ids = set()
            
#             if len(words) > 1:
#                 # First: search for exact phrase
#                 exact_results = (
#                     service.files()
#                     .list(q=f"fullText contains '{query}'", pageSize=10, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)")
#                     .execute()
#                 )
#                 exact_items = exact_results.get("files", [])
#                 for item in exact_items:
#                     all_items.append(item)
#                     seen_ids.add(item['id'])
                
#                 # Second: search for individual words (excluding already found files)
#                 word_queries = " or ".join([f"fullText contains '{word}'" for word in words])
#                 word_results = (
#                     service.files()
#                     .list(q=word_queries, pageSize=20, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)")
#                     .execute()
#                 )
#                 word_items = word_results.get("files", [])
#                 for item in word_items:
#                     if item['id'] not in seen_ids:
#                         all_items.append(item)
#                         seen_ids.add(item['id'])
#             else:
#                 # Single word search
#                 results = (
#                     service.files()
#                     .list(q=f"fullText contains '{query}'", pageSize=20, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)")
#                     .execute()
#                 )
#                 all_items = results.get("files", [])

#             if not all_items:
#                 return f"No files found matching '{query}'."
            
#             # Create download directory
#             download_dir = f"Google_Drive_Retrete/{query}"
#             os.makedirs(download_dir, exist_ok=True)
            
#             # Google Workspace MIME types and their export formats
#             google_mime_types = {
#                 'application/vnd.google-apps.document': ('application/pdf', '.pdf'),
#                 'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
#                 'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
#                 'application/vnd.google-apps.drawing': ('application/pdf', '.pdf'),
#             }
            
#             result_text = f"Files matching '{query}':\n"
#             for item in all_items:
#                 file_name = item['name']
#                 file_id = item['id']
#                 mime_type = item.get('mimeType', 'unknown')
#                 created_time = item.get('createdTime', 'N/A')
#                 modified_time = item.get('modifiedTime', 'N/A')
                
#                 result_text += f"  - {file_name} (ID: {file_id})\n"
#                 result_text += f"    Type: {mime_type}\n"
#                 result_text += f"    Created: {created_time}\n"
#                 result_text += f"    Modified: {modified_time}\n"
                
#                 # Download or export the file
#                 try:
#                     # Check if it's a Google Workspace file that needs export
#                     if mime_type in google_mime_types:
#                         export_mime, extension = google_mime_types[mime_type]
#                         # Add extension if not present
#                         if not any(file_name.endswith(ext) for ext in ['.pdf', '.xlsx', '.pptx', '.docx']):
#                             file_name_with_ext = file_name + extension
#                         else:
#                             file_name_with_ext = file_name
                        
#                         request = service.files().export_media(fileId=file_id, mimeType=export_mime)
#                         file_path = os.path.join(download_dir, file_name_with_ext)
                        
#                         with io.FileIO(file_path, 'wb') as fh:
#                             downloader = MediaIoBaseDownload(fh, request)
#                             done = False
#                             while not done:
#                                 status, done = downloader.next_chunk()
                        
#                         result_text += f"    Exported to: {file_path}\n\n"
#                     else:
#                         # Regular binary file download
#                         request = service.files().get_media(fileId=file_id)
#                         file_path = os.path.join(download_dir, file_name)
                        
#                         with io.FileIO(file_path, 'wb') as fh:
#                             downloader = MediaIoBaseDownload(fh, request)
#                             done = False
#                             while not done:
#                                 status, done = downloader.next_chunk()
                        
#                         result_text += f"    Downloaded to: {file_path}\n\n"
#                 except Exception as download_error:
#                     result_text += f"    Download/Export failed: {download_error}\n\n"
            
#             return result_text
#         except HttpError as error:
#             return f"An error occurred: {error}"

# print(Retreave_from_google_drive("suck now"))







# import psycopg2
# import os
# import json
# from decimal import Decimal
# from datetime import date, datetime
# from dotenv import load_dotenv
# load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# def odoo_database(query: str) -> str:
#     """Execute a SQL query against the Odoo PostgreSQL database and return the results as a JSON string."""
#     try:
#         conn = psycopg2.connect(
#             host=os.getenv("ODOO_DB_HOST", "localhost"),
#             port=os.getenv("ODOO_DB_PORT", 5432),
#             dbname=os.getenv("ODOO_DB_NAME"),
#             user=os.getenv("ODOO_DB_USER", "odoo"),
#             password=os.getenv("ODOO_DB_PASSWORD")
#         )
#         cursor = conn.cursor()
#         cursor.execute(query)
#         cols = [desc[0] for desc in cursor.description]
#         rows = cursor.fetchall()
#         cursor.close()
#         conn.close()

#         def serialize(v):
#             if isinstance(v, Decimal):
#                 return float(v)
#             if isinstance(v, (date, datetime)):
#                 return v.isoformat()
#             return v

#         result = [dict(zip(cols, (serialize(v) for v in row))) for row in rows]
#         return json.dumps(result, indent=2, ensure_ascii=False)
#     except Exception as e:
#         print(f"Error querying Odoo database: {e}")
#         return json.dumps({"error": str(e)})


# def write_odoo_db(query: str) -> str:
#     """Execute a write SQL query (INSERT, UPDATE, DELETE) against the Odoo PostgreSQL database and return the result as a JSON string."""
#     try:
#         conn = psycopg2.connect(
#             host=os.getenv("ODOO_DB_HOST", "localhost"),
#             port=os.getenv("ODOO_DB_PORT", 5432),
#             dbname=os.getenv("ODOO_DB_NAME"),
#             user=os.getenv("ODOO_DB_USER", "odoo"),
#             password=os.getenv("ODOO_DB_PASSWORD")
#         )
#         cursor = conn.cursor()
#         cursor.execute(query)
#         conn.commit()
#         affected = cursor.rowcount
#         cursor.close()
#         conn.close()
#         return json.dumps({"status": "success", "rows_affected": affected})
#     except Exception as e:
#         print(f"Error writing to Odoo database: {e}")
#         return json.dumps({"error": str(e)})

# print(odoo_database("""SELECT column_name FROM information_schema.columns WHERE table_name = 'res_partner' AND is_nullable = 'NO';"""))












from concurrent.futures import ThreadPoolExecutor, as_completed





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
    


print(search_web("Tunisia tax rates 2023"))

















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

print(search_web("Tunisia tax rates 2023"))
