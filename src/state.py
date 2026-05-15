from typing import TypedDict, Annotated, Sequence, Dict, Any
from langchain_core.messages import BaseMessage
from operator import add

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]
    file_path: str
    file_type: str
    geometry_data: Dict[str, Any]
    city: str
    compliance_results: Dict[str, Any]
