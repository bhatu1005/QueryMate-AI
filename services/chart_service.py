"""Chart inference helpers for SQL result tables."""

from typing import Any

import pandas as pd
import plotly.express as px


def build_result_chart(sql_result: dict[str, Any] | None):
    """Build a simple chart when tabular rows contain a usable numeric measure."""
    if not sql_result or not sql_result.get("rows"):
        return None
    frame = pd.DataFrame(sql_result["rows"])
    if frame.empty or len(frame.columns) < 2:
        return None
    for column in frame.columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().sum() >= max(1, int(len(frame) * 0.7)):
            frame[column] = converted
    numeric = list(frame.select_dtypes(include="number").columns)
    if not numeric:
        return None
    measure = numeric[0]
    categories = [column for column in frame.columns if column != measure]
    if categories:
        category = categories[0]
        return px.bar(frame.head(100), x=category, y=measure, title=f"{measure} by {category}")
    return px.line(frame.head(100), y=measure, title=str(measure))
