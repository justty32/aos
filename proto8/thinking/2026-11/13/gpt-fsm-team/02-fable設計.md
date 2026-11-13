# fable 設計（原樣保留）：astra 指揮 sol 的 agent-fsm 實作隊（fable 只讀 01-備料，11-13 晚交稿）

← [入口](../gpt-fsm-team.md)｜上一份 [01-備料](01-備料.md)｜下一份 [03-opus細化](03-opus細化.md)

> 以下是 fable 回覆全文，一字未改（只把轉義的角括號還原）。opus 的修正、對到實際檔案、驗掉的「待驗」在 [03-opus細化](03-opus細化.md)；兩者不同時以 03 為準。

# gpt 實作隊設計（agent-fsm 版，astra 指揮 sol）

> 全部依備料推得，沒有實跑。標「待驗」的是備料沒寫到的行為，開工前要先試。

## 0. 一句話結論

Claude 隊長（opus）起一隻 astra，astra 用 `subagent` 開 sol 照工單寫碼，深度到 sol 為止，第一輪一次只開一隻。兩個角色各用一份新定義，把 self、def、events 整包拿掉，再用一支 `before_tool` 守門 hook 管寫入範圍和 astra 能對 sol 做的事。gpt 隊不 commit、不改設計；做完寄信，Claude 自己重驗、審 diff、commit。

## 1. 隊形

```
使用者
 └ 頂層 Claude（調度，只放行）
    └ opus 隊長（出細化圖紙、起樹、審 diff、commit）
       └ astra 指揮 ×1（定義 gpt-lead，包 astra-medium）
          └ sol 工人 ×1，穩了再 ×2（定義 gpt-worker，包 sol-high）
             └ （不准再生）
```

- **誰開誰**：推薦 opus 起 astra、astra 用 `subagent add` 開 sol。
  - 理由：只有母子之間有 `ask`／`say`／`listen` 和 rm，這才叫「指揮」。
  - 不選「Claude 把 sol 也開好、astra 只寄信」：astra 管不了 sol 的生死，每分鐘才提醒一次的信箱也太慢。
- **幾隻**：第一輪 1 隻 sol、工單一張一張做。跑通後才開到 2 隻，而且只限檔案清單完全不重疊的工單。
  - 理由：只有 main 一個分支、不開 worktree，兩隻同時改同一個工作區沒有隔離。
- **terra**：第一輪不上。雜活量少，多一個角色多一份要驗的權限。
- **深度**：sol 的定義沒有 subagent 包，生不了孫。astra 的 `max_subagents` 設 2。

## 2. 派工與回報

**隊夾**：放在 repo 外、不進版控，位置由隊長定，例如 `<某處>/teams/<批號>/`。放 repo 外是為了讓 `git status` 只看得到工人改的碼。內容：

- `blueprint.txt`：一行，寫圖紙在 repo 裡的路徑。圖紙本體對 gpt 隊唯讀。
- `tickets/T01.md…`：工單，astra 寫。
- `status.md`：進度表，astra 每收一張就更新。astra 掛了，換一隻也能從這裡接手。
- `inbox/`：給 Claude 的信箱路徑（信可以寄到路徑）。

**Claude → astra**：起 astra 時設一句 goal（history 空時 goal 就是第一句題目）：「照 `<隊夾>/blueprint.txt` 指的圖紙做完，全部工單驗收後寄 DONE 到 `<隊夾>/inbox`」。圖紙內容一律走檔案，不塞進訊息。

**astra → sol**：先把工單寫成檔，再 `subagent add` 一隻 sol，用 `ask` 交一句「照 `<工單路徑>` 做，做完照回報格式回答」。

- sol 用 `--history task`，每封新訊息都會把前文切掉。所以返工訊息必須自帶全部線索：工單路徑＋退件理由。
- `ask` 預設等 600 秒，工單常常更久。逾時時間能不能調大待驗；不能就改 `say`，然後反覆 `listen`。

**工單格式**：

