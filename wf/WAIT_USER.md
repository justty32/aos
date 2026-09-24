# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

### A. 等你一句話（其餘我都做得下去，卡的只有這幾條）

> 編號是固定的（別處用「WAIT_USER 第 N 條」引用），拍掉的號碼不回收，所以會跳號（1、2、7 已結；9 移到 C）。

3. **辯論場的四件轉交提案**：`deliver`／`aos enqueue` 要不要插進 T5 之前、「回合中途死掉
   的洞」歸不歸 roadmap 第六節、`k/`／`c/` 兩層命名進不進 `.aos` 標準、有限資源要不要
   獨立成 idea。**四件都是改規格文件，要人拍板。**
   → [pre-agent-loop-core](workflows/workshop/records/pre-agent-loop-core.md)
4. **hackathon 第一場（core-scope）的結論採不採用**：題目是「近期 core 要回撤到哪裡」，
   四個 persona 各實作一版、Torvalds persona 評分，**從白話導讀讀起**。
   → [records/core-scope](workflows/hackathon/records/core-scope/README.md)
5. **有限資源那場的衝突是不是已經自解**：你 2026-08-25 說「外部處理器自己監控一個資料夾、
   甚至不必引用 aos lib」之後，排隊就變成外部處理器的家務——**確認這一句就能收掉那場**。
   → [finite-resource-queue](workflows/workshop/records/finite-resource-queue.md)
