# Codex Log SQLite Guard

Codex Log SQLite Guard は、Codex Desktop が `~/.codex/logs_2.sqlite` に高頻度でローカルログを書き込み続ける問題を診断し、緩和するための Codex skill です。実際に確認された `TRACE` ログ churn の調査結果を、再利用可能で検証しやすく、元に戻せる手順として整理しています。

このリポジトリには公開しても安全なワークフローと補助スクリプトのみを含めています。個人ログ、SQLite バックアップ、Codex の会話内容、プライベートなローカルパス情報は含みません。

## 含まれる skill

### `codex-log-sqlite-guard`

Codex Desktop による `~/.codex/logs_2.sqlite` への高頻度 `TRACE` 書き込みを診断し、緩和します。最初に読み取り専用で `logs_2.sqlite`、`logs_2.sqlite-wal`、`logs` テーブル、`MAX(id)`、WAL サイズ、WAL mtime を確認します。問題が確認された場合は、バックアップ方針を確認し、可逆的な SQLite trigger を作成し、Codex Desktop の手動再起動後に再検証し、書き込み停止を確認してから `VACUUM` で DB を圧縮します。

〖依存〗必須 — Python 3 標準ライブラリ `sqlite3`、および `~/.codex/logs_2.sqlite` へのアクセス。

〖連携 skill〗なし。

利用場面：

  * Codex Desktop が `logs_2.sqlite` または `logs_2.sqlite-wal` に書き込み続けているか確認する。
  * ローカル SQLite ログ DB が `TRACE` ログで肥大化しているか判断する。
  * DB を変更する前に、ファイルサイズ、WAL/SHM サイズ、空き容量、バックアップに必要な容量を確認する。
  * `logs` テーブルに可逆的な trigger を作成し、以後のログ INSERT を止める。
  * ユーザーが Codex Desktop を手動で再起動した後、trigger が有効か再確認する。
  * 高頻度書き込みが止まった後に `VACUUM` を実行し、不要になったバックアップ削除を案内する。
  * Codex 更新後に読み取り専用診断を行い、再実行が必要か判断する。

## ワークフロー

| フェーズ | 操作 | ファイル変更 |
| --- | --- | --- |
| 読み取り専用診断 | DB サイズ、WAL/SHM、最近のログレベル、`COUNT`、`MAX(id)`、WAL mtime を確認 | なし |
| 容量確認 | バックアップ容量、空き容量、`VACUUM` で回収できる可能性を推定 | なし |
| バックアップ判断 | バックアップあり/なしの利点とリスクを説明し、ユーザー確認を待つ | なし |
| trigger 緩和 | `codex_block_logs_insert` を作成し、`logs` への新規 INSERT を止める | あり |
| 再起動後検証 | ユーザーに Codex Desktop の手動終了・再起動を依頼し、再度サンプリング | なし |
| DB 圧縮 | 増加停止を確認してから `VACUUM` と WAL truncate を実行 | あり |
| バックアップ整理 | バックアップを列挙し、明示確認後のみ削除 | あり |

## インストール

Codex にこのリポジトリ URL を送り、skill のインストールを依頼します。

    https://github.com/tsetsugekka/codex-log-sqlite-guard から codex-log-sqlite-guard をインストールして。

手動で skill ディレクトリをコピーすることもできます。

    cp -R codex-log-sqlite-guard ~/.codex/skills/

インストール後の skill ディレクトリには次のファイルが含まれます。

    codex-log-sqlite-guard/
      SKILL.md
      scripts/codex_log_sqlite_guard.py

## 依頼例

    codex-log-sqlite-guard を使って、Codex がまだ logs_2.sqlite に高頻度で書き込んでいるか確認して。

    ~/.codex/logs_2.sqlite に最近 1 分で新規行が増えたか確認して。

    先に logs_2.sqlite のサイズと空き容量を計算し、バックアップすべきか教えて。

    logs テーブルに trigger を作成し、書き込み停止を確認してから、手動再起動後に再検証して。

    Codex 更新後、この trigger がまだ有効か確認して。

    高頻度書き込みが止まったので、logs_2.sqlite を圧縮し、バックアップを削除してよいか確認して。

## スクリプトを直接使う

Codex skill 経由ではなく、skill ディレクトリで補助スクリプトを直接実行することもできます。

    python3 scripts/codex_log_sqlite_guard.py diagnose --sample-seconds 15
    python3 scripts/codex_log_sqlite_guard.py capacity
    python3 scripts/codex_log_sqlite_guard.py install-trigger --backup-dir ./work
    python3 scripts/codex_log_sqlite_guard.py install-trigger --no-backup
    python3 scripts/codex_log_sqlite_guard.py vacuum
    python3 scripts/codex_log_sqlite_guard.py list-backups --dir ./work
    python3 scripts/codex_log_sqlite_guard.py drop-trigger

対象 DB がデフォルトの `~/.codex/logs_2.sqlite` ではない場合のみ、`--db PATH` を指定します。

## 安全上の注意

  * 最初は読み取り専用診断を行い、ユーザー確認前に `~/.codex/logs_2.sqlite` を変更しません。
  * trigger 方式は SQLite レイヤーの workaround であり、Codex 本体の公式なソースコード修正ではありません。
  * trigger はユーザー自身の `logs_2.sqlite` に保存されます。Codex 更新後も残ることがありますが、更新後は読み取り専用診断を推奨します。
  * 再起動が必要な場合、skill はユーザーに Codex Desktop の手動終了・再起動を依頼します。Codex を自動で kill/restart しません。
  * バックアップは一時的に DB と同程度の追加容量を使います。バックアップなしは速い一方、修正前 DB 内容へ完全には戻せません。
  * `VACUUM` は `MAX(id)`、行数、WAL サイズ、WAL mtime が安定していることを確認してから実行します。
  * バックアップ削除前には、`DROP TRIGGER` は可能だが修正前 DB 内容は復元できないことを説明します。
  * `logs_2.sqlite`、バックアップ DB、WAL/SHM、プライベートな Codex ログや会話内容を公開リポジトリにコミットしないでください。

## リポジトリ構成

    codex-log-sqlite-guard/
      SKILL.md
      agents/openai.yaml
      scripts/codex_log_sqlite_guard.py
    README.md
    README.zh.md
    README.ja.md
    LICENSE

## 言語

  * English: `README.md`
  * 中文：`README.zh.md`
  * 日本語：`README.ja.md`

## ライセンス

MIT
