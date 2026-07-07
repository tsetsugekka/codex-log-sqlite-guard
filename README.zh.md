# Codex Log SQLite Guard

Codex Log SQLite Guard 是一个面向 Codex Desktop 本地日志异常写入问题的 Codex skill。它把一次实际排查出来的 `~/.codex/logs_2.sqlite` 高频 TRACE 写盘问题，整理成可复用、可验证、可回滚的安全流程。

这个仓库只保存公开安全的诊断流程和辅助脚本，不包含个人日志、数据库备份、Codex 会话内容或私有路径数据。

## 当前包含的 skill

### `codex-log-sqlite-guard`

诊断并缓解 Codex Desktop 对 `~/.codex/logs_2.sqlite` 的高频 TRACE 日志写入。它会先做只读诊断，确认 `logs_2.sqlite`、`logs_2.sqlite-wal`、`logs` 表、`MAX(id)`、WAL 大小和 mtime 是否持续变化；确认受到影响后，再引导用户选择是否备份、安装可回滚的 SQLite trigger、手动重启 Codex 后复验，并在写入停止后执行 `VACUUM` 缩小数据库。

〖依赖〗必需 — Python 3 标准库 `sqlite3`、可访问的 `~/.codex/logs_2.sqlite`。

〖协同调用〗无。

适用场景：

  * 检查 Codex Desktop 是否仍在持续写入 `logs_2.sqlite` 或 `logs_2.sqlite-wal`。
  * 判断本地 SQLite 日志库是否因为 TRACE 日志而异常膨胀。
  * 在修改数据库前计算文件大小、WAL/SHM 大小、磁盘剩余容量和备份成本。
  * 给 `logs` 表安装可回滚 trigger，拦截后续日志 INSERT。
  * 手动重启 Codex 后再次验证 trigger 是否仍然生效。
  * 高频写入停止后执行 `VACUUM`，并引导清理不再需要的备份。
  * Codex 更新后重新做只读诊断，判断是否需要重新执行修复。

## 工作流

| 阶段 | 操作 | 是否修改文件 |
| --- | --- | --- |
| 只读诊断 | 检查数据库大小、WAL/SHM、最近日志级别、`COUNT`、`MAX(id)`、WAL mtime | 否 |
| 容量评估 | 计算备份成本、磁盘剩余容量和 `VACUUM` 可回收空间 | 否 |
| 备份选择 | 向用户解释备份与不备份的取舍，并等待确认 | 否 |
| trigger 缓解 | 创建 `codex_block_logs_insert`，拦截 `logs` 表后续 INSERT | 是 |
| 重启复验 | 要求用户手动退出并重新打开 Codex Desktop，再只读采样 | 否 |
| 数据库压缩 | 在确认不再增长后执行 `VACUUM` 和 WAL truncate | 是 |
| 备份清理 | 列出备份并说明删除后果，用户确认后再删除 | 是 |

## 安装

在 Codex 里直接发送这个仓库链接，并说明要安装这个 skill：

    请从 https://github.com/tsetsugekka/codex-log-sqlite-guard 安装 codex-log-sqlite-guard。

也可以手动复制 skill 目录：

    cp -R codex-log-sqlite-guard ~/.codex/skills/

安装后的 skill 目录结构应包含：

    codex-log-sqlite-guard/
      SKILL.md
      scripts/codex_log_sqlite_guard.py

## 示例请求

    用 codex-log-sqlite-guard 检查 Codex 是否还在高频写 logs_2.sqlite。

    帮我确认 ~/.codex/logs_2.sqlite 最近 1 分钟有没有新增。

    先计算 logs_2.sqlite 大小和磁盘剩余空间，再告诉我是否建议备份。

    给 logs 表安装 trigger，确认停止写入后让我手动重启 Codex 再复验。

    Codex 更新后帮我确认这个 trigger 是否还有效。

    现在高频写入已经停了，帮我缩小 logs_2.sqlite 并确认备份能不能删除。

## 直接运行脚本

如果不通过 Codex skill，也可以在 skill 目录里直接运行脚本：

    python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
    python3 scripts/codex_log_sqlite_guard.py capacity
    python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
    python3 scripts/codex_log_sqlite_guard.py install-trigger --no-backup
    python3 scripts/codex_log_sqlite_guard.py vacuum
    python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
    python3 scripts/codex_log_sqlite_guard.py drop-trigger

只有在不是默认数据库路径时，才需要额外传入 `--db PATH`。

## 安全说明

  * 默认先做只读诊断，不会在用户确认前修改 `~/.codex/logs_2.sqlite`。
  * trigger 方案是 SQLite 层 workaround，不是 Codex 上游源码修复。
  * trigger 写在用户自己的 `logs_2.sqlite` 里；Codex 更新后通常不一定失效，但应重新做只读诊断。
  * 需要重启时，skill 会要求用户手动完全退出并重新打开 Codex Desktop，不会主动 kill/restart Codex。
  * 备份会临时多占用约一个数据库大小的磁盘空间；不备份则无法完整恢复修复前数据库内容。
  * `VACUUM` 只应在确认 `MAX(id)`、行数、WAL 大小和 WAL mtime 停止增长后执行。
  * 删除备份前必须向用户说明：删除后仍可 `DROP TRIGGER`，但无法恢复修复前数据库内容。
  * 不要把 `logs_2.sqlite`、备份数据库、WAL/SHM 文件、私有 Codex 日志或会话内容提交到公开仓库。

## 仓库结构

    codex-log-sqlite-guard/
      SKILL.md
      agents/openai.yaml
      scripts/codex_log_sqlite_guard.py
    README.md
    README.zh.md
    README.ja.md

## 语言

  * English: `README.md`
  * 中文：`README.zh.md`
  * 日本語：`README.ja.md`

