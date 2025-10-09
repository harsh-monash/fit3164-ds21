COPILOT_INSTRUCTION

Purpose
This file is a comprehensive instruction and workflow tailored to AI code assistants (Copilot-style agents) working in this repository. It consolidates the behavioral rules from `agent.md` and adds a required, explicit code-review workflow that must be followed whenever new files or substantial code changes occur.

---

Table of contents
- Purpose
- Core behavioral rules (from `agent.md`)
- Strong file-management rules
- Mandatory code-review workflow & checklist (NEW)
- Example code-review flow
- FAQs and edge-cases
- Change log

---

Core behavioral rules (source: `agent.md`)
1) Accuracy & hallucination prevention
- Prefer facts explicitly provided in this repository. Do not invent APIs, functions, libraries, or datasets that are not present.
- When uncertain, respond with: "Uncertain — please clarify or provide more details."

2) File management
- Do not create new files unless the user explicitly requests them (or grants permission). If the user requests the creation, confirm scope and intent first.

3) Consistency & integrity
- Maintain repository naming and formatting conventions. Changes to this file or `agent.md` should be additive/corrective, preserving prior context.

4) Clarification protocol
- If instructions are ambiguous, pause and ask a clarifying question before making changes.

5) Collaboration & transparency
- Explain the reasoning behind suggestions or changes. Keep messages concise and factual.

---

Strong file-management rules (enforced)
- Before creating, renaming, or deleting files, obtain explicit user approval.
- Limit file additions to a single logical unit per user request when possible (e.g., one feature directory or one utility module).
- If a change affects public APIs or data formats, explicitly call it out in the code review checklist and in the PR/commit message.

---

Mandatory code-review workflow & checklist (NEW - must be followed)
Overview
Whenever an AI agent creates a new file or introduces a major code change (feature, API change, new module, or significant refactor), the agent must produce a code review package and wait for explicit user or reviewer approval before marking the change as done.

What the agent must produce
1) A concise summary (1–3 lines) explaining intent and what the change accomplishes.
2) A file list showing added/modified/deleted files with relative paths.
3) A short diff excerpt or summary of key code changes (if possible).
4) Tests or verification steps (how to run or a short smoke test). If no tests, explain why and give manual verification steps.
5) A risk assessment listing possible regressions or compatibility issues.
6) A remediation plan if anything breaks (rollback steps, commands, or quick fixes).
7) A mandatory reviewer sign-off area: the user or designated reviewer must explicitly approve in a reply message.

Code review checklist (template)
- Title: Short title for the change (one line)
- Intent: Two-sentence description of why this change was made.
- Files changed:
  - Added:
    - path/to/new_file.ext — purpose
  - Modified:
    - path/to/modified_file.ext — reason
  - Deleted:
    - path/to/deleted_file.ext — reason
- Key code diff (high-level):
  - Show the main functions/classes changed and why.
- Tests / How to verify:
  - Unit tests to run (if any)
  - Manual test steps (curl endpoints, open page X, check Y)
- Risks:
  - Breaking backward compatibility
  - Performance regressions
  - Security or secrets exposure (call out explicitly)
- Remediation plan / rollback steps:
  - Commands or steps to revert or quick patch
- Reviewer sign-off (must be filled by user/reviewer):
  - [ ] Reviewed and approved by: @username or user message here

Required behavior after creation
- Do not mark the task complete until the reviewer/user confirms approval.
- If reviewer requests changes, implement them and re-post the checklist with diffs for re-review.

---

Example code-review flow (minimal)
1) User: "Please add a code review template and a Copilot instruction file." (explicit permission)
2) Agent creates `COPILOT_INSTRUCTION.md` and `CODE_REVIEW_TEMPLATE.md` (drafts).
3) Agent posts the code review checklist:
  - Intent: Add governance docs for AI agents
  - Files added: `COPILOT_INSTRUCTION.md`, `CODE_REVIEW_TEMPLATE.md`
  - Tests: N/A (docs)
  - Risks: low
  - Reviewer sign-off: waiting for user approval
4) User approves or requests changes. If approved, agent marks complete.

---

FAQs and edge cases
- Q: What counts as a "major code change"?
  - A: Any change that adds or modifies public API behavior, adds a new module or package, modifies database schemas, or touches deployment scripts.

- Q: What if the user is unavailable to review?
  - A: The agent should wait for explicit approval. If the user explicitly told the agent to proceed without review, document that permission and proceed.

- Q: Can the agent create small, one-line fixes without review?
  - A: No — even small code changes should be captured in the checklist. However, documentation-only edits are lower-risk and can be noted as such.

---

Change log
- 2025-09-25: Initial creation. Consolidated `agent.md` guidance and added mandatory code-review workflow.

---

How I will operate going forward
- When you request code or file creation, I will:
  1. Confirm scope if instructions are ambiguous.
  2. Create the files (only with your permission).
  3. Produce a code-review checklist above and wait for your explicit sign-off.

If you'd like a different filename or to store this policy in a different location (`.github/`, `docs/`, etc.), tell me and I'll move it after your confirmation.