# Task Catalog — airdrop task patterns and how to automate them

Airdrop work breaks into a small set of repeating patterns. Use this catalog to
know *what* to do on a page and *when to stop and hand back to the user*.

Automation budget: each task gets **one** `browser_exec` call with a single
`wait_for_load` + snapshot, then at most a couple of targeted clicks. Do not
retry the same click more than twice. If the page structure doesn't match
after two attempts → stop, screenshot, tell the user in chat.

## 1. Daily check-in (category `points`, `testnet`, `galxe`, `meme`)

Pattern: logged-in page with a "Check-in", "Daily", "Claim", "签到", or
"Streak" button. Sometimes hidden behind a sidebar > "Quests"/"Rewards".

Procedure:
1. `browser_exec` (session `airdrop`) → `goto_url` task URL → `wait_for_load` → `page_info` + `capture_screenshot`.
2. Look at the visible text: find a button whose label matches `task.title` or one of the labels above, and note the streak counter if one is shown ("Day 12").
3. Click it once; snapshot again to confirm the counter incremented or a toast ("Claimed!") appeared.
4. On success run `registry.py task-done <project> <task-id>` (it sets `last_done` + streak).
5. On failure: button missing → check `notes` for timing quirks, else mark the page as changed and report; CAPTCHA/Cloudflare → stop, screenshot, report (no bypass attempts).

## 2. Trading/volume tasks (`testnet`, `points`, `exchange`)

Pattern: "swap", "bridge", "deposit", "mint", "add liquidity" with a finite
amount to complete. These **require wallet signatures**.

Procedure:
1. Check what the task needs (amount, asset, chain) — read `task.notes`, and the page via `web_extract`.
2. Open the page in the `airdrop` browser session and navigate to the exact action screen; click through to the point where clicking the final button would
   pop the wallet.
3. **Stop before any transaction is submitted.** Set a note (via `patch` on
   the registry or tell the user) "ready to sign — N tokens on Z chain" and mark
   the task as needing signature in your reply to the user.
4. Do not call `task-done` until the user confirms the tx was sent. When they
   say "done" → `task-done`.

## 3. Faucet tasks (`testnet`)

Pattern: paste address, solve captcha, request tokens, wait a cooldown.

- Address comes from the project's `wallets[].address` (watch-only).
- If CAPTCHA appears → stop and hand to the user (see guardrails). If the
  faucet uses a text input + button only, fill with `fill_input` and click; verify
  the success toast.

## 4. Social tasks (`galxe`, `social`)

Pattern: "follow on X", "join Discord/Telegram", "retweet", "visit page", "quiz".

- Visit-style, join-style, and quiz tasks are usually automatable in-browser.
- Follow/retweet via an X session inside the browser automate fine, but many
  social tasks need a *specific* X account to count — confirm which account the
  browser profile is logged into before doing them (check the avatar/URL bar).
- Quizzes: use `web_search` + `web_extract` for answers, still click the answers
  in-browser. Never copy-paste blind from a random "answer" site — cross-check
  two sources.

## 5. On-chain level-up tasks

Pattern: "hold X", "stake", "vote", "delegate".

- These are commitments, not clicks: record them as `milestone` tasks with a
  note, don't push values at the user. Put them in the recap so the user decides.

## 6. Claim (TGE / allocation / chest)

Pattern: a claim page with "Claim", "Check eligibility", or a connected-wallet
state. Details in the Chase procedure of SKILL.md.

## Button-finding tips (CDP via `browser_exec`)

- Use `capture_screenshot` and read the image before clicking — never click
  blind coordinates from memory.
- Prefer visible text and roles: scan `page_info`/`js` results for the label
  from `task.title` or the standard labels above; selectors found on the page
  are hints, not contracts.
- Element text changes between runs (languages, A/B tests). If the exact
  label isn't found, look for the nearest button inside a "quests"/"rewards"
  container.