6. **proto2：子 agent 會自動繼承 `spawn` 工具**，子孫一路都能生小孩（驗過三層）。要不要擋、要不要限深度？（使用者 09-06 說「之後再說」）→ [proto2/README](../proto2/README.md)
8. **proto2：agent 之間的交流（tell／hear，或子回話自動變父的信）**先不做，什麼時候做、走哪種？→ [proto2/README](../proto2/README.md)
10. **proto2：玩出來的 25 條效能與邊緣狀況、各包想要但沒有的接點**，要你看過說哪些現在要做。→ [notes/play/README.md](../proto2/notes/play/README.md)、[docs/packs-api.md](../proto2/docs/packs-api.md) 最後一節
11. **proto2 工作室：預算要不要對 cached token 打折**——claude-cli／anthropic 的 prompt_tokens 把 cache_read 也算進去（真實價格約 1/10），4d 帳面 841k 裡一半以上是 cache。選項：閘門只算 prompt−cached＋completion；或另開一個「真實成本」欄。→ [journey 第 10 節](../proto2/notes/2026-09-07-studio-journey.md)
12. **proto2 工作室：dev 的對話史**——haiku 一輪 10k 漲到 20k，一個任務 21 輪 325k。要不要每個任務開新對話史（做完就清、只留任務說明＋檔案清單）？→ 同上
13. **preset 的 `max_per_member`**——100k 對 claude-cli 太低（4d 手動抬到 500k）。改成 300k？還是照引擎不同給不同值？→ 同上
14. **proto5 重架構收線後的八題**（都不卡實作，agent 重寫照現況做）：(a) 跨代 stop——已送進 cpu 家的舊 stop 在 boot 後仍有效、新 kernel cpu 可能一開機就停，要不要讓 boot 去刪 cpu 家裡舊 chain 的 stop 檔（違反「不由外人刪 cpu 家的檔」）？(b) `kernel.log` 要不要輪替／限大小？(c) 硬砍 kernel cpu 時另一組的 tick 子程式可能還活著，要不要補 kill-tree？(d) agent 連敗暫停要不要改成明確 `fail` 狀態（[cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)）？(e) ~~`pause` 門關了還收不收結果~~——fix-r4 已做掉：暫停中 tick 直接退 0，連回音也不收（aos-agent.md §1.6，[fix-r4 筆記](../proto5/notes/play/fix-r4.md)），要翻案再說；(f) agent 要不要在 info 記自己屬於哪個 K（現在只在 tick.json 與 batch.kernel）？(g) 模型多回的欄位（`reasoning_content`）收回時要不要拿掉——現在原樣進記憶、下一問原樣送回，推理長的模型記憶會一起長大；(h) 封存檔 `*.<消費 id>.done` 誰清、何時清（每收一次輸入多一個，agent 不清）？→ [impl-fix-round1](../proto5/notes/2026-09-23-rearch/impl-fix-round1.md)、[agent-round2-changes](../proto5/notes/2026-09-23-rearch/agent-round2-changes.md)、[agent-impl-findings](../proto5/notes/2026-09-23-rearch/agent-impl-findings.md)
15. **daemon 崩潰窗口測試（C-2／C-3）挖出的兩題**（不卡實作）：(a) daemon 回完音、刪原單前被 KILL——回音裡的 `pid` 已被新任 daemon 弄死，規範沒說回音的 pid 可能過期，要不要在 daemon.md 補一句？(b) 舊孩子的 pid 若被別的使用者的程序重用，新任 daemon 送 TERM 失敗會直接退 1、不自救——要不要改成「發不出 TERM 就當它已消失」？→ [daemon-crash](../proto5/notes/2026-09-24-daemon-crash/README.md)
16. **問模型的 endpoint 壞掉要不要做自動換手**（原 backlog `llm-cpu-fallback`）：現在一個模型代號在 llm.json 只認一個 endpoint、不重試；要支援就要把 `models` 表一個代號改成一串。→ [cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)
17. **kernel 排隊要不要加期限**（原 backlog `kiss-holes` 第 2 條的 kernel 那半）：`queue` 裡等派工的行程沒有期限，只有 `timeout_ms` 管跑的時間；agent 那半（半批沒送完永遠等）已有手動 escape（stop 後把 `batch` 設 `null`）。→ [cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)
18. **once 工作綁在 `tick_ms` 的延遲算不算要處理**（原 backlog `review-leftovers` R11；09-24 one-boot 之後 daemon 看到 `K/requests/` 有新檔就開一格，投單到回音 0.5→0.04 秒，這題多半可以關，[量測](../proto5/notes/2026-09-24-one-boot/README.md)）：kernel 一格派、下一格才收，一次問答最快也要等一格；09-23 已判「算不算要做要人判」，agent 重寫沒碰這塊。→ [cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)
19. **proto5-2 規範草稿要拍的六題**（C 隊照草稿的預設在做，翻案要回這裡改；答案現存於 [proto5 納入報告](../proto5/notes/2026-09-24-fold-in/README.md)「沒做的」一節指到的九題表（proto5-2/notes/2026-09-24-impl/decisions.md 的 Q4～Q9），對應現行 proto5 規範見 [kernel/cli-cpu.md](../proto5/spec/kernel/cli-cpu.md)；前三條規模題 09-24 使用者說先不動，見下 C 段）：`cpu rm NAME` 的 `NAME`＝`P/<i>`、永久退休那個號，對不對；既有池的 `cpu add --env` 草稿直接拒絕，對不對；縮小要不要有 `--now`（現在一律等被收的那顆把手上工作做完）；拉不起來的號卡住的工作要不要訂「放棄」協定；daemon `halt` 後再 `boot` 要不要自動把池拉回來（草稿選「要」）；退休的 cpu 家永不刪，要不要清理指令。
20. **kernel C-7／C-8 崩潰窗口測試挖出的兩件**（[kernel-crash](../proto5/notes/2026-09-24-kernel-crash/README.md)）：(a) 出貨中被 KILL、cpu 已讀掉 stop 並退出後，下一格會照「EEXIST 當已放」重送一份同名 stop 到它家，下次 boot 這顆 cpu 起來就退 0、再下一格才拉起——astra 認為算重複投遞該修，隊長沒修因為會改規範行為（與 A.14(a) 跨代 stop 同一件事）；(b) kernel 拿到 daemon 的 spawn 回音、還沒記帳就崩潰，那則回音永遠沒人 ack，留在 `D/responses/`（只多一個檔，排程不受影響），修法要動 kernel↔daemon 對話。
21. **09-24 四份提案／調查的預設已照做**（使用者 09-24 說「你說的都 OK」，即下列各題的**預設**答案；翻案就回這條）：
    - **agent-access 提案 H**（[報告](../proto5/notes/2026-09-24-agent-access/README.md) §7，共 6 題）：①沒 bwrap 的機器一律拒跑 ②`self` 唯讀 ③牢裡預設無網路 ④改名寫法 `tools` 元素 `{"$opt":{"as":{原名:新名}}}` ⑤映射表放 agent 家的 `access.json` ⑥改表下一批生效、正在跑的不收回。
    - **one-program 調查 I**（[報告](../proto5-2/notes/2026-09-24-one-program/README.md) §6，共 5 題；**①～④已做**，P 隊 [one-boot](../proto5/notes/2026-09-24-one-boot/README.md)：`aos-kernel proc` 入口、`aos up`／`aos down`、帳本 `K/ledger.sqlite`、只放寬 kernel 帳本；⑤照現況）：①規模題現在不動架構，只做「查一筆行程」正式入口 ②「合一」＝`aos up`／`aos down` 包起來、程式不合 ③proto5-2 的 kernel 帳本換 sqlite、cpu 家與信箱仍是檔案 ④kernel 帳本可單獨放寬「不用四樣檔」 ⑤工具結果不明不規定「重跑無害」、照現在回報給 agent。
    - **priority-and-shared-cpu 提案 J**（[報告](../proto5/notes/2026-09-24-priority-and-shared-cpu/README.md)，共 6 題）：優先級①只做到 aos 這層、模型伺服器看端點 ②先用 (c) 專屬池（零改動） ③多級優先 (a) 先不要；共用 cpu ①指 (v) 某支工具給多個 agent 排隊共用 ②工具檔加 `_pool` 一欄可以 ③閒著的 agent 每格被叫醒列進 proto5-2 規模題，這版不做。
    - **tools-base 六題**（[報告](../proto5/notes/2026-09-24-tools-base.md) 尾節「要使用者拍的」，共 6 題，維持現況＝預設）：①工作根目錄維持 `config.json` 的 `root`（`<家>/workspace/`） ②bash 暫不加白名單／沙盒 ③結束時收掉背景行程（要長駐另設計） ④給模型的描述維持英文 ⑤跟 pi 還差的能力（多段 edit、長行續讀、bash 存檔、read 圖片）先不補 ⑥`init --tools base`／`tools ls`／`tools remove` 先不做。