```
# T03 <標題>
圖紙：<檔>#<節>
要做：<逐條>
可動的檔：<清單>      其他一律不動
驗收指令：<指令> → 預期 <結果>
完成定義：<可檢查的條件>
圖紙沒寫或有矛盾：停手，回報 BLOCKED，不要自己決定
```

**sol 回報**（就是它最後那句不帶工具的回答）：

```
STATUS: DONE | BLOCKED | FAILED
改了：<檔清單>
跑了：<指令> → <結果摘要>
沒做：<…>
疑問：<…>
```

**astra 驗收**，三項都過才收，且不信 sol 的自述：

1. 自己跑工單上的驗收指令。
2. `git status`／`git diff --stat`，確認改動的檔都在「可動的檔」清單內。
3. 讀 diff，對照圖紙那一節逐條看。

不過就退件，最多返工 2 輪。

**astra → Claude**：寄信到 `<隊夾>/inbox`。

| status | 什麼時候寄 |
|---|---|
| DONE | 全部工單收完 |
| BLOCKED | 圖紙沒寫、寫錯、或工單返工 2 輪仍不過；`decide` 欄寫清楚要誰決定什麼 |
| NEEDS-USER | 只有使用者能給的東西：額度、權限 |
| FAILED | 環境壞了、做不下去 |

信裡 `outputs`＝改動檔清單＋`status.md` 路徑，`not_done`＝沒收的工單。

## 3. 何時停

- **sol**：一張工單一隻，返工沿用同一隻，驗收過了 astra 立刻 `subagent rm`。agent-fsm 不會自己退，一定要母收。
- **astra**：寄出 DONE／BLOCKED／FAILED 後把 goal 標完成，停在 idle。由 Claude 讀完信後 rm。rm 母會不會連子一起收待驗，所以 Claude 收尾要看一眼 `ctl ls`。
- **防繞圈，四道**：
  1. `--max-tool-calls`：sol 80、astra 300，寫在各自定義的 `fsm.json`。
  2. astra 的 goal 提醒：連 10 次沒動其他工具就自動 paused。
  3. 每寄件人額度（見 6）。
  4. Claude 這邊的看門腳本有總時限（見 8）。
- astra 不用 `--history task`：信箱提醒也算新訊息，會把它的前文切掉。astra 用完整 history，進度另記在 `status.md`。

## 4. 角色 × 權限

兩份新定義（從 agent-fsm 複製後由人或隊長手改；`fsm.json`、`hooks.json` 工具改不了）。

| 包 | astra（gpt-lead） | sol（gpt-worker） |
|---|---|---|
| look、index、gadgets、todo | 開 | 開 |
| change | 開，hook 限只能寫隊夾 | 開，hook 限只能寫工作區，擋 `.git/` |
| delete | 整包關 | 只留 trash，同樣過 hook |
| shell | 開 `shell`（跑驗收、看 diff）；`run_python` 關 | 同左 |
| json／jsonx | 開，會寫檔的幾支一樣過路徑檢查（哪幾支待查） | 同左 |
| mailbox | 開 | 關（回報走 ask 的回答） |
| goal | 開 | 關（第一輪靠 astra 驗收，不靠自報） |
| subagent | 只留 `subagent`；`agents_ctl`、`fork` 關 | 整包關 |
| self | 整包關 | 整包關 |
| def | 整包關 | 整包關 |
| events | 整包關 | 整包關 |
| commit／push | 不准 | 不准 |
| 腦 | 固定 `astra-medium` | 固定 `sol-high` |

**四個特別洞怎麼堵**：

- **self 包能把工具加回來** → 整包從定義拿掉。agent 自己動不了定義的 `$override`。
- **def 包能造新定義** → 整包拿掉。
- **`self_hook` 能關自己的 hook** → events 整包拿掉。
- **母能改子的工具、hook、腦** → 這是最大的洞。astra 的守門 hook 檢查 `subagent` 的參數：
  - 只放行 `add`（`def` 必須是 `gpt-worker`、不准帶 `auto_restart`）、`ask`、`say`、`listen`、`history`、`rm`。
  - `op` 是 `tools`、`llm`、`system`、`hook` 一律攔下。

