"""Reusable Streamlit renderers for assistant messages and query results."""

from typing import Any

import pandas as pd
import streamlit as st

from services.chart_service import build_result_chart


def render_assistant_result(result: dict[str, Any]) -> None:
    """Render answer text, activity, SQL, table/chart, and document references."""
    answer = result.get("answer", "I couldn't produce an answer for this request.")
    st.markdown(str(answer))
    activity = result.get("activity", [])
    if activity:
        st.caption("Completed: " + " / ".join(activity))
    if result.get("error"):
        st.warning("One or more agent steps could not complete. The answer may be partial.")

    if result.get("sql_query"):
        with st.expander("SQL query", expanded=False):
            st.code(result["sql_query"], language="sql")
            validation = result.get("sql_validation_status")
            if validation:
                st.caption(f"Validation: {validation}")

    sql_result = result.get("table")
    if isinstance(sql_result, dict) and sql_result.get("rows"):
        frame = pd.DataFrame(sql_result["rows"], columns=sql_result.get("columns") or None)
        st.dataframe(frame, use_container_width=True, hide_index=True)
        if sql_result.get("truncated"):
            st.caption("Results were limited for display.")
        chart = build_result_chart(sql_result)
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)
    elif result.get("sql_query") and isinstance(sql_result, dict):
        st.caption("The query returned no rows.")

    sources = result.get("sources") or []
    if sources:
        with st.expander(f"Document sources ({len(sources)})", expanded=False):
            seen: set[tuple[str, str]] = set()
            for source in sources:
                filename = str(source.get("filename", "Document"))
                metadata = source.get("metadata", {})
                if isinstance(metadata, list):
                    metadata = metadata[0] if metadata and isinstance(metadata[0], dict) else {}
                if not isinstance(metadata, dict):
                    metadata = {}
                location = metadata.get("page_number") or metadata.get("sheet_name") or metadata.get("source_location")
                key = (filename, str(location or ""))
                if key in seen:
                    continue
                seen.add(key)
                st.write(f"- {filename}" + (f" - {location}" if location else ""))
