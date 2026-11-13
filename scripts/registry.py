#!/usr/bin/env python3
"""Registry and recap helpers for the airdrop-hunter Hermes skill.

Stdlib only. All commands read/write <data_dir>/projects.json and are meant
to be invoked by the agent instead of hand-writing JSON each time.

Data dir resolution: --data-dir flag > $AIRDROP_HUNTER_DATA_DIR > ~/.hermes/airdrop-hunter
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_DATA_DIR = Path.home() / ".hermes" / "airdrop-hunter"

VALID_STATUSES = {"active", "monitoring", "done", "dropped"}
VALID_CATEGORIES = {"testnet", "points", "galxe", "exchange", "social", "meme", "other"}
VALID_TASK_TYPES = {"daily", "weekly", "one-off", "milestone"}
VALID_REPEATS = {"daily", "weekly", "none"}
VALID_CLAIM_STATUSES = {"watching", "claimable", "claimed", "n-a"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_date_only(value: str) -> str:
    """'2026-11-12T09:00:00Z' -> '2026-11-12'."""
    try:
        return parse_iso(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return value


def fail(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_data_dir(args_cli: str | None) -> Path:
    if args_cli:
        return Path(args_cli).expanduser()
    env = os.environ.get("AIRDROP_HUNTER_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return DEFAULT_DATA_DIR


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_raw(data_dir: Path) -> tuple[dict, Path]:
    path = data_dir / "projects.json"
    if not path.exists():
        fail(f"registry not found at {path} — run 'registry.py init' first")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        fail(f"{path} must be a JSON object")
    return data, path


def save_registry(data: dict, path: Path) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_text_atomic(path, text)


def find_project(data: dict, project_id: str) -> dict:
    for proj in data.get("projects", []):
        if proj.get("id") == project_id:
            return proj
    fail(f"no project with id '{project_id}' — run 'registry.py list'")


def slug_ok(slug: str) -> bool:
    return bool(slug) and all(ch.isalnum() or ch in "-_" for ch in slug) and " " not in slug


# ---------------------------------------------------------------- commands

def cmd_init(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    path = data_dir / "projects.json"
    if path.exists() and not args.force:
        fail(f"{path} already exists — use --force to overwrite")
    data = {"schema_version": SCHEMA_VERSION, "projects": []}
    save_registry(data, path)
    (data_dir / "reports").mkdir(parents=True, exist_ok=True)
    print(f"initialized {path}")


def cmd_validate(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    data, path = load_raw(data_dir)
    errors = validate_data(data)
    if errors:
        for err in errors:
            print(f"  - {err}")
        print(f"validate: {len(errors)} problem(s) in {path}")
        sys.exit(1)
    print(f"validate: OK — {len(data.get('projects', []))} project(s), schema v{data.get('schema_version')}")


def validate_data(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    projects = data.get("projects")
    if not isinstance(projects, list):
        errors.append("'projects' must be a list")
        return errors
    seen: set[str] = set()
    for i, proj in enumerate(projects):
        where = f"projects[{i}]"
        if not isinstance(proj, dict):
            errors.append(f"{where}: must be an object")
            continue
        pid = proj.get("id")
        if not isinstance(pid, str) or not slug_ok(pid):
            errors.append(f"{where}: 'id' missing or invalid (a-z 0-9 - _ only)")
        elif pid in seen:
            errors.append(f"{where}: duplicate id '{pid}'")
        else:
            seen.add(pid)
        if not proj.get("name"):
            errors.append(f"{where}: 'name' required")
        status = proj.get("status", "active")
        if status not in VALID_STATUSES:
            errors.append(f"{where}: status '{status}' not in {sorted(VALID_STATUSES)}")
        cat = proj.get("category", "other")
        if cat not in VALID_CATEGORIES:
            errors.append(f"{where}: category '{cat}' not in {sorted(VALID_CATEGORIES)}")
        urls = proj.get("urls")
        if not isinstance(urls, dict) or not urls.get("main"):
            errors.append(f"{where}: urls.main is required")
        for j, wallet in enumerate(proj.get("wallets", [])):
            addr = wallet.get("address", "")
            if wallet.get("chain") == "evm" and not (isinstance(addr, str) and len(addr) == 42 and addr.startswith("0x")):
                errors.append(f"{where}.wallets[{j}]: evm address must look like 0x + 40 hex chars (watch-only)")
            if wallet.get("private_key") or wallet.get("mnemonic") or wallet.get("seed"):
                errors.append(f"{where}.wallets[{j}]: NEVER store private keys/seed phrases — keep wallets watch-only (address only)")
        for j, task in enumerate(proj.get("tasks", [])):
            if not isinstance(task, dict) or not task.get("id"):
                errors.append(f"{where}.tasks[{j}]: 'id' required")
                continue
            if task.get("type") not in VALID_TASK_TYPES:
                errors.append(f"{where}.tasks[{j}]: type must be one of {sorted(VALID_TASK_TYPES)}")
            if task.get("repeat") not in VALID_REPEATS:
                errors.append(f"{where}.tasks[{j}]: repeat must be one of {sorted(VALID_REPEATS)}")
            if task.get("streak") not in (None,) and not isinstance(task.get("streak"), int):
                errors.append(f"{where}.tasks[{j}]: streak must be an integer")
        for j, claim in enumerate(proj.get("claims", [])):
            if not isinstance(claim, dict) or not claim.get("id"):
                errors.append(f"{where}.claims[{j}]: 'id' required")
                continue
            if claim.get("status") not in VALID_CLAIM_STATUSES:
                errors.append(f"{where}.claims[{j}]: status must be one of {sorted(VALID_CLAIM_STATUSES)}")
    return errors


def cmd_add(args) -> None:
    if not slug_ok(args.id):
        fail("--id must be a lowercase slug (a-z, 0-9, -, _)")
    if args.category not in VALID_CATEGORIES:
        fail(f"--category must be one of {sorted(VALID_CATEGORIES)}")
    data_dir = resolve_data_dir(args.data_dir)
    data, path = load_raw(data_dir)
    if any(p.get("id") == args.id for p in data["projects"]):
        fail(f"project '{args.id}' already exists")
    urls = {"main": args.main_url}
    if args.task_url:
        urls["tasks"] = args.task_url
    if args.claim_url:
        urls["claim"] = args.claim_url
    project = {
        "id": args.id,
        "name": args.name,
        "status": args.status,
        "category": args.category,
        "urls": urls,
        "wallets": [],
        "tasks": [],
        "claims": [],
        "metrics": {"points": None, "points_source": "manual", "rank": None, "updated_at": None},
        "notes": args.notes or "",
    }
    data["projects"].append(project)
    data["projects"].sort(key=lambda p: p["id"])
    save_registry(data, path)
    print(f"added project '{args.id}' ({args.name})")


def cmd_list(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    data, _ = load_raw(data_dir)
    for proj in data.get("projects", []):
        print(f"{proj.get('id'):<24} {proj.get('status'):<11} {proj.get('category'):<10} {proj.get('name', '')}")


def cmd_get(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    data, _ = load_raw(data_dir)
    print(json.dumps(find_project(data, args.id), indent=2, ensure_ascii=False))


def cmd_task_add(args) -> None:
    if args.type not in VALID_TASK_TYPES:
        fail(f"--type must be one of {sorted(VALID_TASK_TYPES)}")
    if args.repeat not in VALID_REPEATS:
        fail(f"--repeat must be one of {sorted(VALID_REPEATS)}")
    data_dir = resolve_data_dir(args.data_dir)
    data, path = load_raw(data_dir)
    proj = find_project(data, args.id)
    if any(t.get("id") == args.task_id for t in proj.get("tasks", [])):
        fail(f"task '{args.task_id}' already exists on '{args.id}'")
    proj.setdefault("tasks", []).append(
        {
            "id": args.task_id,
            "type": args.type,
            "title": args.title,
            "repeat": args.repeat,
            "url": args.url or "",
            "last_done": None,
            "streak": 0,
            "notes": "",
        }
    )
    save_registry(data, path)
    print(f"added task '{args.task_id}' to project '{args.id}'")


def cmd_task_done(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    data, path = load_raw(data_dir)
    proj = find_project(data, args.id)
    task = next((t for t in proj.get("tasks", []) if t.get("id") == args.task_id), None)
    if task is None:
        fail(f"no task '{args.task_id}' on project '{args.id}'")
    today = utcnow()
    last = task.get("last_done")
    streak = int(task.get("streak") or 0)
    if args.unset:
        task["last_done"] = None
        task["streak"] = 0
        print(f"task '{args.task_id}' on '{args.id}' reset")
    else:
        if last:
            prev_date = parse_iso(last).date()
            if prev_date == today.date():
                print(f"task '{args.task_id}' on '{args.id}' already done today (streak {streak}) — not incremented")
                task["last_done"] = to_iso(today)
                save_registry(data, path)
                return
            streak = streak + 1 if prev_date == (today.date() - timedelta(days=1)) else 1
        else:
            streak = 1
        task["last_done"] = to_iso(today)
        task["streak"] = streak
        print(f"task '{args.task_id}' on '{args.id}' done — streak {streak}")
    save_registry(data, path)


def cmd_claim_set(args) -> None:
    if args.status not in VALID_CLAIM_STATUSES:
        fail(f"--status must be one of {sorted(VALID_CLAIM_STATUSES)}")
    data_dir = resolve_data_dir(args.data_dir)
    data, path = load_raw(data_dir)
    proj = find_project(data, args.id)
    claim = next((c for c in proj.get("claims", []) if c.get("id") == args.claim_id), None)
    if claim is None:
        claim = {"id": args.claim_id, "label": args.claim_id, "url": "", "status": "watching", "deadline": None, "amount_hint": "", "last_checked": None}
        proj.setdefault("claims", []).append(claim)
    claim["status"] = args.status
    if args.deadline:
        claim["deadline"] = args.deadline
    if args.amount_hint:
        claim["amount_hint"] = args.amount_hint
    claim["last_checked"] = to_iso(utcnow())
    save_registry(data, path)
    print(f"claim '{args.claim_id}' on '{args.id}' -> {args.status}")


def task_is_due(task: dict, today: datetime) -> bool:
    repeat = task.get("repeat")
    last = task.get("last_done")
    if repeat not in ("daily", "weekly"):
        return False
    if not last:
        return True
    prev = parse_iso(last).date()
    if repeat == "daily":
        return prev < today.date()
    return prev <= (today.date() - timedelta(days=7))


def cmd_due(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    data, _ = load_raw(data_dir)
    today = utcnow()
    found = False
    for proj in data.get("projects", []):
        if proj.get("status") not in ("active", "monitoring"):
            continue
        due = [t for t in proj.get("tasks", []) if task_is_due(t, today)]
        if due:
            found = True
            print(f"{proj['id']}:")
            for t in due:
                last = iso_date_only(t.get("last_done")) if t.get("last_done") else "never"
                print(f"  - {t['id']} ({t['repeat']}) last={last} streak={t.get('streak') or 0}")
    if not found:
        print("no due tasks")


def days_until(value: str | None, today: datetime) -> int | None:
    if not value:
        return None
    try:
        return (parse_iso(value).date() - today.date()).days
    except ValueError:
        return None


def cmd_report(args) -> None:
    data_dir = resolve_data_dir(args.data_dir)
    data, path = load_raw(data_dir)
    errors = validate_data(data)
    if errors:
        fail("registry invalid; run 'registry.py validate'\n  " + "\n  ".join(errors))
    today = utcnow()
    projects = data.get("projects", [])
    active = [p for p in projects if p.get("status") in ("active", "monitoring")]
    due_total = sum(1 for p in active for t in p.get("tasks", []) if task_is_due(t, today))
    claims_watching = sum(1 for p in active for c in p.get("claims", []) if c.get("status") == "watching")

    lines: list[str] = []
    lines.append(f"# Airdrop Recap — {today.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Projects:** {len(active)} active/monitoring · **Watching claims:** {claims_watching} · **Tasks due:** {due_total}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Project | Status | Points | Watching claims | Tasks due |")
    lines.append("|---|---|---|---|---|")
    for proj in active:
        points = proj.get("metrics", {}).get("points")
        points_str = str(points) if points is not None else "—"
        due_n = sum(1 for t in proj.get("tasks", []) if task_is_due(t, today))
        claims_n = sum(1 for c in proj.get("claims", []) if c.get("status") == "watching")
        lines.append(f"| {proj.get('id')} | {proj.get('status')} | {points_str} | {claims_n} | {due_n} |")
    lines.append("")
    for proj in active:
        lines.append(f"## {proj.get('name', proj.get('id'))} ({proj.get('id')})")
        lines.append("")
        lines.append(f"**Category:** {proj.get('category')} · **URL:** {proj.get('urls', {}).get('main', '')}")
        due = [t for t in proj.get("tasks", []) if task_is_due(t, today)]
        if due:
            lines.append("")
            lines.append("**Due tasks:**")
            for t in due:
                last = iso_date_only(t.get("last_done")) if t.get("last_done") else "never"
                lines.append(f"- `{t['id']}` — {t.get('title') or t['id']} ({t.get('repeat')}, last: {last}, streak: {t.get('streak') or 0})")
        claims = proj.get("claims", [])
        open_claims = [c for c in claims if c.get("status") in ("watching", "claimable")]
        if open_claims:
            lines.append("")
            lines.append("**Open claims:**")
            for c in open_claims:
                d = days_until(c.get("deadline"), today)
                urgency = ""
                if d is not None:
                    if d < 0:
                        urgency = " (⚠️ deadline passed)"
                    elif d <= 7:
                        urgency = f" (⚠️ {d}d left)"
                lines.append(f"- `{c['id']}` — {c.get('label') or c['id']} [{c.get('status')}]{urgency}")
        if proj.get("notes"):
            lines.append("")
            lines.append(f"Notes: {proj.get('notes')}")
        lines.append("")
    text = "\n".join(lines)

    if args.stdout:
        print(text)
        return
    out_path = data_dir / "reports" / f"{today.strftime('%Y-%m-%d-%H%M')}.md"
    write_text_atomic(out_path, text)
    print(out_path)


# ---------------------------------------------------------------- argparser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="registry.py", description="airdrop-hunter registry helpers")
    parser.add_argument("--data-dir", help="override data dir (default: $AIRDROP_HUNTER_DATA_DIR or ~/.hermes/airdrop-hunter)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create data dir + empty registry")
    p.add_argument("--force", action="store_true", help="overwrite existing registry")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("validate", help="schema-check the registry")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("add", help="register a project")
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--status", default="active", choices=sorted(VALID_STATUSES))
    p.add_argument("--category", default="other", choices=sorted(VALID_CATEGORIES))
    p.add_argument("--main-url", required=True)
    p.add_argument("--task-url")
    p.add_argument("--claim-url")
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get")
    p.add_argument("id")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("task-add")
    p.add_argument("id", help="project id")
    p.add_argument("task_id")
    p.add_argument("--type", required=True, choices=sorted(VALID_TASK_TYPES))
    p.add_argument("--repeat", default="none", choices=sorted(VALID_REPEATS))
    p.add_argument("--title", default="")
    p.add_argument("--url", default="")
    p.set_defaults(func=cmd_task_add)

    p = sub.add_parser("task-done")
    p.add_argument("id", help="project id")
    p.add_argument("task_id")
    p.add_argument("--unset", action="store_true", help="clear last_done/streak instead")
    p.set_defaults(func=cmd_task_done)

    p = sub.add_parser("claim-set")
    p.add_argument("id", help="project id")
    p.add_argument("claim_id")
    p.add_argument("--status", required=True, choices=sorted(VALID_CLAIM_STATUSES))
    p.add_argument("--deadline", help="ISO timestamp or date, e.g. 2026-12-01")
    p.add_argument("--amount-hint")
    p.set_defaults(func=cmd_claim_set)

    p = sub.add_parser("due", help="list tasks that are due today")
    p.set_defaults(func=cmd_due)

    p = sub.add_parser("report", help="generate the recap markdown report")
    p.add_argument("--stdout", action="store_true", help="print report instead of saving to reports/")
    p.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()