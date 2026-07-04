# Codex Log SQLite Guard

<p align="center">
  <strong>诊断、拦截、验证、压缩并清理 Codex <code>logs_2.sqlite</code> TRACE 日志高频写入。</strong>
</p>

<p align="center">
  <a href="#中文">中文</a> |
  <a href="#english">English</a> |
  <a href="#日本語">日本語</a>
</p>

<p align="center">
  <code>Codex Skill</code> · <code>SQLite WAL</code> · <code>Manual restart required</code> · <code>Backup-aware</code>
</p>

---

## 中文

### 这是什么

**Codex Log SQLite Guard** 是一个可分享的 Codex skill，用来诊断并安全缓解 Codex Desktop 对下面这个 SQLite 日志库的高频 `TRACE` 写入：

```text
~/.codex/logs_2.sqlite
```

它适用于 Codex Desktop 持续把本地 TRACE/调试日志写入 SQLite/WAL，导致 `logs_2.sqlite` 变大、WAL 持续更新、磁盘高频写入的情况。

### 它会做什么

| 阶段 | 目的 | 安全策略 |
|---|---|---|
| 诊断 | 检查文件大小、最近日志级别、行数、`MAX(id)`、WAL 大小和 mtime | 只读 |
| 容量评估 | 估算磁盘剩余空间、备份成本、`VACUUM` 可回收空间 | 只读 |
| 缓解 | 安装可回滚的 SQLite trigger，拦截 `logs` 表后续插入 | 需要用户明确确认 |
| 验证 | 安装后采样，并要求用户手动重启 Codex 后再次采样 | 缓解后只读验证 |
| 压缩 | 高频写入停止后执行 `VACUUM` 并截断 WAL | 需要用户明确确认 |
| 清理 | 找出不再需要的备份，引导用户确认是否删除 | 需要用户明确确认 |

### 为什么需要用户手动重启？

这个 skill 明确要求 Codex 告诉用户“请手动完全退出并重新打开 Codex Desktop”，而不是由 Codex 自己 kill/restart 进程。

这样可以避免打断用户当前工作，也让进程控制留在用户手里。

### 安装

下载或 clone 这个仓库后，把 skill 文件夹复制到 Codex skills 目录：

```bash
cp -R codex-log-sqlite-guard ~/.codex/skills/
```

skill 文件夹是：

```text
codex-log-sqlite-guard/
```

安装后可以这样问 Codex：

```text
Use $codex-log-sqlite-guard to check whether Codex is high-frequency writing TRACE logs to logs_2.sqlite, mitigate safely if needed, verify after restart, compact the database, and clean up unneeded backups.
```

### 直接运行脚本

也可以直接运行内置脚本：

```bash
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py capacity
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py vacuum
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py list-backups --dir ./work
```

### 备份选择

缓解前，skill 会先计算 SQLite 文件大小和磁盘剩余容量，再向用户解释是否建议备份：

| 选择 | 优点 | 代价 |
|---|---|---|
| 先备份 | 出问题时回滚路径最好 | 临时多占用大约一个数据库大小的空间 |
| 不备份 | 更快、更省空间 | 仍可删除 trigger，但不能恢复修复前的数据库内容 |

### Codex 更新后是否需要重做

这是一个可回滚的 SQLite trigger workaround，不是 Codex 上游源码级修复。trigger 保存在用户的 `~/.codex/logs_2.sqlite` 数据库里，所以如果 Codex 更新后仍沿用同一个数据库和 `logs` 表，通常不需要重新安装。

每次更新 Codex 后建议先做只读诊断。只有在更新重建了 `logs_2.sqlite`、改变了 `logs` 表结构、删除了 trigger、恢复了旧数据库，或 `MAX(id)`/WAL 又开始高频增长时，才需要重新执行修复。

### 回滚

如果只是取消拦截后续日志插入：

```bash
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py drop-trigger
```

