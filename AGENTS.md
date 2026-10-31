# AI Agent Instructions & Persistent Context Entrypoint (AGENTS.md)

> **CRITICAL RULE FOR ALL CODING AGENTS:**  
> Do **NOT** repeatedly reanalyze the entire repository, reopen every file, rediscover the architecture, or repeat previous investigations. Doing so wastes user tokens, execution time, and context window.  
> Use the `/docs` directory as the persistent project memory.

---

## 1. Protocol Before Starting Any Task

Every AI agent must follow this exact 6-step sequence:

1. **Read `AGENTS.md`** (this file).
2. **Read `docs/CURRENT_STATUS.md`** to know the current phase, working subsystems, and active blockers.
3. **Read `docs/FILE_MAP.md`** to locate the exact files and classes responsible for the requested change.
4. **Read only the specific documentation relevant to the task:**
   * Architectural / pipeline questions ➔ `docs/ARCHITECTURE.md`
   * Architectural decisions & trade-offs ➔ `docs/DESIGN.md`
   * Endpoints, event schemas & WebSocket contracts ➔ `docs/API.md`
   * Coding constraints & rules ➔ `docs/RULES.md`
   * Project goals & technology stack ➔ `docs/PID.md`
   * Development history ➔ `docs/CHANGELOG.md`
5. **Identify the exact files related to the requested change.**
6. **Inspect only those specific files and their direct dependencies.**

---

## 2. Strict Prohibitions ("DO NOT")

* **DO NOT** re-read or list the entire repository on every prompt.
* **DO NOT** rediscover the architecture from scratch; it is fully documented in `docs/ARCHITECTURE.md`.
* **DO NOT** reopen unrelated files (e.g. do not read `upper_body_detector.py` if the user is asking about frontend CSS).
* **DO NOT** repeat completed investigations (e.g. YOLO stride timer bug, EAR pitch compensation, face landmark dropout fallback).
* **DO NOT** rewrite existing documentation files from scratch. Update only the relevant section.
* **DO NOT** run lengthy benchmark evaluations or full test suites for simple code or CSS edits.
* **DO NOT** invent endpoints or assume mock data. Always consult `docs/API.md`.

---

## 3. Incremental Execution Workflow

```
User Request
     │
     ▼
Check `docs/CURRENT_STATUS.md` & `docs/FILE_MAP.md`
     │
     ▼
Inspect Affected Files Only
     │
     ▼
Implement Targeted Fix / Feature
     │
     ▼
Run Targeted Test (e.g. `python -m unittest tests/test_critical_fixes.py`)
     │
     ▼
Update Affected Documentation (`docs/CURRENT_STATUS.md` & `docs/CHANGELOG.md`)
```

---

## 4. Documentation Update Policy

Update documentation **only** when code changes affect documented contracts:
* If a WebSocket event or REST endpoint changes ➔ update `docs/API.md`.
* If a new module or service is added ➔ update `docs/FILE_MAP.md` and `docs/ARCHITECTURE.md`.
* If a design decision or threshold changes ➔ update `docs/DESIGN.md` or `config.py`.
* Always record completed milestones in `docs/CHANGELOG.md` and update `docs/CURRENT_STATUS.md`.

