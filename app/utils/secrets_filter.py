"""Logging filter that redacts API key values from log records.

Attached to the root logger in create_app(). Defensive — even if a service
accidentally logs a full URL containing a key (e.g. AssemblyAI ws_url), the
secret will be replaced with a placeholder before the record is emitted.
"""
import logging
import os


class RedactSecretsFilter(logging.Filter):
    KEYS = ("GEMINI_API_KEY", "ASSEMBLYAI_API_KEY", "VAPI_API_KEY")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        replaced = msg
        for k in self.KEYS:
            v = os.getenv(k, "")
            if v and len(v) > 6 and v in replaced:
                replaced = replaced.replace(v, f"<{k}_REDACTED>")
        if replaced is not msg:
            record.msg = replaced
            record.args = ()
        return True
