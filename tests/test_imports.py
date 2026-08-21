import replyflow
from replyflow.config import AppSettings, load_settings


def test_package_imports() -> None:
    assert replyflow.__version__ == "0.3.0"
    assert AppSettings is not None
    assert callable(load_settings)
