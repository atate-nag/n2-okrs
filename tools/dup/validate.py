#!/usr/bin/env python3
"""
Validate a Dashboard Update Packet (DUP, schema dup-1) and preview the diff
it would produce against a snapshot of the live `slt-1to1` Supabase row.

Usage:
    python3 validate.py <packet.json> [snapshot.json]

If snapshot.json is omitted, paths are checked for syntactic validity only
(no resolution). With a snapshot, paths are resolved and a before/after
diff is printed per update.

Exit code 0 on success, 1 on any validation failure.

This is a strict validator: it refuses anything outside the dup-1 contract.
The applier (Claude Code) runs the same logic before any Supabase PATCH.
"""
from __future__ import annotations
import json, re, sys
from datetime import date, datetime, timedelta
from typing import Any

ALLOWED_TARGETS = {"slt-1to1"}
ALLOWED_OPS = {"set", "replace", "append", "prepend", "delete"}
ALLOWED_STATUS = {"open", "prog", "block", "mon", "done"}
ALLOWED_ITEM_FIELDS = {"label","target","owner","due","status","note","prog","conf"}
PERSON_IDS = {"ian","jake","scales","jack","jen","deepak"}

PCT_RE = re.compile(r"^\d{1,3}%$")
PATH_HEAD_RE = re.compile(r"^people\[([a-z0-9-]+)\](.*)$")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None: errors.append(msg)
def warn(msg: str) -> None: warnings.append(msg)


def parse_path(path: str) -> list[tuple[str, str | None]]:
    """Parse a DUP path into a list of (field, key_or_index_or_None) steps."""
    m = PATH_HEAD_RE.match(path)
    if not m:
        raise ValueError(f"path must start with people[<id>]: {path!r}")
    pid, rest = m.group(1), m.group(2)
    if pid not in PERSON_IDS:
        raise ValueError(f"unknown person id {pid!r}; expected one of {sorted(PERSON_IDS)}")
    steps: list[tuple[str, str | None]] = [("people", pid)]
    # rest looks like ".bonus[<label>]" or ".log" or ".items[<idx>]"
    s = rest
    while s:
        if not s.startswith("."):
            raise ValueError(f"expected '.' after step in path: {path!r}")
        s = s[1:]
        m2 = re.match(r"^([a-z_]+)(\[([^\]]+)\])?(.*)$", s)
        if not m2:
            raise ValueError(f"can't parse step in path: {path!r}")
        field, _, sel, tail = m2.groups()
        steps.append((field, sel))
        s = tail
    return steps


def resolve(data: dict, steps: list[tuple[str, str | None]]) -> tuple[Any, Any, str | int | None]:
    """
    Resolve steps against `data`. Returns (parent, value, last_key) where
    last_key is the index/key used to address `value` in its parent. The
    parent + last_key tuple is what the applier mutates.
    """
    parent, value, last = None, data, None
    for field, sel in steps:
        if not isinstance(value, dict) and field != "people":
            raise KeyError(f"can't descend into {value!r} with field {field!r}")
        if field == "people":
            # selector is person id
            people = value["people"]
            idx = next((i for i, p in enumerate(people) if p.get("id") == sel), None)
            if idx is None: raise KeyError(f"person {sel!r} not found")
            parent, value, last = people, people[idx], idx
            continue
        sub = value.get(field)
        if sub is None: raise KeyError(f"field {field!r} not on object")
        if sel is None:
            parent, value, last = value, sub, field
            continue
        # selector present: list of items addressed by label / index
        if isinstance(sub, list):
            if sel.isdigit():
                i = int(sel)
                if i >= len(sub): raise KeyError(f"index {i} out of range for {field}")
                parent, value, last = sub, sub[i], i
            else:
                # label match (case-insensitive exact, then prefix)
                key = sel.lower()
                exact = [i for i, it in enumerate(sub) if str(it.get("label","")).lower() == key]
                if not exact:
                    exact = [i for i, it in enumerate(sub) if str(it.get("label","")).lower().startswith(key)]
                if not exact: raise KeyError(f"no item in {field} matches label {sel!r}")
                if len(exact) > 1: raise KeyError(f"ambiguous label {sel!r} in {field}: matches indices {exact}")
                parent, value, last = sub, sub[exact[0]], exact[0]
        else:
            raise KeyError(f"selector {sel!r} on non-list field {field!r}")
    return parent, value, last


