---
name: codex-log-sqlite-guard
description: Diagnose and mitigate Codex Desktop high-frequency TRACE writes to ~/.codex/logs_2.sqlite. Use when a user asks whether Codex is writing logs_2.sqlite, logs_2.sqlite-wal, TRACE logs, SQLite logs, disk/SSD wear, Codex log churn, Codex disk high-frequency writes, or wants a safe workflow to stop the writes, compact the SQLite file, verify after restarting or updating Codex, and clean up temporary backups.
---

# Codex Log SQLite Guard

使用本 skill 安全诊断并缓解 Codex Desktop 对 `~/.codex/logs_2.sqlite` 的高频日志写入。这个流程会触碰 Codex 的本地状态文件，所以必须保守执行：先只读诊断，再确认备份策略，再安装可回滚的 SQLite trigger，重启后复验，最后再压缩和清理备份。

## 核心规则

- 使用用户的语言回复；中文用户优先用中文。
- 每个阶段开始前，先告诉用户你要做什么、为什么做、是否会修改文件。
- 不要主动 kill、重启或强制退出 Codex，除非用户明确要求。需要重启时，告诉用户手动完全退出并重新打开 Codex Desktop，然后等待用户确认。
- 先做只读诊断。用户确认前，不要修改 `~/.codex/logs_2.sqlite`。
- 备份或 `VACUUM` 前，先计算 SQLite/WAL/SHM 文件大小和磁盘剩余空间，并说明空间是否足够。
- 询问是否备份时，必须说明两种选择：
  - 备份：回滚路径更完整，但会临时多占用大约一个数据库大小的磁盘空间。
  - 不备份：更快、更省空间，但只能删除 trigger，无法恢复修复前数据库内容。
- 安装 trigger 后，必须在当前会话内验证一次，再要求用户手动重启 Codex 后验证一次。
- trigger 方案是可回滚 workaround，不是 Codex 上游源码修复。Codex 更新后通常不会失效，因为 trigger 保存在用户 SQLite 数据库里；但更新后必须重新做只读验证。
- 最终验证无问题后，列出不再需要的备份，并询问用户是否删除。没有明确确认前，不要删除备份。

## 脚本

使用 `scripts/codex_log_sqlite_guard.py`。路径相对当前 `SKILL.md` 解析。

常用命令：

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
python3 scripts/codex_log_sqlite_guard.py capacity
python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
python3 scripts/codex_log_sqlite_guard.py install-trigger --no-backup
python3 scripts/codex_log_sqlite_guard.py vacuum
python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
python3 scripts/codex_log_sqlite_guard.py drop-trigger
```

只有当用户不是默认数据库路径时，才加 `--db PATH`。

## 执行流程

### 1. 只读诊断

先告诉用户：

```text
我会先做只读检查：确认 logs_2.sqlite/WAL/SHM 大小、logs 表状态、最近 TRACE 写入量，并短时间采样 COUNT、MAX(id)、WAL 大小和 mtime 是否持续增长。不会修改文件。
```

运行：

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
```

满足以下多数条件时，可判断受到影响：

- 采样期间 `MAX(id)` 或行数增长。
- `logs_2.sqlite-wal` 大小或 mtime 持续变化。
- 最近日志大多是 `TRACE`。
- 最新日志时间贴近当前时间。

如果没有受到影响，停止并说明不需要修复。

### 2. 容量评估和备份选择

告诉用户：

```text
接下来我会计算 SQLite 文件大小、WAL/SHM 大小、VACUUM 预计可回收空间，以及磁盘剩余容量。然后我会说明是否建议先备份。
```

运行：

```bash
python3 scripts/codex_log_sqlite_guard.py capacity
```

如果剩余空间足够容纳备份和压缩临时空间，建议备份。如果空间紧张，说明备份可能失败或占用过多磁盘，并询问用户是否不备份继续。

用户选择备份或不备份前，不要继续修改数据库。

### 3. 安装 trigger 缓解

告诉用户：

```text
我会给 logs 表安装一个可回滚的 SQLite trigger，拦截后续 INSERT。它不会删除现有日志；回滚方式是 DROP TRIGGER。安装后会 checkpoint/truncate WAL，然后采样验证。
```

如果用户选择备份：

```bash
python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
```

如果用户选择不备份：

```bash
python3 scripts/codex_log_sqlite_guard.py install-trigger --no-backup
```

然后再次诊断：

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 30
```

当 `MAX(id)`、行数、WAL 大小和 WAL mtime 停止增长时，说明缓解生效。

### 4. 手动重启 Codex 后验证

告诉用户：

```text
现在需要你手动完全退出并重新打开 Codex Desktop。请完成后告诉我，我会再次只读采样，确认重启后 trigger 仍然生效。
```

用户确认后运行：

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 30
```

重启瞬间可能有少量启动 WAL 活动或行数清理。只要 `MAX(id)` 不增加，并且 WAL 在采样窗口内停止变化，就可视为正常。

### 5. 说明 Codex 更新后的持久性

告诉用户：

```text
这个方案是 SQLite trigger workaround，不是 Codex 上游源码修复。trigger 写在 ~/.codex/logs_2.sqlite 里，所以 Codex 更新后通常仍会保留；但如果更新重建了 logs_2.sqlite、改了 logs 表结构、主动删除 trigger，或你恢复/删除了数据库，就需要重新执行修复。每次更新 Codex 后建议先做只读验证。
```

如果用户问更新后是否要重装，先运行只读诊断：

```bash
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 30
```

只有当诊断显示 trigger 缺失，或 `MAX(id)`/WAL 又开始增长时，才重新安装 trigger。

### 6. 压缩数据库

只有在缓解生效且手动重启后验证通过时，才压缩数据库。

告诉用户：

```text
现在高频写入已经停止。我会执行 VACUUM 缩小 logs_2.sqlite，并 truncate WAL。这个步骤会写入数据库，需要足够临时磁盘空间。
```

运行：

```bash
python3 scripts/codex_log_sqlite_guard.py vacuum
python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 20
```

报告压缩前后大小，以及 `freelist_count` 是否接近 0。

### 7. 备份清理

列出备份：

```bash
python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
```

告诉用户：

```text
当前库完整、trigger 生效、重启后验证通过。如果你不打算回滚到修复前状态，这些备份可以删除；删除后仍可通过 DROP TRIGGER 取消拦截，但无法恢复修复前数据库内容。
```

只有在用户明确确认后，才删除备份文件。删除时也要删除同名备份的 `-wal` 和 `-shm` sidecar 文件。

## 回滚

如果只是取消拦截后续插入：

```bash
python3 scripts/codex_log_sqlite_guard.py drop-trigger
```

如果用户保留了修复前备份，并想完整恢复数据库，必须先要求用户手动关闭 Codex Desktop。然后再用备份替换 `~/.codex/logs_2.sqlite`，并移除活动库对应的 `-wal`/`-shm` 文件。没有明确确认前，不要执行完整恢复。