22. **N 隊 cli-agents 提案五題**（[報告](../proto5/notes/2026-09-24-cli-agents/README.md)，2026-09-24 裁決，全部照預設）：①一般用 cpu 池方案 ②第一版牢外靠保守旗標、跳過權限旗標只准牢裡 ③花錢的池另開一個 kernel 家（claude 一個、codex 一個） ④接續對話從上次成功分岔 ⑤不讓它們讀 `~/.claude`／`CLAUDE.md`／codex 設定。
23. **P 隊 daemon-split-review**（[報告](../proto5/notes/2026-09-24-daemon-split-review/README.md)，2026-09-24 裁決）：撤「daemon 要 sudo 切使用者」這條理由並寫進 daemon 規範（已做，7e60aa8）；「開機合一、家不合一」＋帳本換 sqlite **已做**（[one-boot](../proto5/notes/2026-09-24-one-boot/README.md)：`aos up`／`aos down`、daemon 開 tick、kernel cpu 拿掉；報告 §9 三題已裁決，見 A.36）；隔離第一版只有工具進牢、CLI agent 先不進；現在不配 subuid。
24. **K 隊「等模型的 agent 不空轉」提案**（[報告](../proto5-2/notes/2026-09-24-idle-wait/README.md)，2026-09-24 裁決）：方案選 (b) 停車＋喚醒（退出碼 102），閒置沒輸入的也停車，第二步加 kernel 喚醒指令；`park_ms` 300 秒；`start` 拒絕 `done_exit 102` 的 kernel 照預設。
25. **M 隊工具大開發計畫**（[報告](../proto5/notes/2026-09-24-tool-era/README.md)，2026-09-24 裁決）：加第六軸「邊界」；隊形三 agent＋四機械幫手；第一波等 L 牆合上再開（已合，T1／T3 已開）；及格線照 `plan.md`。
26. **O 隊 cli-agents 階 0**（[報告](../proto5/notes/2026-09-24-cli-agents/stage0.md)，2026-09-24 裁決）：claude 範本預設**不帶** `--restricted`（能跑程式；使用者選的不是預設選項）；其他四題照預設——範本放 `proto5/templates/`、K2 家 `check` 報沒 llm 池先忽略、codex 登入檔用符號連結、上限 0.5 美元／8 輪／30 分。
27. **L 隊權限牆「要你拍的」五題**（[報告](../proto5/notes/2026-09-24-access-impl/README.md) 尾節，2026-09-24 裁決；L2 隊正在做前四點）：①檔案工具的根從只看 `cwd` 改成整個 `/work`（原做法：只看起點資料夾） ②換起點不自動塞系統訊息，要模型知道就教程提醒 `say` 一句（照現況） ③`access set` 的相對路徑照打指令時殼的目前資料夾算，不照 `--target` 算（照現況） ④有工具的家卻沒有 `access.json` 改成**拒跑**（原做法：不關牢只 warn） ⑤`tools rm` 從整支資料夾拿掉一支時，改寫成 `only` 列出其餘、接受現況（之後新工具要自己加）。
28. **C 隊 proto5-2 池式實作五題（代裁，非使用者親自拍板，使用者未反對，2026-09-24）**：調度者照 C 隊自己的預設答的——退休號只增不減；`handoff` 補「也等 draining 0」；池刪除後舊單建回來記保證外；`aos-daemon ls` 印 `running 2（含 restarting 1）`；`cpu add` 後一兩秒 `ls` 顯示「下一格確認」接受。翻案就回這條。
29. **晚二後合併鏈四案（2026-09-24）**：
    - **L2**（[round2.md](../proto5/notes/2026-09-24-access-impl/round2.md) 第 4 點補的一條）：`init` 自動寫最小權限表（只掛 `workspace/`、無網路）→ 保留。
    - **T3**（[報告](../proto5/notes/2026-09-24-tool-era/t3/README.md) §「要使用者拍的」共 6 題）：`aos-directives` 兼 system prompt 編輯器與 `$env`／`$ref` 解析器、一支指令 → 是；`md_section` 清單項目只收 `- [工作流] 狀態 → 下一步` → 維持嚴格；`wf_init` 備份留在專案裡 → 是。調度者代裁三條：牢外碰 `$env`／`$fmt` 的家檔案工具拒寫；`wf_residue` 照 IMPORT.md 掃全部 md（跟 wf-lint 數字可能不同）；wf 包每次裝約 0.9 MB 接受。
    - **T1**（[報告](../proto5/notes/2026-09-24-tool-era/t1/README.md) §「要你拍的」共 5 題）：門房跑工具不關牢，第二波再接 aos-jail → 是；`aos-team rm` 預設只搬到已拆資料夾，**加 `--purge` 旗標才真刪**（使用者選非預設，已追加落地 `dba8cbe`）。調度者代裁三條：同一 kernel 兩隊不能同名成員（文件寫明）、`answer` 不在選項照收多印提醒、改名冊重跑 init 只更新工具設定。
    - **S**（[fold-in 報告](../proto5/notes/2026-09-24-fold-in/README.md)「要你拍的」，代裁四條照預設）：`aos-kernel ls` 預設只列有事的行程、`--procs` 看全部；`ls --json` 第 2 版拿掉 `cpus[]`；`init --config` 舊 cpus 格式報錯不轉；`aos-daemon kill` 的 `killed 0` 字眼先不動。
    翻案就回這條。
