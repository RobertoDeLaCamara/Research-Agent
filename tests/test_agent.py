import pytest
from src.agent import app, initialize_state_node, route_chat
from langchain_core.messages import HumanMessage

def test_agent_graph_compilation():
    """Verifies that the LangGraph workflow compiles correctly."""
    assert app is not None

def test_initialize_state_node_minimal():
    """Verifies that initialize_state_node adds all missing mandatory fields."""
    initial_state = {"topic": "Test Topic"}
    result = initialize_state_node(initial_state)
    
    # Check that all keys from AgentState are present
    mandatory_keys = [
        "topic", "video_urls", "video_metadata", "summaries", 
        "web_research", "wiki_research", "arxiv_research", 
        "github_research", "scholar_research", "hn_research", 
        "so_research", "reddit_research", "consolidated_summary", 
        "bibliography", "pdf_path", "report", "messages", 
        "research_plan", "next_node", "iteration_count", "last_email_hash"
    ]
    
    for key in mandatory_keys:
        assert key in result, f"Key {key} missing from initialized state"
    
    assert result["topic"] == "Test Topic"
    assert isinstance(result["summaries"], list)
    assert result["iteration_count"] == 0

def test_initialize_state_node_preserves_existing():
    """Verifies that existing fields are preserved."""
    initial_state = {"topic": "Test", "iteration_count": 5, "extra": "data"}
    result = initialize_state_node(initial_state)
    
    assert result["topic"] == "Test"
    assert result["iteration_count"] == 5
    # The node returns a dict based on defaults, but TypedDict might allow extras
    # depending on how it's handled. In our case, defaults only includes known keys.

def test_route_chat_ends_by_default():
    """Verifies that chat goes to send_email if no research keyword is present."""
    state = {"messages": [HumanMessage(content="Thanks for the info")]}
    assert route_chat(state) == "send_email"

def test_route_chat_triggers_research():
    """Verifies that chat triggers re-planning if research keyword is found."""
    state = {"messages": [HumanMessage(content="Please investigate more about X")]}
    assert route_chat(state) == "re_plan"
    
    state = {"messages": [HumanMessage(content="INVESTIGACIÓN: more about Y")]}
    assert route_chat(state) == "re_plan"
