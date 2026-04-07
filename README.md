# Audit Agent Project

AI-powered audit and invoice processing system for Tunisian tax compliance.

## Project Structure

```
/
├── server.py                   # FastAPI server entry point
├── main.py                     # Main application logic & agent graph
├── .env                        # Environment configuration
│
├── src/                        # Source code
│   ├── agents/                 # LangGraph agents & nodes
│   │   ├── audit_agents.py     # Audit helper agents
│   │   ├── invoice_nodes.py    # Invoice processing nodes
│   │   └── local_db_nodes.py   # Local database agents
│   │
│   ├── api/                    # API layer
│   │   ├── routes.py           # FastAPI routes & endpoints
│   │   └── models.py           # Pydantic models
│   │
│   ├── tools/                  # LangChain tools
│   │   └── document_tools.py   # Document scanning, web search, email
│   │
│   ├── utils/                  # Utilities
│   │   ├── config.py           # Configuration & LLM factories
│   │   └── stream_utils.py     # Streaming utilities
│   │
│   └── database/               # Database tools
│       ├── db_tools.py         # ChromaDB & Postgres tools
│       └── Extract_data_better_embeddings.py
│
├── data/                       # Data files (gitignored)
│   ├── ai_audit_db.sqlite      # SQLite conversation history
│   ├── chroma_db_multilingual/ # Vector database
│   └── uploads/                # User file uploads
│
├── storage/                    # Storage directories (gitignored)
│   ├── email_attachments/      # Downloaded email attachments
│   ├── json_configs/           # JSON configuration files
│   └── Google_Drive_Retrete/   # Google Drive downloads
│
├── tests/                      # Test files
└── archive/                    # Archived code
```

## Running the Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the server
python server.py
```

The server will run on `http://0.0.0.0:8000` with auto-reload enabled.

## Key Features

- **Invoice Processing**: Automated extraction and verification of invoice data
- **Multi-source Retrieval**: Email, Google Drive, and local file support
- **Audit Compliance**: Tunisian tax law compliance checking
- **Vector Database**: ChromaDB for document similarity search
- **Streaming Responses**: Real-time agent output streaming via WebSocket

## Environment Variables

Required environment variables in `.env`:
- `OPENAI_API_KEY` - OpenAI API key
- `DEEPSEEK_API_KEY` - DeepSeek API key
- `EMAIL_ADDRESS` - Email for attachment retrieval
- `EMAIL_APP_PASSWORD` - Email app password
- `ODOO_DB_*` - Odoo database credentials (if using Odoo)
