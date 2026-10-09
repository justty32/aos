# proto7-2 第八輪全日回歸（astra-8）：10-09 新進模組的接縫

**白話結論：今天進的東西各自大致能用，前幾輪回報的大問題（up 交棒誤報、brain 永久卡住、跨信不記得、compact 空摘要、metrics 把多步算重試）都已修好。問題多半出在模組和模組接起來的地方。最嚴重的一條：文件叫你設 `AOS7_LITELLM_KEY`，但核心起任務時會把它丟掉，所以要金鑰的 LiteLLM 透過 up 根本連不上（A10-01，高）。**
**去重後共 24 條：A（會壞）11、B（不一致）12、C（可簡化）1。沒有發現會重複扣帳或重複跑的高嚴重度核心 bug；但有一條核心邊角（A10-02）是「倒數存檔失敗後重起，會多跑一份額度」。**
**統一錯誤路徑還沒有涵蓋全部入口：有 12 支入口沒列進清單也沒寫豁免，其中 aos7-ctl、author CSV、mail ack 游標、aos-exec 長索引還會漏出 traceback。檢查器本身也看不到寫到 HOME 的檔案。**

受測 HEAD：`cd544440`（＝main）。今天約 348 個 commit（`cbc67a3d^..cd544440`），清單見[代定清單](../decisions-2026-10-09.md)。kernel 內部已在 [kernel-astra](2026-10-09-kernel-astra.md) 審過，這輪只看它和其他模組怎麼接（接點沒有新問題）。工人是 4 條 `gpt-6-astra` high，用 `-s read-only` 唯讀審查（[任務書](2026-10-09-astra-8-infra-evidence/tasks/)）。每條發現附的重現腳本，由隊長派的驗證工人在可寫的 `/tmp` 實跑，紀錄在各線的 `verify-<id>.log`、`verify.json`。沒有改程式、測試或文件。

| 線 | 範圍 | 原始輸出 | 實跑核對 |
|---|---|---|---|
| core | 核心 lib 今天的改動、events、history、subd／control／audit／once_retry／tools、kernel 接點 | [codex-out](2026-10-09-astra-8-infra-evidence/core/codex-out.md) | [verify.json](2026-10-09-astra-8-infra-evidence/core/verify.json)：5／5 重現 |
| newbie | up／brain／memory／ask／status、mail、compact、skills、routines、wfnode、QUICKSTART | [codex-out](2026-10-09-astra-8-infra-evidence/newbie/codex-out.md) | [verify.json](2026-10-09-astra-8-infra-evidence/newbie/verify.json)：9／9 重現 |
| llm | llmcall、budget、prompt、author、step、metrics（吸收 usage）、diag（吸收 llmdiag） | [codex-out](2026-10-09-astra-8-infra-evidence/llm/codex-out.md) | [verify.json](2026-10-09-astra-8-infra-evidence/llm/verify.json)：8／8 重現 |
| xmod | 跨模組契約、統一錯誤路徑、入口覆蓋、環境變數 | [codex-out](2026-10-09-astra-8-infra-evidence/xmod/codex-out.md) | [verify.json](2026-10-09-astra-8-infra-evidence/xmod/verify.json)：5／5 重現 |

全套測試：1216 項全過（rc 0，681 秒，[尾段](2026-10-09-astra-8-infra-evidence/suite-tail.txt)）——但下列 24 條都是現有測試沒抓到的。27 條原始發現全部實跑重現（0 條未重現）；core／xmod 的重現腳本存在各線 `scripts/`，newbie／llm 的腳本就是 codex-out 裡的「重現」段。

## 前輪未修項的現況（已修，不再列）

- FL：up 印「起好了」途中收到訊號誤報退 3 → `76e83b41` 已修（`aos7_up.py:165-166` 先交棒再印）。
- longtask：brain＋llmcall 傳輸中被殺永久卡住 → 現在有不確定期限，滿期回卡住信（`aos7_up_brain.py:466-481`）；status 卡住時第七行（`aos7_up_status.py:216-225`）；跨信記憶已接（`aos7_up_memory.py`）；compact jsonl 空摘要已修（`aos7_compact.py:180-205`）；metrics 多步算重試已修（`9b8924a9`）。
- kernel-astra E5（kernel 沒列進 error_path）已補。

## A：會壞（11）

