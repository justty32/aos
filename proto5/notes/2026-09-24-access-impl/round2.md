← [第一輪報告](README.md)｜教程：[04b](../../tutorials/04b-access-and-tool-admin.md)｜審查：[任務書](review2-task.md)／[astra 結果](review2-astra.md)

# 權限牆第二輪：照使用者五題裁決改（2026-09-24）

一句話：**read／write 這些檔案工具現在看得到 access.json 掛進來的全部資料夾，唯讀的寫不進去；家裡沒有 access.json 就不跑工具，並告訴你要打哪一行。**

## 四點各做了什麼（第 5 點照舊，沒動）

1. **檔案工具的根＝整個 `/work`**
   - 牢裡多一個環境變數 `AOS_TOOL_FENCE=/work`，read／write／edit／ls／grep／find 用它決定碰得到的範圍；相對路徑照舊從起點（例如 `/work/ws`）算，所以 `../ref/x`、`/work/ref/x` 都讀得到。`/work` 以外照舊 `OutsideRoot`。
   - aos-jail 掛完之後把牢的根改成唯讀（bwrap 的 `--remount-ro /`）：寫得進去的只剩可寫的掛點和 `/tmp`。以前直接寫 `/work/x` 會「成功」，但牢一收檔就不見了，現在會直接失敗。
   - 寫進唯讀的地方回新代號 `ReadOnly`，訊息會列出哪些資料夾可寫（見下面的真跑畫面）。
   - bash 本來就碰得到整個 `/work`，現在兩邊一樣。
   - 舊家裝的 base 是程式副本，要 `tools add base --force` 重裝才會換成新行為（教程有寫）。
2. **換起點或改表不自動告訴模型**：程式沒動。教程 04b 和兩份 access 規範都補了一句「換完記得 `aos-agent say` 告訴它一聲」。
3. **`access set` 的路徑照打指令時殼所在的資料夾算**：程式沒動。教程 04b、`tools-manage.md`、`access.md` 都補了提醒：要指家裡的資料夾，就寫絕對路徑或 `~` 開頭。
4. **有工具的家沒有 access.json 就不跑工具**
   - 送工具時，要關牢的工具（沒寫 `_jail: false` 的）一律不送，代號 `NoAccess`。模型看到的話裡有要打的那一行指令，tick 的 log 也印同一行。
   - `aos-agent check` 從 warn 改成 bad。`access ls`、`tools ls` 的說明也跟著改。
   - **`aos-agent init` 現在直接寫一份預設 access.json**（只掛 `workspace/`、起點 ws、不上網）。不這樣做的話，新家內建的 `date` 工具第一次就會被擋。這一條是我補的，裁決裡沒明講，請你看一下。
   - 舊家怎麼升級寫進了教程 04b〈舊家升級〉和 `spec/agent/access.md`：跑那一行 `mkdir -p … && aos-agent access set ws … --cwd --target …`，再用 `check` 確認。
   - 如果 `init` 的家已經有表，`tools add base --root X` 不會去改表；起點跟 X 不一樣時，會多印一行 `要讓工具在 X 工作：aos-agent access set ws X --target 家`。
   - 舊測試裡「沒有表也能跑」的假設都改掉了：
     - 整合測試：這台有 bwrap 時真的關牢跑，沒 bwrap 才明寫 `_jail: false`；
     - 專測「不包牢時 inst 長怎樣」「`_meta` 解不開」「argv[0] 找不找得到」的幾條：明寫 `_jail: false`，並註明原因；
     - 原本那條 `test_no_access_file_keeps_old_inst` 改成測「拒跑」。

## 真跑（LiteLLM `localhost:4000` 的 deepseek-chat，沒碰 LM Studio／ollama）

場地在 scratchpad 的 `r2/`（下面用 `$S` 代替），daemon＋kernel 開 3 顆一般 cpu 加 1 顆 llm。

