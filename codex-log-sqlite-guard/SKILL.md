---
name: codex-log-sqlite-guard
description: Diagnose and mitigate Codex Desktop high-frequency TRACE writes to ~/.codex/logs_2.sqlite. Use when a user asks whether Codex is writing logs_2.sqlite, logs_2.sqlite-wal, TRACE logs, SQLite logs, disk/SSD wear, Codex log churn, or wants a safe workflow to stop the writes, compact the SQLite file, verify after restarting Codex, and clean up temporary backups.
---

# Codex Log SQLite Guard

Use this skill to safely diagnose and mitigate Codex Desktop `~/.codex/logs_2.sqlite` high-frequency log writes. The workflow is intentionally conservative because it touches Codex state files.

## Core Rules

- Reply in the user's language.
- Before each phase, tell the user exactly what you will do and why.
- Do not kill, restart, or force-quit Codex yourself unless the user explicitly asks. Tell the user when they need to manually quit/reopen Codex Desktop, then wait for them to say they have done it.
- Start with read-only diagnosis. Do not modify `~/.codex/logs_2.sqlite` until the user confirms the mitigation.
- Before backing up or vacuuming, compute the SQLite file sizes and free disk space. Explain whether there is enough room.
- When asking about backup, explain both choices:
  - Backup: safer rollback path, but temporarily uses roughly another copy of the database on disk.
  - No backup: faster and saves space, but rollback is limited to removing the trigger and cannot restore the prior database contents.
- After mitigation, verify before and after a manual Codex restart.
- After final verification, tell the user any backup files that are no longer needed and ask whether to delete them. Do not delete backups without explicit confirmation.

## Script

Use `scripts/codex_log_sqlite_guard.py`. Resolve it relative to this `SKILL.md`.

Common commands:

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
python3 scripts/codex_log_sqlite_guard.py capacity
python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
python3 scripts/codex_log_sqlite_guard.py vacuum
python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
python3 scripts/codex_log_sqlite_guard.py drop-trigger
```

Use `--db PATH` only when the user is not using the default `~/.codex/logs_2.sqlite`.

## Workflow

### 1. Read-Only Diagnosis

Tell the user:

```text
我会先做只读检查：确认 logs_2.sqlite/WAL/SHM 大小、logs 表状态、最近 TRACE 写入量，并短时间采样 COUNT、MAX(id)、WAL 大小和 mtime 是否持续增长。不会修改文件。
```

Run:

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
```

Interpret as affected when most of these are true:

- `MAX(id)` or row count changes during sampling.
- `logs_2.sqlite-wal` size or mtime keeps changing.
- recent rows are mostly `TRACE`.
- latest log time tracks current time.

If not affected, stop and report that no mitigation is needed.

### 2. Capacity And Backup Decision

Tell the user:

```text
接下来我会计算 SQLite 文件大小、WAL/SHM 大小、VACUUM 预计可回收空间，以及磁盘剩余容量。然后我会说明是否建议先备份。
```

Run:

```bash
python3 scripts/codex_log_sqlite_guard.py capacity
```

If free disk is enough for a backup plus compaction, recommend backup. If free disk is tight, explain that backup may fail or consume too much space and ask whether to continue without backup.

Do not proceed until the user chooses backup or no backup.

### 3. Mitigation

Tell the user:

```text
我会给 logs 表安装一个可回滚的 SQLite trigger，拦截后续 INSERT。它不会删除现有日志；回滚方式是 DROP TRIGGER。安装后会 checkpoint/truncate WAL，然后采样验证。
```

If the user chose backup:

```bash
python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
```

If the user chose no backup:

```bash
python3 scripts/codex_log_sqlite_guard.py install-trigger --no-backup
```

Then run another diagnosis:

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 30
```

The mitigation is working when `MAX(id)`, row count, WAL size, and WAL mtime stop changing.

### 4. Manual Codex Restart Verification

Tell the user:

```text
现在需要你手动完全退出并重新打开 Codex Desktop。请完成后告诉我，我会再次只读采样，确认重启后 trigger 仍然生效。
```

After the user confirms, run:

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 30
```

Expect possible small startup WAL activity or row count cleanup. Treat it as okay if `MAX(id)` does not increase and WAL stops changing during the sampling window.

### 5. Compact The Database

Only compact after mitigation works and restart verification passes.

Tell the user:

```text
现在高频写入已经停止。我会执行 VACUUM 缩小 logs_2.sqlite，并 truncate WAL。这个步骤会写入数据库，需要足够临时磁盘空间。
```

Run:

```bash
python3 scripts/codex_log_sqlite_guard.py vacuum
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 20
```

Report before/after sizes and whether `freelist_count` is near zero.

### 6. Backup Cleanup

List backups:

```bash
python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
```

Tell the user:

```text
当前库完整、trigger 生效、重启后验证通过。如果你不打算回滚到修复前状态，这些备份可以删除；删除后仍可通过 DROP TRIGGER 取消拦截，但无法恢复修复前数据库内容。
```

Only delete backup files after explicit user confirmation. Also remove matching `-wal` and `-shm` sidecar files for the same backup if they exist.

## Rollback

To stop blocking inserts:

```bash
python3 scripts/codex_log_sqlite_guard.py drop-trigger
```

If a pre-mitigation backup was kept and the user wants a full database rollback, require Codex Desktop to be manually closed first. Then restore the backup by replacing `~/.codex/logs_2.sqlite` and removing its active `-wal`/`-shm` files. Do not perform this restore without explicit confirmation.