**守門 hook（一支腳本，兩種角色各一份設定）**：

- 寫檔類工具：路徑先解成真實路徑（防符號連結），不在允許的根目錄下就退 10，路徑含 `.git/` 也退 10。
- hook 攔下時印一句人話，例如「工人不 commit，請回報給指揮」，腦才知道為什麼被擋。

**shell 是真正守不住的地方**：hook 只看得到指令字串，擋不住繞路。兩層做法：

1. **首選**：`shell` 外面包 `aos-sandbox`，照 `shell-boxed` 例子（只寫得到工作區與自己 stack、斷網），再加一條 `.git` 唯讀，等於舊 codex 的 `workspace-write`。
   - 家機沒有 `s6-softlimit`，而且設定寫壞會靜默不套。
   - 所以開工前必須實測：在沙箱裡試寫工作區外、試 `git commit`，兩個都要失敗才算數。
2. **備援**（沙箱起不來時）：hook 用字串黑名單擋 `git commit/push/reset/checkout/restore/stash/clean/rebase`、`sudo`、`curl/wget`。
   - 這只防手滑，不是安全邊界。
   - 真正的底線是：不 push、開工前工作區乾淨、Claude 審全部 diff。

**commit**：照舊規矩，gpt 隊誰都不 commit，隊長 commit，push 要使用者說。

## 5. astra 的界線

- **能做**：把圖紙切成工單、開／收 sol、跑驗收、退件、寫進度、寄信。
- **不能做**：
  - 自己寫產品碼（hook 讓它只寫得到隊夾）。
  - 改圖紙。
  - 補圖紙沒寫的決定。
  - 還原別人的改動。
  - 換模型、改 sol 的權限。
- **圖紙沒寫或寫錯**：那張工單停手，寄 BLOCKED，`decide` 欄寫「缺什麼、有哪幾種做法」，不選。跟它無關的工單可以繼續。Claude 這邊（fable／opus）改圖紙檔後，用 `aos-agent say` 叫它接著做。
- **切工單算不算設計**：只准照圖紙已有的分段切，順序照圖紙的相依關係。圖紙沒分段就回報，不自己分。

**跟舊規矩的關係**：

| 舊規矩 | 這次 |
|---|---|
| gpt 不參與設計決策 | 照舊，寫進兩份 `system.txt`，並由 BLOCKED 流程落實 |
| 審查只挑實作錯與跟圖紙不符 | 照舊，astra 的驗收就是這個範圍 |
| 工人不 commit、隊長 commit | 照舊，astra 也算工人這一邊 |
| astra 只派圖像、創意類 | **衝突**。使用者今晚親口指定 astra 當指揮，等於開了例外，條文要補（見 10-1） |
| 每隊最多兩個 CLI 程序 | agent-fsm 不是 nodejs，但精神沿用：astra 1＋sol 最多 2 |

## 6. 端點與模型

在 llm kernel 的 `kernel.json` 新增兩包，既有的 `sol`、`terra`、`luna` 不動：

| 包名 | 模型 | slots | 用途 |
|---|---|---|---|
| `astra-medium` | `chatgpt-gpt-6-astra-medium` | 1 | 指揮 |
| `sol-high` | `chatgpt-gpt-6.1-sol-high` | 2 | 工人 |

- **effort 理由**：astra 不做設計，只切單和對照，medium 夠；它貴 3 倍又帶完整 history，不往上開。sol 寫碼用 high。不順再各調一級，一級一包。
- 網址 `http://127.0.0.1:4000/v1`。
- **範本對不上**：出廠範本的 terra 寫 `chatgpt-gpt-6.1-terra`，使用者給的清單是 `chatgpt-gpt-5.6-terra`。這次不用 terra，但要記一筆。
- **額度**（起手值，是我估的，跑完第一輪照實際用量調）：

| 對象 | 上限 |
|---|---|
| 寄件人 astra | 400 次／天 |
| 寄件人每隻 sol | 300 次／天 |
| 包 `astra-medium` | 500 次／天 |
| 包 `sol-high` | 1000 次／天 |

