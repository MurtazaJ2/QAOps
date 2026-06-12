import sys
import os
import pytest
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock the env vars before importing QAOpsAgent
os.environ["GEMINI_API_KEY"] = "mock_key"

from agent import QAOpsAgent

def test_synthesize_results():
    agent = QAOpsAgent(model_name="gemini-2.5-flash") # Doesn't matter as we only test synthesize
    
    state = {
        "raw_failure_log": "",
        "summarized_failure": "",
        "commits": [
            {"sha": "123", "score": 20},
            {"sha": "456", "score": 90},
            {"sha": "789", "score": 10}
        ],
        "top_suspect": {}
    }
    
    result = agent.synthesize_results(state)
    assert result["top_suspect"]["sha"] == "456"
    assert result["top_suspect"]["score"] == 90
