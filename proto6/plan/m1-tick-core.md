# 第一段：tick 核心

← [plan 入口](README.md)｜正本：[通用 tick](../spec/settled/tick.md)｜格式：[node 協議](../spec/settled/protocol/node.md)

**做完的樣子**：沒有 daemon、git、cgroup、helper 的機器上，`aos-tick --node /絕對路徑` 直接跑一格：同資料夾只能一格、照 `.aos/tasks.json` 依序跑、每項怎麼結束都寫進 `.aos/tick/current.json`、算得出預設上層。這就是 [B-626](../spec/settled/tick.md#b-626核心與系統級任務的界線) 的驗收。

- 由 AI 隊實作、照各步驟驗收試跑，做完交使用者看；每步的「要使用者裁定的點」集中在文末待問。
- Python 3.9、只用標準庫。inst 的解析、驗證、開程序用從 proto5 複製來的 [src/py/lib/](../src/py/README.md)：`aos_inst.load(path, base)`／`aos_inst.load_obj(obj, base)` 讀驗解一份 inst（壞就丟 `InstError`，`str(e)` 是「代號: 白話」），`aos_exec` 開程序。lib 沒有、tick 要自己接的東西寫在步驟 4 的「注意」與步驟 5 的「tick 要自己接」。
- 建議（非定案）：程式放 `proto6/src/py/aos_tick/`，入口 `proto6/src/bin/aos-tick`；測試用 `unittest`。
- 一格的順序（[B-620「一格怎麼走」](../spec/settled/tick.md#b-620任務註冊表照表依序跑)）：取鎖 → 看擋板 → 換紀錄 → 讀表驗表 → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼。下面的步驟大致照這個順序長出來。

## 步驟 1：找資料夾、取鎖

- **要做到**：認出要跑哪個資料夾，對 `.aos/tick.lock` 取非阻塞獨占鎖；拿不到就回 75、什麼都不動。拿到就整格持鎖。
- **spec**：[B-602](../spec/settled/tick.md#b-602同一資料夾一次一格互斥鎖)；argv 見 [P-203](../spec/settled/protocol/node.md#p-203aos-tick-與任意任務程式建議預設未拍板)。
- **做法**：
  - `--node` 可以是資料夾、`.aos/inst.json` 或 `inst.json`，一律正規化成 node 資料夾；省略時用目前目錄。
  - 取鎖是「定位資料夾之後第一件事」；拿不到直接回 75，不重試、不寫紀錄。
  - 鎖 fd 要留給任務繼承（步驟 5 用）。
  - argv 解析、用法錯回 2、鎖檔不存在就建立、`chdir` 到 node 資料夾。
- **要使用者裁定的點**：已裁定（待問 6）：`.aos/` 不存在就直接報錯、不自建。回 2、stderr `config_invalid: …`，不取鎖、不寫紀錄（沒有 `.aos/` 就沒有任務表，照 P-203 碼表「任務表不合法」歸 2；B-602／B-620 沒有更貼的碼）。`.aos/` 在時鎖檔不存在照 B-602 建立。
- **注意**：
  - Python 開的 fd 預設不會傳給子程序；要傳就得明講（`pass_fds` 或設成可繼承），不然任務拿不到鎖。
  - 鎖檔放 `.aos/tick.lock`，**不是**探針原型放的 git 管理目錄。
  - `--node` 指定時要是絕對路徑（node id 的定義，P-002）；不往上層目錄找。
- **驗收**：
  - 同資料夾同時跑兩個（第一格的任務 `sleep 5`）：一個回 75、另一個照跑。
  - 用資料夾路徑跑一格佔著，同時用 `.aos/inst.json` 路徑跑另一格：回 75（同一把鎖）。
  - 資料夾不是 git repo 也拿得到鎖。

## 步驟 2：擋板檔與結束碼骨架

- **要做到**：取鎖後先看 `.aos/tick-blocked`；有就一項都不跑、不寫紀錄、回 1。順便把整格的結束碼（0／1／2／75）和 stderr 代碼的出口定好。
- **spec**：[B-620 停格檔與擋板檔](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；檔名與內容 [P-213](../spec/settled/protocol/node.md#p-213每項結束碼紀錄停格檔與擋板檔建議預設未拍板)；碼表 P-203。
- **做法**：擋板檢查放在取鎖之後、換紀錄之前；擋住時不加 `seq`、不刪停格檔。stderr 統一印 `代碼: 說明`；讀擋板檔的一行原因。
- **要使用者裁定的點**：無。
- **驗收**：先跑一格建出紀錄，再 `echo 壞了 > .aos/tick-blocked`，跑 `aos-tick`：回 1、stderr 有 `blocked: 壞了`、任務沒跑、`current.json` 與 `last.json` 內容不變；刪掉擋板後下一格照常。

## 步驟 3：結束碼紀錄與格數

- **要做到**：每格開頭把 `current.json` 換成 `last.json`，寫一份新的（`seq` 加 1、`ended:false`、`tasks:[]`）；每跑完一項整份重寫；跑完寫 `ended:true` 與整格結束碼。
- **spec**：[B-633](../spec/settled/tick.md#b-633每項結束碼紀錄與格數)；格式 P-213 與 [node-tick-record schema](../spec/protocol/schemas/node-tick-record.schema.json)。
- **做法**：
  - 算 `seq`：有 `current.json` 取它加 1，沒有取 `last.json` 加 1，都沒有是 1；讀不懂的當沒有。
  - 換檔四步照 B-633「開格：換檔」；特別是「沒有 current 卻有 last」要刪掉 last。
  - 每次寫都是「寫暫存檔 → rename」。
  - 紀錄的讀寫小函式、`started_at_ms`、用 schema 核對紀錄的測試輔助。
- **要使用者裁定的點**：無。
- **驗收**（任務表先只放 `true`）：
  - 同資料夾連跑十格，`seq` 從 1 到 10；中間換成 cron 或另一個 shell 跑，照樣接著數。
  - 鎖被占回 75 時兩份紀錄都不變。
  - 用 schema 核對 `current.json` 與 `last.json` 都合格。

## 步驟 4：讀任務表、只驗四件事

- **要做到**：開格讀一次 `.aos/tasks.json`，只驗：合法 JSON、`_metainfo` 是 `aos-tasks` 第 1 版、每項（整份 `$ref` 展開後）是合法 inst、`id` 在表內唯一。不合就整表拒絕、回 2。
- **spec**：[B-620 讀表與「誰驗什麼」](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；[P-202](../spec/settled/protocol/node.md#p-202任務註冊表建議預設未拍板)；[inst](../spec/base/inst.md)。
- **做法**：
  - 只驗這四件，其餘（缺 `kind`、`system.x`、`methods` 形狀）核心**不驗、照跑**。
  - 表壞時：stderr 印 `config_invalid: 哪裡錯`，紀錄寫 `ended:true`、`exit:2`、`tasks:[]`，回 2。紀錄在讀表之前就換好了，所以表壞的格也佔一個 `seq`。
  - 陌生鍵（包括舊的 `group`、`needs`）照收、忽略。
  - 用 `aos_inst.load_obj(項, node 資料夾)` 驗每一項，`str(InstError)` 就是一行說明。
- **要使用者裁定的點**：已裁定（待問 6）：有 `.aos/` 但沒有 `tasks.json` 算表壞，照表壞的做法回 2（紀錄照換、佔一個 `seq`）。
- **注意**：`id`、`kind`、`methods` 不是 inst 的欄位。整份 `$ref` 的項就照 `$ref` 的規則展開（已裁定，見待問 2）。**tick 要自己接**：`load_obj` 只回七個執行欄位，不認得的鍵（`id`、`kind`、`methods`）直接丟掉，也不回原始 `user`；`id` 要 tick 自己拿（整份 `$ref` 的項先用 `aos_directives.resolve_located` 展開頂層再讀），原始 `user` 直接讀項目的字面值。另外 `load_obj` 看到跟目前身分不同的 `user` 會丟 `UserNotGranted`——開格驗表時別讓它把整表打成壞表，先自己判 `user`、再把拿掉 `user` 的項交給 `load_obj`。
- **開格只驗、不留結果**：這一步的展開只為了驗合不合法；驗過的結果不留，跑到那一項時重新展開（步驟 5，已裁定，見待問 3）。
- **找表**：資料夾沒有 `.aos/` 時去找 `inst.json`（跟 inst 目標找檔同一套：先 `.aos/`，沒有就 `inst.json`）；已裁定，見待問 5。
  - 跟待問 6 怎麼並存：待問 5 講的是「認這個 node 的 inst」怎麼找（步驟 1 正規化 `--node`、步驟 8 判上層都照它）；`aos-tick` 跑一格要的鎖檔、任務表、紀錄都在 `.aos/` 裡，所以資料夾沒有 `.aos/` 時 tick 直接回 2、不自建（待問 6）。
- **驗收**：
  - 表裡 `id` 重複：一項都不跑、回 2、stderr 有 `config_invalid`、紀錄 `exit:2`。
  - 帶 `group`、`needs` 的表照跑；帶 `kind:"system.x"` 的表也照跑。
  - 拿 spec 的反例與正例表（[examples/node/](../spec/protocol/examples/node/) 裡的 `tasks.*.json`）各跑一次，看核心只擋「四件事」的那幾份。

## 步驟 5：照表跑每一項

- **要做到**：照陣列順序一項一項跑，前一項結束才開下一項；每項用 inst 的規則跑，環境多放五個變數；結束後把 `exit` 或 `signal` 寫進紀錄。
- **spec**：[B-620 跑每一項、任務的帳號](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；環境與介面 P-203。
- **做法**：
  - 每項跑到時才重新展開（含整份 `$ref`）再開程序；不重用開格驗過的結果，所以前面的項改了 `$ref` 指到的檔，後面的項看到新內容。重新展開後不合法照失敗處理（不回頭改整格結果，只是這一項失敗），這一條 spec 沒寫、屬待問 6。
  - 成敗：正常退出 0 才算成功；非零、被訊號結束、exec 失敗都算失敗。任務回 3、100、125 都只是一般失敗，後面照跑。
  - 帳號：項目帶 `user` 而且解析成的 UID 跟 tick 自己不同 → 不跑、紀錄 `exit:125`、stderr `user_mismatch: <id>`，其餘照跑。核心**不切帳號**。
  - 五個變數：`AOS_NODE_DIR`、`AOS_TICK_LOCK_FD`、`AOS_TICK_RECORD`、`AOS_TASK_ID`、`AOS_TASK_INDEX`。
  - 整格結束碼：全成功 0，有失敗 1。
  - 用複製來的 lib 跑單項（`load_obj` 解出的 inst：cwd 預設 base＝node 根、串流預設 `/dev/null`、`envs` 疊上去；`aos_exec_run` 開子程序另開 session）；把 wait 結果轉成 `exit`／`signal`。
- **要使用者裁定的點**：已裁定（待問 6）：開格驗過之後到跑到該項之間，假設檔案不會變，不為這種情況特別設計。實作走最自然的行為：重新展開丟錯就當那一項沒跑成（照 inst 算 125），後面照跑。
- **tick 要自己接**（lib 沒有，別去改 lib）：公開的 `aos_exec.run_inst()` 會接管 stdin／stdout，不合用；照 inst 開檔、開程序的是私有的 `aos_exec_run._execute_inst()`。它的 `Popen` 用預設 `close_fds`，鎖 fd 繼承不到；五個 `AOS_*` 要自己塞進 `envs`，而且 `clear` 時 `AOS_TICK_LOCK_FD` 仍要留；回的是單一結束碼（被訊號 N 殺是 128+N），紀錄要分 `exit`／`signal` 得自己等子程序。
- **注意**：
  - 核心**不清後代**（B-602）。任務留下還握著鎖 fd 的程序，下一格會回 75；第一段沒人收，測完自己殺。探針原型在 tick 裡設了 subreaper 收後代，那是舊做法，別照抄。
  - 子程序另開 session，所以直接跑時按 Ctrl-C 只停得了 tick 本身。
  - 任務沒有逾時（延後，P-008）。
- **驗收**：
  - 第一項 `env > out.env`：五個變數都在，`AOS_TASK_INDEX` 是 0。
  - 第二項讀 `$AOS_TICK_RECORD`，看得到第一項的 `exit`。
  - 第三項 `sh -c 'kill -9 $$'`：紀錄是 `signal:9`，後面照跑，整格回 1。
  - 某項帶別的帳號（例如 `"user":"root"`）：那一項 `exit:125`、stderr 有 `user_mismatch`，其餘照跑。
  - 任務裡用 `AOS_TICK_LOCK_FD` 核對得到獨占鎖；它跑著時同資料夾另一格回 75。

## 步驟 6：停格檔

- **要做到**：開第一項前刪掉上一格留下的 `.aos/tick/stop`；每跑完一項就看有沒有它，有就不開後面的項，這格回 1。
- **spec**：[B-620 停格檔與擋板檔](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；紀錄欄位 P-213。
- **做法**：看到停格檔 → 紀錄寫 `ended:true`、`exit:1`、`stopped_after:<剛跑完那項的 id>`；stderr 印 `stopped:` 加檔內原因。最後一項建的也算停下。
- **要使用者裁定的點**：無。
- **驗收**：第二項 `sh -c 'echo 手動停 > .aos/tick/stop'`：第三項沒跑、紀錄有 `stopped_after`、整格回 1；下一格照常三項都跑，停格檔已被刪。

## 步驟 7：紀錄寫不進、`--firstdo-fsync`

- **要做到**：紀錄寫失敗時照表跑完、不再寫；帶 `--firstdo-fsync`（或環境有 `AOS_TICK_FIRSTDO_FSYNC=1`）時在規定的幾個點 fsync。
- **spec**：[B-633 落盤與失效](../spec/settled/tick.md#b-633每項結束碼紀錄與格數)。
- **做法**：
  - 「本格紀錄失效」是一個開關：任何一次寫失敗就打開，之後不再寫、之後開的項不設 `AOS_TICK_RECORD`、stderr 只印一次 `record_unwritable`。
  - 開格就失敗 vs 跑到一半才失敗，下一格看到的不一樣（B-633 失效表），分開處理。
  - 兩份舊紀錄都讀不懂：當開格失敗、兩份都不動、另印 `record_unreadable`。
  - fsync 檔案與目錄的小函式；測試用的寫入失敗注入（建議用環境變數或替換寫檔函式，只在測試開）。
- **要使用者裁定的點**：無。
- **驗收**：
  - `chmod a-w .aos/tick`（或整個 `.aos/`）再跑：任務照跑完、stderr 有 `record_unwritable`、任務拿不到 `AOS_TICK_RECORD`。
  - 用注入讓第二項後寫失敗：第三項沒有 `AOS_TICK_RECORD`；下一格的 `last.json` 是 `ended:false`、只有前兩項。
  - 帶 `--firstdo-fsync` 用 `strace -f -e trace=fsync,fdatasync,rename` 看順序對得上 B-633 的表。真的斷電測試不在這段做。

## 步驟 8：上下層判定

- **要做到**：從本資料夾往上找，最近一個有 `.aos/inst.json` 或 `inst.json` 的資料夾就是預設上層；找不到就沒有。純路徑計算。
- **spec**：[B-628](../spec/settled/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)（登記覆蓋是第三段 daemon 的事）。
- **做法**：路徑逐段往上比、不展開 symlink、不看 daemon。照 spec 實作判定即可，不另加子命令、旗標或輸出（已裁定）。
- **要使用者裁定的點**：無。
- **驗收**：`/a`、`/a/b` 都有 `.aos/inst.json`、`/a/x` 沒有：`/a/b` 與 `/a/x/c` 的上層都是 `/a`，`/a` 沒有上層。上下層判定只是函式，不另加指令或輸出，驗收不用印結果（已裁定，見待問 1）；用單元測試直接呼叫函式核對。

## 步驟 9：整段驗收

照 [V-03 第二十批新增場景](../spec/conformance.md#第二十批新增場景)「tick 核心、停格檔與擋板檔」和[第十九批](../spec/conformance.md#第十九批新增場景)「tick 核心」挑出不需要 daemon 的幾條，全部重跑一次：

- 任務表只放一項 `true`、機器上沒有 daemon、git、cgroup、helper：互斥、照表跑、上下層、紀錄都成立（[B-626](../spec/settled/tick.md#b-626核心與系統級任務的界線)）。
- 直接跑的格照常做完、stderr 沒有 `standard:` 行（[B-627](../spec/settled/tick.md#b-627人手或-cron-直接跑一格風險自負)）。
- 步驟 1～8 的驗收合成一個 `unittest` 檔，一條指令跑完。

## 做完了沒（2026-09-30 晚）

- **步驟 1～8 做完**，程式在 [src/py](../src/py/README.md)（`bin/aos-tick`、`lib/aos_tick*.py`），驗收在 `tests/test_tick.py`（一步一個類別，24 條；連同原本 377 條全過）。
- **步驟 9**：B-626、B-627 兩條寫成 `Step9Whole`；其餘 V-03 條目散在各步的測試裡。
- **還沒做**：步驟 7 用 `strace` 看 fsync 順序那條（這台機器沒有 strace）；目前只測了帶旗標／環境變數時照常跑完。
- 實作時自己做的判斷列在 [src/py README「review 導讀」](../src/py/README.md#review-導讀)，都照「最小合理」做、可改。
- **spec 疑點（待使用者看）**：B-633 驗收句「第二項後滿碟，…下一格的 `last.json` 是 `ended:false` 且只有前兩項」跟同篇失效表「留著最後一次寫成功的」對不上——第二項之後那次寫失敗，最後寫成功的只有第一項。實作照失效表（只有第一項）。

## 第一段不做的，先怎麼擋著

| 不做 | 第一段的樣子 | 哪段做 |
|---|---|---|
| 系統級任務（`aos-git`、`aos-publish`、`aos-clean`）、標準任務表範本 | 測試用的表只放 `true`、`sh -c` 這類普通指令；範本表裡的程式還不存在，跑了是 127 | 第二段 |
| 普通程式 `aos-needs`、`aos-cg`、`aos-as` | 同上，不放進測試表 | 二、四、五段 |
| daemon、runner、通道、佇列 | 只有直接跑；環境裡沒有 `AOS_DAEMON_SOCKET`，核心也不看它 | 三、四段 |
| 清任務留下的後代 | 核心本來就不清；測試結束自己殺 | 第三段（runner 格後收屍） |
| 恢復前驗證（完整 schema、`kind` 的值） | 核心只驗四件事 | 第二段 |
| 任務逾時 | 沒有 | 延後（P-008） |

## 待問

〔使用者方向 2026-09-30 晚〕前五條已裁定：

1. **上下層判定怎麼給人看？已裁定：** 不另加指令或輸出，只在必要時才有影響；第一段照 spec 實作判定即可，驗收不用印結果。
2. **整份 `$ref` 的項怎麼拿 `id`？已裁定：** 就照 `$ref` 的規則展開，不是問題（`id` 與原始 `user` 由 tick 自己從項目拿，見步驟 4「注意」）。
3. **開格驗過的展開結果要不要重用？已裁定：不重用。** 跑到那一項時重新展開。
4. **`system.x` 擋不擋？已裁定：** 核心不擋、不管，自己承擔風險；以 B-620 為準。[V-03](../spec/conformance.md#第十八批新增場景) 原本寫「整份拒收」的那句已改成跟 B-620 一致（核心照跑、不擋）。
5. **資料夾沒有 `.aos/` 時怎麼算？已裁定：** 去找 `inst.json`（跟 inst 目標找檔同一套：先 `.aos/`，沒有就 `inst.json`）。spec B-620「任務表」處已補一句同義的話。

6. **`.aos/`、`tasks.json` 不在，和驗表後檔案被改，怎麼算？已裁定**〔使用者方向 2026-09-30 晚〕：
   - 資料夾沒有 `.aos/`：直接報錯，不自建。碼用 2（P-203「任務表不合法」；B-602／B-620 沒有更貼的），stderr `config_invalid:`，不取鎖、不寫紀錄。
   - 有 `.aos/` 但沒有 `tasks.json`：算表壞，回 2。
   - 開格驗過表之後、跑到某項重新展開之間，假設檔案不會變；不為這種情況特別設計，出事就出事，實作走最簡單的自然行為。
   - spec B-620「任務表」已補一句同義的話。
