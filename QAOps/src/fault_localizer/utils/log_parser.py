import os

class LogParser:
    """Module for reading and doing basic parsing of failure logs."""

    @staticmethod
    def read_log_from_file(file_path: str) -> str:
        """Reads failure log content from a local file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def truncate_log(log_content: str, max_length: int = 15000) -> str:
        """
        Truncates the log if it's too large to fit in a typical LLM context window.
        Prioritizes the end of the log as that's where stack traces and failure summaries usually reside.
        """
        if len(log_content) <= max_length:
            return log_content
        
        # Keep the last max_length characters
        return f"...[TRUNCATED]...\n{log_content[-max_length:]}"

    @staticmethod
    def extract_failure_context(raw_log: str) -> str:
        """
        Basic pre-processing before passing to LLM.
        This could involve regex to strip out timestamps, info logs, etc.
        For now, it relies heavily on the LLM to understand the raw string.
        """
        return LogParser.truncate_log(raw_log)
