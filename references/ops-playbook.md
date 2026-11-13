# Ops Playbook — runtime setup, cron, and escalations

One-time setup the user needs before Daily/Chase can run fully autonomous.
Walk them through these BEFORE doing browser automation, and verify each step
instead of assuming it is done.

## 1. Persistent browser profile (required for full-auto)

Hermes' default browser is throwaway — logins are gone between sessions.
Auto mode needs one of:

- **Best:** `browser.user_data_dir` set in `~/.hermes/config.yaml`. Create the
  profile with `hermes chat`, open the browser, and have the USER log in to the
  sites (X, Discord, Galxe, the project dashboards) once. Then make sure
  `browser.user_data_dir` points at that directory so cookies persist.
- **Alternative:** a real browser profile (`/browser connect` to the user's
  Chrome/Brave/Edge). Remind them this runs in *their* logged-in browser.
- Wallet extension: do NOT try to operate it. Wallet approvals are always
  manual (see guardrails). Chrome profiles still let dapp pages "Connect
  Wallet" remember the connection, which is fine — signature clicks stay with
  the user.

Check before starting a run: navigate to one project URL and verify the page
is logged in (look for the account avatar / missing "Connect" button).

## 2. Skill config (optional)

`airdrop_hunter.data_dir` (default `~/.hermes/airdrop-hunter`),
`airdrop_hunter.auto_click` (default `"true"` — set `"false"` to switch the
whole skill to prepare-and-confirm mode), `airdrop_hunter.report_deliver`
(default `origin`).

Set via `hermes config set skills.airdrop_hunter.auto_click "false"` or
`hermes config edit`.

## 3. Daily schedule

Recommended (in-chat or CLI):

```
hermes cron create "every day at 09:00" "Run the airdrop-hunter Daily routine for all active projects, then deliver the recap. Report any CAPTCHA or signature-needed items clearly." --skill airdrop-hunter --deliver origin
```

- Output lander: `~/.hermes/cron/output/<job_id>/<timestamp>.md`; delivery
  target `origin` replies in the origin chat, `telegram`/`discord`/… need those
  gateways configured first.
- The skill also ships a `blueprint` (frontmatter) — after install it shows up
  under `/suggestions`; accepting creates the cron job. Installing the skill
  never auto-schedules anything.
- Weekly review cadence suggestion: a second cron, "every monday at 09:00",
  prompting a recap + "mark stale projects done/dropped".

## 4. Escalations

| Situation | Action |
|---|---|
| CAPTCHA / Cloudflare challenge on a page | Stop the task, `capture_screenshot`, tell the user; leave `last_done` unchanged. Do not attempt bypasses. |
| Task needs a wallet signature | Prepare the page up to the final button, then stop and ask the user; only call `task-done` after they confirm the tx. |
| Anti-bot page / account locked warning | Stop ALL automation on that project immediately, notify the user, pause the project's dailies (suggest the user sets `status: monitoring` until they clear it). |
| Page structure changed and the button isn't findable | One retry with a different selector strategy, then stop; report what you saw (screenshot) so the skill can be updated later. |
| Claim URL domain doesn't match the project's `urls.main` domain | Never click. Show both domains to the user; proceed only if they confirm. |
| Double-check-in risk (task already shows today's check-in done) | Call `task-done` anyway — the script detects same-day and won't inflate the streak. |

## 5. Hygiene

- Registry is the source of truth: every successful/failed run ends with the
  right `registry.py` call so recaps stay accurate.
- After each daily run, glance at `registry.py validate` — it will flag
  accidental edits or a stray secret field (e.g. if something pasted a private
  key into notes, remove and warn the user).
- Keep `notes` fields updated when timing quirks are discovered
  ("check-in unlocks after 10:00 UTC") — that's the skill's self-improvement
  loop.