30. **T4「記憶與紀錄」六題（2026-09-24 已裁決）**（[報告](../proto5/notes/2026-09-24-tool-era-memory.md) §8）：
    - 封存：不要只剩一行，每段改成機械摘要、上限 8 KB（使用者：「一行？太粗暴了，8kb吧」）；仍不叫模型、仍要壓到上限以下。
    - 自動壓縮：預設開，上限 32000 token，`info.json` 的 `compact` 可改；寫 `false` 或 `max_tokens: 0` 關掉。
    - 封存段尾加一句「這段細節你看不到了，問到就說不記得」（放在封存內容裡，不是人格）。
    - archive 全留，人手動 `compact --prune-archive`（照現況）。
    - `events.jsonl`／`usage.jsonl` 滿就輪換：使用者選「滿 N MB」沒給數字，調度者代裁 10 MB、留 3 份，`info.json` 的 `logs` 可改。
    - 調度者代裁：說明行用 `user` 角色照現況；`failed` 任務算沒做完、不縮，照現況。
    翻案就回這條。
31. **T2「郵差」五題（2026-09-24 已裁決）**（[報告](../proto5/notes/2026-09-24-tool-era-post.md)〈追加：五題裁決與改動〉）：
    - 郵差巡信箱間隔寫在 `team.json` 的 `post.interval_s`，預設 5 秒（閒著每小時約 25 cpu 秒）。
    - 心跳用自己的身分 `beat` 派工（保留名、信頭「心跳（定時器）」），不再用人的名義。
    - catalog 的一次性例行欄位改叫 `once`，跟程式一致（調度者代裁）。
    - 檢查器壞（跑不起來、環境缺東西、條目寫錯）≠ 隊員沒過：不扣次數、寄信給人、單子停在 verifying，修好 `aos-team verify ID --again`。
    - 例行做完不再寄 DONE 給人，只寄失敗、逾時、檢查器壞、卡住等異常。
    翻案就回這條。
