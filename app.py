"""Streamlit interface for the QueryMate AI local assistant."""

import asyncio
import hashlib
import logging
from typing import Any

import streamlit as st

from config.logging_config import configure_logging
from config.settings import get_settings
from mcp_client.client import QueryMateMCPClient
from services.file_service import ingest_uploaded_files, remove_indexed_document
from services.health_service import check_database, check_models
from services.query_service import stream_querymate
from ui.components import render_assistant_result

WELCOME = "Hello! I'm QueryMate. Ask questions about your database or upload documents to get started."
SUPPORTED_TYPES = ["pdf", "docx", "txt", "csv", "xlsx"]
logger = logging.getLogger(__name__)


@st.cache_data(ttl=30, show_spinner=False)
def _database_status() -> tuple[bool, str]:
    return check_database()


@st.cache_data(ttl=30, show_spinner=False)
def _model_status() -> tuple[bool, str]:
    return check_models()


@st.cache_data(ttl=30, show_spinner=False)
def _mcp_status() -> tuple[bool, str]:
    async def discover() -> list[str]:
        async with QueryMateMCPClient() as client:
            return [tool.name for tool in await client.discover_tools(refresh=True)]

    try:
        names = asyncio.run(discover())
        return True, f"Ready ({len(names)} tools)"
    except Exception:
        logger.exception("MCP status check failed")
        return False, "Unavailable"


@st.cache_data(ttl=20, show_spinner=False)
def _indexed_documents() -> list[dict[str, Any]]:
    try:
        from rag.vector_store import list_documents

        return list_documents()
    except Exception:
        logger.exception("Could not list indexed documents")
        return []


def _status_line(label: str, result: tuple[bool, str]) -> None:
    healthy, detail = result
    symbol = "[OK]" if healthy else "[OFF]"
    st.markdown(f"{symbol} **{label}**  \n{detail}")


def _init_state() -> None:
    if "conversation" not in st.session_state:
        st.session_state.conversation = [{"role": "assistant", "result": {"answer": WELCOME}}]
    if "ingested_uploads" not in st.session_state:
        st.session_state.ingested_uploads = set()
    if "upload_statuses" not in st.session_state:
        st.session_state.upload_statuses = []


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("QueryMate AI")
        st.caption("Local database and document assistant")
        st.divider()

        st.subheader("System status")
        _status_line("Database", _database_status())
        _status_line("Ollama", _model_status())
        _status_line("MCP server", _mcp_status())
        st.divider()

        st.subheader("Upload documents")
        uploads = st.file_uploader(
            "Choose files",
            type=SUPPORTED_TYPES,
            accept_multiple_files=True,
            help=f"PDF, DOCX, TXT, CSV, XLSX - up to {get_settings().max_upload_size_mb} MB per file",
            label_visibility="collapsed",
        )
        if uploads:
            fresh = []
            for upload in uploads:
                digest = hashlib.sha256(upload.getvalue()).hexdigest()
                if digest not in st.session_state.ingested_uploads:
                    fresh.append((upload, digest))
            if fresh:
                with st.spinner("File Agent is extracting and indexing documents..."):
                    statuses = ingest_uploaded_files([item[0] for item in fresh])
                st.session_state.upload_statuses = statuses
                for (_, digest), status in zip(fresh, statuses):
                    st.session_state.ingested_uploads.add(digest)
                _indexed_documents.clear()
            for status in st.session_state.upload_statuses:
                if status.get("status") == "indexed":
                    st.success(f"Indexed {status.get('filename', 'document')}")
                    if status.get("summary"):
                        with st.expander("File summary", expanded=False):
                            st.write(status["summary"])
                else:
                    st.error(f"{status.get('filename', 'File')}: {status.get('error', 'Processing failed')}")

        st.subheader("Uploaded documents")
        documents = _indexed_documents()
        if documents:
            for document in documents:
                document_id = str(document.get("document_id", ""))
                st.markdown(
                    f"**{document.get('filename', 'Document')}**  \n"
                    f"{str(document.get('source_type', '')).upper()} - "
                    f"{document.get('chunk_count', 0)} chunks"
                )
                if st.button("Remove", key=f"remove_document_{document_id}"):
                    try:
                        removed_chunks = remove_indexed_document(document_id)
                        st.session_state.ingested_uploads.discard(document_id)
                        _indexed_documents.clear()
                        st.success(f"Removed {document.get('filename', 'document')} ({removed_chunks} chunks)")
                        st.rerun()
                    except Exception:
                        logger.exception("Could not remove indexed document %s", document_id)
                        st.error("Could not remove this document from the local index.")
        else:
            st.caption("No indexed documents yet.")

        st.divider()
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.conversation = [{"role": "assistant", "result": {"answer": WELCOME}}]
            st.rerun()