| 編號 | 原編 | 模組 | 嚴重度 | 一行摘要 | 實跑 |
|---|---|---|---|---|---|
| A10-01 | xmod-1 | up→核心→brain→llmcall | 高 | 核心起任務的環境白名單（`aos7_task.py:317`）把 `AOS7_LITELLM_KEY` 濾掉，brain 只補回 URL（`aos7_up_brain.py:187-190`）；up ADVANCED:38 叫你設金鑰，實際送不出 Authorization。K1 白名單已知限制的延伸 | 重現（KEY_PASS=False）；隊長讀碼確認 |
| A10-02 | core-1 | 核心 daemon | 中 | 開回合前存 `owe` 失敗時只記錯、照開回合（`aos7_daemon.py:173-175`、`aos7_daemon_timeline.py:245-252`），重起後倒數沒扣，多跑；違反「不確定寧可少跑」 | 重現（first_round=2、磁碟 k=2 無 owe、重起後 final_round=4） |
| A10-03 | xmod-2 | compact→llmcall | 中 | llmcall 退 4（內容已交付、帳未清）時 compact 當失敗退 3，pending 一直卡著，重跑也一樣 | 重現（兩次 rc 3、pending 仍在） |
| A10-04 | llm-1 | metrics | 中 | 指向上層資料夾時，不同 node 的 `author/csv1` 被併成同一件：13 件變 2 件、憑空多 11 次重試；內部鍵沒帶 node | 重現（上層 2 件／13 呼叫／11 重試；逐夾 13／13／0） |
| A10-05 | newbie-1 | up | 中 | 重跑 `aos7-up` 會把使用者在 `.aos/up.json` 設的 brain 參數清回預設 | 重現（五個自訂 brain 參數全不見） |
| A10-06 | newbie-2 | brain | 中 | `brain/task.json` 壞掉後重播，只看 journal 最後 20 行去重，超過就重記同一步 | 重現（第三步記兩筆，總 26 筆） |
| A10-07 | newbie-3 | ask | 中 | 回信正文帶 Markdown 標題時，`ask` 丟掉標題前的那段答案（`parts[0]`） | 重現（只印「算完了」，「關鍵答案：42」漏掉） |
| A10-08 | newbie-4 | mail | 中 | ack 游標檔型別錯就 traceback，連 `read` 都讀不了 | 重現（TypeError traceback，退 1） |
| A10-09 | core-3 | tools（aos7-ctl） | 中 | 寫 ctl 遇 OSError 直接 traceback、退 1；壞參數也退 1（應 2）；沒接統一錯誤路徑 | 重現 |
| A10-10 | llm-4 | author | 中 | CSV `propose` 的鎖／寫檔 OSError 漏出 traceback 退 1（應 unknown 退 3）；register／publish 有包，propose 沒包 | 重現（IsADirectoryError traceback，退 1） |
| A10-11 | core-2 | aos_inst | 低 | A9-03 修法只對去前導零後的長度設限，4301 個 0 的索引仍 `int()` 爆 ValueError、traceback 退 1 | 重現 |

## B：不一致（12）

| 編號 | 原編 | 模組 | 嚴重度 | 一行摘要 | 實跑 |
|---|---|---|---|---|---|
| B10-01 | xmod-3（併 llm-7、llm-8） | 錯誤路徑覆蓋 | 中 | 31 支入口裡 12 支沒列進 `error_path.json` 也沒寫豁免（aos-exec、aos7-ctl／daemon／run／tock／wait-tock、audit、subd、adapt、step、step-result、usage stub）；adapt 壞參數兩行 usage、step 沒接人話一行、usage stub `--help` 也退 1（llmdiag stub 不同） | 重現 |
| B10-02 | xmod-4 | error_path 檢查器 | 中 | 「不留檔」只看暫存 cwd：寫到 HOME 看不到，`--help` 的目錄變動也不檢查 | 重現（故意寫檔的假入口 issues 仍為 []） |
| B10-03 | xmod-5 | 錯誤契約表 | 低 | `blueprint-errors-items.json` 現狀欄仍是改碼前的 3／4／5 定義、mail「2 含 OSError」、up「設計中」 | 重現 |
| B10-04 | core-4 | events | 中 | `read` 遇讀檔 EIO 只把 `file_unreadable` 放進 errors、退 0；events ADVANCED:51 與 blueprint-errors:41「不知道不能降成 0」互相矛盾 | 重現 |
| B10-05 | core-5＋newbie-5 | events、compact、mail | 低 | 退 2（用法錯，契約說什麼都沒動）的路徑先建了資料夾、鎖檔、state.json（events `too_large`；compact、mail 部分路徑） | events 重現；compact／mail 也重現（留下 `compact/lock`、`inbox/.handle.lock`） |
| B10-06 | newbie-6 | brain↔compact | 低 | brain 改用「步」後，compact 解析仍認「回合」，摘要用舊詞 | 重現（「回合」解析得 step=7，「步」得 None） |
| B10-07 | newbie-7 | up↔mail／ask | 中 | up 允許把 node 取名 `teams`，ask 與 mail 都拒收這個名字；裝完才發現 | 重現（up rc 0 起動，ask 退 2） |
| B10-08 | newbie-8 | compact、routines、skills | 低 | 三個入口 `--help` 可能在程式目錄寫 `__pycache__`（其他入口都設了 dont_write_bytecode） | 重現（三個入口都產生 .pyc） |
| B10-09 | llm-2 | metrics↔budget | 中 | 一般 fakeapi 預算也被算成 AI 呼叫，7 單位成本混進 token 帳差 | 重現（calls=1、ledger.used=7、diff=7） |
| B10-10 | llm-3 | metrics↔llmcall | 中 | 超支時「每件花掉的 token」只算帳內 used、不含 overrun，預設輸出也不提示 | 重現（回條 overrun=90，輸出只說每件 10 token） |
| B10-11 | llm-5 | author↔llmcall | 中 | 模型拒答（llmcall 退 1）被 author 報成使用者輸入錯誤、退 2 | 重現（llm.exit=1、rejected，author 退 2） |
| B10-12 | llm-6 | budget | 中 | `call --amount 0` 入口沒擋，退 3 並在 inbox 留一份 `amount:0` 請求（應退 2 不寫） | 重現（退 3，inbox 留 `amount:0`） |

