"""export_parquet — bulk export of mimir_articles to a Parquet file."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# Rationale: duckdb's Python wrapper is only partially typed; all three
# suppressions are confined to this file.
from __future__ import annotations

import duckdb


def export_parquet(db_path: str, parquet_path: str) -> int:
    """Export all rows from ``mimir_articles`` to a Parquet file.

    Args:
        db_path: Path to the DuckDB database file.
        parquet_path: Destination ``.parquet`` file path (created or overwritten).

    Returns:
        Number of articles written.

    Note:
        The ``categories`` column is exported as a JSON-encoded ``VARCHAR``
        (e.g. ``'["Cat A", "Cat B"]'``).  Consumers must parse it with
        ``json.loads`` or DuckDB's ``json_extract`` / ``json_array_elements``.
    """
    with duckdb.connect(db_path) as conn:
        result = conn.execute(
            # COPY … TO requires a string literal for the path; parameterised
            # binding is not supported by DuckDB for file destinations.
            f"COPY (SELECT * FROM mimir_articles) TO '{parquet_path}' (FORMAT PARQUET)"
        )
        row = result.fetchone()
        return int(row[0]) if row else 0
