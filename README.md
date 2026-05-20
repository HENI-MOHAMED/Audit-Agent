# Audit Buddy AI (Audit Agent)

![Audit Agent Banner](https://img.shields.io/badge/Status-Active-success)
![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![AI Models](https://img.shields.io/badge/AI-DeepSeek%2FOpenAI-orange)

An intelligent, AI-powered financial auditing and intelligence platform. **Audit Buddy AI** leverages state-of-the-art Large Language Models (LLMs) and Machine Learning to automate financial audits, detect anomalies, forecast revenue, and generate professional analytical PDF reports.

## ✨ Key Features

- **🧠 Multi-Agent AI System:** Uses LangGraph and LangChain to orchestrate specialized agents for document analysis, financial calculations, and local database querying.
- **📊 AI Financial Intelligence Reports:** Dynamically assembles multi-page PDF reports containing rich frontend charts (Recharts) and deep AI-generated contextual analysis (using FPDF2 & DeepSeek).
- **🕵️ Anomaly Detection:** Applies `IsolationForest` across purchase orders and invoices to flag suspicious transactions automatically.
- **📈 ML Profit Predictions:** Predicts future cash flows and profitability using `XGBoost` and `RandomForest` regression models.
- **🖇️ Odoo Integration:** Connects directly to Odoo databases to ingest and map financial schemas and data streams.
- **🛡️ Secure Authentication:** Firebase-powered role-based access control (RBAC) ensuring that only authorized auditors and admins can access intelligent insights.
- **💬 Conversational Interface:** Includes an interactive chat interface with adjustable "thinking modes" (fast vs. reasoning) for querying financial data on the fly.

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI, Python 3.12
- **AI / LLMs:** LangChain, LangGraph, DeepSeek (`helper_llm`), OpenAI
- **Machine Learning:** Scikit-Learn (IsolationForest, RandomForest), XGBoost, Pandas
- **PDF Generation:** FPDF2
- **Database:** SQLite (Local AI State/Vector data) & Odoo (Source DB)

### Frontend
- **Framework:** React 18, Vite, TypeScript
- **Styling:** Tailwind CSS, shadcn/ui
- **Data Visualization:** Recharts, HTML2Canvas 
- **Package Manager:** Bun / NPM

## 📂 Project Structure

```text
📦 Audit-Agent
 ┣ 📂 archive/audit-buddy-ai-96-main/ # React Frontend (Vite + Tailwind + shadcn/ui)
 ┣ 📂 data/                           # Local SQLite databases and Vector stores
 ┣ 📂 scripts/                        # Utility scripts (Firebase auth setup, etc.)
 ┣ 📂 src/                            # Backend Application
 ┃ ┣ 📂 agents/                       # LangGraph AI agents (Audit, Local DB, Invoices)
 ┃ ┣ 📂 api/                          # FastAPI routes and Pydantic models
 ┃ ┣ 📂 database/                     # DB connection handlers
 ┃ ┣ 📂 tools/                        # Agent tool definitions (LLM function calling)
 ┃ ┗ 📂 utils/                        # ML, PDF generation, Configs, Firebase admin
 ┣ 📂 storage/                        # Processed documents, email attachments, JSON configs
 ┣ 📜 main.py                         # FastAPI application entry point
 ┣ 📜 server.py                       # Secondary server/script entry
 ┣ 📜 requirements.txt                # Python dependencies
 ┗ 📜 .env                            # Environment variables (API keys, DB config)
```

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- Node.js & npm (or [Bun](https://bun.sh/))
- Firebase Service Account JSON
- DeepSeek and/or OpenAI API Keys

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-username/audit-buddy-ai.git
cd audit-buddy-ai

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
# Navigate to the frontend directory
cd archive/audit-buddy-ai-96-main

# Install dependencies (using Bun or NPM)
bun install
# or npm install --legacy-peer-deps

# Start the Vite development server
bun run dev
# or npm run dev
```

### 3. Environment Configuration (`.env`)

Create a `.env` file in the root directory and configure your keys:

```ini
# AI Models
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...

# Odoo Database Source
ODOO_DB_HOST=localhost
ODOO_DB_PORT=5432
ODOO_DB_NAME=odoo_db
ODOO_DB_USER=admin
ODOO_DB_PASSWORD=admin

# Firebase 
FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json
```

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This means:
- ✅ Free to use, study, and modify
- ✅ Free to distribute and contribute
- ⚠️ Any derivative work or SaaS deployment **must also be open-sourced** under AGPL-3.0
- ❌ You may **not** use this in a closed-source commercial product without a separate commercial license

For commercial licensing inquiries, contact: **your@email.com**

See the [LICENSE](./LICENSE) file for the full legal text.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! 
1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.
