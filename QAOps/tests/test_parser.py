import sys
import os
import pytest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from log_parser import LogParser

def test_truncate_log():
    long_log = "A" * 20000
    truncated = LogParser.truncate_log(long_log, max_length=15000)
    assert len(truncated) == 15000 + len("...[TRUNCATED]...\n")
    assert truncated.startswith("...[TRUNCATED]...")

def test_extract_failure_context():
    raw_log = "INFO: Starting build\nERROR: NullPointerException at line 42\nINFO: Build failed"
    # For now, extract just truncates. In the future it might do more.
    processed = LogParser.extract_failure_context(raw_log)
    assert processed == raw_log
