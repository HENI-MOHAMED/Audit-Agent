from typing import TypedDict, Sequence, Annotated
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


@dataclass
class invoice:
    invoice_number: str
    note: str
    invoice_data: dict
    state: str
    audits_results: dict = field(default_factory=dict)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_input: str
    invoces: list[invoice]
    local_db_files: list[str]
    db_source: str
    company_info: dict
    route: str  # "chat" | "audit" | "local_db" | "upload" | "exit"
    thinking_mode: str