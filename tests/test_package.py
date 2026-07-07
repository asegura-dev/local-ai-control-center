"""
Smoke tests: the package imports and exposes a version.
"""

import local_ai_control_center


def test_package_imports() -> None:
    """The package can be imported."""
    assert local_ai_control_center is not None


def test_version_is_a_nonempty_string() -> None:
    """The package exposes a non-empty version string."""
    assert isinstance(local_ai_control_center.__version__, str)
    assert local_ai_control_center.__version__
