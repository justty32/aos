← [notes 索引](../README.md)｜設計稿：[agent-access 提案](../2026-09-24-agent-access/README.md)｜教程：[04b 限制 agent 能碰什麼、管理工具](../../tutorials/04b-access-and-tool-admin.md)

# 權限牆＋工具管理 CLI：實作報告（2026-09-24）

「工具大開發時代」要先做好的權限設定。照 H 隊提案的六個預設答案做完了：agent 的工具只碰得到你列出來的資料夾，你也能用指令或文字編輯器加工具、刪工具、改名、管權限。

| 檔 | 內容 |
|---|---|
| 本檔 | 做了什麼、長什麼樣、真跑、數字、沒做的、要你拍的 |
| [progress.md](progress.md) | 定案（兩隊共同約定）與分段進度 |
| [real-run.md](real-run.md) | 真跑兩輪的完整畫面（deepseek-chat） |
| [review-task.md](review-task.md)／[review-astra.md](review-astra.md) | astra 唯讀審查 |

## 做了什麼

1. **`access.json`**：放在 agent 家，寫「工具看得到哪些資料夾」。沒有這個檔＝照舊不關牢。`tools add base` 發現家裡沒有這個檔，會順手建一份只給 `workspace/` 的。
2. **牆**：aos-agent 每次送工具時，自動在指令前面接 `aos-jail`，用 bwrap 開一個小世界：只掛表裡的資料夾（牢裡叫 `/work/<名字>`），環境變數清乾淨，預設不能上網。改表**下一批**才生效，不用重 start。
3. **工具管理**：`tools ls/add/rm/alias/unalias`。`rm` 只解除這個 agent 的登記，不刪任何檔。
4. **權限管理**：`access ls/set/rm/cwd/net`，其實就是改 `access.json` 那幾行，改完把整張表印出來。
5. **給人改的格式**：`info.json`、`access.json` 都寫成縮排 2 格的 JSON，打錯了 `aos-agent check` 會指出是哪一格（例如 `mounts.ws`）。

## access.json 長這樣

```json
{
  "mounts": {
    "ws": "../workspace",
    "ref": {"$opt": "ro", "$val": "~/docs"}
  },
  "cwd": "ws",
  "net": false
}
```

- `mounts`：左邊是牢裡的名字，右邊是真的資料夾。相對路徑從 agent 家算起，可以寫 `~`，也可以用指示詞（`$env`、`$ref`、`$fmt`）。`{"$opt": "ro", …}` 表示唯讀。
- `cwd`：工具從哪個資料夾開始，沒寫就是 `/work`。`net`：`true` 打開網路（跟主機共用，連得到 localhost）。
- **有些東西工具永遠寫不到**：`info.json`、`access.json`、工具檔與程式、`state.json`、`input/`、`work/`、aos 自己的程式。可寫的資料夾蓋到它們，那一批工具就不跑（`AccessUnsafe`）。所以 agent 自己的家只能唯讀掛（`access set` 會自動改成 ro，並說明原因）。
- 工具在 info.json 裡改名：`{"$opt": {"as": {"bash": "sh"}, "only": ["read", "bash"]}, "$val": "tools/base.json"}`。

## 指令一覽（都是 `--target DIR`，不給就用目前資料夾）

```
aos-agent tools ls      [--json]                      列工具：名字、原名、來源檔、關不關牢、池
aos-agent tools add     NAME|DIR|FILE.json [--as NEW | --as OLD=NEW,…] [--only a,b] [--root DIR] [--force]
                                                      內建包／工具包資料夾＝複製進家；其他資料夾或單一檔＝原地引用（共用）
aos-agent tools rm      NAME                          解除登記，檔留在原地（會印出位置）
aos-agent tools alias   NAME NEW  ／ tools unalias NEW
aos-agent access ls     [--json]                      表＋cwd＋net＋bwrap 在不在
aos-agent access set    NAME PATH [--ro|--rw] [--cwd] PATH 照你的殼的目前資料夾算
aos-agent access rm     NAME ／ access cwd NAME ／ access net on|off
aos-jail                                              aos-agent 自動用，平常不用自己叫
```

`tools` 和 `access` 的寫入指令共用一把鎖（`<家>/.admin.lock`），同時下兩個指令不會互相蓋掉。access.json 壞了（JSON 語法錯、格式不對），所有寫入指令都拒絕，檔一個字都不動，並說哪裡壞。

## 真跑（LiteLLM deepseek-chat，兩輪都過）

場地：amy 的家、家外的 `workspace/`、`secret/x.txt`、`other/`；開 daemon 之前故意 `export OPENAI_API_KEY=sk-fake-should-not-leak`。

