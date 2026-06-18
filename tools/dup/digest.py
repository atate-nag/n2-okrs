#!/usr/bin/env python3
"""
Generate an SLT state digest for the Claude.ai DUP project.

The digest is a compact, human-readable map of every modifiable field in
the slt-1to1 Supabase row — enough for the upstream Claude to pick correct
semantic paths, avoid duplicate inserts, and skip no-op set ops.

Usage:
    python3 digest.py                 # print to stdout
    python3 digest.py > slt-state.txt # capture for upload to Claude.ai

Workflow: regenerate after each batch of applied DUPs, then re-upload the
text to your Claude.ai DUP project (as a project file, or paste at the
top of a chat). See tools/dup/SCHEMA.md and tools/dup/starter-prompt.md.
"""
from __future__ import annotations
import datetime, json, subprocess, sys

URL = 'https://hsmdmcpmeqdowiwutlhb.supabase.co'
KEY = ('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
       'eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhzbWRtY3BtZXFkb3dpd3V0bGhiIi'
       'wicm9sZSI6ImFub24iLCJpYXQiOjE3NzQwNzM0NDYsImV4cCI6MjA4OTY0OTQ0Nn0.'
       'ZfZDiTGxaeo9YNZ1EGwJ5r0NzPYmbgJu6iezEmDO_dg')
ROW_KEY = 'slt-1to1'
LOG_RECENT = 3        # how many recent log entries to include per person
TITLE_MAX = 60        # truncate item titles / theme names to this
LABEL_MAX = 52        # truncate bonus/goal labels
LOG_TEXT_MAX = 88     # truncate log snippets


def fetch_row() -> dict:
    """Use curl (portable; sidesteps platform-specific Python SSL config)."""
    cmd = ['curl', '-s',
           f'{URL}/rest/v1/dashboard_data?key=eq.{ROW_KEY}&select=data',
           '-H', f'apikey: {KEY}',
           '-H', f'Authorization: Bearer {KEY}']
    out = subprocess.check_output(cmd, text=True)
    rows = json.loads(out)
    if not rows:
        raise RuntimeError(f'row {ROW_KEY!r} not found')
    return rows[0]['data']


def short(s, n):
    s = (s or '').replace('\n', ' ').replace('\r', '').strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def format_digest(data: dict) -> str:
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    L: list[str] = []
    L.append(f'SLT STATE DIGEST — generated {now}')
    L.append('Schema: slt-1to1 (one Supabase row, key=slt-1to1)')
    L.append('')
    L.append('HOW TO USE THIS WHEN EMITTING A DUP')
    L.append('  • For `set` on bonus/goals → copy the label EXACTLY from below.')
    L.append('  • For `set` on items/themes/log → use the [index] number shown.')
    L.append('  • Before `append`, scan this digest to avoid duplicates.')
    L.append('  • status/prog/conf are shown so you can skip no-op `set` ops.')
    L.append('  • Log shows only the recent 3 entries — older log entries')
    L.append('    exist but you almost never need to touch them.')
    L.append('')
    sep = '─' * 76
    L.append(sep)
    for person in data.get('people', []):
        pid = person.get('id', '?')
        name = person.get('name', '?')
        role = person.get('role', '')
        cur = person.get('cur', '')
        L.append('')
        L.append(f'{pid}  —  {name}   ({role})   cur:{cur}')
        L.append('')

        bonus = person.get('bonus') or []
        L.append(f'  bonus goals ({len(bonus)})' + (':' if bonus else '   (empty)'))
        for i, b in enumerate(bonus):
            L.append(f'    [{i}] "{short(b.get("label",""), LABEL_MAX)}"'
                     f'  status:{b.get("status","?")}'
                     f'  prog:{b.get("prog","—")}'
                     f'  conf:{b.get("conf","—")}')

        goals = person.get('goals') or []
        L.append(f'  personal goals ({len(goals)})' + (':' if goals else '   (empty)'))
        for i, g in enumerate(goals):
            L.append(f'    [{i}] "{short(g.get("label",""), LABEL_MAX)}"'
                     f'  status:{g.get("status","?")}'
                     f'  prog:{g.get("prog","—")}'
                     f'  conf:{g.get("conf","—")}')

        items = person.get('items') or []
        L.append(f'  priorities/items ({len(items)})' + (':' if items else '   (empty)'))
        for i, it in enumerate(items):
            L.append(f'    [{i}] {it.get("type","?"):6s}'
                     f' — "{short(it.get("title",""), TITLE_MAX)}"'
                     f'  status:{it.get("status","?")}')

        themes = person.get('themes') or []
        L.append(f'  PR themes ({len(themes)})' + (':' if themes else '   (empty)'))
        for i, th in enumerate(themes):
            L.append(f'    [{i}] "{short(th.get("theme",""), TITLE_MAX)}"')

        log = person.get('log') or []
        if log:
            L.append(f'  log ({len(log)} entries, most recent {min(LOG_RECENT, len(log))} shown):')
            for i, e in enumerate(log[:LOG_RECENT]):
                L.append(f'    [{i}] {e.get("date","?")}'
                         f'  "{short(e.get("text",""), LOG_TEXT_MAX)}"')
        else:
            L.append('  log (0)   (empty)')

        L.append('')
        L.append(sep)
    L.append('')
    L.append(f'TOTAL: {len(data.get("people", []))} people')
    return '\n'.join(L) + '\n'


def main(argv: list[str]) -> int:
    try:
        data = fetch_row()
    except Exception as e:
        print(f'fetch failed: {e}', file=sys.stderr)
        return 1
    sys.stdout.write(format_digest(data))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
