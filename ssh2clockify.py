#!/usr/bin/env python3
"""
Convert `last(1)` login history into a CSV: Start Date, Start Time, End Date,
End Time, and Duration (h) as HH:MM:SS (defaults match common US spreadsheet
templates). Use --omit-end-datetime to drop the end columns.

Typical usage:
  ./ssh2clockify.py -o sessions.csv
  ./ssh2clockify.py --email you@company.com -o clockify_timesheets.csv

Requires util-linux `last` with session lines that include a duration in parentheses
for completed sessions (e.g. from `last -w -F`).
"""

from __future__ import annotations

import argparse
import csv
import getpass
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Iterator, Sequence


TS_RE = re.compile(
    r"([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\s*\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})"
)
DUR_RE = re.compile(
    r"\s*\(((?P<days>\d+)\+)?(?P<h>\d{1,4}):(?P<m>\d{2})\)\s*$"
)


@dataclass(frozen=True)
class Session:
    tty: str
    host: str
    start: datetime
    duration_minutes: int
    raw: str


def _parse_last_timestamp(s: str) -> datetime:
    """Parse `last -F` timestamps: 'Sat May  9 20:26:51 2026'."""
    return datetime.strptime(s.strip(), "%a %b %d %H:%M:%S %Y")


def _parse_duration_minutes(match: re.Match[str]) -> int:
    days = int(match.group("days") or 0)
    h = int(match.group("h"))
    m = int(match.group("m"))
    return days * 24 * 60 + h * 60 + m


def _split_user_tty_host(line: str) -> tuple[str, str, str, str] | None:
    """
    Split a `last -w` line into user, tty, host, remainder.
    Host column is variable; we peel user and tty then take a fixed host width
    heuristic matching util-linux padding (~17 chars) before the first timestamp.
    """
    line = line.rstrip("\n")
    if not line.strip():
        return None
    parts = line.split(None, 2)
    if len(parts) < 2:
        return None
    user, tty, rest = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
    m = TS_RE.search(rest)
    if not m:
        return None
    prefix_end = m.start()
    host = rest[:prefix_end].rstrip()
    tail = rest[prefix_end:].lstrip()
    return user, tty, host, tail


def parse_last_line(line: str) -> Session | None:
    """Parse one line of `last -w -F` output; None if no usable session."""
    if "wtmp begins" in line:
        return None
    split = _split_user_tty_host(line)
    if not split:
        return None
    _user, tty, host, tail = split
    dm = DUR_RE.search(tail)
    if not dm:
        return None
    duration_minutes = _parse_duration_minutes(dm)
    before_dur = tail[: dm.start()].rstrip()
    ts_matches = list(TS_RE.finditer(before_dur))
    if not ts_matches:
        return None
    start_raw = ts_matches[0].group(1)
    try:
        start = _parse_last_timestamp(start_raw)
    except ValueError:
        return None
    return Session(
        tty=tty.strip(),
        host=host.strip(),
        start=start,
        duration_minutes=duration_minutes,
        raw=line.rstrip("\n"),
    )


def run_last(
    *,
    last_bin: str,
    login_user: str,
    limit: int | None,
    extra_args: Sequence[str],
) -> str:
    cmd: list[str] = [last_bin, *extra_args]
    if limit is not None:
        cmd.extend(["-n", str(limit)])
    if login_user:
        cmd.append(login_user)
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or "")
        raise SystemExit(proc.returncode or 1)
    return proc.stdout


def format_duration_hms(total_minutes: int) -> str:
    """Duration as HH:MM:SS (from whole minutes; seconds are 00)."""
    total_seconds = total_minutes * 60
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def iter_sessions(
    lines: Iterable[str],
    *,
    tty_pattern: re.Pattern[str] | None,
    min_minutes: float,
) -> Iterator[Session]:
    for line in lines:
        sess = parse_last_line(line)
        if sess is None:
            continue
        if tty_pattern is not None and not tty_pattern.search(sess.tty):
            continue
        if sess.duration_minutes < min_minutes:
            continue
        yield sess


def build_description(sess: Session, template: str) -> str:
    return template.format(
        tty=sess.tty,
        host=sess.host or "",
        start=sess.start.isoformat(),
        duration_min=sess.duration_minutes,
    )