## C：可簡化（1）

- **C10-01**（newbie-9，QUICKSTART／up，中）：up 本身已只剩三個指令，但第一次成功仍要先知道：要有模板 repo（缺模板第一步退 1，訊息直接丟出 Git SSH、別的 repo、環境變數）、repo 根和 `/tmp/aos/bob` 是兩個資料夾、alias 不跨視窗、第一個視窗不能關。建議 QUICKSTART 明列模板前置條件，用相對路徑取代每視窗 alias，工作簿／技能的概念延到第一封回信之後。（實跑：缺模板退 1，訊息要人 git clone SSH 或設 `AOS7_WF_HOME`）

ELI5 後是否仍複雜：**是，但複雜度已從「指令與概念」移到「前置環境」**——指令 3 個、要懂的概念約 5 個，卡人的是模板與資料夾位置。

## 可疑未證（不編號）

- kernel 檢查 `ctl.json` 空著到寫入之間，可能被別的寫者搶寫；核心本來就不保證不同寫者互蓋，要不要給跨寫者仲裁契約待定。
- wfnode 體檢掃到 `brain/`、`notes/done/` 裡討論模板語法的信（含 `{{`）時可能誤報模板殘留。
- `up.json` 的 `compact:false` 只關 brain 主動呼叫，獨立的 `compact watch` 任務照跑；文件沒說清楚是否承諾全關。

## 沒審完的範圍

- 四條線都是唯讀審查，沒有做 SIGKILL／EIO／多寫者壓力矩陣（前幾輪已做核心）；重現只跑各條發現的最小腳本，每條一次。
- 全庫重複實作（原子寫、flock、tmp 清理、JSON 讀錯、名稱編碼）的比對沒做完，所以沒有提出這方面的 C 類。
- skills 題庫評測器、wfnode 模板填補細節、author 第二關 bwrap 隔離、真 LiteLLM 行為都沒驗。

## 建議下一隊修的順序

1. **A10-01**：白名單放行 `AOS7_LITELLM_KEY`（或 brain 從 up 設定補回），否則要金鑰的端點完全不能用。
2. **A10-02**：`owe` 存不進去就不開回合（核心幾行）。
3. **A10-03＋B10-11**：呼叫 llmcall 的各方統一解讀 0／1／3／4（compact 收 4、author 把 1 當模型失敗），建議抽一個共用對照。
4. **traceback 一批**：A10-08、A10-09、A10-10、A10-11，加上 B10-01 把 12 支入口列進 error_path（或寫豁免）、B10-02 讓檢查器看 HOME。
5. **up／brain／ask 三條**：A10-05、A10-06、A10-07（新手第一眼就會碰到）。
6. **metrics 一批**：A10-04、B10-09、B10-10（鍵帶 node、依資源分帳、顯示 overrun）。
7. 其餘 B 與 C10-01 排到下次動該模組時。

## 收場

codex 四條 scope、兩個驗證工人、全套 scope 都已結束；`/tmp/astra8*` 已刪，ps 核對沒有殘留（[ps-before](2026-10-09-astra-8-infra-evidence/ps-before.txt)）。注意：兩個驗證工人共用 `/tmp/astra8-verify-*` 前綴，newbie／llm 工人把 core／xmod 的腳本又跑了一次，覆寫了 core／xmod 的 `verify-*.log`；內容仍是同一份腳本的實跑結果，結論不變。tracked 檔零修改。
