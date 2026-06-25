# Daily Report Sender

Automatically email the day's **ASC Web Monitoring Report** (a PDF file) to a
list of people, once every day. It is built to run unattended on a schedule
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

1. Looks inside a folder you choose for the **newest PDF**.
2. Checks that the PDF is really today's report:
   - the **filename contains today's date** (written as `YYYY-MM-DD`),
   - the file is a **genuine PDF** (not a renamed text file),
   - the file was **modified today** (not a leftover from a previous day).
3. If everything checks out, it **emails the PDF** as an attachment to your
   **To / CC / BCC** recipients using Gmail.
4. It **remembers** that it sent today, so it will not send a duplicate if it
   runs again the same day.
5. If anything goes wrong, it **writes an error to the log** and sends an
   **alert email** to an admin address, so a failure is never silent.

**The email looks like this:**

- **Subject:** `ASC Web Monitoring Report - 2026-06-25` (today's date is added
  automatically)
- **Body:**
  ```
  Hello Team,

  This is your ASC Web Monitoring Report for today.
  For any further details, kindly contact the TLSOC team.
  Regards,
  Team TLSOC
  ```
- **Attachment:** the validated PDF.

---

## 2. How it works (the daily flow)

```
START
  │
  ├─ Load settings from .env, check they are valid ──► invalid? log + STOP (exit 1)
  │
  ├─ Already sent today? ──► yes ► log "nothing to do" + STOP (exit 0)
  │
  ├─ Find the newest PDF in REPORT_DIR ──► none? alert + STOP (exit 1)
  │
  ├─ Filename contains today's date? ──► no? alert + STOP (exit 1)
  ├─ File is a real PDF (%PDF- header)? ──► no? alert + STOP (exit 1)
  ├─ File modified today? ──► no? alert + STOP (exit 1)
  │
  ├─ Send the email (PDF attached) ──► failed? alert + STOP (exit 1)
  │
  └─ Record "sent today" + STOP (exit 0)  ✅
```

**Exit codes** (useful for cron and scripts):

| Code | Meaning |
|------|---------|
| `0`  | Success — sent, or already sent earlier today (nothing to do) |
| `1`  | Failure — bad config, no valid report, send error, or crash |

---

## 3. Project layout

```
Daily_Report_Sender/
├── report_sender.py     # Main program you run (the entry point)
├── config.py            # All settings + secrets, loaded from .env
├── file_checker.py      # Finds the newest PDF and validates it
├── email_sender.py      # Builds and sends the email via Gmail
├── state_store.py       # Remembers if today's report was already sent
├── logger.py            # Logging to file + screen
├── requirements.txt     # Python packages needed
├── .env.example         # Template — copy this to .env and fill it in
├── .env                 # YOUR real settings + secrets (never shared/committed)
├── .gitignore
├── logs/                # sender.log lives here
├── state/               # last_sent.txt (the "already sent today" marker)
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

| Variable         | What it is                                            | Example                                       |
|------------------|-------------------------------------------------------|-----------------------------------------------|
| `REPORT_DIR`     | Folder to watch for the PDF (**this is the key one**) | `/opt/TLSOCDockerDeploy/reporting/output/pdf` |
| `LOG_LEVEL`      | How much detail to log: `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO`                                     |
| `LOG_FILE`       | Where to write logs (relative = inside project)       | `logs/sender.log`                             |
| `STATE_FILE`     | Where the "already sent today" marker is stored       | `state/last_sent.txt`                         |
| `SMTP_HOST`      | Mail server                                           | `smtp.gmail.com`                              |
| `SMTP_PORT`      | Mail server port                                      | `587`                                         |
| `SMTP_USER`      | **Secret** — your Gmail address                       | `you@gmail.com`                               |
| `SMTP_PASSWORD`  | **Secret** — your Gmail **App Password**              | `abcd efgh ijkl mnop`                         |
| `EMAIL_FROM`     | "From" address (leave blank to reuse `SMTP_USER`)     | `you@gmail.com`                               |
| `EMAIL_TO`       | Recipients, separated by commas                       | `alice@x.com,bob@y.com`                       |
| `EMAIL_CC`       | CC recipients (optional)                              | `boss@x.com`                                  |
| `EMAIL_BCC`      | BCC recipients (optional, hidden from others)         | `audit@x.com`                                 |
| `ALERT_EMAIL_TO` | Who gets an email if a run **fails**                  | `admin@x.com`                                 |
| `EMAIL_SUBJECT`  | Subject text (today's date is added automatically)    | `ASC Web Monitoring Report`                   |

**Notes:**
- For **multiple recipients**, separate them with commas:
  `EMAIL_TO=alice@x.com,bob@y.com,carol@z.com`
- `EMAIL_CC` and `EMAIL_BCC` can be left empty.
- The accepted PDF filename only needs to **contain today's date**, e.g.
  `web_report_2026-06-25.pdf`, `report_2026-06-25_final.pdf`, or even
  `2026-06-25.pdf`.

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

Create a sample PDF for today and point the tool at it:

```bash
# Make a temporary test folder + a valid sample PDF named with today's date
mkdir -p /tmp/report_test
printf '%%PDF-1.7\nSample report body.\n%%%%EOF\n' > /tmp/report_test/web_report_$(date +%F).pdf