def write_timesheet_csv(
    sessions: Iterable[Session],
    *,
    out,
    email: str | None,
    date_fmt: str,
    time_fmt: str,
    omit_end_datetime: bool,
    project: str,
    client: str,
    task: str,
    tag: str,
    billable: str,
    description_template: str | None,
) -> None:
    fieldnames: list[str] = []
    if email:
        fieldnames.append("Email")
    fieldnames.extend(["Start Date", "Start Time"])
    if not omit_end_datetime:
        fieldnames.extend(["End Date", "End Time"])
    fieldnames.append("Duration (h)")
    if project:
        fieldnames.append("Project")
    if client:
        fieldnames.append("Client")
    if task:
        fieldnames.append("Task")
    if description_template is not None:
        fieldnames.append("Description")
    if tag:
        fieldnames.append("Tag")
    if billable:
        fieldnames.append("Billable")

    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for sess in sessions:
        dur = format_duration_hms(sess.duration_minutes)
        end = sess.start + timedelta(minutes=sess.duration_minutes)
        row: dict[str, str] = {}
        if email:
            row["Email"] = email
        row["Start Date"] = sess.start.strftime(date_fmt)
        row["Start Time"] = sess.start.strftime(time_fmt)
        if not omit_end_datetime:
            row["End Date"] = end.strftime(date_fmt)
            row["End Time"] = end.strftime(time_fmt)
        row["Duration (h)"] = dur
        if project:
            row["Project"] = project
        if client:
            row["Client"] = client
        if task:
            row["Task"] = task
        if description_template is not None:
            row["Description"] = build_description(sess, description_template)
        if tag:
            row["Tag"] = tag
        if billable:
            row["Billable"] = billable
        writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Convert `last` output to a timesheet CSV (Start/End + Duration (h))."
    )
    p.add_argument(
        "--email",
        default=None,
        help=(
            "If set, add an Email column first (e.g. for Clockify import). "
            "Must match an active workspace user when importing there."
        ),
    )
    p.add_argument(
        "--user",
        "-u",
        default=getpass.getuser(),
        help="Login name passed to `last` (default: current user).",
    )
    p.add_argument(
        "--min-duration-minutes",
        type=float,
        default=5.0,
        help="Skip sessions shorter than this many minutes (default: 5).",
    )
    p.add_argument(
        "--limit",
        "-n",
        type=int,
        default=5000,
        help="Max lines for `last -n` (default: 5000). Use 0 for no limit.",
    )
    p.add_argument(
        "--last-bin",
        default="last",
        help="Path to the `last` binary (default: last).",
    )
    p.add_argument(
        "--last-args",
        type=str,
        default="-w -F",
        help='Extra arguments for `last`, shell-quoted (default: "-w -F").',
    )
    p.add_argument(
        "--tty-regex",
        default="",
        help="If set, only include sessions whose TTY matches this regex (e.g. '^pts/').",
    )
    p.add_argument(
        "--date-format",
        default="%m/%d/%Y",
        help="strftime for date columns (default: %%m/%%d/%%Y).",
    )
    p.add_argument(
        "--time-format",
        default="%I:%M:%S %p",
        help="strftime for time columns (default: 12h %%I:%%M:%%S %%p).",
    )
    p.add_argument(
        "--omit-end-datetime",
        action="store_true",
        help="Omit End Date and End Time columns (keep Start + Duration (h) only).",
    )
    p.add_argument(
        "--project",
        default="",
        help="Optional Project column for every row.",
    )
    p.add_argument(
        "--client",
        default="",
        help="Optional Client column for every row.",
    )
    p.add_argument(
        "--task",
        default="",
        help="Optional Task column for every row.",
    )
    p.add_argument(
        "--tag",
        default="",
        help="Optional Tag column (comma-separated inside the cell for multiple tags).",
    )
    p.add_argument(
        "--billable",
        default="",
        help="Optional Billable column (Yes/No per Clockify).",
    )
    p.add_argument(
        "--description-template",
        default=None,
        metavar="TEMPLATE",
        help=(
            "If set, add a Description column using this Python format string "
            "(keys: {tty},{host},{start},{duration_min}). Omit the column by default."
        ),
    )
    p.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output CSV path, or - for stdout (default: -).",
    )
    args = p.parse_args(argv)

    limit = None if args.limit == 0 else args.limit
    try:
        extra = shlex.split(args.last_args)
    except ValueError as e:
        p.error(f"Invalid --last-args: {e}")

    tty_re = re.compile(args.tty_regex) if args.tty_regex else None
    desc_tpl = args.description_template

    text = run_last(
        last_bin=args.last_bin,
        login_user=args.user,
        limit=limit,
        extra_args=extra,
    )
    sessions = list(
        iter_sessions(
            text.splitlines(),
            tty_pattern=tty_re,
            min_minutes=args.min_duration_minutes,
        )
    )

    out_fp = open(args.output, "w", newline="", encoding="utf-8") if args.output != "-" else sys.stdout
    try:
        write_timesheet_csv(
            sessions,
            out=out_fp,
            email=args.email,
            date_fmt=args.date_format,
            time_fmt=args.time_format,
            omit_end_datetime=args.omit_end_datetime,
            project=args.project,
            client=args.client,
            task=args.task,
            tag=args.tag,
            billable=args.billable,
            description_template=desc_tpl,
        )
    finally:
        if out_fp is not sys.stdout:
            out_fp.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
