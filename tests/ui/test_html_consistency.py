"""
Smoke tests for UI HTML consistency.

DOM/HTML correctness checks using pytest + BeautifulSoup.
Not unit tests — validate structure, no CDN refs, and styling conventions.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# Project root: tests/ui -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "web"

# CDN substrings to forbid in src/href
CDN_PATTERNS = ("cdn.", "cdnjs.", "jsdelivr.", "unpkg.", "googleapis.")

# Required CSS order (substring match in href)
CSS_ORDER = [
    "vendor/tailwind",
    "css/theme.css",
    "css/base.css",
    "css/layout.css",
    "css/components.css",
]

# Required vendor files (relative to repo root)
VENDOR_FILES = [
    "web/vendor/tailwind/tailwind.min.css",
    "web/vendor/xterm/xterm.js",
    "web/vendor/xterm/xterm.css",
]


def _html_files():
    """All HTML files under web/."""
    return sorted(WEB_ROOT.rglob("*.html"))


def _parse(path):
    """Parse HTML file with BeautifulSoup."""
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


@pytest.fixture(scope="module")
def html_file_list():
    return _html_files()


# --- test_no_cdn_references ---


def test_no_cdn_references(html_file_list):
    """No cdn/cdnjs/jsdelivr/unpkg/googleapis in any src or href."""
    violations = []
    for path in html_file_list:
        soup = _parse(path)
        rel = path.relative_to(REPO_ROOT)
        for tag in soup.find_all(True):
            for attr in ("src", "href"):
                val = tag.get(attr)
                if not val:
                    continue
                val_lower = val.lower()
                for pattern in CDN_PATTERNS:
                    if pattern in val_lower:
                        violations.append(f"{rel}: {tag.name} {attr}={val!r}")
                        break
    assert not violations, "CDN references found:\n" + "\n".join(violations)


# --- test_css_load_order ---


def test_css_load_order(html_file_list):
    """Stylesheets appear in order: vendor/tailwind, theme, base, layout, components."""
    for path in html_file_list:
        soup = _parse(path)
        head = soup.find("head")
        if not head:
            continue
        links = [
            a.get("href", "")
            for a in head.find_all("link", rel="stylesheet")
        ]
        # Build list of indices for each required substring
        order_indices = []
        for want in CSS_ORDER:
            idx = None
            for i, href in enumerate(links):
                if want in href:
                    idx = i
                    break
            order_indices.append((want, idx))
        # Each required sheet must appear and in order
        prev_idx = -1
        for name, idx in order_indices:
            assert idx is not None, f"{path.relative_to(REPO_ROOT)}: missing stylesheet containing {name!r}"
            assert idx > prev_idx, (
                f"{path.relative_to(REPO_ROOT)}: stylesheet order wrong — {name!r} at index {idx}, expected after {prev_idx}"
            )
            prev_idx = idx


# --- test_vendor_files_exist ---


def test_vendor_files_exist():
    """Required vendor assets exist on disk."""
    missing = []
    for rel in VENDOR_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            missing.append(rel)
    assert not missing, "Missing vendor files: " + ", ".join(missing)


# --- test_buttons_have_btn_class ---


def test_buttons_have_btn_class(html_file_list):
    """At least 90% of button and a[role=button] have class containing 'btn'."""
    without_btn = []
    total = 0
    for path in html_file_list:
        soup = _parse(path)
        rel = path.relative_to(REPO_ROOT)
        buttons = soup.find_all("button") + soup.find_all("a", role="button")
        for el in buttons:
            total += 1
            classes = el.get("class") or []
            if not any("btn" in c for c in classes):
                without_btn.append(f"{rel}: <{el.name}> without btn class")
    if total == 0:
        pytest.skip("No button or a[role=button] elements found")
    pct = (total - len(without_btn)) / total * 100
    assert pct >= 90.0, (
        f"Only {pct:.1f}% of buttons have btn class ({len(without_btn)} missing):\n"
        + "\n".join(without_btn[:20])
        + ("\n..." if len(without_btn) > 20 else "")
    )


# --- test_inputs_have_input_class ---


def test_inputs_have_input_class(html_file_list):
    """At least 90% of text/number/password/search inputs have class containing 'input'."""
    without_input = []
    total = 0
    for path in html_file_list:
        soup = _parse(path)
        rel = path.relative_to(REPO_ROOT)
        for input_type in ("text", "number", "password", "search"):
            for el in soup.find_all("input", type=input_type):
                total += 1
                classes = el.get("class") or []
                if not any("input" in c for c in classes):
                    without_input.append(f"{rel}: <input type={input_type!r}> without input class")
    if total == 0:
        pytest.skip("No text/number/password/search inputs found")
    pct = (total - len(without_input)) / total * 100
    assert pct >= 90.0, (
        f"Only {pct:.1f}% of inputs have input class ({len(without_input)} missing):\n"
        + "\n".join(without_input[:20])
        + ("\n..." if len(without_input) > 20 else "")
    )


# --- test_tables_have_container ---


def test_tables_have_container(html_file_list):
    """Every table has an ancestor with class containing 'table-container'."""
    violations = []
    for path in html_file_list:
        soup = _parse(path)
        rel = path.relative_to(REPO_ROOT)
        for table in soup.find_all("table"):
            parent = table.parent
            found = False
            while parent:
                classes = parent.get("class") or []
                if any("table-container" in c for c in classes):
                    found = True
                    break
                parent = parent.parent
            if not found:
                violations.append(f"{rel}: <table> without table-container ancestor")
    assert not violations, "Tables without table-container ancestor:\n" + "\n".join(violations)


# --- test_nav_aria_attributes ---


def test_nav_aria_attributes(html_file_list):
    """#sidebar has role=navigation; .nav-mobile-toggle has aria-label, aria-expanded, aria-controls."""
    for path in html_file_list:
        soup = _parse(path)
        rel = path.relative_to(REPO_ROOT)
        sidebar = soup.find(id="sidebar")
        if not sidebar:
            continue
        assert sidebar.get("role") == "navigation", (
            f"{rel}: #sidebar must have role='navigation'"
        )
        toggle = soup.find(class_="nav-mobile-toggle")
        if not toggle:
            continue
        for attr in ("aria-label", "aria-expanded", "aria-controls"):
            assert toggle.get(attr) is not None, (
                f"{rel}: .nav-mobile-toggle must have {attr}"
            )