def validate_packet(pkt: dict) -> None:
    if pkt.get("version") != "dup-1":
        err(f"version must be 'dup-1', got {pkt.get('version')!r}")
    src = pkt.get("source", {})
    if not isinstance(src, dict) or not src.get("meeting_title") or not src.get("meeting_date"):
        err("source.meeting_title and source.meeting_date are required")
    try:
        d = date.fromisoformat(src["meeting_date"])
        if d > date.today() + timedelta(days=1): err(f"meeting_date is in the future: {d}")
        if d < date.today() - timedelta(days=60): warn(f"meeting_date is more than 60 days old: {d}")
    except Exception as e:
        err(f"meeting_date isn't ISO YYYY-MM-DD: {e}")
    ups = pkt.get("updates")
    if not isinstance(ups, list) or not ups:
        err("updates must be a non-empty array")
        return
    for k, u in enumerate(ups):
        tag = f"updates[{k}]"
        if not isinstance(u, dict):
            err(f"{tag} must be an object"); continue
        if u.get("target") not in ALLOWED_TARGETS:
            err(f"{tag}.target must be one of {sorted(ALLOWED_TARGETS)} (got {u.get('target')!r})")
        if u.get("op") not in ALLOWED_OPS:
            err(f"{tag}.op must be one of {sorted(ALLOWED_OPS)} (got {u.get('op')!r})")
        try:
            steps = parse_path(u.get("path",""))
        except ValueError as e:
            err(f"{tag}: {e}"); continue
        op = u.get("op")
        if op == "set":
            f = u.get("fields")
            if not isinstance(f, dict) or not f:
                err(f"{tag}: op=set requires non-empty 'fields'"); continue
            # If targeting a bonus/goal item, enforce known fields + value shapes
            tail = next((field for field, _ in steps[1:] if field in ("bonus","goals")), None)
            if tail and len(steps) >= 3 and steps[-1][1] is not None:
                for fk, fv in f.items():
                    if fk not in ALLOWED_ITEM_FIELDS:
                        err(f"{tag}: unknown field {fk!r} on bonus/goal item")
                    if fk == "status" and fv not in ALLOWED_STATUS:
                        err(f"{tag}: status must be in {sorted(ALLOWED_STATUS)}")
                    if fk in ("prog","conf") and (not isinstance(fv, str) or not PCT_RE.match(fv)):
                        err(f"{tag}: {fk}={fv!r} must look like '0%'…'100%'")
        elif op in ("replace","append","prepend"):
            v = u.get("value")
            if not isinstance(v, dict):
                err(f"{tag}: op={op} requires 'value' object")
        elif op == "delete":
            if "fields" in u or "value" in u:
                warn(f"{tag}: op=delete ignores fields/value")
        # rationale recommended for subjective changes
        if op == "set" and isinstance(u.get("fields"), dict):
            if any(k in u["fields"] for k in ("status","prog","conf")) and not u.get("rationale"):
                warn(f"{tag}: status/prog/conf change without a 'rationale' quote")


def diff_preview(pkt: dict, snap: dict) -> None:
    print("\n— diff preview against snapshot —")
    for k, u in enumerate(pkt["updates"]):
        try:
            steps = parse_path(u["path"])
            parent, value, last = resolve(snap, steps)
        except KeyError as e:
            print(f"  updates[{k}] ✗ resolve failed: {e}"); continue
        op = u["op"]
        if op == "set":
            for fk, fv in (u.get("fields") or {}).items():
                old = (value or {}).get(fk, "—")
                print(f"  updates[{k}] set {u['path']}.{fk}: {old!r} → {fv!r}")
        elif op in ("append","prepend"):
            print(f"  updates[{k}] {op} {u['path']}: + {json.dumps(u['value'], ensure_ascii=False)[:100]}…")
        elif op == "replace":
            print(f"  updates[{k}] replace {u['path']}: was {json.dumps(value, ensure_ascii=False)[:80]}…")
        elif op == "delete":
            print(f"  updates[{k}] delete {u['path']} (was {json.dumps(value, ensure_ascii=False)[:80]}…)")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    pkt_path, snap_path = argv[1], argv[2] if len(argv) > 2 else None
    try:
        pkt = json.load(open(pkt_path))
    except Exception as e:
        print(f"can't read {pkt_path}: {e}"); return 1
    validate_packet(pkt)
    if warnings:
        print("warnings:")
        for w in warnings: print(f"  ⚠ {w}")
    if errors:
        print("errors:")
        for e in errors: print(f"  ✗ {e}")
        return 1
    print(f"✓ valid dup-1 packet, {len(pkt['updates'])} update(s)")
    if snap_path:
        try:
            snap = json.load(open(snap_path))
            # snapshot could be the row directly, or {"data": {...}}; accept both
            if "data" in snap and "people" in snap.get("data", {}): snap = snap["data"]
            diff_preview(pkt, snap)
        except Exception as e:
            print(f"diff preview skipped: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