# Dry run against that folder
REPORT_DIR=/tmp/report_test python report_sender.py --dry-run
```
**Expected (in the log):**
- `Latest PDF found: .../web_report_<today>.pdf`
- `Filename date matches today`
- `Confirmed PDF signature`
- `File modification date matches today`
- `[DRY-RUN] Would send 'ASC Web Monitoring Report - <today>' ... to N recipient(s)`
- `finished successfully`

No email is sent. This proves the whole pipeline and your recipient list are
correct.

### Test 2 — Real send (a real email goes out)

```bash
rm -f state/last_sent.txt        # clear today's marker so it will actually send
REPORT_DIR=/tmp/report_test python report_sender.py
echo "exit: $?"
```
**Expected:** ends with `Email sent to N recipient(s).` and
`finished successfully`, exit `0`. Check the recipients' inboxes (and spam) for
the email with the PDF attached.

### Test 3 — Duplicate protection (it should NOT send twice)

Right after Test 2 succeeded, run it again **without** `--force`:

```bash
REPORT_DIR=/tmp/report_test python report_sender.py
echo "exit: $?"
```
**Expected:** `Report already sent today ...` → `Nothing to do — today's report
was already sent.`, exit `0`, **no email**. This is the safety net that
prevents duplicate emails.

### Test 4 — Force a resend

```bash
REPORT_DIR=/tmp/report_test python report_sender.py --force
```
**Expected:** it sends again (a second email arrives). Use this when you
deliberately want to re-send.

### Test 5 — A bad/old file is rejected

```bash
# A file with YESTERDAY's date in the name should be refused
touch /tmp/report_test/web_report_$(date -d yesterday +%F).pdf
rm -f /tmp/report_test/web_report_$(date +%F).pdf
rm -f state/last_sent.txt
REPORT_DIR=/tmp/report_test python report_sender.py
echo "exit: $?"
```
**Expected:** validation fails (date does not match today), an **alert email**
is sent to `ALERT_EMAIL_TO`, exit `1`.

### Clean up after testing

```bash
rm -rf /tmp/report_test
rm -f state/last_sent.txt        # optional: allow a fresh real send today
```

### Bonus — Watch a folder live (for interactive testing)

Run the tool in a loop so it sends as soon as you drop a valid PDF in:

```bash
source .venv/bin/activate
mkdir -p /home/pranjaltiwari/Documents/testing
rm -f state/last_sent.txt

while true; do
  REPORT_DIR=/home/pranjaltiwari/Documents/testing python report_sender.py
  sleep 15
done
```
In another terminal, drop a sample PDF:
```bash
printf '%%PDF-1.7\nLive test.\n%%%%EOF\n' \
  > /home/pranjaltiwari/Documents/testing/web_report_$(date +%F).pdf