- token 上限第一輪先不設，只記用量。
- 到頂用報錯（`BudgetMissing`），不用 `spent: wait`：wait 沒期限，會變成無聲卡死。
- 額度的 key 是寄件人的 stack 路徑，每開一隻新 sol 路徑都不同，能不能用樣式或上層夾一次設定待驗。不行就只靠每包上限。

## 7. 失敗與卡住

| 狀況 | 處理 |
|---|---|
| 腦掛（BrainFailed／proxy 掛） | 兩種角色都不設 `auto_restart`。sol 掛：astra 重開一隻重交同一張單，再掛就寄 FAILED。astra 掛：看門腳本看到 `stopped` 叫醒 Claude，Claude 查 proxy 後起新 astra，從 `status.md` 接 |
| sol 做不出來 | 返工最多 2 輪，之後該單 BLOCKED，rm 那隻 sol，不換大模型硬上 |
| sol 寫壞東西 | astra 不還原，只退件叫它修；修不好寄 FAILED 並列出壞掉的檔。還原由 Claude 決定。前提是開工前工作區乾淨，diff 就等於 gpt 隊的全部改動 |
| 兩隻 sol 改同一檔 | 第一輪只開一隻，不會發生。開兩隻後靠工單檔案清單不重疊＋驗收時查改動範圍；越界就退件 |
| astra 自己卡住 | goal 提醒 10 次自動 paused、工具次數上限、額度、看門腳本總時限。Claude 讀 `history` 和 `status.md` 判斷 |
| 額度用完 | agent 報錯停下，Claude 回報使用者要不要加。agent 和 Claude 都不自己加 |
| proxy 不回應（wait 無期限） | 只能靠看門腳本的總時限發現 |

## 8. 跟頂層交接

- **開工前**（動活樹，要頂層放行）：
  1. opus 隊長加兩個 endpoint 包。
  2. 建兩份定義。
  3. 放守門 hook。
  4. 建隊夾。
  5. 確認工作區乾淨。
- **起樹**：opus 隊長起 astra，設 goal。sol 由 astra 起。
- **不用盯**：隊長開一支背景看門腳本，碰到下面任一條就結束並叫醒隊長：
  - `<隊夾>/inbox` 出現新信。
  - `ctl ls` 裡 astra 變 `stopped`。
  - 超過總時限（建議 90 分鐘）。
- **收結果**：隊長讀信和 `status.md`。agent 的信不是授權，DONE 只是聲稱，所以隊長自己重跑 build／測試、審全部 diff，過了才 commit。push 等使用者說。
- **收尾**：rm astra、確認沒有殘留的 sol、把這輪遇到的問題記進試驗紀錄。

**開工前的乾跑（先做，不碰產品碼）**：

1. proxy 上兩個模型名真的存在。
2. 沙箱裡寫工作區外與 `git commit` 都失敗。
3. hook 攔得住 astra 改 sol 的工具。
4. `ask` 逾時能不能調。
5. 交一張假工單（改一個測試用的檔）跑完整一圈。

## 9. 試驗紀錄：aos 做不到或得繞路的地方