如果保留了修复前备份，并且想完整恢复数据库，需要先手动关闭 Codex Desktop，再恢复备份文件。不要在 Codex 运行时覆盖活动 SQLite 文件。

### 安全说明

- 缓解动作不会删除现有日志。
- trigger 可以回滚。
- 只有在确认高频写入停止后，才应该执行 `VACUUM`。
- 备份文件只有在最终验证通过、并且用户明确确认后才应该删除。

---

## English

### What This Is

**Codex Log SQLite Guard** is a shareable Codex skill for diagnosing and safely mitigating high-frequency `TRACE` log writes to:

```text
~/.codex/logs_2.sqlite
```

It is designed for the failure mode where Codex Desktop continuously appends detailed local logs to SQLite/WAL files, causing rapid disk writes and a large `logs_2.sqlite` database.

### What It Does

| Phase | Purpose | Safety posture |
|---|---|---|
| Diagnose | Read file sizes, recent log levels, row counts, `MAX(id)`, WAL size, and WAL mtime | Read-only |
| Capacity check | Estimate disk free space, backup cost, and likely `VACUUM` savings | Read-only |
| Mitigate | Install a reversible SQLite trigger that blocks new rows in `logs` | Requires explicit user approval |
| Verify | Sample before and after a manual Codex Desktop restart | Read-only after mitigation |
| Compact | Run `VACUUM` and truncate WAL after writes are stopped | Requires explicit user approval |
| Cleanup | Identify obsolete backups and ask before deletion | Requires explicit user approval |

### Why Manual Restart?

The skill deliberately tells the user to manually quit and reopen Codex Desktop. It should not kill or restart Codex by itself unless the user explicitly asks for that behavior.

This avoids interrupting active work and keeps process control in the user's hands.

### Install

Clone or download this repository, then copy the skill folder into your Codex skills directory:

```bash
cp -R codex-log-sqlite-guard ~/.codex/skills/
```

The skill folder is:

```text
codex-log-sqlite-guard/
```

After installation, ask Codex:

```text
Use $codex-log-sqlite-guard to check whether Codex is high-frequency writing TRACE logs to logs_2.sqlite, mitigate safely if needed, verify after restart, compact the database, and clean up unneeded backups.
```

### Direct Script Usage

The bundled helper script can also be run directly:

```bash
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py capacity
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py vacuum
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py list-backups --dir ./work
```

### Backup Decision

Before mitigation, the skill should compute the SQLite size and free disk space, then explain the tradeoff:

| Choice | Benefit | Cost |
|---|---|---|
| Backup first | Best rollback path if something goes wrong | Temporarily consumes roughly another database-sized file |
| No backup | Faster and uses less disk | You can drop the trigger, but cannot restore the old DB contents |

### Codex Updates

This is a reversible SQLite trigger workaround, not an official upstream source-code fix. The trigger is stored inside the user's `~/.codex/logs_2.sqlite` database, so a Codex app update usually does not require reinstalling it if the same database and `logs` table are preserved.

Re-run the read-only diagnosis after updating Codex. Reinstall the trigger only if the update rebuilt `logs_2.sqlite`, changed the `logs` table schema, removed the trigger, restored an old database, or high-frequency `MAX(id)`/WAL growth returns.

### Rollback

To stop blocking inserts:

```bash
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py drop-trigger
```

If you kept a pre-mitigation backup and want a full database restore, close Codex Desktop manually first, then restore the backup file. Do not overwrite active SQLite files while Codex is running.

### Safety Notes

- The mitigation does not delete existing logs.
- The trigger is reversible.
- `VACUUM` should run only after high-frequency writes are confirmed stopped.
- Backup files should be deleted only after final verification and explicit user confirmation.

---

## 日本語

### これは何か

**Codex Log SQLite Guard** は、Codex Desktop が次の SQLite ログ DB に対して高頻度に `TRACE` ログを書き込み続けているかを診断し、安全に緩和するための共有可能な Codex skill です。