```
It sends once within ~15 seconds, then skips. Press **Ctrl+C** to stop.
> Tip: put the PDF in **before** starting the loop, otherwise every empty cycle
> sends a failure alert email.

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

**A successful send** (the happy path — found, validated, emailed, recorded):
```
2026-06-25 13:58:30 | INFO     | __main__     | === Daily Report Sender starting (Phase 7) ===
2026-06-25 13:58:30 | INFO     | __main__     | Monitored report directory: /home/pranjaltiwari/Documents/testing
2026-06-25 13:58:30 | INFO     | __main__     | Log level: INFO
2026-06-25 13:58:30 | INFO     | __main__     | Log file: /home/pranjaltiwari/Desktop/Daily_Report_Sender/logs/sender.log
2026-06-25 13:58:30 | INFO     | file_checker | Latest PDF found: /home/pranjaltiwari/Documents/testing/web_report_2026-06-25.pdf (out of 1 PDF file(s))
2026-06-25 13:58:30 | INFO     | file_checker | Filename date matches today (2026-06-25): web_report_2026-06-25.pdf
2026-06-25 13:58:30 | INFO     | file_checker | Confirmed PDF signature: /home/pranjaltiwari/Documents/testing/web_report_2026-06-25.pdf
2026-06-25 13:58:30 | INFO     | file_checker | File modification date matches today (2026-06-25): /home/pranjaltiwari/Documents/testing/web_report_2026-06-25.pdf
2026-06-25 13:58:30 | INFO     | __main__     | Validated report ready to send: /home/pranjaltiwari/Documents/testing/web_report_2026-06-25.pdf
2026-06-25 13:58:30 | INFO     | email_sender | Connecting to SMTP smtp.gmail.com:587 (STARTTLS) as you@gmail.com
2026-06-25 13:58:34 | INFO     | email_sender | Email sent to 2 recipient(s).
2026-06-25 13:58:34 | INFO     | state_store  | Recorded successful send for 2026-06-25 in /home/pranjaltiwari/Desktop/Daily_Report_Sender/state/last_sent.txt.
2026-06-25 13:58:34 | INFO     | __main__     | === Daily Report Sender finished successfully ===
```

**An already-sent run** (duplicate protection — stops early, no email):
```
2026-06-25 14:01:24 | INFO     | __main__     | === Daily Report Sender starting (Phase 7) ===
2026-06-25 14:01:24 | INFO     | __main__     | Monitored report directory: /home/pranjaltiwari/Documents/testing
2026-06-25 14:01:24 | INFO     | state_store  | Report already sent today (2026-06-25) — recorded in .../state/last_sent.txt.
2026-06-25 14:01:24 | INFO     | __main__     | Nothing to do — today's report was already sent.
```

**A failed run** (no valid report — logs the error and sends an admin alert):
```
2026-06-25 09:15:02 | INFO     | __main__     | === Daily Report Sender starting (Phase 7) ===
2026-06-25 09:15:02 | INFO     | __main__     | Monitored report directory: /opt/TLSOCDockerDeploy/reporting/output/pdf
2026-06-25 09:15:02 | WARNING  | file_checker | No PDF files found in report directory: /opt/TLSOCDockerDeploy/reporting/output/pdf
2026-06-25 09:15:02 | ERROR    | __main__     | No latest PDF available in the report directory.
2026-06-25 09:15:06 | INFO     | email_sender | Email sent to 1 recipient(s).
```

> In the failed example the last "Email sent" line is the **alert** going to
> `ALERT_EMAIL_TO`, not the report itself.

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `Problems: ... SMTP_PASSWORD is not set` | Fill `SMTP_PASSWORD` in `.env` with your **App Password** (not your normal password). |
| `Username and Password not accepted` | You used your normal Gmail password. Create an **App Password** and use that. |
| `No latest PDF available` | `REPORT_DIR` is wrong/empty, or no `.pdf` file is in it. |
| `Filename date(s) ... do not match today` | The PDF name does not contain today's date (`YYYY-MM-DD`). |
| `File is not a valid PDF` | The file is not a real PDF (e.g. a renamed text file). |
| `File modification date ... is not today` | The file is old. Re-create it today, or run `touch yourfile.pdf`. |
| It says "already sent today" but I want to resend | Use `--force`, or `rm -f state/last_sent.txt`. |
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
rm -f state/last_sent.txt      # so it isn't skipped by today's marker
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
