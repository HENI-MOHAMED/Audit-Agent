from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from transformers import AutoTokenizer
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import os
import glob
import json
from datetime import datetime
import signal
from contextlib import contextmanager

# Timeout context manager
class TimeoutException(Exception):
    pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

# Initialize converter and tokenizer once
converter = DocumentConverter()
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", model_max_length=1024)
chunker = HybridChunker(
    tokenizer = tokenizer,
    max_tokens = 1000,
    merge_peers=True
)

# BETTER EMBEDDING MODEL - Choose one:
# Option 1: Larger multilingual model (recommended)
print("Initializing embeddings...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",  # Better than MiniLM
    model_kwargs={'device': 'cpu'},  # Change to 'cuda' if you have GPU
    encode_kwargs={'normalize_embeddings': True}  # Normalize for better scoring
)

# Option 2: Even better - multilingual-e5 (uncomment to use)
# embeddings = HuggingFaceEmbeddings(
#     model_name="intfloat/multilingual-e5-large",
#     model_kwargs={'device': 'cpu'},
#     encode_kwargs={'normalize_embeddings': True}
# )

# Option 3: Best for French/Arabic - labse (uncomment to use)
# embeddings = HuggingFaceEmbeddings(
#     model_name="sentence-transformers/LaBSE",
#     model_kwargs={'device': 'cpu'},
#     encode_kwargs={'normalize_embeddings': True}
# )

# Initialize or load existing ChromaDB vector store with NEW collection name
pdf_lib_path = "./archive/PDF_lib"
progress_file = "./tests/processing_progress_v2.json"
persist_directory = "./data/chroma_db_multilingual"
collection_name = "audit_documents_better_embeddings"  # Different collection name

print("Initializing ChromaDB vector store...")
vectorstore = Chroma(
    embedding_function=embeddings,
    collection_name=collection_name,
    persist_directory=persist_directory
)

# Load progress tracking
processed_pdfs = set()
skipped_pdfs = set()
if os.path.exists(progress_file):
    with open(progress_file, 'r') as f:
        progress_data = json.load(f)
        processed_pdfs = set(progress_data.get('processed', []))
        skipped_pdfs = set(progress_data.get('skipped', []))
    print(f"Resuming: {len(processed_pdfs)} PDFs already processed, {len(skipped_pdfs)} skipped")

def save_progress():
    with open(progress_file, 'w') as f:
        json.dump({
            'processed': list(processed_pdfs),
            'skipped': list(skipped_pdfs),
            'last_updated': datetime.now().isoformat()
        }, f, indent=2)

# Walk through all subdirectories in PDF_lib
print(f"Scanning {pdf_lib_path} for PDF files...")
pdf_count = 0
total_processed = 0
total_skipped = 0
total_chunks_stored = 0

