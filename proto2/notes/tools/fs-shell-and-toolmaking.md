# 工具包：fs（讀寫檔＋跑指令）與 toolsmith（自己造工具）

一句話：**fs 讓 agent 動得了檔案跟指令，toolsmith 讓它把常做的事變成自己的新工具。**

底下是建議稿，不是已落地的東西。現在的 `packs/shell.py` 只有一個 `sh`，建議直接擴成 `packs/fs.py`。

## 一、fs 包：read / write / ls / edit / sh / sh_bg

共通規則：路徑相對於**世界資料夾**（`ctx.world`）；輸出一律走 `ctx.truncate()`，超過 4000 字截掉並註明。

### read
`read(path, start=1, count=200)`。回 `{path, start, end, total, text}`。
大檔就是**行數範圍**：預設只給前 200 行，回覆裡寫「總共 N 行，還有 M 行沒看，用 start 續讀」。
模型什麼時候用：想看一個檔的內容就用它，不要用 `sh cat`——這個會告訴你檔多長、看到哪。

### write
`write(path, text, append=false)`。`append=false` 是**整檔覆蓋**，`true` 是**追加**。
父資料夾不在就自己建。回 `{path, bytes, mode}`。
模型什麼時候用：要產一個新檔、或整檔重寫時用；只改幾個字用 edit 比較省。

### ls
`ls(path=".", all=false)`。不遞迴，一行一個：名字、是不是資料夾、大小、改動時間。
超過 200 個就截並說還有幾個。`all=true` 才列點開頭的。
模型什麼時候用：不知道有什麼檔、或想確認自己剛寫的檔在不在，先 ls 再說。

### edit（建議要做）
`edit(path, old, new)`。**old 在檔裡剛好出現一次才換**，0 次或多次就回錯誤，叫模型把 old 抄長一點。
回 `{path, line}`（改在第幾行）。
理由：不做的話模型只能整檔重寫，大檔一來一回很貴，這一格也會變長。

### sh
`sh(command, stdin=null, timeout=60)`。cwd＝**世界資料夾**。逾時上限 120 秒，預設 60。
`stdin` 有給就當標準輸入餵進去。回 `{exit, stdout, stderr}`，兩邊各截 4000 字。
逾時就砍掉，回 `{exit: null, stderr: "跑超過 N 秒被砍掉了，長指令請改用 sh_bg"}`。
模型什麼時候用：查東西、跑小程式、git 之類**幾秒內會好**的事。會跑很久的不要用它，一格會卡住。

### sh_bg（長時間指令：另開一個世界）
照使用者的想法：**跑很久的事不該卡在一格裡**，所以把它變成一個新世界，向 daemon 要一個鐘。

`sh_bg(command, note="")` 做的事：
1. 建 `<home>/jobs/<時間戳>/`，指令寫進 `cmd.sh`，`note` 寫進 `note.txt`。
2. 寫它的 `.aos/inst`，就一行：
   `sh cmd.sh > out.txt 2> err.txt; echo $? > exit.txt; aos-user say <父世界> --source job-<id> < 一段摘要; aos-daemon unregister <job 絕對路徑> --no-wait`
3. `aos-daemon register <job 路徑> --no-wait` 要一個自己的鐘；沒 `AOS_DAEMON_DIR` 就只建資料夾，回一句「自己開 `aos-loop <路徑> --keep-inst`」。
4. 那個鐘的第一格就把指令從頭跑到尾（卡多久都沒關係，卡的是它自己的鐘），跑完把結果寫回**父 agent 的 `inbox/job-<id>/`**，然後把自己的鐘退掉。
5. 父 agent 下次 `idle` 掃信箱就看到「你有新信：job-xxx 1 封」，用 mailbox 那包去讀。

回給模型的是 `{job: "job-<id>", dir: ..., message: "在跑了，好了會寄信到你的信箱"}`。
模型什麼時候用：編譯、下載、跑測試、任何**可能超過一分鐘**的事，一律 sh_bg，然後去做別的，別空轉等它。

## 二、toolsmith 包：自己造工具

最土的兩條路：①往自己 `tools.json` 的 `tools[]` 加一條 shell-command 工具；②往 `<home>/packs/` 寫一個 `.py`。

**存哪**：一律自己的 home（`<home>/tools.json`、`<home>/packs/<名字>.py`），**不碰全域 `proto2/packs/`**。
全域那些是出廠內建，一個 agent 不該改到別人的。

**什麼時候生效**：`aos-agent exec` 每一格開頭都重讀 `tools.json`、重載工具包（包的快取用 mtime 當 key，改了就自動重載），
所以**下一格才生效**——這一格模型看到的工具清單是這一格開頭算好的。要當格驗，用 `tool_try`。

