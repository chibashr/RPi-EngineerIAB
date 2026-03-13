# HTML Consistency Test Failures Report

**Generated:** 2026-03-13  
**Test Suite:** `tests/ui/test_html_consistency.py`  
**Status:** 3 failures (pre-existing)

---

## Summary

| Test | Status | Files Affected |
|------|--------|----------------|
| `test_no_cdn_references` | PASSED | - |
| `test_css_load_order` | PASSED | - |
| `test_vendor_files_exist` | PASSED | - |
| `test_buttons_have_btn_class` | FAILED | 2 files |
| `test_inputs_have_input_class` | FAILED | 2 files |
| `test_tables_have_container` | FAILED | 6 files |
| `test_nav_aria_attributes` | PASSED | - |

---

## Failure 1: `test_buttons_have_btn_class`

**Requirement:** At least 90% of `<button>` and `<a role="button">` elements must have a class containing `btn`.

**Current:** 64.1% compliance (47 buttons missing `btn` class)

### Affected Files

| File | Count |
|------|-------|
| `web/advanced/capture.html` | 1 |
| `web/advanced/docs.html` | 46 |

### Recommended Fix

Add the appropriate `btn` class to buttons:

```html
<!-- Before -->
<button>Click me</button>

<!-- After -->
<button class="btn btn-secondary">Click me</button>
```

For `docs.html`, the buttons are likely navigation or accordion toggles that may need a different approach (e.g., `btn-ghost` or a custom class that includes `btn`).

---

## Failure 2: `test_inputs_have_input_class`

**Requirement:** At least 90% of `<input type="text|number|password|search">` elements must have a class containing `input`.

**Current:** 57.1% compliance (9 inputs missing `input` class)

### Affected Files

| File | Missing Inputs |
|------|----------------|
| `web/advanced/snmp.html` | 4 (1 text, 3 number) |
| `web/advanced/syslog.html` | 5 (1 text, 4 number) |

### Recommended Fix

Add the `input` class to form inputs:

```html
<!-- Before -->
<input type="text" id="community-string" />
<input type="number" id="port" />

<!-- After -->
<input type="text" id="community-string" class="input" />
<input type="number" id="port" class="input" />
```

---

## Failure 3: `test_tables_have_container`

**Requirement:** Every `<table>` must have an ancestor element with a class containing `table-container`.

**Current:** 12 tables without proper container

### Affected Files

| File | Tables Missing Container |
|------|--------------------------|
| `web/advanced/index.html` | 1 |
| `web/advanced/network.html` | 3 |
| `web/advanced/serial.html` | 1 |
| `web/advanced/snmp.html` | 3 |
| `web/advanced/syslog.html` | 3 |
| `web/advanced/system.html` | 1 |

### Recommended Fix

Wrap tables in a container div:

```html
<!-- Before -->
<table>
  <thead>...</thead>
  <tbody>...</tbody>
</table>

<!-- After -->
<div class="table-container">
  <table>
    <thead>...</thead>
    <tbody>...</tbody>
  </table>
</div>
```

---

## Priority

These are **style/convention issues**, not functional bugs. They should be addressed to maintain UI consistency but are not blocking.

| Priority | Test | Rationale |
|----------|------|-----------|
| Low | `test_buttons_have_btn_class` | Most violations in docs.html which may use different button patterns |
| Medium | `test_inputs_have_input_class` | Affects form styling in SNMP/Syslog pages |
| Medium | `test_tables_have_container` | May cause horizontal scroll issues on mobile |

---

## Notes

- These failures are **pre-existing** and unrelated to recent update screen changes
- The `updates.html` file passes all HTML consistency tests
- Consider updating the test thresholds or fixing the HTML to reach 90%+ compliance