32. **K2「閒置停車＋喚醒」實作收尾五題（2026-09-24 已裁決，照預設）**（[報告](../proto5/notes/2026-09-24-idle-wait-impl/README.md) §6）：
    - 停車上限（`park_ms`）預設 5 分鐘（300000）。
    - `aos-agent start` 不擋還沒開過機的 kernel（沒帳本時看不出認不認得 102，等 boot 後再判）。
    - 升級中的 agent 最多多等一次 5 分鐘（舊批送出時沒帶 `wake`，升級後等那批會停車一次；要快就 `say` 一句或 `aos-kernel wake`）。
    - 暫停的 agent（連敗暫停／手動暫停）不停車，照舊每格輪詢——門是外人開的，kernel 不知道何時開。
    - `ls --json` 留在第 2 版，只加 `parked` 鍵，不升版。
    翻案就回這條。
33. **工具大開發時代第一波收尾（T5）：已裁決＋十條代裁**（[報告](../proto5/notes/2026-09-24-tool-era/t5/README.md) §5、§6）：
    - **已裁決＋已做**：工人每問一次模型都送整份工具表（六包約 11,000 字元≈2,800 token；一件導入 17～25 次＝5～7 萬 token，是資源軸 2 分的一半原因）——使用者裁決「先不改，併進第二波 A 隊」；第二波 A 隊已做（見 34：拆模板、新增導入工人 `importer`，只裝 10 支工具，例子 1 從 17～25 次降到 6～7 次）。
    - 代裁（翻案就回這條，細節在報告 §5）：寄壓縮申請的工具叫 `compact_me` 放 task 包（不讓 `team_say` 帶 kind），reviewer 不給；筆記掛載做成模板旗標 `notes: true`，舊家重跑 init 只補這一格；事件一律在成員家 `log/`；門房 `run` 會換 `{群組}` 但子命令寫死、群組值不准當選項；`examples/routes.json` 的導入規則只放通用檢查（試跑的事實檢查放腳本）；`wf_doc` 讀 IMPORT.md 開頭先講「腳本＝哪支工具」；facts.json 比 plan 多給專案名、語言、直接做／先問、回覆風格、頂層目錄、導入日期；score 的起點推定與「信照時間窗、郵差終局通知例外」；`aos-team ls` 多兩行郵差／心跳（`--json` 不變）；例子 1 正式數字用 one-boot 之後那 3 次。
    - 真跑結果（不用拍、給你看）：導入 3/3、改寫＋審查 2/2、心跳 1/1 都 done；新手試玩 4/4/4/3/4 → 5/4/4/4/4（**模型扮的新手只是代理，你要自己照 [教程 08](../proto5/tutorials/08-team.md) 走一遍**）。
