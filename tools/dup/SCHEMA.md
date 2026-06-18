# Dashboard Update Packet (DUP) — `dup-1`

A DUP is the **only** way the SLT 1:1 hub gets patched from a Fireflies transcript. One meeting → one packet → one review beat → applied.

> **Scope:** DUPs **only** target the SLT 1:1 hub (`target: "slt-1to1"`).
> OKRs and annual Targets are updated live in the group OKR meeting and are explicitly **out of scope** for any transcript-driven flow. A DUP that names `target: "okrs"` or `target: "targets"` is rejected by the validator and by the applier.

## Top-level shape

```jsonc
{
  "version": "dup-1",
  "source": {
    "meeting_title": "Ian Wilson 1:1 — 17 Jun 2026",
    "meeting_date":  "2026-06-17",      // ISO date
    "fireflies_url": "https://app.fireflies.ai/view/…",
    "attendees":     ["Adrian Tate", "Ian Wilson"]
  },
  "updates": [
    { "target": "slt-1to1", "path": "…", "op": "…", /* fields | value */ "rationale": "…" }
  ]
}
```

`source` is required. Every applied DUP is appended verbatim into the repo's `audit/` directory keyed by date + meeting slug — so provenance survives the merge into Supabase.

## State digest (`tools/dup/digest.py`)

The upstream Claude needs to know what already exists in order to pick correct `set` paths and to avoid duplicate `append`s. Rather than ship it the full ~30 KB row, we maintain a small (~6–10 KB) **state digest** — a text snapshot listing every modifiable surface keyed by id/label/index, with the current `status` / `prog` / `conf` shown so no-op sets can be skipped.

Generate it with:

```
python3 tools/dup/digest.py > slt-state.txt
```

…then upload `slt-state.txt` as a project file in the Claude.ai DUP project (or paste it at the top of a chat as a fallback). Refresh after each batch of applied DUPs — the apply flow in Claude Code regenerates it automatically and offers the new file for re-upload.

## Path grammar

Paths use **semantic identifiers** in brackets wherever possible, so reordering arrays doesn't invalidate them. Numeric indices are a fallback.

| Use case | Path |
|---|---|
| Person object | `people[<person-id>]` |
| Bonus goal (compensation) | `people[<person-id>].bonus[<label>]` |
| Personal goal (development) | `people[<person-id>].goals[<label>]` |
| Priority item by index | `people[<person-id>].items[<index>]` |
| PR theme by index | `people[<person-id>].themes[<index>]` |
| 1:1 log (array, no index needed for append/prepend) | `people[<person-id>].log` |
| 1:1 log entry by index | `people[<person-id>].log[<index>]` |

**Person IDs:** `ian`, `jake`, `scales`, `jack`, `jen`, `deepak`.

When you reference `bonus[<label>]` or `goals[<label>]`, the resolver does a case-insensitive exact match first, then a prefix match. If multiple match, the update is rejected (you'll be asked to disambiguate).

## Ops

| `op` | Body field | Meaning |
|---|---|---|
| `set` | `fields: {…}` | Update only the named fields on the object at `path`. Other fields are preserved. |
| `replace` | `value: {…}` | Swap the whole object at `path`. Rare; prefer `set`. |
| `append` | `value: {…}` | Append to the array at `path`. De-duped on content equality. |
| `prepend` | `value: {…}` | Prepend to the array at `path`. De-duped. |
| `delete` | (none) | Remove the object at `path`. |

## Validation rules

1. `version` must be `"dup-1"`.
2. `source.meeting_date` must be ISO (YYYY-MM-DD) and within the last 60 days.
3. Each update's `target` must be `"slt-1to1"`. Otherwise → rejected.
4. `path` must parse against the grammar above. Otherwise → rejected.
5. For `op:set`/`replace`/`append`/`prepend`, the body field must be present and an object (or for `append`/`prepend`, a single object — not an array).
6. **`set` on a bonus/goal item may only touch known fields:** `label`, `target`, `owner`, `due`, `status`, `note`, `prog`, `conf`. Unknown fields → rejected.
7. `status` must be one of `open|prog|block|mon|done`. `prog` / `conf` must be a percentage string (e.g. `"0%"`, `"55%"`).
8. **Do not invent data.** If a value isn't explicitly in the transcript, omit the update. The upstream Claude is instructed to do this; the applier won't catch hallucinations, only schema breaches.
9. Subjective updates (`status` / `prog` / `conf`) should include a `rationale` quoting the supporting line from the transcript.

## End-to-end flow

```
Fireflies transcript
      │
      ▼
Claude.ai (Fireflies MCP)  ──[DUP JSON]──▶  paste into Claude Code
                                                  │
                                                  ▼
                                           validate.py-equivalent in-session
                                                  │
                                                  ▼
                                           Diff preview shown to user
                                                  │
                                                  ▼ (on "apply")
                                           PATCH dashboard_data
                                           write audit/<date>-<slug>.json
                                                  │
                                                  ▼
                                           Re-fetch + confirm
```

## Examples

See `examples/sample-dup.json` for a worked example covering `set`, `prepend`, `append`, and a goal vs bonus distinction.