```text
~/.codex/logs_2.sqlite
```

Codex Desktop が詳細なローカルログを SQLite/WAL に継続的に書き込み、`logs_2.sqlite` が肥大化したり、WAL が頻繁に更新されたりするケースを想定しています。

### 何をするか

| フェーズ | 目的 | 安全方針 |
|---|---|---|
| 診断 | ファイルサイズ、最近のログレベル、行数、`MAX(id)`、WAL サイズ、WAL mtime を確認 | 読み取り専用 |
| 容量確認 | 空き容量、バックアップに必要な容量、`VACUUM` で回収できる見込みを推定 | 読み取り専用 |
| 緩和 | `logs` テーブルへの新規 INSERT を止める可逆的な SQLite trigger を作成 | ユーザーの明示確認が必要 |
| 検証 | 緩和後と Codex Desktop 手動再起動後にサンプリング | 緩和後は読み取り検証 |
| 圧縮 | 書き込み停止確認後に `VACUUM` と WAL truncate を実行 | ユーザーの明示確認が必要 |
| 後片付け | 不要になったバックアップを提示し、削除前に確認 | ユーザーの明示確認が必要 |

### なぜ手動再起動が必要か

この skill は、Codex 自身がプロセスを kill/restart するのではなく、ユーザーに Codex Desktop を手動で完全終了して再起動してもらう方針です。

作業中のセッションを不用意に中断せず、プロセス制御をユーザー側に残すためです。

### インストール

このリポジトリを clone またはダウンロードし、skill フォルダを Codex の skills ディレクトリにコピーします。

```bash
cp -R codex-log-sqlite-guard ~/.codex/skills/
```

skill フォルダは次の場所です。

```text
codex-log-sqlite-guard/
```

インストール後、Codex に次のように依頼します。

```text
Use $codex-log-sqlite-guard to check whether Codex is high-frequency writing TRACE logs to logs_2.sqlite, mitigate safely if needed, verify after restart, compact the database, and clean up unneeded backups.
```

### スクリプトを直接使う

内蔵スクリプトを直接実行することもできます。

```bash
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py capacity
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py vacuum
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py list-backups --dir ./work
```

### バックアップ判断

緩和前に、skill は SQLite ファイルサイズとディスク空き容量を計算し、バックアップするかどうかの判断材料を提示します。

| 選択 | 利点 | コスト |
|---|---|---|
| 先にバックアップ | 問題発生時の復旧パスが最も安全 | 一時的に DB と同程度の追加容量を使う |
| バックアップなし | 速く、容量を節約できる | trigger は削除できるが、修正前 DB の内容には戻せない |

### Codex 更新後について

これは可逆的な SQLite trigger による workaround であり、Codex 本体の公式なソースコード修正ではありません。trigger はユーザーの `~/.codex/logs_2.sqlite` データベース内に保存されるため、Codex の更新後も同じ DB と `logs` テーブルが維持されていれば、通常は再インストール不要です。

Codex 更新後は読み取り専用診断を再実行してください。`logs_2.sqlite` が再作成された、`logs` テーブル構造が変わった、trigger が削除された、古い DB を復元した、または `MAX(id)`/WAL の高頻度増加が戻った場合のみ、修正を再実行します。

### ロールバック

新規 INSERT のブロックだけを解除する場合:

```bash
python3 codex-log-sqlite-guard/scripts/codex_log_sqlite_guard.py drop-trigger
```

修正前バックアップを使って DB 全体を戻す場合は、先に Codex Desktop を手動で終了してください。Codex が起動中のままアクティブな SQLite ファイルを上書きしないでください。

### 安全上の注意

- 緩和処理は既存ログを削除しません。
- trigger は削除して元に戻せます。
- `VACUUM` は高頻度書き込みが停止したことを確認してから実行してください。
- バックアップ削除は最終確認が終わり、ユーザーが明示的に同意した後だけ行ってください。