for root, dirs, files in os.walk(pdf_lib_path):
    # Get the category (folder name)
    category = os.path.relpath(root, pdf_lib_path)
    if category == ".":
        category = "root"
    
    # Process all PDF files in current directory
    pdf_files = [f for f in files if f.lower().endswith('.pdf')]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(root, pdf_file)
        pdf_count += 1
        
        # Skip if already processed
        if pdf_path in processed_pdfs:
            print(f"\n[{pdf_count}] Skipping (already processed): {pdf_file}")
            total_processed += 1
            continue
        
        # Skip if previously failed/skipped
        if pdf_path in skipped_pdfs:
            print(f"\n[{pdf_count}] Skipping (previously failed): {pdf_file}")
            total_skipped += 1
            continue
        
        print(f"\n[{pdf_count}] Processing: {pdf_file}")
        print(f"    Category: {category}")
        
        try:
            # Convert PDF with timeout (300 seconds = 5 minutes)
            with time_limit(300):
                result = converter.convert(pdf_path)
            
            # Chunk the document
            chunk_iter = chunker.chunk(result.document)
            chunks = list(chunk_iter)
            print(f"    Created {len(chunks)} chunks")
            
            # Convert chunks to LangChain Documents
            documents = []
            for i, chunk in enumerate(chunks):
                chunk_data = chunk.model_dump()
                
                # Create LangChain Document with metadata including category
                doc = Document(
                    page_content=chunk_data['text'],
                    metadata={
                        'chunk_index': i,
                        'source': pdf_path,
                        'filename': pdf_file,
                        'category': category,
                        'headings': str(chunk_data.get('meta', {}).get('headings', [])),
                        'doc_items': str(chunk_data.get('meta', {}).get('doc_items', []))
                    }
                )
                documents.append(doc)
            
            # Store this PDF's chunks in ChromaDB immediately
            print(f"    Storing {len(documents)} chunks in database...")
            vectorstore.add_documents(documents)
            total_chunks_stored += len(documents)
            print(f"    ✓ Stored in database (total: {total_chunks_stored} chunks)")
            
            # Mark as processed and save progress
            processed_pdfs.add(pdf_path)
            total_processed += 1
            save_progress()
            print(f"    ✓ Progress saved")
                
        except TimeoutException:
            print(f"    ⚠ Timeout! Skipping {pdf_file} (took longer than 5 minutes)")
            skipped_pdfs.add(pdf_path)
            total_skipped += 1
            save_progress()
            continue
        except Exception as e:
            print(f"    ✗ Error processing {pdf_file}: {str(e)}")
            skipped_pdfs.add(pdf_path)
            total_skipped += 1
            save_progress()
            continue

print(f"\n{'='*80}")
print(f"Processing complete!")
print(f"Total PDFs scanned: {pdf_count}")
print(f"Successfully processed: {total_processed}")
print(f"Skipped/Failed: {total_skipped}")
print(f"Total chunks stored in database: {total_chunks_stored}")
print(f"{'='*80}\n")

# Create retriever for LangChain integration
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Function to retrieve chunks based on query (LangChain compatible)
def retrieve_chunks(query: str, k: int = 5):
    """
    Retrieve relevant chunks from the vector store based on a query.
    
    Args:
        query (str): The search query
        k (int): Number of results to return (default: 5)
    
    Returns:
        list[Document]: List of LangChain Document objects with content and metadata
    """
    documents = vectorstore.similarity_search(query, k=k)
    return documents

def retrieve_chunks_with_scores(query: str, k: int = 5):
    """
    Retrieve relevant chunks with similarity scores.
    
    Args:
        query (str): The search query
        k (int): Number of results to return (default: 5)
    
    Returns:
        list[tuple]: List of (Document, score) tuples
    """
    results = vectorstore.similarity_search_with_score(query, k=k)
    return results

# Example usage
print("\n" + "="*80)
print("Testing retrieval function:")
print("="*80)
test_query = "freelancer"
results = retrieve_chunks_with_scores(test_query, k=3)

print(f"\nQuery: '{test_query}'")
print(f"Found {len(results)} relevant chunks:\n")

for i, (doc, score) in enumerate(results):
    print(f"--- Result {i+1} (Score: {score:.4f}) ---")
    print(f"Chunk Index: {doc.metadata.get('chunk_index', 'N/A')}")
    print(f"Source: {doc.metadata.get('source', 'N/A')}")
    print(f"Category: {doc.metadata.get('category', 'N/A')}")
    print(f"Text Preview: {doc.page_content[:200]}...")
    print()







# import json
# import os
# _LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ai_audit_db.sqlite")


# def write_local_db(query: str) -> str:
#     """Execute a write SQL query (INSERT, UPDATE, DELETE) against the local SQLite database and return the result as a JSON string."""
#     import sqlite3
#     try:
#         conn = sqlite3.connect(_LOCAL_DB_PATH, timeout=30)
#         cursor = conn.cursor()
#         cursor.execute(query)
#         conn.commit()
#         affected = cursor.rowcount
#         cursor.close()
#         conn.close()
#         print(f"Executed local DB write query: {query}\nRows affected: {affected} \n \n")
#         return json.dumps({"status": "success", "rows_affected": affected})
#     except Exception as e:
#         print(f"Error writing to local database: {e}")
#         return json.dumps({"error": str(e)})



# write_local_db("""""")