34. **工具大開發時代第二波 A 隊（造工具）：已裁決＋代裁**（[報告](../proto5/notes/2026-09-24-tool-era/w2a/README.md) §5、§6；33 的「工具表瘦身」由這條接手）：
    - **已裁決（2026-09-24，翻案原預設「先不改」）**：導入這種事**預設**交給新的導入工人 `importer`（只裝 10 支工具，工具表約一般工人的一半）：`spec/team/examples/team.json`、`spec/team/roster.md` 的範例名冊、教程 08 的名冊都加一列 `importer-1`，門房的導入規則（`spec/team/examples/routes.json`）改派給它。例子 1：importer 6～7 次、3 萬 token；一般 worker 加了 wf_fill 是 14 次、13 萬。
    - 代裁（翻案就回這條，細節在報告 §5）：瘦身選「拆模板」（不選派工信挑包、不改 base 描述）；importer 不給 bash／write／grep／notes／compact_me；wf_fill 名字對應只認三層（一樣／同義詞／包含），兩條以上不填；第一格是佔位的表格列一律不填（要刪帶 `drop_template_rows`）；`drop_examples` 只刪認得出範圍的；〔模板說明〕一律刪；mail 搬到新檔（郵差裡的舊 `cmd_mail` 留給 B 隊刪），`--json` 多一種 `kind: ask`；派工信寫明「檔案在、含某段字」不用先 read 確認。
    - 真跑結果（不用拍、給你看）：例子 1 導入 3/3 done，模型 17～25 → 6～7 次、22～34 萬 → 3.0～3.6 萬 token、141～183 → 42～54 秒；wrap-py 包的工具裝給工人、派工信叫它用，模型沒寫 bash。
35. **工具大開發時代第二波 B 隊（牆接線）：已裁決＋十一條代裁**（[報告](../proto5/notes/2026-09-24-tool-era/w2b/README.md) §8）：
    - **已裁決（2026-09-24，照 B 隊預設）**：團隊的邊界軸只看會想的成員能寫哪裡（B＝4，成員只寫得到專案、自己的寄件格和筆記，逃逸測試 19 條全擋）；郵差替大家投信到別人的 `input/` 不算整隊的邊界扣分——郵差是寫死的機械員、讀信時又再驗一次。
    - 代裁（翻案就回這條，細節在報告 §8）：真跑場地改用 `~/tmp/wf-try-b/`（避開 A 隊同時真跑）；`cmd_ok` 白名單放 `team.json` 頂層由人寫、單子上的 `run` 要整串對上、逾時不能更長；`cmd_ok` 與門房 `tool` 規則預設專案唯讀（門房要寫得明寫 `"project": "rw"`）；純讀的檢查器（file_exists、table_filled、contains、wf_residue）留在牢外；假信頭只擋成員、一律退件不偷改字；recall／context 放進 notes 包；`mem` 只掛自己家的 `prompts/`；board 唯讀掛給每個成員（含 importer）；commit 署名照你規定的 Fable 5.1。
    - 真跑結果（不用拍、給你看）：例子 1 在關牢下跑 10/10 過（15～29 次、19～40 萬 token、122～224 秒，領隊 0 次）、例子 2 2/2、例子 3 1/1；六軸 L2 S4 R2 F4 H4 B4。新手試玩 wall-r1 4/4/3/4/4（**模型扮的新手只是代理，你要自己照 [教程 08](../proto5/tutorials/08-team.md) 第 9 節走一遍**）。
36. **P 隊 one-boot 報告三題（2026-09-24 已裁決）**（[報告](../proto5/notes/2026-09-24-one-boot/README.md) §9）：
    - `proto5/cli/aos` 跟 repo 的 C++ 主程式 `aos` 同名（PATH 把 `proto5/cli` 放前面會蓋過 C++ 那支）→ **保留 `aos`**（跟 C++ 的 aos 同名，接受；C++ 那支平常在 `build/`，不在 PATH）。
    - 新單觸發沒有最小間隔（忙的時候 kernel 一格接一格，每格一次 Python 起動）→ 照預設不設，等上千顆 cpu 再量。
    - 機器崩過之後 `aos down` 印 `not running`、但帳本還寫 `running`（daemon 不在，沒人跑 halt）→ 照預設不管，下次 `aos up` 會接上。
    翻案就回這條。
