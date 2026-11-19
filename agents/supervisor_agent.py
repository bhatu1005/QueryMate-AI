"""Intent classifier and deterministic safe fallback for the supervisor node."""

import json
import logging
import re
from typing import Any

from config.settings import Settings, get_settings
from llm.ollama_client import get_chat_model

logger = logging.getLogger(__name__)
INTENTS = {"SQL_QUERY", "DOCUMENT_QUERY", "FILE_SUMMARY", "HYBRID_QUERY", "GENERAL_QUERY"}


def _fallback_intent(question: str, has_files: bool) -> str:
    text = question.lower()
    db_terms = (
        "database", "sql", "table", "column", "rows", "records", "mysql",
        "employee", "employees", "department", "departments", "salary", "salaries",
        "project", "projects", "attendance", "leave", "leaves",
    )
    doc_terms = ("document", "uploaded", "file", "pdf", "report", "according to", "in the")
    mentions_db = any(word in text for word in db_terms)
    mentions_docs = any(word in text for word in doc_terms)
    asks_summary = any(word in text for word in ("summarize", "summary", "overview"))
    if asks_summary and (has_files or mentions_docs):
        return "FILE_SUMMARY"
    if mentions_db and mentions_docs:
        return "HYBRID_QUERY"
    if has_files and not mentions_db:
        return "FILE_SUMMARY" if any(word in text for word in ("summarize", "summary")) else "DOCUMENT_QUERY"
    if mentions_docs:
        return "DOCUMENT_QUERY"
    if mentions_db:
        return "SQL_QUERY"
    return "GENERAL_QUERY"


def _intent_from_explicit_cues(question: str, has_files: bool) -> str | None:
    """Return a deterministic intent for clear data-source wording.

    Small local models can return a valid but contextually unrelated class. Strong
    source cues (for example, 'according to quarterly_report.txt') take precedence.
    """
    text = question.lower()
    doc_cues = (
        "according to", "uploaded", "document", "report", "pdf", ".txt", ".docx",
        ".csv", ".xlsx", "in the file", "from the file", "in the document",
    )
    db_cues = (
        "database", "mysql", "sql", "table", "column", "records", "rows",
        "employee", "employees", "department", "departments", "salary", "salaries",
        "project", "projects", "attendance", "leave", "leaves",
    )
    file_reference = bool(re.search(r"\b[\w-]+\.(?:pdf|docx|txt|csv|xlsx)\b", text))
    has_doc_cue = has_files or file_reference or any(cue in text for cue in doc_cues)
    has_db_cue = any(cue in text for cue in db_cues)
    asks_summary = any(word in text for word in ("summarize", "summary", "overview"))
    if has_db_cue and has_doc_cue:
        return "HYBRID_QUERY"
    if asks_summary and has_doc_cue:
        return "FILE_SUMMARY"
    if has_doc_cue:
        return "DOCUMENT_QUERY"
    if has_db_cue:
        return "SQL_QUERY"
    return None


def classify_intent(
    question: str,
    has_files: bool = False,
    settings: Settings | None = None,
) -> tuple[str, list[str]]:
    """Classify intent with robust parsing and deterministic keyword fallback."""
    active = settings or get_settings()
    fallback = _fallback_intent(question, has_files)
    explicit_intent = _intent_from_explicit_cues(question, has_files)
    try:
        prompt = (
            "Classify the request into exactly one intent: SQL_QUERY, DOCUMENT_QUERY, "
            "FILE_SUMMARY, HYBRID_QUERY, GENERAL_QUERY. Return one JSON object with keys "
            "intent and agents (array of SQL, RAG, FILE). Route requests needing both database "
            "and uploaded document facts as HYBRID_QUERY. Uploaded files plus summarize means FILE_SUMMARY."
        )
        response = get_chat_model(active).invoke(
            f"{prompt}\nFiles attached: {has_files}\nQuestion: {question}"
        )
        raw = str(response.content).strip()
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        parsed: dict[str, Any] = json.loads(match.group(0)) if match else {}
        intent = str(parsed.get("intent", "")).upper()
        if intent not in INTENTS:
            intent = explicit_intent or fallback
        elif explicit_intent is not None and intent != explicit_intent:
            logger.info("Overriding inconsistent model intent %s with source-cue intent %s", intent, explicit_intent)
            intent = explicit_intent
        default_agents = {
            "SQL_QUERY": ["SQL"], "DOCUMENT_QUERY": ["RAG"],
            "FILE_SUMMARY": ["FILE"], "HYBRID_QUERY": ["SQL", "RAG"],
            "GENERAL_QUERY": [],
        }
        # Routing contract is deterministic even if the model suggests other agents.
        return intent, default_agents[intent]
    except Exception as exc:
        logger.warning("Intent classification fell back to rules: %s", exc)
        intent = explicit_intent or fallback
        return intent, {
            "SQL_QUERY": ["SQL"], "DOCUMENT_QUERY": ["RAG"],
            "FILE_SUMMARY": ["FILE"], "HYBRID_QUERY": ["SQL", "RAG"],
            "GENERAL_QUERY": [],
        }[intent]
