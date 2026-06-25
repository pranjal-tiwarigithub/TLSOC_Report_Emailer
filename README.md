# Daily Report Sender

Automatically email the day's **ASC Web Monitoring Report** (a PDF) to a list
of recipients. Designed to run unattended once per day via cron, but also
usable on demand.

Each run:

1. Looks in a configurable directory for the **newest** PDF.
2. Validates it:
   - the filename contains **today's date** (`YYYY-MM-DD`),
   - the file is a real PDF (`%PDF-` magic bytes),
   - the file's **modification time** is today.
3. If valid (and not already sent today), emails the PDF as an attachment via
   **Gmail SMTP** to the configured **To / CC / BCC** recipients.
4. Records the send so it never delivers twice in one day.
5. On any failure, logs the reason and emails an **admin alert**.

---

## Project layout

```
Daily_Report_Sender/
├── report_sender.py     # Entry point / orchestrator (CLI)
├── config.py            # Central config + secrets (loaded from .env)
├── file_checker.py      # Find newest PDF + validate name/PDF/mtime
├── email_sender.py      # Build + send report and alert emails (Gmail SMTP)
├── state_store.py       # Dedup: "already sent today?" marker
├── logger.py            # Rotating file + console logging
├── requirements.txt     # Dependencies (python-dotenv)
├── .env.example         # Template for your local .env (copy + fill in)
├── .gitignore
├── logs/                # sender.log (rotating; git-ignored contents)
└── state/               # last_sent.txt dedup marker (git-ignored contents)
```

---

## Requirements

- Python **3.11+**
- A Gmail account with **2-Step Verification** and a **16-character App
  Password** (a normal Google password will not work over SMTP).

---

## Setup

```bash
cd /home/pranjaltiwari/Desktop/Daily_Report_Sender

# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your configuration from the template
cp .env.example .env
```

Then edit **`.env`** and fill in your values (this file is git-ignored and must
never be committed):

| Variable         | Purpose                                              | Example                              |
|------------------|------------------------------------------------------|--------------------------------------|
| `REPORT_DIR`     | Directory to monitor for the PDF (**configurable**)  | `/opt/TLSOCDockerDeploy/reporting/output/pdf` |
| `LOG_LEVEL`      | `DEBUG` / `INFO` / `WARNING` / `ERROR`               | `INFO`                               |
| `LOG_FILE`       | Log file path (relative resolves to project root)    | `logs/sender.log`                    |
| `STATE_FILE`     | Dedup marker path                                    | `state/last_sent.txt`                |
| `SMTP_HOST`      | SMTP server                                          | `smtp.gmail.com`                     |
| `SMTP_PORT`      | SMTP port (STARTTLS)                                 | `587`                                |
| `SMTP_USER`      | Gmail address (**secret**)                           | `you@gmail.com`                      |
| `SMTP_PASSWORD`  | Gmail **App Password** (**secret**)                  | `abcd efgh ijkl mnop`                |
| `EMAIL_FROM`     | Sender address (defaults to `SMTP_USER`)             | `you@gmail.com`                      |
| `EMAIL_TO`       | Recipients, comma-separated                          | `a@x.com,b@y.com`                    |
| `EMAIL_CC`       | CC recipients, comma-separated (optional)            |                                      |
| `EMAIL_BCC`      | BCC recipients, comma-separated (optional)           |                                      |
| `ALERT_EMAIL_TO` | Admin address(es) for failure alerts                 | `admin@x.com`                        |
| `EMAIL_SUBJECT`  | Subject base (today's date is appended)              | `ASC Web Monitoring Report`          |

> Get an App Password at <https://myaccount.google.com/apppasswords>
> (requires 2-Step Verification enabled).

---

## Usage

```bash
source .venv/bin/activate

# Normal run (what cron will execute)
python report_sender.py

# Dry run — build the email and log what WOULD be sent, but don't connect to SMTP
python report_sender.py --dry-run

# Force a resend even if today's report was already sent
python report_sender.py --force

# Override the monitored directory for this run only
REPORT_DIR=/path/to/pdfs python report_sender.py
```

### Exit codes

| Code | Meaning                                                              |
|------|---------------------------------------------------------------------|
| `0`  | Success — report sent, or already sent earlier today (nothing to do)|
| `1`  | Failure — invalid config, no valid report, send error, or crash     |

### The email

- **Subject:** `ASC Web Monitoring Report - YYYY-MM-DD` (today's date appended)
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

## Local testing (watch a folder)

Run the script in a loop so it sends as soon as a valid PDF appears:

```bash
source .venv/bin/activate
mkdir -p /home/pranjaltiwari/Documents/testing
rm -f state/last_sent.txt           # allow a fresh send today

while true; do
  REPORT_DIR=/home/pranjaltiwari/Documents/testing python report_sender.py
  sleep 15
done
```

In another terminal, drop a sample PDF (any name containing today's date,
ending in `.pdf`):

```bash
printf '%%PDF-1.7\nLocal test report.\n%%%%EOF\n' \
  > /home/pranjaltiwari/Documents/testing/web_report_$(date +%F).pdf
```

The watcher picks it up within ~15s, emails it once, and then skips (dedup).
Press **Ctrl+C** to stop. To re-test: `rm -f state/last_sent.txt` and drop the
file again.

> Tip: while the folder is empty, each cycle counts as a failure and emails an
> alert. Drop the PDF in **before** starting the loop to avoid alert spam.

---

## Logging

- Written to `logs/sender.log` (rotating: ~1 MB × 5 backups) **and** the console.
- Set `LOG_LEVEL=DEBUG` in `.env` for verbose output.

---

## Scheduling (cron)

Phase 8 will install a cron entry to run daily at **12:30 PM**. (Documentation
to be completed in that phase.)

---

## Security notes

- Secrets live only in `.env`, which is **git-ignored**. Never commit it.
- The App Password is never logged.
- `logs/` and `state/` keep only a `.gitkeep` in version control; their
  contents are ignored.