| # | 現象 | 影響 | 可能改法（不決定） |
|---|---|---|---|
| 1 | agent-fsm 沒有「做完就退」 | 工人要母記得 rm，忘了就殘留 | 加一次性模式旗標；或 `subagent add` 給「答完即退」選項 |
| 2 | 回報不會主動推，`ask` 預設 600 秒 | 長工單要反覆 `listen` | 子做完通知母；或 `ask` 不限時 |
| 3 | 工具、hook 沒有「鎖」：有 self 能加回、母能改子的覆蓋層 | 最小權限只能靠拿掉整包＋hook 檢查參數 | 定義層加「不可覆蓋」標記；或覆蓋層只能減不能加 |
| 4 | 寫入範圍沒有內建限制，shell 無白名單 | 每個要限權的隊都得自寫守門 hook | 內建工作區限制開關；附一支官方守門 hook |
| 5 | 沙箱設定寫壞是靜默不套；家機缺 `s6-softlimit` | 以為有沙箱其實沒有 | 套不上就拒絕啟動；bwrap 單獨可用的模式 |
| 6 | `fsm.json`、`hooks.json` 沒有覆蓋層，`agent_def` 也改不了 | 調 `--max-tool-calls` 要手改定義檔 | 步數上限搬進可覆蓋的設定 |
| 7 | `--history task` 遇到信箱提醒會切掉前文 | 指揮角色不能用，只好帶完整 history（貴） | 系統提醒不算新任務起點 |
| 8 | agent 端沒有 effort 欄位 | 一個 effort 一個包，包表膨脹 | 開欄位；或包名帶參數 |
| 9 | 額度沒有金額上限、寄件人不驗身分 | 3 倍價的 astra 只能用次數估 | `cost` 參與計算；寄件人由 kernel 認定 |
| 10 | wait 等腦沒期限，沒有 429／5xx 重試 | proxy 卡住就無聲卡死 | wait 加期限；端點程式加退避重試 |
| 11 | 頂層不是 agent，沒有新信通知 | 得自寫看門腳本輪詢 | 提供「等信」阻塞指令（`aos-mailbox wait`） |
| 12 | 信箱 `from` 自報、誰都能寄 | 工人可冒名寄信給頂層，所以這次把 sol 的信箱關了 | 寄件人由系統填 |
| 13 | 單一分支、無工作區隔離 | 多工人平行只能靠檔案清單自律 | 每工單的檔案擁有權交給 hook 檢查；或工人各有複本再合併 |
| 14 | 子的環境變數來自 daemon、`envs` 明文落盤 | 不方便把工單範圍這類參數傳給子的 hook | 母可傳不落盤的參數 |
| 15 | 出廠 endpoint 範本沒有 astra、terra 型號對不上 | 每台機器都要手補 | 範本跟上模型清單 |
| 16 | 只走 chat completions | 帶思考的模型跨工具呼叫時思考內容能否保留，備料沒寫（待驗） | 視實測決定要不要支援別的介面 |

## 10. 要使用者裁的題

1. **astra 當指揮 vs 舊條文「astra 只派圖像、創意類」**
   - A：開窄例外「astra 可當 gpt 實作隊指揮，不寫碼、不設計」。
   - B：指揮改用 sol-high，astra 維持舊用途。
   - **推薦 A**：是你今晚指定的，試了才知道值不值 3 倍價；第一輪記下 astra 的用量再回頭看。
2. **shell 的防線**
   - A：先把沙箱弄通（可能要裝 `s6-softlimit` 或改成只用 bwrap）才開工。
   - B：先用 hook 黑名單跑，沙箱另案。
   - **推薦 A**：乾跑時實測；若一小時內弄不通就退到 B，並把第一輪任務限在小範圍。
3. **動活樹還是另起試驗樹**
   - A：在 `~/aos-home` 只做新增（兩個包、兩份定義），不改既有東西。
   - B：另起一棵樹。
   - **推薦 A**：新增不影響現有 agent。另起一棵樹要花多少工夫，備料沒有，我不知道。
4. **第一輪做什麼**
   - A：挑一件小、有明確測試、改動檔少的真工作。
   - B：直接上大件。
   - **推薦 A**：這輪主要目的是抓 aos 的問題，任務小才分得清是隊形的問題還是題目的問題。
5. **同時幾隻 sol**
   - A：先 1 隻，跑通兩輪後開到 2 隻。
   - B：一開始就 2 隻。
   - **推薦 A**。
6. **額度起手值**（第 6 節那組數字）
   - 照用，或你給數字。
   - **推薦照用**，第一輪後按實際用量調。
7. **sol 要不要開 goal**（舊 codex 規矩是要設完成條件）
   - A：第一輪不開，靠 astra 獨立驗收。
   - B：開，讓它自己被提醒做到完。
   - **推薦 A**：goal 提醒跟 `ask` 的回答怎麼互動沒驗過。先看 sol 會不會「做一半說做完」，會的話第二輪改 B。
