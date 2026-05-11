# ssh2clockify

Small helper that reads your [`last(1)`](https://man7.org/linux/man-pages/man1/last.1.html) login history and writes a **CSV** you can import into **Clockify** as timesheets.

Clockify’s column rules and import flow are documented here: [Import data into Clockify](https://clockify.me/help/getting-started/import-timesheets).

## Requirements

- **Python 3** (stdlib only; no `pip install` needed)
- **`last`** from util-linux (typical on Linux)
- A Clockify workspace where **timesheet CSV import** is available on your plan, and an **active** user whose **email** matches the `--email` you pass

## Quick start

```bash
chmod +x ssh2clockify.py
./ssh2clockify.py --email you@company.com -o timesheets.csv
```

Then in Clockify: **Workspace settings → Import**, upload the CSV, and confirm date/time formats when prompted.

Match **Start date**, **Start time**, and **Duration** to your **profile and workspace** settings (same as Clockify’s import article). This tool defaults to:

- **Start date:** `MM/DD/YYYY` (`%m/%d/%Y`)
- **Start time:** 24-hour `HH:MM` (`%H:%M`)
- **Duration:** clock form `HH:MM` (zero-padded), unless you pass `--duration-decimal`

## What gets imported

- Only lines that include a **session length in parentheses** at the end, e.g. `(01:23)` or `(2+23:21)`, are turned into rows. Entries like **`gone - no logout`** with **no** duration are **skipped**.
- By default, sessions **shorter than 5 minutes** are **skipped** (change with `--min-duration-minutes`).
- By default, `last` is run as: `last -w -F -n 5000 <your unix login>`.  
  `-w` / `-F` improve parsing (wide fields, full timestamps).

## Examples

SSH-oriented TTYs only (`pts/…`):

```bash
./ssh2clockify.py --email you@company.com --tty-regex '^pts/' -o ssh.csv
```

Drop very short sessions and cap how much history `last` returns:

```bash
./ssh2clockify.py --email you@company.com --min-duration-minutes 10 -n 2000 -o out.csv
```

European date order in the CSV:

```bash
./ssh2clockify.py --email you@company.com --date-format '%d/%m/%Y' -o out.csv
```

12-hour times in the CSV:

```bash
./ssh2clockify.py --email you@company.com --time-format '%I:%M %p' -o out.csv
```

Decimal hours for duration (if your workspace uses decimal duration):

```bash
./ssh2clockify.py --email you@company.com --duration-decimal -o out.csv
```

Custom `last` invocation (e.g. alternate wtmp):

```bash
./ssh2clockify.py --email you@company.com --last-args '-w -F -f /var/log/wtmp' -o out.csv
```

Tag every row and set a project name:

```bash
./ssh2clockify.py --email you@company.com --project "Admin" --tag "SSH" -o out.csv
```

Custom **Description** (Python `str.format` fields: `{tty}`, `{host}`, `{start}`, `{duration_min}`):

```bash
./ssh2clockify.py --email you@company.com \
  --description-template 'Login {tty} from {host}, {duration_min} min' -o out.csv
```

## Options

Run:

```bash
./ssh2clockify.py --help
```

for the full list. Common flags:

| Flag | Purpose |
|------|--------|
| `--email` | Clockify user email (**required**) |
| `-u` / `--user` | Unix login passed to `last` (default: current user) |
| `--min-duration-minutes` | Minimum session length to include (default: `5`) |
| `-n` / `--limit` | `last -n` limit (default: `5000`; `0` = no limit) |
| `--tty-regex` | Only include TTYs matching this regex |
| `--date-format` / `--time-format` | `strftime` formats for CSV columns |
| `--duration-decimal` | Duration as decimal hours instead of `HH:MM` |
| `--project`, `--client`, `--task`, `--tag`, `--billable` | Optional Clockify columns |
| `-o` / `--output` | Output file (`-` = stdout) |
| `--last-bin`, `--last-args` | Control how `last` is invoked |

## Caveats

- **Clockify does not dedupe** CSV imports; review the file before uploading.
- **Timesheet import** may require a **paid** Clockify plan; see their help article.
- **Permissions:** reading login history may require your user to have access to the wtmp data `last` uses (normal for your own user on many systems).
