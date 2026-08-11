from __future__ import annotations

import importlib
import json
import time
import urllib.request

from .config import validate_cdp_endpoint, validate_target_conversation_url
from .errors import BridgeError
from .markers import validate_handoff_id


def import_playwright(module_name: str):
    try:
        return importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError) as exc:
        raise BridgeError(f"playwright is not installed ({module_name})") from exc


class CdpFetchSender:
    """Non-owning input-only virtual finger for one dedicated ChatGPT conversation."""

    def __init__(
        self,
        cdp_endpoint: str,
        target_url: str,
        profile_path: str = "",
        playwright_module: str = "playwright.sync_api",
        page_timeout_ms: int = 30_000,
    ):
        self.cdp_endpoint = validate_cdp_endpoint(cdp_endpoint)
        validated_target = validate_target_conversation_url(target_url, required=True)
        assert validated_target is not None
        self.target_url = validated_target
        self.profile_path = profile_path
        self.playwright_module = playwright_module
        self.page_timeout_ms = page_timeout_ms

    def _resolve_page(self, browser):
        for context in browser.contexts:
            for page in context.pages:
                if page.url and page.url.rstrip("/") == self.target_url:
                    return page
        raise BridgeError("configured target conversation is not already open; fail closed")

    def send(self, handoff_id: str) -> None:
        validate_handoff_id(handoff_id)
        # Revalidate at the action boundary in case an instance was constructed or
        # mutated outside the normal config loader.
        validate_cdp_endpoint(self.cdp_endpoint)
        pw = import_playwright(self.playwright_module)
        driver = pw.sync_playwright().start()
        try:
            try:
                browser = driver.chromium.connect_over_cdp(self.cdp_endpoint)
            except Exception as exc:  # noqa: BLE001
                raise BridgeError(f"CDP connect failed: {self.cdp_endpoint}") from exc
            page = self._resolve_page(browser)
            page.set_default_timeout(self.page_timeout_ms)
            if self._looks_like_login_or_challenge(page):
                raise BridgeError("login screen or challenge detected; fail closed")
            composer = self._locate_composer(page)
            composer.fill(f"fetch {handoff_id}")
            before = self._composer_text(composer)
            composer.press("Enter")
            time.sleep(1.0)
            after = self._composer_text(composer)
            if not self._submission_confirmed(before, after, self._url_is_target(page)):
                raise BridgeError("submission not positively confirmed; trigger marker withheld")
        except BridgeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"CDP fetch submit failed: {exc}") from exc
        finally:
            # The external Chrome is not owned by this process. Never browser.close(),
            # page.close(), context.close(), goto(), or new_page().
            driver.stop()

    def _url_is_target(self, page) -> bool:
        try:
            return page.url.rstrip("/") == self.target_url
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _composer_text(composer) -> str | None:
        try:
            return composer.text_content() or ""
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _submission_confirmed(before: str | None, after: str | None, url_unchanged: bool) -> bool:
        return bool(url_unchanged and before is not None and after is not None and before.strip() and not after.strip())

    @staticmethod
    def _looks_like_login_or_challenge(page) -> bool:
        for probe in ("Email", "Continue with Google", "Sign in", "I'm a human"):
            try:
                if page.get_by_text(probe, exact=False).count() > 0:
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def _locate_composer(self, page):
        candidate = self._choose_composer_candidate(self._composer_meta(page))
        selector = self._selector_for(candidate)
        locator = page.locator(selector)
        try:
            count = locator.count()
        except Exception as exc:  # noqa: BLE001
            raise BridgeError("composer locator evaluation failed") from exc
        if count != 1:
            raise BridgeError(f"composer selector is not unique ({count} matches); fail closed")
        return locator

    @staticmethod
    def _composer_meta(page) -> list[dict]:
        return page.evaluate(
            """() => [...document.querySelectorAll('textarea, [contenteditable]')].map((el, index) => {
                const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
                let inForm = false, depth = 0, a = el;
                while (a && depth < 8) { if (a.tagName === 'FORM') { inForm = true; break; } a = a.parentElement; depth += 1; }
                return {index, tag: el.tagName.toLowerCase(), id: el.id || null,
                    contenteditable: el.getAttribute('contenteditable'), lexical: el.getAttribute('data-lexical-editor'),
                    role: el.getAttribute('role'), aria_label: el.getAttribute('aria-label'), name: el.getAttribute('name'),
                    class_list: (typeof el.className === 'string' && el.className) ? el.className : null,
                    display: s.display, visibility: s.visibility, width: Math.round(r.width), height: Math.round(r.height),
                    disabled: Boolean(el.disabled), in_form: inForm};
            })"""
        )

    @staticmethod
    def _visible(meta: dict) -> bool:
        return not meta.get("disabled") and meta.get("display") != "none" and meta.get("visibility") not in ("hidden", "collapse") and int(meta.get("width") or 0) > 0 and int(meta.get("height") or 0) > 0

    @classmethod
    def _editable_candidates(cls, meta: list[dict]) -> list[dict]:
        out: list[dict] = []
        for item in meta:
            if not cls._visible(item):
                continue
            ce = item.get("contenteditable")
            if ce in ("true", "plaintext-only"):
                out.append(item)
            elif item.get("tag") == "textarea" and "wcDTda_fallbackTextarea" not in (item.get("class_list") or ""):
                out.append(item)
        return out

    @classmethod
    def _choose_composer_candidate(cls, meta: list[dict]) -> dict:
        editable = cls._editable_candidates(meta)
        if not editable:
            raise BridgeError("no visible editable composer candidate found")

        def rank(item: dict) -> int:
            if item.get("id") == "prompt-textarea" and item.get("contenteditable") in ("true", "plaintext-only"):
                return 0
            if item.get("lexical") == "true" and item.get("contenteditable") in ("true", "plaintext-only"):
                return 1
            if item.get("in_form"):
                return 2
            return 3

        editable.sort(key=rank)
        best = editable[0]
        if any(rank(item) == rank(best) for item in editable[1:]):
            raise BridgeError("multiple visible editable composer candidates; fail closed")
        return best

    @staticmethod
    def _selector_for(candidate: dict) -> str:
        if candidate.get("id"):
            safe_id = str(candidate["id"]).replace('"', '\\"')
            return f'[id="{safe_id}"]'
        tag = candidate.get("tag") or "div"
        ce = candidate.get("contenteditable")
        if candidate.get("lexical") == "true" and ce in ("true", "plaintext-only"):
            return f'{tag}[contenteditable="{ce}"][data-lexical-editor="true"]'
        if ce in ("true", "plaintext-only"):
            return f'{tag}[contenteditable="{ce}"]'
        return tag


