"Test lunchmoney-assets"

import lunchmoney_assets


def test_import() -> None:
    "Test that the package can be imported"

    assert isinstance(lunchmoney_assets.__name__, str)


def test_version() -> None:
    "Test that the version is available"

    assert isinstance(lunchmoney_assets.__version__, str)
