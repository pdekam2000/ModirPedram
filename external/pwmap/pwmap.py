#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PW-MAP — Interactive page scanner and Playwright locator report generator.

Usage:
    python pwmap.py <url>                    # open URL, wait for login, auto-scan
    python pwmap.py <url> --no-wait-login    # scan immediately after page load
    python pwmap.py <url> --report --quit    # scan, save report, exit
    python pwmap.py                          # interactive menu only

Examples:
    python pwmap.py https://app.runwayml.com/login
    python pwmap.py https://example.com --no-wait-login --report
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

try:
    from playwright.sync_api import BrowserContext, Page, sync_playwright
except ImportError:
    print(
        "\n[ERROR] Playwright is not installed.\n"
        "  pip install playwright\n"
        "  playwright install chromium\n"
    )
    from exit_codes import EXIT_RUNTIME_ERROR

    sys.exit(EXIT_RUNTIME_ERROR)

from exit_codes import EXIT_CODE_MEANINGS, EXIT_RUNTIME_ERROR, EXIT_SESSION_NOT_READY

# Subprocess exit codes (shared with runway_agent.py — see exit_codes.py):
#   0 = success
#   1 = runtime error (Chrome/Playwright/generation failure)
#   2 = session/browser not ready (missing session file, expired Runway login, argparse CLI error)

CHROME_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
)

PROFILE_DIR = Path.cwd() / "pwmap_profile"
DATA_FILE = Path.cwd() / "pwmap_data.json"
SCREENSHOTS_DIR = Path.cwd() / "pwmap_screenshots"

# Common desktop Chrome user agent (updated periodically).
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Patches common automation fingerprints before page scripts run.
STEALTH_INIT_SCRIPT = """
(() => {
  if (navigator.webdriver !== undefined) {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  }
  if (!window.chrome) {
    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
  }
  if (navigator.plugins && navigator.plugins.length === 0) {
    Object.defineProperty(navigator, 'plugins', {
      get: () => [1, 2, 3, 4, 5],
    });
  }
  if (!navigator.languages || navigator.languages.length === 0) {
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  }
  const originalQuery = window.navigator.permissions.query;
  if (originalQuery) {
    window.navigator.permissions.query = (parameters) =>
      parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
  }
  delete window.__playwright;
  delete window.__pw_manual;
})();
"""