```
[結果 ls]   hello.txt  notes.md
[結果 read] 工具 read 失敗（exit 1）：{"ok": false, "error": "OutsideRoot", "message": "../secret/x.txt is outside the project directory /work/ws"}
[結果 bash] 工具 bash 失敗（exit 1）：cat: ../secret/x.txt: No such file or directory
[結果 bash] 工具 bash 失敗（exit 1）：cat: /tmp/…/access-impl/secret/x.txt: No such file or directory     ← 主機上檔在，牢裡看不到
env 只有 8 個名字：沒有 OPENAI_API_KEY、AOS_KERNEL_HOME、AOS_LLM_CONFIG
```

- 不重啟就換：`aos-agent access set other ../other --cwd`，下一句 `pwd` 就是 `/work/other`，`ls` 看到 `other-only.txt`。
- 網路：`access net on`，curl localhost:4000 拿得到模型清單；`net off` 時連不上（`curl: (7) Failed to connect`）。
- 修正後複跑：用 `$env` 讀 `OPENAI_API_KEY` 的工具被擋成 `EnvUnsafe`，`grep -r sk-fake amy/` 找不到。
- 清場：`pgrep -fa scratchpad/access-impl` 是空的。完整畫面在 [real-run.md](real-run.md)。

## 數字

- 全測：1343 → **1447**（分支上）；rebase 到 main（ce8f25c，多了 talk 的測試）後是 **1470 條全綠**。新測試檔：`test_agent_access.py`（53 條）、`test_jail.py`（13 條，真的跑 bwrap）、`test_agent_tools_manage.py`（31 條）、`test_access_more.py`（7 條）。
- astra 必修 **8 條，修了 8 條**：
  - aos-jail 改用絕對路徑，aos 自己的程式算進「寫不到」的清單；
  - 符號連結本身也保護；
  - 金鑰類的 `$env` 換個名字也擋得住，而且值不會寫進 inst 檔；
  - 兩種指令共用鎖；
  - `access set` 跟送件用同一套檢查；
  - 寫檔前把整份再驗一次；
  - 明寫了但不存在的 access 檔要報錯；
  - state 裡的快照要驗型別。

  建議 4 條做了 3 條，沒做的是「用 barrier 固定順序的安全回歸測試」裡最完整的那部分（實際經 `/proc/*/fd` 的探測）。
- 真跑找到兩個小問題也修了：`check` 事先抓得到會 EnvUnsafe 的工具；被權限牆擋下時，給模型的話改成「這不是你能修的，請告訴使用者去跑 aos-agent check」。

## 沒做的（明講）

- **擋不住的**（寫在 [spec/agent/access.md](../../spec/agent/access.md)）：
  - 資料夾裡的 Unix socket；
  - `net: true` 時連得到的本機服務；
  - 事先建好的硬連結；
  - 檢查之後、下一批之前才被換掉的符號連結；
  - 資源上限（磁碟、記憶體、行程數）；
  - 同一批平行跑的工具互相蓋檔；
  - `_meta` 裡一層層 `$ref` 到的檔收不全。
- **沒 bwrap 的機器**：要關牢的工具一律不跑，不偷偷降級。
- **Claude Code／Codex 這種整支 CLI agent 不進牢**、不換 uid、沒碰 daemon 規範。這三條照調度者轉達的拍板。
- 正在跑的工具不會因為改表被撤權限；要馬上停，只能 `pause`，或等它逾時。
- `listen --last N --show-calls-full` 會從一輪的中間開始印。這是 listen 的舊問題，這次沒動。

## 要你拍的（新）

| # | 題目 | 現在的做法 |
|---|---|---|
| 1 | read／ls 等檔案工具只看得到起點（`cwd`）那個資料夾。同時掛兩個資料夾時，另一個只有 bash 碰得到 | 照舊。另一個做法是把檔案工具的根改成整個 `/work` |
| 2 | 換資料夾或起點時要不要告訴模型（真跑時模型看到 `pwd` 變了，自責了好幾段） | 不告訴。要它知道就 `say` 一句 |
| 3 | `access set` 的路徑照你的殼的目前資料夾算，不照 `--target` 算（真跑踩到一次，錯誤訊息有印出算出來的絕對路徑） | 照殼算（跟一般 CLI 一樣） |
| 4 | 有工具的家卻沒有 access.json（例如只有 init 的 `date` 工具） | 不關牢，`check` 印一行 warn |
| 5 | `tools rm` 從「整個資料夾」那條拿掉一支，會改寫成 `only` 列出其餘的；之後放進資料夾的新工具要自己加 | 照這樣（會印提醒） |