class CdpTargetMetadata:
    def __init__(self, cdp_endpoint: str):
        self.cdp_endpoint = validate_cdp_endpoint(cdp_endpoint)

    def list_targets(self) -> list[dict]:
        url = self.cdp_endpoint.rstrip("/") + "/json"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"cannot query DevTools targets at {url}") from exc
        return [{"type": t.get("type"), "url": t.get("url", ""), "title": t.get("title", "")} for t in data if isinstance(t, dict)]

    def find_target(self, exact_url: str) -> dict | None:
        exact = exact_url.rstrip("/")
        for target in self.list_targets():
            if str(target["url"]).rstrip("/") == exact:
                return target
        return None


class NoopLifecycleDiagnostic:
    def __init__(self, cdp_endpoint: str, target_url: str, hold_seconds: float = 30.0, playwright_module: str = "playwright.sync_api"):
        self.cdp_endpoint = validate_cdp_endpoint(cdp_endpoint)
        validated_target = validate_target_conversation_url(target_url, required=True)
        assert validated_target is not None
        self.target_url = validated_target
        self.hold_seconds = max(1.0, hold_seconds)
        self.playwright_module = playwright_module

    def run(self) -> dict:
        metadata = CdpTargetMetadata(self.cdp_endpoint)
        before = metadata.find_target(self.target_url)
        if before is None:
            raise BridgeError("target conversation absent before no-op attach")
        pw = import_playwright(self.playwright_module)
        driver = pw.sync_playwright().start()
        try:
            try:
                driver.chromium.connect_over_cdp(self.cdp_endpoint)
                time.sleep(self.hold_seconds)
            except Exception as exc:  # noqa: BLE001
                raise BridgeError(f"no-op CDP attach failed: {exc}") from exc
        finally:
            driver.stop()
        after = metadata.find_target(self.target_url)
        if after is None or before["url"] != after["url"] or before["title"] != after["title"]:
            raise BridgeError("target changed during pure no-op probe")
        return {"before": before, "after": after, "hold_seconds": self.hold_seconds}