JS_LIB = r"""
function esc(s){ if(window.CSS&&window.CSS.escape) return window.CSS.escape(s);
  return String(s).replace(/[^a-zA-Z0-9_-]/g,function(c){return "\\"+c;}); }
function q(s){ return '"'+String(s).replace(/\\/g,"\\\\").replace(/"/g,'\\"')+'"'; }
function clean(s){ return (s||"").replace(/\s+/g," ").trim(); }
var TESTID=["data-testid","data-test-id","data-test","data-cy","data-qa","data-automation-id"];
function testId(el){ for(var i=0;i<TESTID.length;i++){var v=el.getAttribute(TESTID[i]); if(v) return {attr:TESTID[i],val:v};} return null; }
function role(el){
  var ex=el.getAttribute("role"); if(ex) return ex.trim();
  var tag=el.tagName.toLowerCase(), type=(el.getAttribute("type")||"").toLowerCase();
  if(tag==="a"&&el.hasAttribute("href")) return "link";
  if(tag==="button") return "button";
  if(tag==="select") return "combobox";
  if(tag==="textarea") return "textbox";
  if(tag==="img") return "img";
  if(/^h[1-6]$/.test(tag)) return "heading";
  if(tag==="input"){
    if(type==="submit"||type==="button"||type==="reset") return "button";
    if(type==="checkbox") return "checkbox";
    if(type==="radio") return "radio";
    if(type==="range") return "slider";
    if(["","text","email","password","search","tel","url","number"].indexOf(type)>=0) return "textbox";
  }
  return "";
}
function labelInfo(el){
  var v;
  if((v=el.getAttribute("aria-label"))&&clean(v)) return {text:clean(v),source:"aria-label"};
  var lb=el.getAttribute("aria-labelledby");
  if(lb){ var t=""; lb.split(/\s+/).forEach(function(id){var r=document.getElementById(id); if(r) t+=" "+r.textContent;});
    if(clean(t)) return {text:clean(t),source:"aria-labelledby"}; }
  if(el.id){ try{ var lf=document.querySelector('label[for="'+esc(el.id)+'"]');
    if(lf&&clean(lf.textContent)) return {text:clean(lf.textContent),source:"label[for]"}; }catch(e){} }
  var w=el.closest?el.closest("label"):null;
  if(w&&clean(w.textContent)) return {text:clean(w.textContent),source:"wrapping-label"};
  var tag=el.tagName.toLowerCase(), type=(el.getAttribute("type")||"").toLowerCase();
  if(tag==="input"&&(type==="submit"||type==="button"||type==="reset")&&el.value) return {text:clean(el.value),source:"value"};
  var tx=clean(el.textContent); if(tx&&tx.length<=100) return {text:tx,source:"text"};
  if((v=el.getAttribute("placeholder"))&&clean(v)) return {text:clean(v),source:"placeholder"};
  if((v=el.getAttribute("title"))&&clean(v)) return {text:clean(v),source:"title"};
  if((v=el.getAttribute("alt"))&&clean(v)) return {text:clean(v),source:"alt"};
  return {text:"",source:"none"};
}
function actionOf(el){
  var tag=el.tagName.toLowerCase(), type=(el.getAttribute("type")||"").toLowerCase();
  if(tag==="a"){ var h=el.getAttribute("href"); return h?"navigate -> "+h:"link (no href)"; }
  if(tag==="button"||(tag==="input"&&(type==="button"||type==="submit"||type==="reset"))){
    if(type==="submit") return "submit form"; if(type==="reset") return "reset form"; return "click / action"; }
  if(tag==="input"){
    if(type==="checkbox") return "toggle checkbox"; if(type==="radio") return "select radio";
    if(type==="file") return "upload file"; if(type==="range") return "slider";
    if(type==="password") return "type password"; return "type text ("+(type||"text")+")"; }
  if(tag==="select") return "select option";
  if(tag==="textarea") return "type multiline";
  if(el.getAttribute("contenteditable")==="true") return "editable text";
  if(el.hasAttribute("onclick")) return "click (onclick handler)";
  var r=el.getAttribute("role"); if(r) return "role="+r+" action";
  return "interactive";
}
var IROLES=["button","link","checkbox","radio","textbox","combobox","menuitem","menuitemcheckbox",
  "menuitemradio","tab","switch","slider","option","searchbox","spinbutton"];
function isInteractive(el,r){
  var tag=el.tagName.toLowerCase();
  if(["a","button","input","select","textarea"].indexOf(tag)>=0) return true;
  if(el.hasAttribute("onclick")) return true;
  if(el.getAttribute("contenteditable")==="true") return true;
  if(r&&IROLES.indexOf(r)>=0) return true;
  return false;
}
function visible(el){
  var r=el.getBoundingClientRect();
  if(r.width===0&&r.height===0) return false;
  var s=getComputedStyle(el);
  if(s.display==="none"||s.visibility==="hidden"||parseFloat(s.opacity)===0) return false;
  return true;
}
function cssSelector(el){
  if(!(el instanceof Element)) return "";
  if(el.id){ var sel="#"+esc(el.id); try{ if(document.querySelectorAll(sel).length===1) return sel; }catch(e){} }
  var path=[], node=el;
  while(node&&node.nodeType===1&&node!==document.documentElement){
    var part=node.tagName.toLowerCase();
    if(node.id){ path.unshift("#"+esc(node.id)); break; }
    var parent=node.parentNode;
    if(parent){ var same=[],ch=parent.children;
      for(var i=0;i<ch.length;i++) if(ch[i].tagName===node.tagName) same.push(ch[i]);
      if(same.length>1) part+=":nth-of-type("+(same.indexOf(node)+1)+")"; }
    path.unshift(part); node=node.parentNode;
  }
  return path.join(" > ");
}
function xpath(el){
  if(el.id) return '//*[@id="'+el.id+'"]';
  var parts=[],node=el;
  while(node&&node.nodeType===1){
    var ix=1,sib=node.previousSibling;
    while(sib){ if(sib.nodeType===1&&sib.tagName===node.tagName) ix++; sib=sib.previousSibling; }
    parts.unshift(node.tagName.toLowerCase()+"["+ix+"]");
    node=node.parentNode; if(node&&node.nodeType!==1) break;
  }
  return "/"+parts.join("/");
}
function pwLocator(info){
  var name=info.label,tid=info.testId,r=info.role,tag=info.tag,ph=info.placeholder;
  if(tid) return {code:"page.get_by_test_id("+q(tid.val)+")",kind:"test_id"};
  if(r&&name) return {code:"page.get_by_role("+q(r)+", name="+q(name)+")",kind:"role+name"};
  if(tag==="input"&&ph) return {code:"page.get_by_placeholder("+q(ph)+")",kind:"placeholder"};
  if(name&&(r==="link"||r==="button"||r==="heading")) return {code:"page.get_by_text("+q(name)+")",kind:"text"};
  if(info.id) return {code:"page.locator("+q("#"+info.id)+")",kind:"id"};
  if(name) return {code:"page.get_by_text("+q(name)+")",kind:"text"};
  return {code:"page.locator("+q(info.css)+")",kind:"css"};
}
function captureEl(el,idx){
  var li=labelInfo(el),tid=testId(el),r=role(el),rect=el.getBoundingClientRect();
  var info={ i:idx, tag:el.tagName.toLowerCase(),
    type:(el.getAttribute("type")||"").toLowerCase()||null, role:r,
    label:li.text, labelSource:li.source, id:el.id||null,
    nameAttr:el.getAttribute("name")||null, placeholder:el.getAttribute("placeholder")||null,
    value:(el.value!==undefined&&typeof el.value==="string")?el.value.slice(0,60):null,
    href:el.getAttribute("href")||null,
    classes:(typeof el.className==="string"?el.className.trim():"")||null,
    action:actionOf(el), interactive:isInteractive(el,r), visible:visible(el),
    disabled:!!(el.disabled||el.getAttribute("aria-disabled")==="true"),
    testId:tid,
    pos:{x:Math.round(rect.left+window.scrollX),y:Math.round(rect.top+window.scrollY),
         w:Math.round(rect.width),h:Math.round(rect.height)},
    css:cssSelector(el), xpath:xpath(el) };
  info.best=pwLocator(info);
  info.candidates=[];
  if(tid) info.candidates.push("get_by_test_id("+q(tid.val)+")");
  if(r&&info.label) info.candidates.push("get_by_role("+q(r)+", name="+q(info.label)+")");
  if(info.placeholder) info.candidates.push("get_by_placeholder("+q(info.placeholder)+")");
  if(info.label) info.candidates.push("get_by_text("+q(info.label)+")");
  if(info.id) info.candidates.push('locator("#'+info.id+'")');
  info.candidates.push("locator("+q(info.css)+")");
  info.candidates.push('locator("xpath='+info.xpath+'")');
  return info;
}
function scanAll(){
  var SEL="a[href],button,input,select,textarea,[role],[onclick],[tabindex],summary,[contenteditable='true']";
  var nodes=document.querySelectorAll(SEL), seen=[], out=[], idx=0;
  var cap=Math.min(nodes.length,3000);
  for(var i=0;i<cap;i++){ var el=nodes[i]; if(seen.indexOf(el)>=0) continue; seen.push(el); out.push(captureEl(el,++idx)); }
  return {url:location.href, title:document.title||location.pathname,
          scannedAt:new Date().toISOString(), total:out.length, elements:out};
}
"""

