# Daily Report Sender

Automatically email **each of the day's monitoring report PDFs** (web, email,
proxy, or any type you configure) to its **own list of people**, once every day.
Every report type gets a **separate email** whose subject and body name that
report type and your department. It is built to run unattended on a schedule
(via cron), but you can also run it by hand at any time.

If you are new to this project, read the sections in order. Every step has
copy-paste commands.

---

## Table of contents

1. [What it does](#1-what-it-does)
2. [How it works (the daily flow)](#2-how-it-works-the-daily-flow)
3. [Project layout](#3-project-layout)
4. [Requirements](#4-requirements)
5. [One-time setup](#5-one-time-setup)
6. [Configuration (`.env`)](#6-configuration-env)
7. [Running the application](#7-running-the-application)
8. [Testing — make sure it works](#8-testing--make-sure-it-works)
9. [Understanding the logs](#9-understanding-the-logs)
10. [Troubleshooting](#10-troubleshooting)
11. [Scheduling with cron (run daily at 12:30 PM)](#11-scheduling-with-cron-run-daily-at-1230-pm)

---

## 1. What it does

Once a day the tool:

1. Looks inside a folder you choose for **every PDF that was created today**.
2. Works out each file's **report type** from its name
   (`daily_<type>_report_<YYYY-MM-DD>.pdf` → e.g. `web`, `email`, `proxy`).
3. Checks that each PDF is really today's report:
   - the **filename contains today's date** (written as `YYYY-MM-DD`),
   - the file is a **genuine PDF** (not a renamed text file),
   - the file was **modified today** (not a leftover from a previous day).
4. For each valid report it sends a **separate email** to **that type's own
   recipients** (To / CC / BCC), using Gmail, with the PDF attached.
5. It **remembers per type** that it sent today, so it will not send a duplicate
   if it runs again the same day (but a report that arrives later in the day is
   still delivered).
6. Any PDF whose type is **not configured** is skipped; anything that fails is
   logged, and a **single alert email** to an admin address summarises every
   skipped/failed report — so a problem is never silent.

**Each email looks like this** (example for the proxy report):

- **Subject:** `TLSOC Daily Proxy Report - 2026-07-17` — where `TLSOC` is your
  configured `DEPARTMENT`, `Proxy` is the report type, and today's date is added
  automatically.
- **Body:** addressed to the team, naming the department and report type, e.g.
  "the TLSOC Proxy Monitoring Report for today … the current status of the
  monitored proxy assets …".
- **Attachment:** the validated PDF.

---

## 2. How it works (the daily flow)

```
START
  │
  ├─ Load settings from .env, check they are valid ──► invalid? log + STOP (exit 1)
  │
  ├─ Find ALL PDFs modified today in REPORT_DIR ──► none? log "nothing to do" + STOP (exit 0)
  │
  └─ For EACH of today's PDFs:
        ├─ Work out its type from the filename
        ├─ Type not configured?      ──► skip + add to alert summary
        ├─ Filename/PDF/mtime valid? ──► no? add to alert summary (this run will exit 1)
        ├─ Already sent this type today? (unless --force) ──► yes? skip
        └─ Send the email for this type (PDF attached) ──► failed? add to alert summary
                                                        └─ ok? record "sent today" for this type
  │
  ├─ If anything was skipped/failed ► send ONE admin alert summarising it
  └─ STOP: exit 1 if any report failed to validate/send, else exit 0  ✅
```

**Exit codes** (useful for cron and scripts):

| Code | Meaning |
|------|---------|
| `0`  | Success — all found reports sent (or already sent / nothing to do). Unconfigured files alone still exit `0` (they are only reported). |
| `1`  | Failure — bad config, or a report failed to validate/send, or a crash |

---

## 3. Project layout

```
Daily_Report_Sender/
├── report_sender.py     # Main program you run (the entry point)
├── config.py            # All settings + secrets, loaded from .env
├── file_checker.py      # Finds today's PDFs, reads each one's report type, validates
├── email_sender.py      # Builds and sends each email via Gmail
├── state_store.py       # Remembers, per report type, if it was already sent today
├── logger.py            # Logging to file + screen
├── requirements.txt     # Python packages needed
├── .env.example         # Template — copy this to .env and fill it in
├── .env                 # YOUR real settings + secrets (never shared/committed)
├── .gitignore
├── logs/                # sender.log lives here
├── state/               # last_sent_<type>.txt (the per-type "already sent" markers)
└── README.md            # This file
```

You normally only ever **run `report_sender.py`** and **edit `.env`**. The
other files are the building blocks it uses.

---

## 4. Requirements

- **Python 3.11 or newer.** Check with:
  ```bash
  python3 --version
  ```
- **A Gmail account** with:
  - **2-Step Verification** turned on, and
  - a **16-character App Password** (a normal Gmail password will **not** work
    for sending mail from a script).

  Create an App Password here: <https://myaccount.google.com/apppasswords>

---

## 5. One-time setup

Run these once on the machine where the tool will live.

```bash
# 1. Go to the project folder
cd /path/to/Daily_Report_Sender

# 2. Create an isolated Python environment (called a "virtual environment")
python3 -m venv .venv

# 3. Activate it (you must do this in every new terminal before running)
source .venv/bin/activate

# 4. Install the one dependency the project needs
pip install -r requirements.txt

# 5. Create your settings file from the template
cp .env.example .env
```

Now open `.env` in an editor and fill in your real values (next section).

> **What is the virtual environment (`.venv`)?** It is a private copy of Python
> for this project so its packages do not clash with the rest of the system.
> Whenever you open a new terminal to use the tool, run
> `source .venv/bin/activate` first. Your prompt will show `(.venv)`.

---

## 6. Configuration (`.env`)

All settings live in the `.env` file. It is **git-ignored**, so your password
is never committed or shared. Edit it with any text editor (e.g. `nano .env`).

| Variable            | What it is                                               | Example                                       |
|---------------------|---------------------------------------------------------|-----------------------------------------------|
| `REPORT_DIR`        | Folder to watch for the PDFs (**this is the key one**)  | `/opt/TLSOCDockerDeploy/reporting/output/pdf` |
| `LOG_LEVEL`         | How much detail to log: `DEBUG`/`INFO`/`WARNING`/`ERROR`| `INFO`                                        |
| `LOG_FILE`          | Where to write logs (relative = inside project)         | `logs/sender.log`                             |
| `STATE_FILE`        | Base path for the per-type "already sent" markers       | `state/last_sent.txt`                         |
| `SMTP_HOST`         | Mail server                                             | `smtp.gmail.com`                              |
| `SMTP_PORT`         | Mail server port                                        | `587`                                         |
| `SMTP_USER`         | **Secret** — your Gmail address                         | `you@gmail.com`                               |
| `SMTP_PASSWORD`     | **Secret** — your Gmail **App Password**                | `abcd efgh ijkl mnop`                         |
| `EMAIL_FROM`        | "From" address (leave blank to reuse `SMTP_USER`)       | `you@gmail.com`                               |
| `ALERT_EMAIL_TO`    | Who gets the alert if a run has skips/failures          | `admin@x.com`                                 |
| `DEPARTMENT`        | Name shown in every subject/body                        | `TLSOC`                                       |
| `REPORT_TYPES`      | Which report types to send (comma-separated)            | `web,email,proxy`                             |
| `EMAIL_TO_<TYPE>`   | **To** recipients for one type (`<TYPE>` uppercased)    | `EMAIL_TO_WEB=web-team@x.com`                 |
| `EMAIL_CC_<TYPE>`   | **CC** recipients for that type (optional)              | `EMAIL_CC_WEB=boss@x.com`                     |
| `EMAIL_BCC_<TYPE>`  | **BCC** recipients for that type (optional, hidden)     | `EMAIL_BCC_WEB=audit@x.com`                   |

**How report types and recipients fit together:**
- Each type in `REPORT_TYPES` maps to a file named
  `daily_<type>_report_<YYYY-MM-DD>.pdf` in `REPORT_DIR`, and to its own
  `EMAIL_TO_<TYPE>` / `EMAIL_CC_<TYPE>` / `EMAIL_BCC_<TYPE>` recipients.
  For example, `proxy` uses the file `daily_proxy_report_<today>.pdf` and the
  `EMAIL_*_PROXY` recipients.
- **To add a new report type**, add it to `REPORT_TYPES` and add its
  `EMAIL_TO_<TYPE>` line (e.g. `dns` → `REPORT_TYPES=web,email,proxy,dns` plus
  `EMAIL_TO_DNS=...`). No code changes needed.
- Every declared type must have at least one recipient, or the config is
  rejected at startup.
- For **multiple recipients**, separate them with commas:
  `EMAIL_TO_WEB=alice@x.com,bob@y.com`. CC/BCC may be left empty.
- A PDF whose type is **not** in `REPORT_TYPES` is skipped and named in the
  admin alert.

---

## 7. Running the application

Always activate the environment first:

```bash
cd /path/to/Daily_Report_Sender
source .venv/bin/activate
```

Then:

```bash
# Normal run — this is exactly what the daily schedule does
python report_sender.py

# Dry run — does everything EXCEPT actually sending. Safe to test config.
python report_sender.py --dry-run

# Force a send even if today's report was already sent
python report_sender.py --force

# Use a different folder just for this one run
REPORT_DIR=/some/other/folder python report_sender.py
```

After any run, check the result:
```bash
echo $?                       # 0 = success, 1 = failure
tail -n 30 logs/sender.log    # see what happened
```

---

## 8. Testing — make sure it works

This section gives you safe, repeatable tests. Start with the dry run (sends
nothing), then do a real send, then test the duplicate-protection.

### Test 0 — Is the configuration valid?

```bash
source .venv/bin/activate
python -c "import config; p = config.validate_config(); print('Problems:', p or 'NONE — config is valid')"
```
**Expected:** `Problems: NONE — config is valid`. If it lists problems (e.g.
missing password or recipients), fix them in `.env` and run again.

### Test 1 — Dry run (no email sent)

Create a sample PDF **per report type** for today and point the tool at them:

```bash
# Make a temporary test folder + one valid PDF per configured type (today's date)
mkdir -p /tmp/report_test
for t in web email proxy; do
  printf '%%PDF-1.7\nSample %s report.\n%%%%EOF\n' "$t" \
    > /tmp/report_test/daily_${t}_report_$(date +%F).pdf
done

# Dry run against that folder
REPORT_DIR=/tmp/report_test python report_sender.py --dry-run
```
**Expected (in the log):**
- `Found 3 PDF file(s) modified today (<today>)`
- for each type: `Filename date matches today`, `Confirmed PDF signature`,
  `File modification date matches today`
- `[DRY-RUN] Would send '<DEPARTMENT> Daily Web Report - <today>' ... to N recipient(s)`
  (and the same for Email and Proxy, each to its own recipients)
- `Run summary: 3 sent, 0 skipped ...` → `Daily Report Sender finished`

No email is sent. This proves the whole pipeline and your per-type recipient
lists are correct.

### Test 2 — Real send (real emails go out)

```bash
rm -f state/last_sent_*.txt      # clear today's markers so it will actually send
REPORT_DIR=/tmp/report_test python report_sender.py
echo "exit: $?"
```
**Expected:** one `Email sent to N recipient(s).` per report type and exit `0`.
Check each type's recipients' inboxes (and spam) for the email with the PDF
attached.

### Test 3 — Duplicate protection (it should NOT send twice)

Right after Test 2 succeeded, run it again **without** `--force`:

```bash
REPORT_DIR=/tmp/report_test python report_sender.py
echo "exit: $?"
```
**Expected:** `'web' report already sent today ...` (and email, proxy) →
`Run summary: 0 sent, 3 skipped ...`, exit `0`, **no email**. This is the safety
net that prevents duplicate emails, tracked per type.

### Test 4 — Force a resend

```bash
REPORT_DIR=/tmp/report_test python report_sender.py --force
```
**Expected:** it sends again (a fresh email per type arrives). Use this when you
deliberately want to re-send.

### Test 5 — Unknown / bad files

```bash
# An unconfigured type: skipped and reported in the admin alert (still exit 0)
printf '%%PDF-1.7\n%%%%EOF\n' > /tmp/report_test/daily_dns_report_$(date +%F).pdf
# A configured type that is NOT a real PDF: validation fails (exit 1)
printf 'not a pdf\n' > /tmp/report_test/daily_web_report_$(date +%F).pdf
rm -f state/last_sent_*.txt
REPORT_DIR=/tmp/report_test python report_sender.py
echo "exit: $?"
```
**Expected:** the `dns` file is skipped ("unrecognized/unconfigured"), the
invalid `web` file fails content validation, a **single alert email** to
`ALERT_EMAIL_TO` summarises both, and the exit code is `1` (because a configured
report failed to validate).

### Test 6 (developers) — automated unit tests

If you have the dev tools installed (`pip install -r requirements-dev.txt`),
run the full test suite:

```bash
python -m pytest
```
**Expected:** all tests pass. These use temporary folders and a fake SMTP, so
**no real email is ever sent** and your real `REPORT_DIR` is never touched.

### Clean up after testing

```bash
rm -rf /tmp/report_test
rm -f state/last_sent_*.txt       # optional: allow a fresh real send today
```

### Bonus — Watch a folder live (for interactive testing)

Run the tool in a loop so it sends as soon as you drop a valid PDF in:

```bash
source .venv/bin/activate
mkdir -p /home/pranjaltiwari/Documents/testing
rm -f state/last_sent_*.txt

while true; do
  REPORT_DIR=/home/pranjaltiwari/Documents/testing python report_sender.py
  sleep 15
done
```
In another terminal, drop a sample PDF (named for a configured type):
```bash
printf '%%PDF-1.7\nLive test.\n%%%%EOF\n' \
  > /home/pranjaltiwari/Documents/testing/daily_web_report_$(date +%F).pdf
```
It sends that type once within ~15 seconds, then skips it. Press **Ctrl+C** to
stop.
> Tip: an empty folder just logs "nothing to do" (no alert). An **unconfigured**
> file, however, triggers an alert every cycle — remove it or add its type.

---

## 9. Understanding the logs

- Logs go to **`logs/sender.log`** *and* to the screen.
- The file **rotates automatically** (about 1 MB per file, 5 backups kept), so
  it never fills the disk.
- See more detail by setting `LOG_LEVEL=DEBUG` in `.env`.

Handy commands:
```bash
tail -n 50 logs/sender.log       # last 50 lines
tail -f logs/sender.log          # watch live (Ctrl+C to stop)
grep ERROR logs/sender.log       # only errors
```

### Sample `logs/sender.log` output

Each line is: `timestamp | LEVEL | module | message`.

**A successful run** (multiple types found, validated, emailed, recorded):
```
2026-07-17 13:58:30 | INFO     | __main__     | === Daily Report Sender starting (Phase 13) ===
2026-07-17 13:58:30 | INFO     | __main__     | Department: TLSOC
2026-07-17 13:58:30 | INFO     | __main__     | Report types: web, email, proxy
2026-07-17 13:58:30 | INFO     | __main__     | Monitored report directory: /opt/TLSOCDockerDeploy/reporting/output/pdf
2026-07-17 13:58:30 | INFO     | file_checker | Found 2 PDF file(s) modified today (2026-07-17) in /opt/TLSOCDockerDeploy/reporting/output/pdf
2026-07-17 13:58:30 | INFO     | file_checker | Confirmed PDF signature: .../daily_proxy_report_2026-07-17.pdf
2026-07-17 13:58:34 | INFO     | email_sender | Email sent to 1 recipient(s).
2026-07-17 13:58:34 | INFO     | state_store  | Recorded successful send of 'proxy' for 2026-07-17 in .../state/last_sent_proxy.txt.
2026-07-17 13:58:34 | INFO     | __main__     | Sent 'proxy' report: daily_proxy_report_2026-07-17.pdf
2026-07-17 13:58:38 | INFO     | email_sender | Email sent to 2 recipient(s).
2026-07-17 13:58:38 | INFO     | __main__     | Sent 'web' report: daily_web_report_2026-07-17.pdf
2026-07-17 13:58:38 | INFO     | __main__     | Run summary: 2 sent, 0 skipped (already sent), 0 problem(s).
2026-07-17 13:58:38 | INFO     | __main__     | === Daily Report Sender finished ===
```

**An already-sent run** (per-type duplicate protection — no email):
```
2026-07-17 14:01:24 | INFO     | __main__     | === Daily Report Sender starting (Phase 13) ===
2026-07-17 14:01:24 | INFO     | file_checker | Found 2 PDF file(s) modified today (2026-07-17) in ...
2026-07-17 14:01:24 | INFO     | state_store  | 'proxy' report already sent today (2026-07-17) — recorded in .../state/last_sent_proxy.txt.
2026-07-17 14:01:24 | INFO     | __main__     | Skipping 'proxy' — already sent today (daily_proxy_report_2026-07-17.pdf).
2026-07-17 14:01:24 | INFO     | __main__     | Run summary: 0 sent, 2 skipped (already sent), 0 problem(s).
```

**A run with problems** (unknown type + a bad PDF — one consolidated alert):
```
2026-07-17 09:15:02 | INFO     | __main__     | === Daily Report Sender starting (Phase 13) ===
2026-07-17 09:15:02 | WARNING  | __main__     | Skipped unrecognized/unconfigured report daily_dns_report_2026-07-17.pdf (type 'dns' not in REPORT_TYPES).
2026-07-17 09:15:02 | ERROR    | __main__     | PDF content validation failed for daily_web_report_2026-07-17.pdf.
2026-07-17 09:15:02 | INFO     | __main__     | Run summary: 0 sent, 0 skipped (already sent), 2 problem(s).
2026-07-17 09:15:06 | INFO     | email_sender | Email sent to 1 recipient(s).
```

> In the last example the final "Email sent" line is the single **alert** going
> to `ALERT_EMAIL_TO`, summarising both problems — not a report.

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `Problems: ... SMTP_PASSWORD is not set` | Fill `SMTP_PASSWORD` in `.env` with your **App Password** (not your normal password). |
| `Problems: Report type 'X' has no recipients` | Add `EMAIL_TO_X=...` (uppercased) in `.env`, or remove `X` from `REPORT_TYPES`. |
| `Username and Password not accepted` | You used your normal Gmail password. Create an **App Password** and use that. |
| `Nothing to do — no report PDFs modified today` | `REPORT_DIR` is wrong/empty, or no PDF in it was modified today. |
| `Skipped unrecognized/unconfigured report ...` | The file's type isn't in `REPORT_TYPES`, or its name isn't `daily_<type>_report_<date>.pdf`. Add the type, or fix the name. |
| `Filename date(s) ... do not match today` | The PDF name does not contain today's date (`YYYY-MM-DD`). |
| `File is not a valid PDF` | The file is not a real PDF (e.g. a renamed text file). |
| `File modification date ... is not today` | The file is old. Re-create it today, or run `touch yourfile.pdf`. |
| It says a type is "already sent today" but I want to resend | Use `--force`, or `rm -f state/last_sent_<type>.txt`. |
| Nothing happens when cron should run | See the cron section below (paths, timezone). |

---

## 11. Scheduling with cron (run daily at 12:30 PM)

Cron is the Linux service that runs commands on a schedule. The important thing
to know: **cron runs with a bare environment** — no activated virtual
environment and a minimal `PATH`. So we must use **full, absolute paths** to
both the Python inside `.venv` and the script.

### Step 1 — Find your absolute paths

```bash
cd /path/to/Daily_Report_Sender
APP_DIR=$(pwd)
ls "$APP_DIR/.venv/bin/python"     # make sure this file exists
```

### Step 2 — Build the cron line

```bash
echo "30 12 * * * cd $APP_DIR && $APP_DIR/.venv/bin/python report_sender.py >> $APP_DIR/logs/cron.log 2>&1"
```

Copy the line it prints. Here is what each part means:

```
30 12 * * *   cd /app && /app/.venv/bin/python report_sender.py >> /app/logs/cron.log 2>&1
│  │  │ │ │   └────────────────────────── the command cron will run ──────────────────────┘
│  │  │ │ └── day of week (any)
│  │  │ └──── month (any)
│  │  └────── day of month (any)
│  └───────── hour  = 12  (afternoon)
└──────────── minute = 30
            → "at 12:30 PM, every day"
```

- `>> logs/cron.log 2>&1` saves any screen output/errors as a backstop. Your
  normal logs still go to `logs/sender.log`.

### Step 3 — Install the cron job

```bash
crontab -e
```
Paste the line, then save and exit. Confirm it is installed:
```bash
crontab -l
```

> **One-line install** (run only once, or you will get duplicates):
> ```bash
> ( crontab -l 2>/dev/null; echo "30 12 * * * cd $APP_DIR && $APP_DIR/.venv/bin/python report_sender.py >> $APP_DIR/logs/cron.log 2>&1" ) | crontab -
> ```

### Step 4 — Check the server's timezone

Cron fires at **12:30 in the server's local time**, and the tool's "today"
check uses the same clock, so they always agree. Just confirm the timezone:
```bash
timedatectl        # look at "Time zone"
date               # current server time
```
If the server is in UTC but you want local time, either change the hour in the
cron line or set the server timezone.

### Step 5 — Test the cron command now (don't wait for 12:30)

Run it exactly the way cron will — with an empty environment — to catch any
path problems before the real schedule:

```bash
cd $APP_DIR
rm -f state/last_sent_*.txt    # so it isn't skipped by today's markers
env -i /bin/bash -c "cd $APP_DIR && $APP_DIR/.venv/bin/python report_sender.py >> $APP_DIR/logs/cron.log 2>&1"
echo "exit: $?"
tail -n 30 logs/cron.log
```
If this sends the email and exits `0`, the scheduled run will too.

### Step 6 (optional) — Prove the schedule fires

Temporarily set the time a few minutes ahead (e.g. `36 14 * * *` for 2:36 PM),
wait for it, then check:
```bash
tail -n 20 logs/sender.log
```
Once you see it triggered on time, change the line back to `30 12 * * *`.

### Removing or changing the schedule

```bash
crontab -e         # edit the line, or delete it, then save
crontab -r         # remove ALL cron jobs for this user (careful!)
```

---

## Security notes

- Secrets live **only** in `.env`, which is git-ignored. Never commit or email
  it.
- The App Password is never written to the logs.
- `logs/` and `state/` keep only a placeholder in version control; their actual
  contents are ignored.

---

**That's it.** For day-to-day use you only need:
```bash
cd /path/to/Daily_Report_Sender && source .venv/bin/activate
python report_sender.py
```
…and cron does it for you automatically at 12:30 PM every day.
