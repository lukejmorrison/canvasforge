# CanvasForge Feature Request Agent Instructions

## Purpose

- Keep every document inside `featurerequest/` aligned with `CHANGELOG.md` so release notes and design specs never drift.
- Provide a single checklist any AI/agent must follow before touching feature request content.

## Required Files to Touch

1. `featurerequest/<feature-name>.md`
2. `CHANGELOG.md`
3. `TODO.md` (only if the request changes priorities or introduces new tasks)

## Authoring Rules for Feature Request Docs

- Start each file with `# Feature Request: <Name>` (H1) so quick searches stay reliable.
- Follow with a "Document Metadata" table containing **all** of the following fields:
  - `Doc ID` (e.g., `FR-20251206-ImageLibrary`)
  - `Version` (increment when content changes materially)
  - `Date` (UTC or local timestamp used in the changelog)
  - `Owner / Author`
  - `Status` (Draft, In Progress, Complete, Deprecated)
  - `Priority`
  - `Changelog Tag` (copy the exact `[YYYY-MM-DD HH:MM] Heading` used inside `CHANGELOG.md`; if no dated entry exists yet, use `[Unreleased] Feature Name` and update it once the first timestamped change lands)
  - `Related Files` (paths such as `main.py`, `assets/...`)
- After metadata, include sections for Overview, Goals, Requirements, Dependencies, Risks, Success Metrics, and Next Steps. Use consistent heading levels (`##` for section headers).

## Timeline & Changelog Synchronization

Every feature document **must** contain a `## Timeline` section with the following table so edits mirror the changelog. Before a feature has a dated entry, record `[Unreleased]` in the first column so replacements are easy to track:

| Changelog Timestamp | Feature Doc Version | Summary of Change | Link to Evidence |
| --- | --- | --- | --- |
| `[2025-12-04 17:30]` | `v1.0` | Example entry pointing back to `CHANGELOG.md`. | `CHANGELOG.md` |

Update procedure:

1. **Before editing** a feature doc, search `CHANGELOG.md` for the matching `Changelog Tag` or timestamp (or confirm the feature still belongs under `[Unreleased]`).
2. If the changelog lacks the upcoming change, add a new entry under the appropriate dated section **before** updating the feature doc. Use the same timestamp in both files.
3. Update the `Document Metadata` table (`Version`, `Date`, `Status`, `Changelog Tag`) and append a new row to the `Timeline` table summarizing what changed.
4. Cross-reference any new artifacts (screenshots, scripts, etc.) in both the `Timeline` table and the body text.
5. When work lands or scope changes, also adjust `TODO.md` so its priorities reflect the latest status.

## Update Checklist for Agents

1. Confirm the feature doc has all mandatory headings and tables.
2. Compare the doc's `Changelog Tag` against `CHANGELOG.md`; they must match character-for-character.
3. Increment the `Version` field (semver or vX.Y) whenever content changes.
4. Insert or update the `Timeline` row that corresponds to the changelog entry you just touched.
5. Run a quick grep for `FR-` to ensure no duplicate IDs exist.
6. Mention any pending engineering work in `TODO.md` if priorities change.

## Template Snippet

```markdown
# Feature Request: <Name>

## Document Metadata
| Field | Value |
| --- | --- |
| Doc ID | FR-YYYYMMDD-Label |
| Version | v1.0 |
| Date | 2025-12-06 10:15 |
| Owner / Author | <name> |
| Status | Draft |
| Priority | Medium |
| Changelog Tag | [Unreleased] Feature Title |
| Related Files | main.py, assets/... |

## Overview
...

## Timeline
| Changelog Timestamp | Feature Doc Version | Summary | Link |
| --- | --- | --- | --- |
| [Unreleased] | v1.0 | Initial draft created. | CHANGELOG.md |
```

Paste the template when creating new feature requests so future automation stays predictable.
