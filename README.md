# Codex Log SQLite Guard

Codex Log SQLite Guard is a Codex skill for diagnosing and mitigating abnormal high-frequency local log writes from Codex Desktop to `~/.codex/logs_2.sqlite`. It turns a real-world `TRACE` log churn investigation into a reusable, verifiable, and reversible workflow.

This repository contains only public-safe workflow instructions and helper code. It does not include personal logs, SQLite backups, Codex conversation data, or private local path data.

## Included Skill

### `codex-log-sqlite-guard`

Diagnoses and mitigates high-frequency `TRACE` writes from Codex Desktop to `~/.codex/logs_2.sqlite`. The skill starts with read-only checks for `logs_2.sqlite`, `logs_2.sqlite-wal`, the `logs` table, `MAX(id)`, WAL size, and WAL mtime. When the issue is confirmed, it guides the user through backup choice, installs a reversible SQLite trigger, verifies again after a manual Codex restart, and compacts the database with `VACUUM` only after writes are confirmed stopped.

〖Dependencies〗Required — Python 3 standard-library `sqlite3`, plus access to `~/.codex/logs_2.sqlite`.

〖Companion skills〗None.

Use cases:

  * Check whether Codex Desktop is still writing to `logs_2.sqlite` or `logs_2.sqlite-wal`.
  * Determine whether the local SQLite log database is bloated by `TRACE` logs.
  * Measure database size, WAL/SHM size, free disk space, and backup cost before modification.
  * Install a reversible trigger on the `logs` table to block future log inserts.
  * Verify after the user manually quits and reopens Codex Desktop.
  * Run `VACUUM` after high-frequency writes stop, then guide backup cleanup.
  * Re-check after Codex updates to decide whether the workaround still applies.

## Workflow

| Phase | Action | Writes files |
| --- | --- | --- |
| Read-only diagnosis | Inspect database size, WAL/SHM, recent levels, `COUNT`, `MAX(id)`, and WAL mtime | No |
| Capacity check | Estimate backup cost, free disk space, and possible `VACUUM` recovery | No |
| Backup decision | Explain backup vs no-backup tradeoffs and wait for user confirmation | No |
| Trigger mitigation | Create `codex_block_logs_insert` to block future INSERTs into `logs` | Yes |
| Restart verification | Ask the user to manually quit and reopen Codex Desktop, then sample again | No |
| Database compaction | Run `VACUUM` and truncate WAL after growth is confirmed stopped | Yes |
| Backup cleanup | List backups and delete them only after explicit user confirmation | Yes |

## Installation

In Codex, send this repository URL and ask Codex to install the skill:

    Install codex-log-sqlite-guard from https://github.com/tsetsugekka/codex-log-sqlite-guard.

You can also copy the skill directory manually:

    cp -R codex-log-sqlite-guard ~/.codex/skills/

The installed skill directory should contain:

    codex-log-sqlite-guard/
      SKILL.md
      scripts/codex_log_sqlite_guard.py

## Example Prompts

    Use codex-log-sqlite-guard to check whether Codex is still high-frequency writing logs_2.sqlite.

    Check whether ~/.codex/logs_2.sqlite added new rows in the last minute.

    Calculate logs_2.sqlite size and free disk space first, then tell me whether backup is recommended.

    Install the trigger on the logs table, verify the writes stopped, then ask me to manually restart Codex and verify again.

    After a Codex update, check whether the trigger is still effective.

    The high-frequency writes have stopped. Compact logs_2.sqlite and tell me whether old backups can be deleted.

## Direct Script Usage

The helper script can also be run directly from the skill directory:

    python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
    python3 scripts/codex_log_sqlite_guard.py capacity
    python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
    python3 scripts/codex_log_sqlite_guard.py install-trigger --no-backup
    python3 scripts/codex_log_sqlite_guard.py vacuum
    python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
    python3 scripts/codex_log_sqlite_guard.py drop-trigger

Use `--db PATH` only when the target database is not the default `~/.codex/logs_2.sqlite`.

## Safety Notes

  * The workflow starts with read-only diagnosis and does not modify `~/.codex/logs_2.sqlite` before user confirmation.
  * The trigger approach is a SQLite-layer workaround, not an upstream Codex source-code fix.
  * The trigger is stored inside the user's own `logs_2.sqlite`; Codex updates do not always remove it, but read-only verification is recommended after every update.
  * When a restart is needed, the skill asks the user to manually quit and reopen Codex Desktop. It does not kill or restart Codex by itself.
  * Backup temporarily consumes roughly another database-sized file. No-backup mode is faster but cannot restore the pre-mitigation database contents.
  * `VACUUM` should run only after `MAX(id)`, row count, WAL size, and WAL mtime are confirmed stable.
  * Before deleting backups, explain that `DROP TRIGGER` remains possible, but the pre-mitigation database contents cannot be restored.
  * Do not commit `logs_2.sqlite`, backup databases, WAL/SHM files, private Codex logs, or conversation data to a public repository.

## Repository Structure

    codex-log-sqlite-guard/
      SKILL.md
      agents/openai.yaml
      scripts/codex_log_sqlite_guard.py
    README.md
    README.zh.md
    README.ja.md

## Languages

  * English: `README.md`
  * 中文：`README.zh.md`
  * 日本語：`README.ja.md`

