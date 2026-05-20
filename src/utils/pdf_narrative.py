import json
from langchain_core.messages import HumanMessage, SystemMessage
from src.utils.config import get_helper_llm

def generate_pdf_narrative(report_data: dict) -> dict:
    """Generate a structured professional executive summary and sections based on the report data."""
    llm = get_helper_llm()
    # Assume we use json wrapper if it provides better JSON, but we can also prompt standard model to return JSON
    
    summary = report_data.get('summary', {})
    anomalies_count = len(report_data.get('anomalies', {}).get('flagged_invoices', []))
    
    data_summary = json.dumps({
        "summary_metrics": summary,
        "anomaly_count": anomalies_count
    }, indent=2)

    system_msg = SystemMessage(
        content=(
            "You are a senior financial analyst. Based on the provided data summary, "
            "write a deep and professional structured analysis for a PDF report. "
            "You MUST output ONLY valid JSON matching this exact structure, with no markdown code blocks:\n"
            "{\n"
            '  "executive_summary": "3-4 paragraphs of overall executive summary.",\n'
            '  "chart-revenue": "1-2 paragraphs analyzing Revenue & Profitability Trends.",\n'
            '  "chart-cogs": "1-2 paragraphs analyzing Cost Breakdown Over Time.",\n'
            '  "chart-margin": "1 paragraph analyzing Margin & Ratio Trends.",\n'
            '  "chart-dso": "1 paragraph analyzing DSO & Overdue Trend.",\n'
            '  "chart-billed": "1 paragraph analyzing Billed vs Collected.",\n'
            '  "chart-volume": "1 paragraph analyzing Invoice Volume & Avg Value.",\n'
            '  "chart-customer": "1 paragraph analyzing Customer Concentration Risk.",\n'
            '  "chart-predict": "1-2 paragraphs analyzing ML Profit Predictions.",\n'
            '  "conclusion": "1-2 paragraphs of conclusion and strategic advice."\n'
            "}\n"
            "Do not use markdown formatting (like ** or *) in the text values, just plain text."
        )
    )
    human_msg = HumanMessage(content=f"Analyze this financial data summary:\n{data_summary}")
    
    response = llm.invoke([system_msg, human_msg])
    content = response.content.strip()
    
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
        
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        print("Failed to decode JSON from AI response:")
        print(content)
        # fallback simple dict
        return {
            "executive_summary": content,
            "conclusion": "Analysis generated, but specific charts lacked detail due to formatting error."
        }