def _render_history() -> None:
    for message in st.session_state.conversation:
        role = message["role"]
        with st.chat_message(role):
            if role == "assistant":
                render_assistant_result(message.get("result", {}))
            else:
                st.markdown(message.get("content", ""))


def _run_user_turn(question: str) -> None:
    st.session_state.conversation.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        progress = st.empty()
        activity_status = {
            "Supervisor Agent": "waiting",
            "SQL Agent": "not selected",
            "RAG Agent": "not selected",
            "File Agent": "not selected",
            "Response Agent": "waiting",
        }
        final_state: dict[str, Any] = {}
        statuses = {
            "supervisor": "Supervisor Agent",
            "sql_agent": "SQL Agent",
            "rag_agent": "RAG Agent",
            "file_agent": "File Agent",
            "response_agent": "Response Agent",
        }
        specialist_names = {"SQL": "SQL Agent", "RAG": "RAG Agent", "FILE": "File Agent"}
        try:
            with st.status("Agents are working...", expanded=True) as status:
                activity_status["Supervisor Agent"] = "classifying request"
                progress.write("Supervisor Agent: classifying request...")
                history = [
                    {"role": item["role"], "content": item.get("content", item.get("result", {}).get("answer", ""))}
                    for item in st.session_state.conversation[:-1]
                ]
                for node_name, state in stream_querymate(question, conversation_history=history):
                    final_state = state
                    if node_name == "supervisor":
                        intent = state.get("detected_intent", "")
                        selected = state.get("selected_agents", [])
                        activity_status["Supervisor Agent"] = f"complete ({intent or 'request'})"
                        for name, label in specialist_names.items():
                            activity_status[label] = "queued" if name in selected else "not selected"
                        progress.markdown("\n".join(f"- {name}: {state_text}" for name, state_text in activity_status.items()))
                    elif node_name in {"sql_agent", "rag_agent", "file_agent"}:
                        agent = statuses[node_name]
                        output_key = node_name.split("_")[0].upper()
                        output = state.get("agent_outputs", {}).get(output_key, {})
                        state_text = "completed" if output.get("status") in {"ok", "partial"} else "completed with an issue"
                        activity_status[agent] = state_text
                        progress.markdown("\n".join(f"- {name}: {value}" for name, value in activity_status.items()))
                    elif node_name == "response_agent":
                        activity_status["Response Agent"] = "composing answer"
                        progress.markdown("\n".join(f"- {name}: {value}" for name, value in activity_status.items()))
                status.update(label="Answer ready", state="complete", expanded=False)
            answer_result = dict(final_state.get("final_answer", {}))
            activity_status["Response Agent"] = "complete"
            answer_result["activity"] = [f"{name}: {value}" for name, value in activity_status.items()]
            answer_result["error"] = final_state.get("error")
            render_assistant_result(answer_result)
            st.session_state.conversation.append({"role": "assistant", "result": answer_result})
        except Exception:
            logger.exception("Query workflow failed")
            safe_result = {
                "answer": "I couldn't complete that request. Check that the local services are running and try again.",
                "activity": [f"{name}: {value}" for name, value in activity_status.items()],
                "error": True,
            }
            render_assistant_result(safe_result)
            st.session_state.conversation.append({"role": "assistant", "result": safe_result})


def main() -> None:
    """Render the QueryMate chat interface and connect it to LangGraph services."""
    settings = get_settings()
    configure_logging(settings.log_level)
    st.set_page_config(page_title="QueryMate AI", page_icon="Q", layout="wide")
    st.markdown(
        """<style>
        .block-container {max-width: 1100px; padding-top: 2rem; padding-bottom: 7rem;}
        [data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.18);}
        </style>""",
        unsafe_allow_html=True,
    )
    _init_state()
    _render_sidebar()
    st.title("QueryMate AI")
    st.caption("Ask questions about your database or uploaded documents.")
    _render_history()
    question = st.chat_input("Ask a question about your data...")
    if question and question.strip():
        _run_user_turn(question.strip())


if __name__ == "__main__":
    main()
