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
    assert CdpFetchSender._choose_composer_candidate(meta)["lexical"] == "true"


def test_same_rank_ambiguity_fails_closed():
    meta = [_meta(contenteditable="true"), _meta(contenteditable="true")]
    with pytest.raises(BridgeError):
        CdpFetchSender._choose_composer_candidate(meta)


def test_submission_confirmation_requires_clear_and_same_url():
    fn = CdpFetchSender._submission_confirmed
    assert fn("fetch H_001", "", True)
    assert not fn("fetch H_001", "fetch H_001", True)
    assert not fn("fetch H_001", "", False)
    assert not fn(None, "", True)


def test_selector_is_semantic():
    assert CdpFetchSender._selector_for({"id": "prompt-textarea"}) == '[id="prompt-textarea"]'
    assert CdpFetchSender._selector_for({"tag": "div", "contenteditable": "true"}) == 'div[contenteditable="true"]'