JS_SCAN = "(() => {" + JS_LIB + " return scanAll(); })()"


def load_saved_pages() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open(encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload.get("pages", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_pages(pages: list[dict[str, Any]]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as fh:
        json.dump({"pages": pages}, fh, ensure_ascii=False, indent=2)


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def canonical_url(url: str) -> str:
    """Normalize URL for duplicate detection (strip fragment and trailing slash)."""
    parsed = urlparse(normalize_url(url))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _md_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _safe_filename(text: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", text.strip())
    return cleaned[:max_len] or "page"


def take_page_screenshot(page: Page, title: str) -> str | None:
    """Capture a full-page screenshot and return a path relative to cwd."""
    try:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"page_{timestamp}_{_safe_filename(title)}.png"
        path = SCREENSHOTS_DIR / filename
        page.screenshot(path=str(path), full_page=True, animations="disabled")
        return str(path.relative_to(Path.cwd()))
    except Exception:
        return None


def build_markdown_report(pages: list[dict[str, Any]]) -> str:
    total_elements = sum(page["total"] for page in pages)
    lines = [
        "# PW-MAP Report",
        "",
        f"- Generated: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"- Pages scanned: {len(pages)}",
        f"- Total elements: {total_elements}",
        "",
    ]

    for page_index, page in enumerate(pages, start=1):
        elements = page["elements"]
        lines.extend([
            f"## Page {page_index} — {page['title']}",
            f"`{page['url']}`",
            f"Scanned at: {page.get('scannedAt', 'unknown')}",
            f"Elements: {len(elements)}",
            "",
        ])

        screenshot = page.get("screenshot")
        if screenshot:
            lines.extend([f"![Page screenshot]({screenshot.replace(chr(92), '/')})", ""])

        lines.extend([
            "| # | role | label | action | recommended locator | position (x,y) |",
            "|---|------|-------|--------|---------------------|--------------|",
        ])

        for element in elements:
            role = element["role"] or element["tag"]
            label = element["label"] or "(no label)"
            lines.append(
                f"| {element['i']} | {role} | {_md_cell(label)} | "
                f"{_md_cell(element['action'])} | `{element['best']['code']}` | "
                f"{element['pos']['x']},{element['pos']['y']} |"
            )

        lines.extend(["", "### Element details", ""])
        for element in elements:
            tag_line = f"#### {element['i']}. `<{element['tag']}"
            if element["type"]:
                tag_line += f" type={element['type']}"
            tag_line += f'>` — "{element["label"] or "(no label)"}"'
            lines.append(tag_line)
            lines.append(
                f"- **Recommended:** `{element['best']['code']}.click()` "
                f"_(strategy: {element['best']['kind']})_"
            )
            lines.append(f"- Action: {element['action']}")
            lines.append(f'- Label: "{element["label"]}" (source: {element["labelSource"]})')

            meta = (
                f"- Role: {element['role'] or '-'} | id: {element['id'] or '-'} "
                f"| name: {element['nameAttr'] or '-'}"
            )
            if element["placeholder"]:
                meta += f" | placeholder: {element['placeholder']}"
            if element["href"]:
                meta += f" | href: {element['href']}"
            if element["testId"]:
                meta += f" | {element['testId']['attr']}={element['testId']['val']}"
            lines.append(meta)

            pos = element["pos"]
            lines.append(
                f"- Position: x={pos['x']}, y={pos['y']}, size {pos['w']}×{pos['h']} "
                f"| visible: {_yes_no(element['visible'])} "
                f"| disabled: {_yes_no(element['disabled'])} "
                f"| interactive: {_yes_no(element['interactive'])}"
            )
            lines.append("- Locator candidates (best first):")
            for candidate in element["candidates"]:
                lines.append(f"    - `page.{candidate}`")
            lines.append(f"- CSS: `{element['css']}`")
            lines.append(f"- XPath: `{element['xpath']}`")
            lines.append("")

    return "\n".join(lines)


def export_json_file(pages: list[dict[str, Any]], path: Path) -> None:
    payload = {
        "exportedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        "pageCount": len(pages),
        "pages": pages,
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def export_csv_file(pages: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "page_index", "page_title", "page_url", "scanned_at",
        "element_index", "tag", "role", "label", "label_source",
        "action", "best_locator", "locator_strategy",
        "css", "xpath", "pos_x", "pos_y", "visible", "disabled",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for page_index, page in enumerate(pages, start=1):
            for element in page["elements"]:
                writer.writerow({
                    "page_index": page_index,
                    "page_title": page["title"],
                    "page_url": page["url"],
                    "scanned_at": page.get("scannedAt", ""),
                    "element_index": element["i"],
                    "tag": element["tag"],
                    "role": element.get("role") or "",
                    "label": element.get("label") or "",
                    "label_source": element.get("labelSource") or "",
                    "action": element.get("action") or "",
                    "best_locator": element["best"]["code"],
                    "locator_strategy": element["best"]["kind"],
                    "css": element.get("css") or "",
                    "xpath": element.get("xpath") or "",
                    "pos_x": element["pos"]["x"],
                    "pos_y": element["pos"]["y"],
                    "visible": element.get("visible", False),
                    "disabled": element.get("disabled", False),
                })


def find_page_index_by_url(pages: list[dict[str, Any]], url: str) -> int | None:
    target = canonical_url(url)
    for index, page in enumerate(pages):
        if canonical_url(page["url"]) == target:
            return index
    return None


def find_google_chrome() -> Path | None:
    """Return the Google Chrome executable path if installed."""
    for candidate in CHROME_PATHS:
        if candidate.is_file():
            return candidate
    return None


CDP_URL = "http://127.0.0.1:9222"


def connect_existing_chrome(playwright: Any) -> BrowserContext | None:
    """Reuse Chrome if it is already running with remote debugging enabled."""
    try:
        browser = playwright.chromium.connect_over_cdp(CDP_URL)
        if browser.contexts:
            print(f"[i] Browser: reusing open Chrome via CDP ({CDP_URL})")
            return browser.contexts[0]
        context = browser.new_context()
        print(f"[i] Browser: connected Chrome via CDP ({CDP_URL})")
        return context
    except Exception:
        return None


def _profile_in_use_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    needles = (
        "browsersitzung",
        "browser session",
        "profile",
        "singletonlock",
        "already running",
        "user data directory",
    )
    return any(n in msg for n in needles)


def launch_google_chrome_context(
    playwright: Any,
    launch_kwargs: dict[str, Any],
) -> BrowserContext:
    """Launch a persistent context using Google Chrome only (never Edge/Chromium)."""
    errors: list[str] = []

    try:
        context = playwright.chromium.launch_persistent_context(
            channel="chrome",
            **launch_kwargs,
        )
        print("[i] Browser: Google Chrome (channel=chrome)")
        return context
    except Exception as exc:
        errors.append(f"channel=chrome failed: {exc}")
        if _profile_in_use_error(exc):
            existing = connect_existing_chrome(playwright)
            if existing:
                return existing

    chrome_exe = find_google_chrome()
    if chrome_exe:
        try:
            context = playwright.chromium.launch_persistent_context(
                executable_path=str(chrome_exe),
                **launch_kwargs,
            )
            print(f"[i] Browser: Google Chrome ({chrome_exe})")
            return context
        except Exception as exc:
            errors.append(f"executable_path failed: {exc}")
            if _profile_in_use_error(exc):
                existing = connect_existing_chrome(playwright)
                if existing:
                    return existing

    print(
        "\n[ERROR] Google Chrome is required but could not be launched.\n"
        "  Install Chrome: https://www.google.com/chrome/\n"
        "  Then run: playwright install chrome\n"
        "  Close all Chrome windows and retry.\n"
    )
    for detail in errors:
        safe = detail.encode("ascii", errors="replace").decode("ascii")
        print(f"  - {safe}")
    sys.exit(EXIT_RUNTIME_ERROR)


def apply_stealth_cdp(context: BrowserContext) -> None:
    """Extra CDP patches applied on top of init scripts."""
    try:
        session = context.new_cdp_session(context.pages[0] if context.pages else context.new_page())
        session.send(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": STEALTH_INIT_SCRIPT},
        )
    except Exception:
        pass


def launch_browser_context(
    playwright: Any,
    *,
    headless: bool,
    stealth: bool,
    profile_dir: Path | str | None = None,
    storage_state_path: Path | str | None = None,
    prefer_cdp: bool = True,
) -> BrowserContext:
    if prefer_cdp and not headless:
        existing = connect_existing_chrome(playwright)
        if existing is not None:
            return existing

    launch_args = [
        "--start-maximized",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        f"--remote-debugging-port=9222",
    ]
    if stealth:
        launch_args.extend([
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ])

    user_data_dir = Path(profile_dir) if profile_dir else PROFILE_DIR
    user_data_dir.mkdir(parents=True, exist_ok=True)

    common_kwargs: dict[str, Any] = {
        "user_data_dir": str(user_data_dir),
        "headless": headless,
        "args": launch_args,
        "no_viewport": True,
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "color_scheme": "light",
    }

    session_file = Path(storage_state_path) if storage_state_path else None
    if session_file and session_file.is_file():
        common_kwargs["storage_state"] = str(session_file)
        print(f"[i] Browser: loading Runway session from {session_file}")

    if stealth:
        common_kwargs["ignore_default_args"] = ["--enable-automation"]
        common_kwargs["user_agent"] = DEFAULT_USER_AGENT
        common_kwargs["extra_http_headers"] = {
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        }

    context = launch_google_chrome_context(playwright, common_kwargs)

    if stealth:
        context.add_init_script(STEALTH_INIT_SCRIPT)
        apply_stealth_cdp(context)

    return context


def human_pause(stealth: bool) -> None:
    """Brief delay before DOM scan to reduce bot-pattern timing signals."""
    if stealth:
        time.sleep(0.4)


def stealth_goto(page: Page, url: str, stealth: bool) -> None:
    page.goto(
        normalize_url(url),
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    if stealth:
        page.wait_for_timeout(300)


def perform_scan(page: Page, *, stealth: bool) -> dict[str, Any]:
    human_pause(stealth)
    data = page.evaluate(JS_SCAN)
    screenshot = take_page_screenshot(page, data["title"])
    if screenshot:
        data["screenshot"] = screenshot
    return data


def wait_for_page_ready(page: Page, stealth: bool) -> None:
    """Wait until the page is loaded enough to scan."""
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        try:
            page.wait_for_load_state("load", timeout=10_000)
        except Exception:
            pass
    if stealth:
        page.wait_for_timeout(500)


def prompt_login_wait() -> bool:
    """Wait for user to finish login. Returns False if interrupted."""
    print("\n[i] Log in manually in Chrome if needed.")
    print("[i] Go to the page you want to scan (same tab or a new tab).")
    try:
        input("[i] Press Enter here in the terminal when ready to scan... ")
        return True
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def scan_current_page(
    page: Page,
    pages: list[dict[str, Any]],
    *,
    stealth: bool,
    replace: bool = False,
) -> dict[str, Any]:
    """Scan the current page and save results."""
    data = perform_scan(page, stealth=stealth)
    total, was_replaced = upsert_scan(pages, data, replace=replace)
    verb = "replaced" if was_replaced else "saved"
    print(
        f"[OK] Scanned {data['total']} elements on \"{data['title']}\" "
        f"— {verb}. ({total} page(s))"
    )
    return data


def scan_url_flow(
    context: BrowserContext,
    page: Page,
    pages: list[dict[str, Any]],
    url: str,
    *,
    stealth: bool,
    replace: bool = False,
    wait_login: bool = True,
    wait_seconds: int = 0,
) -> tuple[dict[str, Any] | None, Page | None]:
    """Navigate to a URL and scan the page."""
    target = normalize_url(url)
    print(f"[i] Opening: {target}")

    active = resolve_active_page(context, page) or context.new_page()
    stealth_goto(active, target, stealth)
    wait_for_page_ready(active, stealth)

    if wait_login:
        if not prompt_login_wait():
            print("[!] Scan cancelled.")
            return None, active
    elif wait_seconds > 0:
        print(f"[i] Waiting {wait_seconds}s before scan...")
        time.sleep(wait_seconds)

    active = resolve_active_page(context, active)
    if active is None:
        print("[ERROR] Browser window was closed. Run the program again.")
        return None, None

    try:
        data = scan_current_page(active, pages, stealth=stealth, replace=replace)
        return data, active
    except Exception as exc:
        if "closed" in str(exc).lower():
            active = resolve_active_page(context, active)
            if active:
                print("[i] Using the active browser tab, retrying scan...")
                data = scan_current_page(active, pages, stealth=stealth, replace=replace)
                return data, active
        print(f"[ERROR] Scan failed: {exc}")
        return None, active


def save_auto_report(pages: list[dict[str, Any]], filename: str | None = None) -> Path:
    """Write the Markdown report and return its path."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = filename or f"pwmap_report_{timestamp}.md"
    if not name.lower().endswith(".md"):
        name += ".md"
    report_path = Path(name).resolve()
    report_path.write_text(build_markdown_report(pages), encoding="utf-8")
    return report_path


def upsert_scan(
    pages: list[dict[str, Any]],
    data: dict[str, Any],
    *,
    replace: bool,
) -> tuple[int, bool]:
    """Insert or replace a scan. Returns (total_pages, was_replaced)."""
    if replace:
        existing = find_page_index_by_url(pages, data["url"])
        if existing is not None:
            pages[existing] = data
            save_pages(pages)
            return len(pages), True
    pages.append(data)
    save_pages(pages)
    return len(pages), False


def resolve_active_page(context: BrowserContext, page: Page) -> Page | None:
    """Return the best active page (prefer the most recently opened tab)."""
    candidates = list(context.pages)
    if page not in candidates:
        candidates.append(page)
    for candidate in reversed(candidates):
        try:
            candidate.url  # noqa: B018
            return candidate
        except Exception:
            continue
    return None


MENU_ITEMS: list[tuple[str, str]] = [
    ("scan", "Scan current page (new entry)"),
    ("scan_replace", "Scan current page (replace previous scan of same URL)"),
    ("scan_url", "Enter URL → open page → scan automatically"),
    ("list", "List scanned pages"),
    ("report", "Export Markdown report (with screenshot)"),
    ("export_json", "Export JSON"),
    ("export_csv", "Export CSV"),
    ("goto", "Navigate to URL (no scan)"),
    ("clear", "Clear all scans"),
    ("help", "Help"),
    ("quit", "Quit"),
]


def print_banner(*, stealth: bool, headless: bool) -> None:
    print("\n=== PW-MAP ===")
    mode = []
    if stealth:
        mode.append("stealth: ON")
    else:
        mode.append("stealth: OFF")
    if headless:
        mode.append("headless: ON")
    print(" | ".join(mode))
    print("Enter a menu number (e.g. 1 or 3).")
    print("Tip: pass a URL at launch for auto-scan: python pwmap.py https://...\n")


def print_menu(current_url: str) -> None:
    prompt_url = current_url if len(current_url) <= 55 else current_url[:52] + "..."
    print(f"\n--- Menu | {prompt_url} ---")
    for index, (_, label) in enumerate(MENU_ITEMS, start=1):
        print(f"  {index}) {label}")
    print()


def print_help() -> None:
    print("\n--- Help ---")
    for index, (_, label) in enumerate(MENU_ITEMS, start=1):
        print(f"  {index}) {label}")
    print("\nEnter the option number and press Enter.")
    print("For options 5-8 you can leave filename/URL blank to use defaults.\n")


def print_scan_list(pages: list[dict[str, Any]]) -> None:
    if not pages:
        print("[!] No pages scanned yet.")
        return
    print(f"\n{'#':>3}  {'elements':>8}  {'scanned_at':<20}  title / url")
    print("-" * 72)
    for index, page in enumerate(pages, start=1):
        scanned = page.get("scannedAt", "?")[:19]
        title = page.get("title", "?")[:30]
        url = page.get("url", "?")[:40]
        print(f"{index:>3}  {page.get('total', 0):>8}  {scanned:<20}  {title}")
        print(f"{'':>3}  {'':>8}  {'':<20}  {url}")
    print()


def parse_menu_choice(raw: str) -> int | None:
    """Parse user input as a menu number (1..N) or 0 for quit."""
    text = raw.strip()
    if not text:
        return None
    if text.isdigit():
        number = int(text)
        if number == 0:
            return len(MENU_ITEMS)
        if 1 <= number <= len(MENU_ITEMS):
            return number
    return None


def prompt_optional(label: str) -> str:
    try:
        return input(f"{label} (Enter = default): ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def handle_menu_action(
    action: str,
    context: BrowserContext,
    page: Page,
    pages: list[dict[str, Any]],
    *,
    stealth: bool,
) -> tuple[bool, Page]:
    """Run one menu action. Returns (continue_repl, active_page)."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    active = resolve_active_page(context, page)
    if active is None and action != "quit":
        print("[ERROR] Browser window was closed. Run the program again.")
        return False, page

    if action == "quit":
        return False, page

    if action == "scan":
        try:
            scan_current_page(active, pages, stealth=stealth, replace=False)
        except Exception as exc:
            print(f"[ERROR] Scan failed: {exc}")
        return True, active

    if action == "scan_replace":
        try:
            scan_current_page(active, pages, stealth=stealth, replace=True)
        except Exception as exc:
            print(f"[ERROR] Scan failed: {exc}")
        return True, active

    if action == "scan_url":
        url = prompt_optional("URL to scan (e.g. https://example.com)")
        if not url:
            print("[!] No URL entered.")
            return True, active
        _, active = scan_url_flow(
            context, active, pages, url,
            stealth=stealth, replace=False, wait_login=True,
        )
        return True, active or page

    if action == "list":
        print_scan_list(pages)
        return True, active

    if action == "report":
        if not pages:
            print("[!] No scans yet. Run option 1, 2, or 3 first.")
            return True, active
        filename = prompt_optional("Markdown filename (.md)")
        if not filename:
            filename = f"pwmap_report_{timestamp}.md"
        elif not filename.lower().endswith(".md"):
            filename += ".md"
        report_path = Path(filename).resolve()
        report_path.write_text(build_markdown_report(pages), encoding="utf-8")
        print(f"[OK] Report saved: {report_path}")
        return True, active

    if action == "export_json":
        if not pages:
            print("[!] No scans yet. Run option 1, 2, or 3 first.")
            return True, active
        filename = prompt_optional("JSON filename (.json)")
        path = Path(filename or f"pwmap_export_{timestamp}.json").resolve()
        export_json_file(pages, path)
        print(f"[OK] JSON saved: {path}")
        return True, active

    if action == "export_csv":
        if not pages:
            print("[!] No scans yet. Run option 1, 2, or 3 first.")
            return True, active
        filename = prompt_optional("CSV filename (.csv)")
        path = Path(filename or f"pwmap_export_{timestamp}.csv").resolve()
        export_csv_file(pages, path)
        print(f"[OK] CSV saved: {path}")
        return True, active

    if action == "goto":
        url = prompt_optional("URL (e.g. google.com)")
        if not url:
            print("[!] No URL entered.")
            return True, active
        stealth_goto(active, url, stealth)
        print(f"[i] Navigated to: {active.url}")
        return True, active

    if action == "clear":
        pages.clear()
        if DATA_FILE.exists():
            DATA_FILE.unlink()
        print("[i] All scans cleared.")
        return True, active

    if action == "help":
        print_help()
        return True, active

    return True, active


def run_repl(
    context: BrowserContext,
    page: Page,
    pages: list[dict[str, Any]],
    *,
    stealth: bool,
) -> None:
    while True:
        page = resolve_active_page(context, page)
        if page is None:
            print("[!] Browser closed. Exiting.")
            break

        print_menu(page.url)

        try:
            line = input(f"Choice (1-{len(MENU_ITEMS)} or 0=quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        choice = parse_menu_choice(line)
        if choice is None:
            print(f"[!] Enter a number between 1 and {len(MENU_ITEMS)} (or 0 to quit).")
            continue

        action = MENU_ITEMS[choice - 1][0]

        try:
            continue_repl, page = handle_menu_action(
                action, context, page, pages, stealth=stealth,
            )
            if not continue_repl:
                break
        except Exception as exc:
            print(f"[ERROR] {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PW-MAP — scan web pages and generate Playwright locator reports.",
    )
    parser.add_argument(
        "start_url",
        nargs="?",
        help="URL to open and scan automatically",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without a visible window (easier to detect by anti-bot systems)",
    )
    parser.add_argument(
        "--no-stealth",
        action="store_true",
        help="Disable anti-detection patches (not recommended)",
    )
    parser.add_argument(
        "--no-wait-login",
        action="store_true",
        help="Scan immediately after page load (skip Enter-to-continue prompt)",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Wait N seconds before scanning (use with --no-wait-login)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace previous scan of the same URL instead of adding a new entry",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Save Markdown report automatically after scanning",
    )
    parser.add_argument(
        "--report-file",
        metavar="FILE",
        help="Report filename (used with --report)",
    )
    parser.add_argument(
        "--quit",
        action="store_true",
        help="Skip interactive menu after auto-scan (browser stays open)",
    )
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="Close Chrome when the program exits (default: keep browser open)",
    )
    return parser.parse_args()


def shutdown(playwright: Any, context: BrowserContext, *, close_browser: bool) -> None:
    if close_browser:
        try:
            context.close()
        except Exception:
            pass
        try:
            playwright.stop()
        except Exception:
            pass
        print("Browser closed. Goodbye.")
    else:
        print("\n[i] Done. Chrome stays open — close the browser window yourself when finished.")
        print("[i] You can close this terminal now.")


def main() -> None:
    args = parse_args()
    stealth = not args.no_stealth

    if args.headless and stealth:
        print("[!] Warning: headless mode is easier for anti-bot systems to detect.")

    playwright = sync_playwright().start()
    context = launch_browser_context(
        playwright,
        headless=args.headless,
        stealth=stealth,
    )
    page = context.pages[0] if context.pages else context.new_page()
    pages = load_saved_pages()

    if pages:
        print(
            f"[i] Loaded {len(pages)} page(s) from a previous session. "
            "Run option 9 (clear) to start fresh."
        )

    auto_scanned = False
    if args.start_url:
        result, page = scan_url_flow(
            context,
            page,
            pages,
            args.start_url,
            stealth=stealth,
            replace=args.replace,
            wait_login=not args.no_wait_login,
            wait_seconds=args.wait,
        )
        auto_scanned = result is not None

        if auto_scanned and args.report and pages:
            report_path = save_auto_report(pages, args.report_file)
            print(f"[OK] Report saved: {report_path}")

        if auto_scanned:
            print("\n[i] Auto-scan complete.")

        if args.quit:
            shutdown(playwright, context, close_browser=args.close_browser)
            return

    print_banner(stealth=stealth, headless=args.headless)
    run_repl(context, page, pages, stealth=stealth)
    shutdown(playwright, context, close_browser=args.close_browser)


if __name__ == "__main__":
    main()
