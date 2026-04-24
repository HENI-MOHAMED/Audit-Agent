from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_chroma import Chroma
from src.utils.config import embeddings
import os
import json
from decimal import Decimal
from datetime import date, datetime
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
import psycopg2
import re


# Cache Chroma DB instances to avoid re-creating connections on every retrieval
_db_cache: dict[tuple, Chroma] = {}

def LoadDataBase(persist_directory: str = "./data/chroma_db_multilingual", collection_name: str = "audit_documents_better_embeddings"):
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
def retreave_information(query: str, persist_directory: str = "./data/chroma_db_multilingual", collection_name: str = "audit_documents_better_embeddings") -> str:
    """ Retreaving information from the database based on the query. It uses similarity search to find the most relevant chunks of information."""
    db = LoadDataBase(persist_directory=persist_directory, collection_name=collection_name)
    results = db.similarity_search(query, k=1)
    print(f"Retreaved Information for the query: '{query}' in collection '{collection_name}': {[r.page_content for r in results]}")
    return "\n".join(r.page_content for r in results)

@tool
def store_data(info: str, persist_directory: str = "./data/chroma_db_multilingual", collection_name: str = "default_collection") -> str:
    """Store new information in the database. This can be used to update the database with new findings or insights. it takes the information to store as a string, the persist directory and the collection name as input. it returns a success message with the collection name and the length of the stored information."""
    # Convert string to Document object
    doc = Document(page_content=info, metadata={"source": "stored_data"})
    
    db = LoadDataBase(persist_directory=persist_directory, collection_name=collection_name)
    db.add_documents([doc])
    print(f"Stored information in collection '{collection_name}' successfully. Content length: {len(info)} characters.")
    print(f"Document metadata: {doc.metadata}")
    print(f"Document content preview: {doc.page_content[:200]}...")  # Print the first 200 characters of the content as a preview
    return f"Successfully stored information in collection '{collection_name}'. Content length: {len(info)} characters."


@tool
def read_odoo_db(query: str) -> str:
    """Execute a SQL query against the Odoo PostgreSQL database and return the results as a JSON string."""
    from src.utils.config import get_odoo_db_host, get_odoo_db_port, get_odoo_db_name, get_odoo_db_user, get_odoo_db_password
    try:
        conn = psycopg2.connect(
            host=get_odoo_db_host(),
            port=get_odoo_db_port(),
            dbname=get_odoo_db_name(),
            user=get_odoo_db_user(),
            password=get_odoo_db_password()
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
    from src.utils.config import get_odoo_db_host, get_odoo_db_port, get_odoo_db_name, get_odoo_db_user, get_odoo_db_password
    try:
        conn = psycopg2.connect(
            host=get_odoo_db_host(),
            port=get_odoo_db_port(),
            dbname=get_odoo_db_name(),
            user=get_odoo_db_user(),
            password=get_odoo_db_password()
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


@tool
def db_connector(query: str, type: str = "read", source: str = "local_db") -> str:
    """ A unified database connector tool that can execute read and write sql queries to the database """
    print(f"DB Connector called with query: {query}, type: {type}, source: {source}")
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

  
_LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ai_audit_db.sqlite")

def local_db_exists() -> bool:
    """Check if the local SQLite database exists."""
    return os.path.exists(_LOCAL_DB_PATH)


@tool
def read_local_db(query: str) -> str:
    """Execute a read SQL query against the local SQLite database and return the results as a JSON string."""
    import sqlite3
    try:
        conn = sqlite3.connect(_LOCAL_DB_PATH, timeout=30)
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
        conn = sqlite3.connect(_LOCAL_DB_PATH, timeout=30)
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
@tool
def import_file_to_local_db(file_path: str, mapping: dict, transformations: dict = None):
    """
    Reads a CSV or XLSX file and inserts its contents into the local database
    using a provided JSON mapping.
    
    The mapping format should be:
    {
      "canonical_table_name": {
        "where_clause": "pandas query string if needed to filter rows, else null",
        "field_mapping": {
          "canonical_column": "file_column_name",
          "another_canonical": "'hardcoded_value'"
        }
      }
    }

    The transformations format (optional) should be:
    {
      "canonical_table_name": {
        "canonical_column": "python expression string using 'x' as the variable, e.g., \"str(x).replace('noise', '')\" or \"pd.to_datetime(x, format='%Y%m%d').strftime('%Y-%m-%d')\""
      }
    }
    """
    import pandas as pd
    import sqlite3
    import os
    import json
    import re

    print(f"Reading file: {file_path}")
    if file_path.lower().endswith('.csv'):
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            print("UTF-8 decoding failed, falling back to latin1 encoding.")
            df = pd.read_csv(file_path, encoding='latin1')
    elif file_path.lower().endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Please provide a CSV or XLSX file.")

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ai_audit_db.sqlite")
    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()

    transformations = transformations or {}

    for canonical_table, config in mapping.items():
        field_map = config.get("field_mapping", {})
        where_clause = config.get("where_clause", None)
        table_transformations = transformations.get(canonical_table, {})

        if not field_map:
            print(f"Skipping {canonical_table}: no valid field mappings found.")
            continue
            
        cursor.execute(f"PRAGMA table_info({canonical_table})")
        valid_columns = [row[1] for row in cursor.fetchall()]
        if not valid_columns:
            print(f"Skipping {canonical_table}: table does not exist.")
            continue
            
        field_map = {k: v for k, v in field_map.items() if k in valid_columns}
        if not field_map:
            print(f"Skipping {canonical_table}: no valid field mappings found after checking schema.")
            continue

        table_df = df
        if where_clause:
            try:
                table_df = table_df.query(where_clause)
            except Exception as e:
                print(f"Error applying where_clause '{where_clause}' to dataframe: {e}")
                continue

        columns = list(field_map.keys())
        batch = []

        for _, row in table_df.iterrows():
            values = []
            for c_field in columns:
                s_field = field_map[c_field]
                
                # Handle quoted strings as static hardcoded values
                if isinstance(s_field, str) and s_field.startswith("'") and s_field.endswith("'"):
                    val = s_field[1:-1]
                else:
                    val = row.get(s_field, None)
                    # Convert pandas NaT or NaN to None for SQLite
                    if pd.isna(val):
                        val = None
                
                # Apply transformation if specified for this column
                if c_field in table_transformations and val is not None:
                    transform_expr = table_transformations[c_field]
                    try:
                        # Evaluate the transformation expression with 'x' being the current value
                        new_val = eval(transform_expr, {"__builtins__": __builtins__}, {"x": val, "re": re, "pd": pd, "str": str, "int": int, "float": float})
                        val = None if pd.isna(new_val) else new_val
                    except Exception as e:
                        print(f"Error applying transformation '{transform_expr}' on value '{val}' for column '{c_field}': {e}")

                # SQLite can't bind dict/list - serialize to JSON string
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                    
                values.append(val)
            batch.append(values)

        if batch:
            placeholders = ",".join(["?"] * len(columns))
            query = f"INSERT INTO {canonical_table} ({','.join(columns)}) VALUES ({placeholders})"
            try:
                cursor.executemany(query, batch)
                print(f"Imported {len(batch)} rows into {canonical_table} from {os.path.basename(file_path)}")
            except Exception as e:
                print(f"Error inserting into {canonical_table}: {e}")

    conn.commit()
    conn.close()