**第 4 點**：`old` 是 `init` 之後把 access.json 刪掉，模擬以前的家。
```
$ aos-agent check --target old
bad  access: 沒有 access.json：date 這 1 支工具都不會跑（NoAccess）。先建一份：mkdir -p $S/old/workspace && aos-agent access set ws $S/old/workspace --cwd --target $S/old
$ aos-agent say "現在幾點？用 date 工具查。" --wait 300 --target old
[結果 date] 工具 date 沒有執行：這個 agent 還沒設定工具能碰哪些資料夾（沒有 access.json），被 aos 擋下（NoAccess）。這不是你能修的，也不要改用別的工具繞過；請告訴使用者：「工具 date 沒有 access.json 不能跑，請先跑 mkdir -p $S/old/workspace && aos-agent access set ws $S/old/workspace --cwd --target $S/old，再叫我一次」。
模型回：工具 date 沒有 access.json 不能跑，請先跑 `mkdir -p … && aos-agent access set ws … --cwd --target …`，再叫我一次。
log：aos-agent: NoAccess: 工具 date 沒送：家裡沒有 access.json（有工具的家要先設定工具能碰哪些資料夾）；跑：mkdir -p … && aos-agent access set …
```
照那一行跑完，`check` 的 access 三行都是 ok；再 `say` 一次，模型回「現在是 2026-09-24 17:54:44。」

**第 1 點**：`amy` 是 `init` 之後裝 base，另外用 `access set ref $S/ref --ro` 掛一個唯讀資料夾。
```
[呼叫 ls] {"path": "/work"}              → ref/  ws/
[呼叫 read] {"path": "../ref/doc.txt"}   → 參考資料：第二個資料夾裡的內容。
[呼叫 write] {"path": "../ref/new.txt"}  → 工具 write 失敗（exit 1）：{"ok": false, "error": "ReadOnly", "message": "cannot write ../ref/new.txt: that folder is read-only (mounted read-only by the user in access.json). Writable folders: /work/ws. …"}
[呼叫 write] {"path": "ok.txt"}          → created ok.txt (2 bytes)
模型總結：1 成功、2 成功、3 因唯讀失敗、4 成功。
```
主機上 `ref/` 裡只有 `doc.txt`，`amy/workspace/` 多了 `ok.txt`。（這段是在修 astra 那條之前跑的，所以訊息還是舊版；現在的訊息改成 `that folder is on a read-only mount (usually mounted read-only by the user in access.json)`。）
清場：daemon、kernel 都停了，`pgrep -fa scratchpad/r2` 只撈到 pgrep 自己的殼。

## 數字

- 全測：1470 → 在分支上 1484；rebase 到 main（436690d，多了 T1、T3 隊的測試）之後是 **49 個檔、1593 條，全部通過**。T3 的 `tools/files`、`tools/wf` 各帶一份 base `_common.py` 副本，已同步成新版。
- 新測試檔 `test_access_round2.py` 有 10 條，其中 6 條真的跑 bwrap。`test_agent_access.py` 從 53 條變 57 條。另外改了 7 個測試檔的假設（上面第 4 點）。

## astra 審查（gpt-6-astra，唯讀，審到 9b7ca32）

**必修 5 條，5 條都修了：**
1. 舊版在沒有表的時候寫好了 inst、還沒送出就崩潰；升級後重送會跳過檢查，工具就不關牢地跑了。→ 現在只要還沒送出，不管 inst 在不在都先檢查一次；補了測試，也確認拿掉修正時這條測試會失敗。
2. 沒有表的時候，`check` 提早結束，漏印 `_jail: false` 的警告。→ 先印警告再結束。
3. 教你打的那行指令沒幫路徑加引號，家的路徑有空白就會拆錯。→ 改用 `shlex.quote`，補了測試。
4. 不關牢時碰到主機本來就唯讀的檔案系統，也說成「access.json 設的」。→ 分開講，補了測試。
5. 規範和教程裡還有幾句舊的或會誤導的話（`self .` 掛的其實是殼所在的資料夾、`--root` 不會改牢裡的起點、舊指令名 `aos-kernel check --agent`）。→ 都對回了。

**建議 3 條，做了 2 條**：教程補「舊家要 `tools add base --force`」；init 的測試改成真的過一次權限檢查。沒做的是「更多真牢邊界測試，以及 bwrap 探測別用受測的 build_argv」。

## 沒做的

- 第 5 題（`tools rm` 改寫成 `only`）照裁決不動。
- 第 2、3 題的程式不動，只補文件。
- 上面沒做的那條 astra 建議。
- base.json 只改了 read、ls 兩支的描述，其他幾支還是寫 project directory。
- 已經裝進各個家的舊 base 副本不會自動更新，要手動重裝。
