"""OS-aware prerequisite checker: git, uv, Databricks CLI.

Re-exports the top-level prereqs module so callers can use either path.
"""

from enterprise_adk.prereqs import check_and_fix  # noqa: F401
