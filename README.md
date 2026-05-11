# ssh2clockify

Small helper that reads your [`last(1)`](https://man7.org/linux/man-pages/man1/last.1.html) login history and writes a **CSV** with **Start Date**, **Start Time**, **End Date**, **End Time**, and **Duration (h)** in a spreadsheet-friendly layout (US-style dates, 12-hour times with seconds, duration as `HH:MM:SS`).

You can add **`--email`** when you need a leading **Email** column (e.g. [Clockify timesheet import](https://clockify.me/help/getting-started/import-timesheets)); Clockify’s docs focus on start + duration, so confirm their importer accepts your column set before a large upload.

## Requirements

- **Python 3** (stdlib only; no `pip install` needed)
- **`last`** from util-linux (typical on Linux)

## Quick start

```bash
chmod +x ssh2clockify.py
./ssh2clockify.py -o sessions.csv
```

Default columns:

| Column | Default format |
|--------|----------------|
| **Start Date** | `MM/DD/YYYY` (`%m/%d/%Y`) |
| **Start Time** | `HH:MM:SS AM/PM` (`%I:%M:%S %p`) |
| **End Date** | same as start date |
| **End Time** | same as start time |
| **Duration (h)** | `HH:MM:SS` (from `last`’s session length; minute resolution, seconds are `:00`) |

End date/time are **start + duration** (correct across midnight).

Omit **End Date** and **End Time**:

```bash
./ssh2clockify.py --omit-end-datetime -o sessions.csv
```

Clockify-style file with **Email** first:

```bash
./ssh2clockify.py --email you@company.com -o timesheets.csv
```

## What gets imported

- Only lines that include a **session length in parentheses** at the end, e.g. `(01:23)` or `(2+23:21)`, become rows. Entries like **`gone - no logout`** with **no** duration are **skipped**.
- By default, sessions **shorter than 5 minutes** are **skipped** (`--min-duration-minutes`).
- By default, `last` is run as: `last -w -F -n 5000 <your unix login>`.

Optional columns (**Project**, **Client**, **Task**, **Description**, **Tag**, **Billable**) are added only when you pass the matching flags.

## Examples

SSH-oriented TTYs only (`pts/…`):

```bash
./ssh2clockify.py --tty-regex '^pts/' -o ssh.csv
```

European date order:

```bash
./ssh2clockify.py --date-format '%d/%m/%Y' -o out.csv
```

24-hour times:

```bash
./ssh2clockify.py --time-format '%H:%M:%S' -o out.csv
```

Custom `last` invocation:

```bash
./ssh2clockify.py --last-args '-w -F -f /var/log/wtmp' -o out.csv
```

## Options

```bash
./ssh2clockify.py --help
```

| Flag | Purpose |
|------|--------|
| `--email` | Prepend **Email** column (optional; for tools that expect it) |
| `--omit-end-datetime` | Drop **End Date** and **End Time** |
| `-u` / `--user` | Unix login for `last` (default: current user) |
| `--min-duration-minutes` | Minimum session length (default: `5`) |
| `-n` / `--limit` | `last -n` limit (default: `5000`; `0` = no limit) |
| `--tty-regex` | Only include matching TTYs |
| `--date-format` / `--time-format` | `strftime` for date/time columns |
| `--project`, `--client`, `--task`, `--tag`, `--billable` | Optional columns when non-empty |
| `--description-template` | Add **Description** (`{tty}`, `{host}`, `{start}`, `{duration_min}`) |
| `-o` / `--output` | Output file (`-` = stdout) |
| `--last-bin`, `--last-args` | How `last` is invoked |

## Caveats

- **`last`** only gives duration to the **minute**; **Duration (h)** uses seconds `00` after the minutes.
- **Clockify** may expect different header names or only **start + duration**; align with their current import UI.
- Reading wtmp may require appropriate permissions on your system.
