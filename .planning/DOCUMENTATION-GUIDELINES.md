# Documentation Guidelines

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [User Documentation Structure](#user-documentation-structure)
3. [Technical Documentation Standards](#technical-documentation-standards)
4. [Embedded Documentation Format](#embedded-documentation-format)
5. [Common Troubleshooting Workflows](#common-troubleshooting-workflows)
6. [Device-Specific Guides](#device-specific-guides)
7. [Documentation Update Procedures](#documentation-update-procedures)
8. [Style Guide and Templates](#style-guide-and-templates)

---

## Overview

### Purpose

This document defines the structure, standards, and maintenance procedures for all RPi Engineer-in-a-Box documentation. It ensures consistency, findability, and usefulness for both end users and implementers.

### Documentation Types

**User Documentation**:
- How-to guides for end users
- Embedded in web interface
- Offline-accessible

**Technical Documentation**:
- API reference
- Architecture and design
- Developer guides

**Operational Documentation**:
- Deployment procedures
- Troubleshooting guides
- Maintenance procedures

### Principles

1. **User-Centric**: Write for the reader's task, not the system's structure
2. **Progressive**: Simple first, details on demand
3. **Consistent**: Same terms, same structure, same tone
4. **Maintainable**: Easy to update, version-controlled
5. **Accessible**: Works offline, searchable, clear language

---

## User Documentation Structure

### Primary Location

**Embedded in Web Interface**: `/opt/rpi-engineer/web/docs/`

**Access**: Help icon or "Documentation" link in web interface

**Format**: HTML or Markdown rendered to HTML

### Top-Level Structure

```
docs/
├── index.html              # Documentation home
├── getting-started/
│   ├── quick-start.html
│   ├── first-capture.html
│   └── first-serial-session.html
├── features/
│   ├── packet-capture.html
│   ├── serial-console.html
│   ├── network-management.html
│   └── remote-access.html
├── troubleshooting/
│   ├── common-issues.html
│   ├── network-issues.html
│   ├── serial-issues.html
│   └── capture-issues.html
├── devices/
│   ├── cisco.html
│   ├── juniper.html
│   └── hp-aruba.html
└── reference/
    ├── keyboard-shortcuts.html
    └── bpf-filters.html
```

### Page Structure

Each user doc page should include:

1. **Title**: Clear, task-oriented
2. **Brief Summary**: 1-2 sentences, what this page covers
3. **Prerequisites**: What user needs before starting
4. **Steps**: Numbered, actionable
5. **Tips/Warnings**: Callouts where relevant
6. **Related**: Links to related docs
7. **Last Updated**: Date

### Navigation

**Sidebar**: Hierarchical navigation, expandable sections

**Breadcrumbs**: Home > Section > Page

**Search**: Full-text search across docs (future)

---

## Technical Documentation Standards

### Specification Documents

**Location**: `.planning/` directory

**Format**: Markdown

**Structure** (per existing specs):
- Document Information header
- Table of Contents
- Overview/Introduction
- Detailed sections
- Document Control (version history)
- Related Documents

**Naming**: `{TOPIC}-SPECIFICATION.md` or `{TOPIC}-GUIDE.md`

### API Documentation

**Source**: Code comments (OpenAPI/Swagger) or separate API-REFERENCE.md

**Required for Each Endpoint**:
- Method and path
- Description
- Request parameters/body
- Response format
- Error codes
- Example request/response

### Code Documentation

**Python**:
- Module docstring: Purpose of module
- Class docstring: Purpose, key attributes
- Function docstring: Purpose, args, returns, raises
- Inline comments: Why, not what

**Example**:
```python
def validate_ip_address(ip: str) -> bool:
    """Validate IPv4 address format.
    
    Args:
        ip: String to validate as IPv4 address
        
    Returns:
        True if valid IPv4, False otherwise
    """
```

---

## Embedded Documentation Format

### Markdown Support

**Supported**:
- Headers (h1-h6)
- Bold, italic
- Lists (ordered, unordered)
- Code blocks with syntax highlighting
- Links (internal and external)
- Tables
- Blockquotes (for tips, warnings)

**Rendering**: Markdown to HTML at build time or client-side

### Callouts

**Tip**:
```markdown
> **Tip**: Use the Advanced mode for more control over capture filters.
```

**Warning**:
```markdown
> **Warning**: Stopping a capture will finalize the file. Ensure you have enough disk space.
```

**Note**:
```markdown
> **Note**: Serial console requires a USB-to-serial adapter. Most Cisco devices use 9600 8N1.
```

### Code Examples

**Format**:
````markdown
```bash
# Start a packet capture
# 1. Select interface eth0
# 2. Click Start Capture
```
````

**Syntax Highlighting**: bash, json, python, text as appropriate

### Images and Diagrams

**Location**: `web/docs/images/`

**Format**: PNG or SVG preferred

**Alt Text**: Required for accessibility

**Captions**: Optional, below image

---

## Common Troubleshooting Workflows

### Structure for Each Issue

1. **Symptom**: What the user sees
2. **Possible Causes**: Brief list
3. **Resolution Steps**: Ordered by likelihood
4. **If Still Failing**: Escalation or additional resources
5. **Prevention**: How to avoid in future

### Documented Workflows

**Network Issues**:
- Cannot connect to WiFi hotspot
- No internet access (WAN)
- Failover not working
- Interface not detected

**Serial Issues**:
- Device not detected
- Permission denied opening port
- Garbled characters (wrong baud rate)
- Session disconnects unexpectedly

**Capture Issues**:
- No packets captured
- Capture file corrupt
- Live view not updating
- Filter not working

**Remote Access Issues**:
- Cannot connect to device
- Connection ID not displayed
- Service not starting

**General**:
- Web interface not loading
- Slow performance
- Update failed
- Factory reset procedure

### Troubleshooting Template

```markdown
## [Issue Name]

**Symptom**: [What user experiences]

**Common Causes**:
- Cause 1
- Cause 2

**Resolution**:

### Step 1: [Action]
[Detailed steps]

### Step 2: [Action]
[Detailed steps]

**If problem persists**: [Next steps, logs to collect, support info]

**Prevention**: [How to avoid]
```

---

## Device-Specific Guides

### Purpose

Help users connect to specific network equipment brands with correct serial settings and workflows.

### Supported Devices (Initial)

**Cisco**:
- Default: 9600 8N1, no flow control
- Console cable: Rollover or straight-through (device-dependent)
- Common commands for initial config
- Copy config via serial (XMODEM)

**Juniper**:
- Default: 9600 8N1
- Console access workflow
- File transfer considerations

**HP/Aruba**:
- Newer devices: 115200 8N1
- Older: 9600 8N1
- Differences from Cisco

### Guide Structure

```markdown
# [Vendor] Device Connection Guide

## Default Settings
- Baud rate: X
- Data bits: X
- Parity: X
- Stop bits: X
- Flow control: X

## Connection Steps
1. [Step]
2. [Step]

## Common Operations
- [Operation 1]
- [Operation 2]

## Troubleshooting
- [Vendor-specific issues]

## References
- [Links to vendor docs]
```

### Extensibility

- Add new vendors as needed
- Community contributions welcome
- Keep vendor-neutral where possible

---

## Documentation Update Procedures

### When to Update

**Trigger Updates When**:
- Feature added or changed
- UI workflow changes
- New troubleshooting scenario discovered
- API changes
- Configuration option added/removed

### Update Process

1. **Identify** affected documentation
2. **Edit** in appropriate format/location
3. **Review** for accuracy and clarity
4. **Test** any procedures (especially troubleshooting)
5. **Commit** with clear message referencing change
6. **Update** "Last Updated" date if applicable

### Version Control

**Specifications**: In Git with code

**Embedded Docs**: In Git with web assets

**Changelog**: Maintain CHANGELOG.md for user-facing changes

### Review Cycle

**Specifications**: Review when related feature implemented

**User Docs**: Review with each release

**Troubleshooting**: Update when new issues identified

---

## Style Guide and Templates

### Writing Style

**Tone**: Professional, helpful, concise

**Voice**: Second person ("you") for user docs, passive or third person for technical

**Sentences**: Short, one idea per sentence

**Paragraphs**: 3-5 sentences max

**Avoid**: Jargon without definition, assumptions about expertise

### Terminology

**Consistent Terms**:
- "Web interface" (not "UI" or "dashboard" alone)
- "Serial console" (not "terminal" or "console" alone)
- "Packet capture" (not "pcap" in user docs)
- "WiFi hotspot" (not "AP" or "access point" in user docs)
- "Simple mode" / "Advanced mode" (capitalized)

**Abbreviations**: Define on first use, e.g., "Berkeley Packet Filter (BPF)"

### Formatting

**Headers**: Sentence case, not title case

**Lists**: Use when 3+ items; parallel structure

**Numbers**: Spell out one through nine, use numerals for 10+

**Code/Commands**: Monospace, distinguish from prose

### Template: Feature Guide

```markdown
# [Feature Name]

[1-2 sentence description]

## Before You Start

- [Prerequisite 1]
- [Prerequisite 2]

## [Main Task]

1. [Step with detail]
2. [Step with detail]
3. [Step with detail]

## Tips

- [Tip 1]
- [Tip 2]

## Troubleshooting

See [link to troubleshooting page] for common issues.

## Related

- [Related doc 1]
- [Related doc 2]
```

### Template: Troubleshooting Entry

```markdown
### [Issue Name]

**Symptom**: [Description]

**Solution**:

1. [Step]
2. [Step]

**Still not working?** [Escalation]
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial documentation guidelines |

## Related Documents
- PROJECT-OVERVIEW.md
- WEB-INTERFACE-SPECIFICATION.md
- SERIAL-CONSOLE-SPECIFICATION.md
- PACKET-CAPTURE-SPECIFICATION.md
- API-REFERENCE.md
