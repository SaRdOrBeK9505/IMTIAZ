"""
JSON structured log formatter.
Production'da ELK Stack, Datadog yoki boshqa log aggregator uchun.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Har bir log yozuvini JSON qatoriga aylantiradi.

    Chiqish formati:
    {
        "timestamp": "2026-08-04T10:00:00.000Z",
        "level":     "ERROR",
        "logger":    "apps.ai_assistant.services",
        "message":   "AI provider xatosi",
        "module":    "services",
        "line":      42,
        "exc_info":  "Traceback ...",   // faqat xatoliklarda
        "data":      {...}              // extra={data: ...} bo'lsa
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            'timestamp': datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds'),
            'level':     record.levelname,
            'logger':    record.name,
            'message':   record.getMessage(),
            'module':    record.module,
            'line':      record.lineno,
        }

        # Extra data (RequestLoggingMiddleware va boshqalardan)
        if hasattr(record, 'data'):
            log['data'] = record.data

        # Exception stack trace
        if record.exc_info:
            log['exc_info'] = self.formatException(record.exc_info)
        elif record.exc_text:
            log['exc_info'] = record.exc_text

        # Celery task ma'lumotlari
        if hasattr(record, 'task_id'):
            log['task_id'] = record.task_id

        return json.dumps(log, ensure_ascii=False, default=str)
