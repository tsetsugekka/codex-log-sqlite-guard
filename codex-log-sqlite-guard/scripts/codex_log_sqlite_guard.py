#!/usr/bin/env python3
import argparse
import datetime as dt
import glob
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time


TRIGGER_NAME = "codex_block_logs_insert"
DEFAULT_DB = Path.home() / ".codex" / "logs_2.sqlite"


def human_size(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    v = float(n)
    for unit in units:
        if abs(v) < 1024 or unit == units[-1]:
            return f"{v:.1f} {unit}" if unit != "B" else f"{int(v)} B"
        v /= 1024
    return f"{n} B"


def db_paths(db: Path) -> list[Path]:
    return [db, Path(str(db) + "-wal"), Path(str(db) + "-shm")]


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def connect_readonly(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def connect_rw(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(db), timeout=60)


def scalar(conn: sqlite3.Connection, sql: str):
    return conn.execute(sql).fetchone()[0]


def ensure_db(db: Path) -> None:
    if not db.exists():
        raise SystemExit(f"missing database: {db}")


def db_summary(db: Path) -> dict:
    ensure_db(db)
    with connect_readonly(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        if "logs" not in tables:
            raise SystemExit(f"{db} does not contain a logs table")
        count, max_id, max_ts = conn.execute(
            "SELECT COUNT(*), MAX(id), MAX(ts) FROM logs"
        ).fetchone()
        trigger = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='trigger' AND name=?", (TRIGGER_NAME,)
        ).fetchone()
        page_size = scalar(conn, "PRAGMA page_size")
        page_count = scalar(conn, "PRAGMA page_count")
        freelist_count = scalar(conn, "PRAGMA freelist_count")
        journal_mode = scalar(conn, "PRAGMA journal_mode")
    max_time = None
    if max_ts is not None:
        max_time = dt.datetime.fromtimestamp(max_ts).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "db": str(db),
        "db_size": file_size(db),
        "wal_size": file_size(Path(str(db) + "-wal")),
        "shm_size": file_size(Path(str(db) + "-shm")),
        "count": count,
        "max_id": max_id,
        "max_time": max_time,
        "trigger_installed": bool(trigger),
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": freelist_count,
        "journal_mode": journal_mode,
    }


def print_summary(summary: dict) -> None:
    print(f"database: {summary['db']}")
    print(f"db size: {human_size(summary['db_size'])}")
    print(f"wal size: {human_size(summary['wal_size'])}")
    print(f"shm size: {human_size(summary['shm_size'])}")
    print(f"rows: {summary['count']}")
    print(f"max id: {summary['max_id']}")
    print(f"latest log time: {summary['max_time']}")
    print(f"trigger installed: {summary['trigger_installed']}")
    print(f"journal mode: {summary['journal_mode']}")
    print(f"page size: {summary['page_size']}")
    print(f"page count: {summary['page_count']}")
    print(f"freelist count: {summary['freelist_count']}")


def recent_levels(db: Path, minutes: int) -> None:
    with connect_readonly(db) as conn:
        rows = conn.execute(
            """
            SELECT level, COUNT(*) AS n, COALESCE(SUM(estimated_bytes), 0) AS bytes
            FROM logs
            WHERE ts >= strftime('%s','now', ?)
            GROUP BY level
            ORDER BY n DESC
            """,
            (f"-{minutes} minutes",),
        ).fetchall()
    print(f"recent levels ({minutes} minute window):")
    if not rows:
        print("  none")
    for level, n, bytes_ in rows:
        print(f"  {level}: {n} rows, {human_size(bytes_)} estimated")


def sample(db: Path, seconds: int, interval: float) -> None:
    print(f"sampling for {seconds}s every {interval:g}s")
    end = time.time() + seconds
    while True:
        s = db_summary(db)
        wal = Path(str(db) + "-wal")
        try:
            mtime = dt.datetime.fromtimestamp(wal.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except FileNotFoundError:
            mtime = "missing"
        now = dt.datetime.now().strftime("%H:%M:%S")
        print(
            f"{now} rows={s['count']} max_id={s['max_id']} "
            f"latest={s['max_time']} wal={human_size(s['wal_size'])} wal_mtime={mtime}",
            flush=True,
        )
        if time.time() >= end:
            break
        time.sleep(interval)


def cmd_diagnose(args: argparse.Namespace) -> None:
    db = Path(args.db).expanduser()
    s = db_summary(db)
    print_summary(s)
    recent_levels(db, args.recent_minutes)
    if args.sample_seconds > 0:
        sample(db, args.sample_seconds, args.interval)


def cmd_capacity(args: argparse.Namespace) -> None:
    db = Path(args.db).expanduser()
    s = db_summary(db)
    usage = shutil.disk_usage(db.parent)
    current_bundle = sum(file_size(p) for p in db_paths(db))
    reclaimable = s["freelist_count"] * s["page_size"]
    estimated_after_vacuum = max(0, (s["page_count"] - s["freelist_count"]) * s["page_size"])
    recommended_for_backup_and_vacuum = s["db_size"] + estimated_after_vacuum + 256 * 1024 * 1024
    print_summary(s)
    print(f"current db bundle: {human_size(current_bundle)}")
    print(f"estimated reclaimable by VACUUM: {human_size(reclaimable)}")
    print(f"estimated db after VACUUM: {human_size(estimated_after_vacuum)}")
    print(f"disk free at db location: {human_size(usage.free)}")
    print(f"rough free space recommended for backup + VACUUM: {human_size(recommended_for_backup_and_vacuum)}")
    print(f"enough for recommended path: {usage.free > recommended_for_backup_and_vacuum}")


def backup_db(db: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    dest = backup_dir / f"logs_2.sqlite.backup-{stamp}"
    with connect_readonly(db) as src, sqlite3.connect(str(dest)) as dst:
        src.backup(dst)
    return dest


def cmd_install_trigger(args: argparse.Namespace) -> None:
    db = Path(args.db).expanduser()
    ensure_db(db)
    if not args.no_backup:
        dest = backup_db(db, Path(args.backup_dir).expanduser())
        print(f"backup: {dest} ({human_size(file_size(dest))})")
    with connect_rw(db) as conn:
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {TRIGGER_NAME}
            BEFORE INSERT ON logs
            BEGIN
              SELECT RAISE(IGNORE);
            END
            """
        )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    print(f"installed trigger: {TRIGGER_NAME}")


def cmd_vacuum(args: argparse.Namespace) -> None:
    db = Path(args.db).expanduser()
    ensure_db(db)
    before = db_summary(db)
    with connect_rw(db) as conn:
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    after = db_summary(db)
    print("before:")
    print_summary(before)
    print("after:")
    print_summary(after)


def cmd_drop_trigger(args: argparse.Namespace) -> None:
    db = Path(args.db).expanduser()
    ensure_db(db)
    with connect_rw(db) as conn:
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME}")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    print(f"dropped trigger if present: {TRIGGER_NAME}")


def cmd_list_backups(args: argparse.Namespace) -> None:
    base = Path(args.dir).expanduser()
    patterns = ["logs_2.sqlite.backup-*", "logs_2.sqlite.backup-*-wal", "logs_2.sqlite.backup-*-shm"]
    found: list[Path] = []
    for pattern in patterns:
        found.extend(Path(p) for p in glob.glob(str(base / pattern)))
    for path in sorted(set(found)):
        print(f"{path}\t{human_size(file_size(path))}")
    if not found:
        print(f"no backups found in {base}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guard Codex logs_2.sqlite from high-frequency TRACE writes.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to logs_2.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("diagnose", help="Read-only summary plus optional sampling")
    p.add_argument("--sample-seconds", type=int, default=15)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--recent-minutes", type=int, default=1)
    p.set_defaults(func=cmd_diagnose)

    p = sub.add_parser("capacity", help="Estimate disk space, backup cost, and VACUUM reclaim")
    p.set_defaults(func=cmd_capacity)

    p = sub.add_parser("install-trigger", help="Install the INSERT-blocking trigger")
    p.add_argument("--backup-dir", default="./work")
    p.add_argument("--no-backup", action="store_true")
    p.set_defaults(func=cmd_install_trigger)

    p = sub.add_parser("vacuum", help="Run VACUUM and truncate WAL")
    p.set_defaults(func=cmd_vacuum)

    p = sub.add_parser("drop-trigger", help="Remove the INSERT-blocking trigger")
    p.set_defaults(func=cmd_drop_trigger)

    p = sub.add_parser("list-backups", help="List backup files in a directory")
    p.add_argument("--dir", default="./work")
    p.set_defaults(func=cmd_list_backups)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except sqlite3.Error as exc:
        print(f"sqlite error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
