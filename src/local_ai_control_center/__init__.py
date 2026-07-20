"""Local AI Control Center (LACC).

A local-first framework for private, reproducible, auditable AI-assisted
workflows. This package currently exposes its version and a placeholder
entry point; functional modules are added incrementally in later phases.
"""

__version__ = "0.7.0"

__all__ = ["__version__"]


def main() -> None:
    """Placeholder entry point.

    Kept so the console script defined in pyproject.toml resolves. The real
    command-line interface is introduced in a later phase.
    """
    print("Hello from local-ai-control-center!")