37. **工具大開發時代第二波 C 隊（申請類）：已裁決＋六條代裁**（[報告](../proto5/notes/2026-09-24-tool-era/w2c/README.md) §4、§5）：
    - **已裁決（2026-09-24，翻案原預設「先不改」）**：新加的兩種申請（`access_request`、`persona_propose`）借用既有的 `kind: ask`，`aos-team wait ls` 在這兩種問句前加固定前綴分辨：權限申請 `[權限]`、人格申請 `[人格]`，一般問題不加；前綴從申請的 kind／欄位判斷，不靠字串猜。
    - 代裁（翻案就回這條，細節在報告 §4）：領隊派「改寫 X.md 更白話」這類單忘記放 `wf_lint_strict`，選在 `handoff` 工具層機械補、不改門房規則（A 隊地盤，改動範圍較大）；`access_request`／`persona_propose` 不開新申請種類、借用 `kind: ask`；鎖（`lock`）的 `acquire／release／ls` 全部非同步（模型端沒有同步等待）；鎖逾時只看時間，不跨查 agent 還在不在跑；人格只做 show／set／append，不做結構化分段；不因為模型收到「同意」後自己嘗試跑指令（被牢擋住、老實回 BLOCKED）就改問句措辭——這是牢起作用的證據，不是漏洞。
    - 真跑結果（不用拍、給你看）：四種申請（`access_request`、`persona_propose`、`lock`、`routine_propose`）各真跑一次，都走完「模型寄申請→人 answer→生效」（lock 例外，設計上不經問人）；`routine_propose` 批准後心跳真的派出任務、worker 做完、檔案真的寫出來。

### B. 要你親自做的（環境／帳號，我跨不過去）

（目前沒有。）

### C. 你已明說先不決定的（不催，只記「什麼時候會被迫要答」）

放這裡是為了**別再拿它們去煩你**，不是待辦：

- **proto5-2 規模三題**（kernel 帳本仍整份讀寫、aos-agent 每格偷看整份帳本、一顆 cpu＝一支 Python 程序）——09-24 使用者說「規模這塊先不動」；什麼時候會被迫要答：proto5-2 要實作，或 cpu 上千顆時。→ [proto5 納入報告](../proto5/notes/2026-09-24-fold-in/README.md)「沒做的」一節（proto5-2/notes/2026-09-24-impl/decisions.md 的 Q1～Q3）
  - **多一條同類的**：閒著的 agent 每格還是被叫醒看一眼（J 隊 priority-and-shared-cpu 挖到，見 [報告](../proto5/notes/2026-09-24-priority-and-shared-cpu/README.md) §「要使用者拍的」題 2-3）；K 隊正在提案「等模型的 agent 不空轉」，做完再一起拍。

- **pi 當介面層**（2026-08-30「先擱置」）——接法與代價在 [pi-interface](../core/agent/docs/pi-interface.md)，要投資時從那裡起。

- **B12 判準／loop 分支的形式／版面知識放哪**（2026-08-30 三題都「先不決定」）——
  會撞上的時機：要動 `exec_loop` 時（分支）、要寫第一支 CLI 小程式時（版面 lib）。
  → verdicts B12、core-layering
- **workshop 那四個設計選擇**（World 抽象、`kernel.json` 分層合成、子行程拓樸、親緣綁
  路徑還是 UUID）——你明講「窩不想看惹」，方向是**用實測取代拍板**，所以不列 A 區。
- **top-down-cli 的 14 條**——已裁「實作時順便解決」。
- （原 A.9）**proto2：拍板題 T-01～T-77 全照建議做了（使用者 09-06 說「都 OK」）**；要翻案就回編號。→ [notes/tools/README.md](../proto2/notes/tools/README.md)

> 設計上還沒答完、但不卡你的細節不放這裡——記在 [`roadmap`](workflows/roadmap.md) 與各 idea 文件的開放問題。
