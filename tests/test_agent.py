import pytest
from src.agent import app

def test_agent_graph_compilation():
    """Verifies that the LangGraph workflow compiles correctly."""
    assert app is not None
