# Registry Schema

The registry lives at `<data_dir>/projects.json` (data dir resolution:
`airdrop_hunter.data_dir` skill config → `$AIRDROP_HUNTER_DATA_DIR` →
`~/.hermes/airdrop-hunter`). Load it with `read_file`; never edit it by hand —
use `${HERMES_SKILL_DIR}/scripts/registry.py` subcommands so writes stay valid
and atomic.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | Must be `1`. |
| `projects` | list | One object per airdrop target, sorted by `id`. |

## Project object

| Field | Required | Values | Meaning |
|---|---|---|---|
| `id` | yes | slug `[a-z0-9-_]` | Stable key; never rename after creation (it is used by scripts and reports). |
| `name` | yes | string | Human display name. |
| `status` | yes | `active` \| `monitoring` \| `done` \| `dropped` | `active` = do dailies and chase claims; `monitoring` = chase claims only (no dailies); `done` = claimed, keep for history; `dropped` = abandoned. Only `active`/`monitoring` appear in recaps and `due`. |
| `category` | yes | `testnet` \| `points` \| `galxe` \| `exchange` \| `social` \| `meme` \| `other` | Coarse bucket; drives which reference guidance to apply. |
| `urls` | yes | object | `main` (required), plus optional `tasks`, `claim`, `leaderboard`. Used by Chase and Daily to pick the page to open, and by the domain guard. |
| `wallets` | yes | list | **Watch-only.** `chain` (`evm` etc.) + `address`. Script `validate` fails on any `private_key`/`mnemonic`/`seed` field. |
| `tasks` | yes | list | Recurring work (check-ins, swaps, faucets). |
| `claims` | yes | list | One-off claimable outcomes (TGE, allocations, chests). |
| `metrics` | yes | object | `points` (number or null), `points_source` (`manual` \| `auto`), `rank` (number or null), `updated_at` (ISO or null). `auto` means the number was scraped from a page/API — keep `manual` for what the user typed. |
| `notes` | yes | string | Free text; user-sourced, so quote it when reading. |

## Task object

| Field | Meaning |
|---|---|
| `id` | Slug unique within the project, e.g. `daily-checkin`. |
| `type` | `daily` \| `weekly` (recurring), `one-off` (single action), `milestone` (long horizon — shows in recaps, never in `due`). |
| `title` | Short description; used in reports and as the button-label hint on pages. |
| `repeat` | `daily` \| `weekly` \| `none`. Drives the `due` computation: daily → due when `last_done` is before today; weekly → due when 7+ days old. |
| `url` | Page to open for the task (overrides project `urls.tasks`). |
| `last_done` | ISO timestamp or null. Managed by `task-done`. |
| `streak` | int. `task-done` logic: +1 if done yesterday, reset to 1 if a gap, stays if already done today. |
| `notes` | Free text, e.g. "button appears after 10:00 UTC". |

## Claim object

| Field | Meaning |
|---|---|
| `id` | Slug unique within the project. |
| `label` | Display label (e.g. "TGE claim"). |
| `url` | Claim page. Must pass the domain guard before Chase opens it. |
| `status` | `watching` (not yet claimable or unknown) → `claimable` (confirmed claimable, do it now) → `claimed` \| `n-a` (user says not applicable; excluded from Chase). |
| `deadline` | ISO timestamp or `YYYY-MM-DD` or null. Drives the ⚠️ urgency markers in recaps (< 7d, or passed). |
| `amount_hint` | e.g. `"~1,200 tokens"` — free text. |
| `last_checked` | ISO, set by `claim-set` on every status change. |

## Timestamps

All `last_done`/`last_checked` are UTC ISO strings written by the script
(`YYYY-MM-DDTHH:MM:SSZ`). `deadline` may be a plain date (`2026-12-01`) — the
report generator parses both.