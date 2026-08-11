import ast
import inspect
import textwrap

import pytest

from webgpt_wake_bridge.browser import CdpFetchSender
from webgpt_wake_bridge.errors import BridgeError


def _meta(**kw):
    base = {
        "tag": "div", "id": None, "contenteditable": None, "lexical": None,
        "class_list": None, "display": "block", "visibility": "visible",
        "width": 500, "height": 40, "disabled": False, "in_form": True,
    }
    base.update(kw)
    return base


def test_hidden_fallback_textarea_is_excluded():
    meta = [
        _meta(tag="textarea", class_list="wcDTda_fallbackTextarea", display="none", width=0, height=0),
        _meta(id="prompt-textarea", contenteditable="true"),
    ]
    chosen = CdpFetchSender._choose_composer_candidate(meta)
    assert chosen["id"] == "prompt-textarea"


def test_lexical_editor_preferred_over_generic():
    meta = [
        _meta(contenteditable="true", in_form=False),
        _meta(contenteditable="true", lexical="true"),
    ]
    chosen = CdpFetchSender._choose_composer_candidate(meta)
    assert chosen["lexical"] == "true"
    assert CdpFetchSender._selector_for(chosen) == 'div[contenteditable="true"][data-lexical-editor="true"]'


def test_same_rank_ambiguity_fails_closed():
    meta = [_meta(contenteditable="true"), _meta(contenteditable="true")]
    with pytest.raises(BridgeError):
        CdpFetchSender._choose_composer_candidate(meta)


def test_submission_confirmation_requires_clear_and_same_url():
    fn = CdpFetchSender._submission_confirmed
    assert fn("fetch repo=owner/demo handoff=H_001", "", True)
    assert not fn("fetch repo=owner/demo handoff=H_001", "still here", True)
    assert not fn("fetch repo=owner/demo handoff=H_001", "", False)
    assert not fn(None, "", True)


def test_selector_is_semantic():
    assert CdpFetchSender._selector_for({"id": "prompt-textarea"}) == '[id="prompt-textarea"]'
    assert CdpFetchSender._selector_for({"tag": "div", "contenteditable": "true"}) == 'div[contenteditable="true"]'


def test_wake_message_contains_repository_and_handoff():
    sender = CdpFetchSender(
        "http://127.0.0.1:9222",
        "https://chatgpt.com/c/demo",
        "owner/demo",
    )
    assert sender._wake_message("H_001") == "fetch repo=owner/demo handoff=H_001"


def test_constructor_rejects_spoofed_cdp_or_invalid_repository():
    with pytest.raises(BridgeError):
        CdpFetchSender(
            "http://127.0.0.1.evil.example:9222",
            "https://chatgpt.com/c/demo",
            "owner/demo",
        )
    with pytest.raises(BridgeError):
        CdpFetchSender(
            "http://127.0.0.1:9222",
            "https://chatgpt.com/c/demo",
            "https://github.com/owner/demo",
        )


def test_normal_sender_ast_has_no_owning_browser_lifecycle_calls():
    tree = ast.parse(textwrap.dedent(inspect.getsource(CdpFetchSender.send)))
    forbidden_attrs = {"goto", "new_page"}
    close_receivers = {"browser", "page", "context"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        assert node.func.attr not in forbidden_attrs
        if node.func.attr == "close" and isinstance(node.func.value, ast.Name):
            assert node.func.value.id not in close_receivers