### tool_add
`tool_add(name, description, parameters, command)`——加一條 shell 工具進 `<home>/tools.json` 的 `tools[]`。
`parameters` 給 `{"type":"object","properties":{...},"required":[...]}`；模型給得不完整就自動包成 object。
`command` 是一句 shell，**參數 JSON 從 stdin 進去**，cwd＝世界資料夾（跟現有 `tools[]` 規則一樣）。
同名已存在就回錯，叫它先 `tool_remove`。
另一種用法：只給 `pack="名字"`，就是把 `<home>/packs/<名字>.py` 或內建的那包**打開**（加進 `packs[]`），不用 command。
模型什麼時候用：同一串指令打第三次的時候，就把它變成一個工具，之後一句話就叫得動。

### tool_list
`tool_list()`——列現在有哪些工具：名字、來自哪一包（或 `custom`）、一句描述，自製的多印 `command`。
模型什麼時候用：造工具前先看有沒有重複、刪之前先確認名字。

### tool_remove
`tool_remove(name)`——只能刪 `tools[]` 裡自製的。要刪包裡的就回一句「那是 <包名> 包的，要關整包用 `tool_remove(pack="<包名>")`」。
模型什麼時候用：工具寫壞了、或用不到了就刪掉，工具清單每格都要送給 LLM，越短越省。

### tool_try
`tool_try(name, args)`——**當格**就照 `command` 跑一次自製工具，回 `{exit, stdout, stderr}`，不用等下一格。
模型什麼時候用：`tool_add` 完馬上 `tool_try` 一次，確定它會動再去用。

## 三、安全與範圍：先不做沙箱

現在**故意不擋**的（撞到再說）：

- `rm -rf`、`sudo`、任何毀滅性指令——`sh` 就是原封不動丟給 shell。
- 跨世界寫檔——路徑沒有關在世界資料夾裡，`../../` 出去改別人的檔完全可以。
- 改自己的 `.aos/inst`、`system-prompt.json`、`state.json`、`tools.json`——它可以改掉自己的心跳、人格、狀態機進度。
- `tool_add` 的 `command` 就是一句 shell，等於多一條沒有逾時限制的 `sh`。
- 網路：`curl`／`pip install` 都通。
- 唯一的限制只有 `sh` 的逾時跟輸出截斷，那是為了不卡格、不爆 context，不是為了安全。

安全靠外圈：daemon 的 `--config {"user": "bob"}` 換身份、或整個世界放在容器裡。這層以後再做。

## 四、跟現有東西怎麼接

- `packs/shell.py` → 改成 `packs/fs.py`（`sh` 留著，加 read/write/ls/edit/sh_bg）。
- 新增 `packs/toolsmith.py`。
- `examples/agent/agent/tools.json` 的 `packs` 改成 `["mailbox", "fs", "self", "kids", "toolsmith"]`。
- `aos_agent.py`：`Ctx` 加三個小把手——`ctx.put_mail(source, text)`（已有函式，掛上去就好）、`ctx.jobs_dir()`、`ctx.tools_path()`。
- `aos-user say` 加一個 `--source`（預設 `user`），job 世界要用它把結果寄回父的信箱。
- 新資料夾：`<home>/jobs/<id>/`（每個長指令一個世界）、`<home>/packs/`（自己寫的工具包）。
- README 加一節「工具包」，把 fs／toolsmith 各兩三行寫上去。

## 五、現在故意不做的邊緣狀況

- 路徑沙箱、指令白名單、要人審批。
- 檔案鎖：兩個工具同時寫 `tools.json` 會互相蓋掉。
- `read` 的二進位檔／編碼偵測（一律當 UTF-8，讀不動就回錯誤）。
- `edit` 的多處取代、regex、模糊比對。
- `sh` 的互動輸入、tty、環境變數設定、換 cwd。
- job 的取消、逾時、上限、`jobs/` 的清理——只會越堆越多。
- job 世界只跑一格就自己退鐘，中途機器重開就沒人收尾。
- 自製工具的名字沒檢查會不會撞到工具包的（撞了工具包贏，模型會很困惑）。
- 輸出大檔只截斷，不會存成檔再給路徑。

## 六、要使用者拍板

1. `shell.py` 直接擴成一包 `fs`（讀寫檔＋跑指令都在裡面），還是 fs／shell 分兩包？**建議一包**，反正一起開。
2. `edit` 做不做？**建議做**，最土的「old 剛好出現一次才換」，省下整檔重寫的 token。
3. 長指令走「子世界＋daemon 要鐘」還是直接 `nohup &`？**建議子世界**，跟你的世界觀一致，也不會逃出 daemon 管束。
4. 自製工具存自己 home 還是全域 `packs/`？**建議 home**，全域那份當出廠內建，agent 不准改。
5. `spawn` 要不要順手把 `<home>/packs/` 抄一份給小孩？**建議要**，不然抄過去的 `tools.json` 會提到小孩載不到的包。
