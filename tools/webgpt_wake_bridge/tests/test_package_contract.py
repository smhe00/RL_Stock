import re
import tomllib
from pathlib import Path

import webgpt_wake_bridge


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "webgpt_wake_bridge"


def test_package_and_pyproject_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == webgpt_wake_bridge.__version__
    assert webgpt_wake_bridge.PROTOCOL_VERSION == "web_fetch_bridge_v1"


def test_source_has_no_rl_stock_business_state_dependency():
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in SRC.glob("*.py"))
    for exact in (
        "claude_status.yaml",
        "chatgpt_review.yaml",
        "miniqmt",
        "03110",
    ):
        assert exact not in source
    for business_word in ("gate4", "maxdiv", "qmt", "ppo", "sac", "td3"):
        assert re.search(rf"\b{re.escape(business_word)}\b", source) is None


def test_browser_source_does_not_use_full_page_text_or_output_scraping_helpers():
    source = (SRC / "browser.py").read_text(encoding="utf-8")
    for forbidden in (
        "get_by_text(",
        "page.content(",
        "page.inner_text(",
        "locator('main').inner_text",
        'locator("main").inner_text',
    ):
        assert forbidden not in source
