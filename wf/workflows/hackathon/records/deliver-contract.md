# Deliver 的介面與契約

> **以下是風格模擬，不是本人的意見。**

| 項目 | 內容 |
|---|---|
| 題目 | Deliver 的介面與契約（對到 OPEN-QUESTIONS 第 7、8、9 題） |
| 開場日期 | 2026-08-26 |
| 環境 | 原生 Linux（Manjaro，不是 WSL）；codex 0.149.1；`-s workspace-write`；無網路；四位平行；單輪逾時 1800 秒 |
| reasoning effort | `high` |
| 評委 | Leslie Lamport persona |
| 狀態 | 第 2 輪已完成，共三輪 |

| 參賽者 | persona | 場地 | codex thread id（續輪 resume 用） |
|---|---|---|---|
| p1 | Rob Pike | `~/aos-hack/deliver-contract/p1` | `01a03e24-2e95-7640-b64c-99d5a6648d6f` |
| p2 | Rich Hickey | `~/aos-hack/deliver-contract/p2` | `01a03e24-310d-7413-bebf-109eb39a8c70` |
| p3 | Bryan Cantrill | `~/aos-hack/deliver-contract/p3` | `01a03e24-2eeb-7750-8fe8-7ced989b0848` |
| p4 | Julia Evans | `~/aos-hack/deliver-contract/p4` | `01a03e24-31d4-7d53-af4e-ee6ca3cbbdb3` |

## 第 1 輪紀錄

### 1. 各人做了什麼

Pike persona 這一路做了四種 CLI 共用的假投遞核心，另做 queue key probe、五份輸出、6 行 shell consumer 與假的 tool caller。四種 CLI 的人工檔案、pipe 單筆、agent batch 都跑通；(a) 的 pipe 與 tool caller各造一份 caller temp，巢狀 world 也真的列出兩個候選。完整成功輪在 `p1/deliver-lab/run.6hO44M`。這一路沒有把 ready 檔交給既有 `aos exec`，而是把 CLI、key 與輸出契約留在自己的假核心內跑。

Hickey persona 這一路把 `WORLD`、`FILE|stdin` 與 publish result 拆開，先寫 fixture，再做 Python mock。四種 CLI 的三個現場都產生 ready delivery，之後交給既有 `aos exec`，每個草案都實際執行 4 筆並把 ready 歸零；key probe 也使用真的 `aos exec` 做 aggregate。場地在 `p2/deliver-contract/`。

Cantrill persona 這一路集中做 (d) 的可執行 Python 假件 `WORLD [-f FILE|-]`，成功時真的寫唯一 `.json.temp` 再 rename 成 `.json`，另跑四種 CLI 的 12 次呼叫矩陣、key probe、五份輸出、10 行 shell consumer 與假的 tool caller。成功 batch 再交給既有 `aos exec`，兩筆都被執行、delivery 被刪、沒有殘留 `.temp`。本輪有效結果放在 `p3/wf/workflows/experiments/deliver-contract-p3/out/round3/`；round1、round2 的錯誤現場仍保留。

Evans persona 這一路做四支 wrapper 假裝四種 `aos deliver`，逐一跑人工檔案、pipe 單筆、假 agent batch；另做 toy queue、五份手寫 machine output、10 行 shell consumer 與假的 tool caller。12 次呼叫都留下 ready file，最後現場是 `ready_files=12`、`protocol_temp_files=0`、`cxx_files_touched=0`；沒有再把它們交給既有 aggregator。完整結論在 `p4/deliver-contract-lab/R1-RESULTS.md`。

### 2. 坑的總表

四位獨立地都撞到 canonical batch validator 的接縫。四份假件都只驗了本題需要的 JSON 外形或 `/argv/0`，都沒有把它說成可照抄的 C++ parser。Pike persona 與 Hickey persona 記到公開 C ABI 只有單筆 instruction parser；Cantrill persona 記到既有公開 C ABI 不能一次驗整個 array 並定位第二筆；Evans persona 記到 `inst.h` 連 handoff C 入口都沒有。四路都把「假件能跑」和「真實作可沿用 validator」分開了。

四位獨立地都撞到 aggregate 會刪掉 delivery，因而刪掉 key 的歷史證據。Hickey、Cantrill、Evans 三路把 publish 前的 `.temp` 視為 attempt、不是 committed publish，所以只算發布後到 aggregate 前那一步答得出來；Pike persona 另在活 process 裡放 volatile reservation，因此把發布前也算成有證據。四路都記到 aggregate 後缺 key 與內容的綁定，process 重開後又缺記憶體或耐久 ledger；四路最後都交「第一版不要使用者提供的 key」。

四位獨立地都撞到 (a) 把 FILE 同時當 payload 與 world locator。pipe 與 agent caller 本來只有 bytes，兩個現場都被迫各造一份檔；巢狀 `.aos` 又讓同一個 FILE 可以推出不同 world。Pike persona 真列出的現場是：

```text
$ find ancestors of .../outer/inner/one.json containing .aos
candidate_world=.../outer/inner
candidate_world=.../outer
```

四位獨立地都撞到 (c) 目前沒有第二個廣義 target 使用者，卻要求每次多交 `--target`；相對 target 的基準、`X` 是 CPU 名還是路徑、以及 `X.json`／`X.tempd` 的公開形狀都還沒有共同答案。四路對歧義的計數不同：Pike persona 算 0、Hickey persona 算三個現場各 1、Cantrill persona 合計算 2、Evans persona 算三個現場各 1。

四位獨立地都沒有把 rename 實驗寫成 durability 證明。四路都留下 no-replace、同名競爭、兩 producer 並行、file/directory fsync、斷電等未測項；Pike、Hickey、Cantrill 三路另明寫 rename 仍可能覆蓋同名 ready。成功 publish 已發生、但 caller 還沒收到 JSON 就被殺的窗口，也都沒有在本輪跑。

三位獨立地都把 (b) 與 (d) 的三現場 caller temp 算成 0，並把兩者帶到最後比較；Pike persona 選 (b)，Hickey、Cantrill、Evans 三路選 (d)。輸入來源仍有兩組實際口徑：Pike persona 讓 FILE 缺席即讀 stdin；Hickey persona 與 Cantrill persona保留 `-f FILE | -`；Evans persona 進一步改成來源必須明寫的 `WORLD (-f FILE | -)`。Evans persona 另外真的造出 (b) 的相對 FILE 兩解現場：

```text
$ ./bin/aos-b deliver fixtures/world one.json
{"actual_source": "/home/lorkhan/aos-hack/deliver-contract/p4/deliver-contract-lab/one.json",
 "actual_target": "/home/lorkhan/aos-hack/deliver-contract/p4/deliver-contract-lab/fixtures/world/.aos/inst.tempd",
 "actual_world": "/home/lorkhan/aos-hack/deliver-contract/p4/deliver-contract-lab/fixtures/world",
 "ambiguities": 1,
 "ambiguity_notes": ["relative FILE: caller cwd or FOLDER"],
 "caller_temp_files": 0,
 "count": 1,
 "required_parameters": 1,
 "variant": "b"}
```

四路的輸出都讓 shell 與假 tool caller 真正讀過五份 case，但 stream 與欄位形狀沒有收斂。Pike persona 是 success stdout、error stderr；Cantrill persona也是 success stdout、error stderr；Hickey persona 把成功與錯誤 JSON 都放 stdout、stderr 留空；Evans persona 的消費實驗是手寫 fixture。欄位聯集從 4、6、6 到 18 個，退出碼也有三套：Pike persona 用 `0/1/2/3`，Hickey persona 用 `0/2/3/4`，Cantrill 與 Evans persona 用 `0/2/3/4/5/6`。

本輪保留的失敗現場如下。Pike persona 第一次 consumer 被 shell quoting 弄壞，失敗輪留在 `run.zP3WBH`，原文是：

```text
SyntaxError: f-string: expecting a valid expression after '{'
```

Hickey persona 第一版 harness 假設 `aos init` 會建立 world 資料夾，先卡在：

```text
$ python3 deliver-contract/run_calls.py
$ ./build/bin/aos init .../world-a
exit=1
stderr:
aos init: cannot open .../world-a: No such file or directory
Traceback (most recent call last):
...
FileNotFoundError: .../world-a/.aos/version
```

Hickey persona 修成先建立 world 後才跑完；初版 (d) driver 也曾寫成 `-f -`，後來依題目改為裸 `-`；初版 I/O error 的 `io_13` 也在重跑時改成 `io_eacces`。

Cantrill persona 先確認現有 binary 沒有 `deliver`，原文是：

```text
$ ./build/bin/aos deliver
exit=2
./build/bin/aos: unknown command 'deliver'
```

Cantrill persona 的 round1 還有 `actual` 被 Python 寫成 `int`、手寫 parse byte 是 25 但實跑是 24 的漂移；round2 修資料，round3 才補齊 consumer 對退出碼的核對。指定清單只有成功加四個錯誤，他另外跑了 usage，讓 exit 2 也有現場。

Evans persona 的場地 `.git` 是空殼，第一個範圍檢查卡在：

```text
$ git status
fatal: not a git repository (or any of the parent directories): .git
```

因此這一路改用檔案清單與 `cxx_files_touched=0` 記錄改動範圍。Evans persona 沒有實際製造不可寫目錄；I/O case 是依題意先手寫再由兩個 consumer 消費。Pike persona用普通檔案佔住 `inst.tempd` 取得 `ENOTDIR`；Cantrill persona 對 `0555` inbox 實際取得 errno 13；Hickey persona 的 fixture 與 mock 則回 `io_eacces`。

### 3. 好處／壞處

#### 好處

Pike persona 的 (b) 讓三個現場共用「有 FILE 讀 FILE，沒有就讀 stdin」，三場 caller temp 都是 0；成功輸出只保留 `ok` 與 `count`，錯誤再用 `code`、`at`。Hickey persona 與 Cantrill persona 的 (d) 把 WORLD 與輸入來源分開，pipe 與 tool caller 都直接走 stdin；Evans persona 的修正版再把來源改成必須明寫。四路的單筆與 batch 都沒有拆成兩支命令。

Hickey persona 與 Cantrill persona 都把假 publisher 產生的 ready 檔交給現有 `aos exec`；兩路都觀察到 instruction 被執行、delivery 被 aggregate 後刪掉。Pike persona 的錯誤案記到 `bad-version published=0`、`bad-io published=0`、`all protocol temps=0`；Cantrill persona也記到 JSON、schema、world 錯誤沒有可見 delivery，發布成功後沒有 `.json.temp`。Evans persona 的 12 次呼叫最後是 `protocol_temp_files=0`。

四份輸出契約都有 shell 與假 tool caller 的消費紀錄。Pike persona 的 4 個欄位全部被讀；Hickey persona 的 6 個欄位全部被兩邊合計讀到；Cantrill persona 的 consumer 不只讀 JSON，也核對 exit；Evans persona 的 flat JSON 讓 10 行 shell consumer直接讀 top-level 欄位。

#### 壞處

Pike persona 記到 (b) 在互動 terminal 忘記 FILE 時會等 stdin；Hickey persona 記到 (d) 的裸 `-` 對第一次使用者不如自動讀 stdin；Cantrill persona 記到 (d) 比 (b) 多 `-f`，而 success stdout、failure stderr 要求 wrapper 同時捕捉兩條 stream；Evans persona 的修正版則是每次都要多打一個 `-` 或 `-f`。

四路第一版都沒有能跨 aggregate 保存的 key 保證。Pike、Hickey、Cantrill 三路連 correlation 也先不公開；Evans persona保留系統產生的 `delivery`，但只叫 correlation，不把它當 dedupe key，並記到若沒有後續 query consumer，下一輪要再檢查是否移除。

Hickey persona 的 6 欄位結果使用 `where.kind/value` 區分 byte offset、JSON Pointer、版本與路徑；Pike persona 的單一 `at` 同時裝這四種值，並記到若需要程式化分派修復可能要拆。Cantrill persona 的實驗聯集有 18 個欄位，每份 variant 並非固定同形，caller 要先按 `code` 分支；其中 `message/published/receipt/target` 沒被讀。Evans persona 保留 `message` 給第一次使用者，但也記到退出碼 3 在既有 `aos exec` 與 Deliver 草案代表不同事情。

### 4. 題目那三個數字

#### 數字一：四種 CLI 的 caller temp／歧義／必填參數

目前四份回報的總表如下。每格依序是「額外 caller temp／歧義／必填參數」；Pike、Cantrill 與 Evans persona 的必填參數是 CLI 文法最低數量，Hickey persona 把必填值按三個現場合計，因此同一文法分別會記成 1 與 3、2 與 6。Evans persona 的歧義也是三現場合計，但必填參數仍用文法最低數量。

| 回報者 | (a) FILE | (b) FOLDER [FILE] | (c) WORLD --target X | (d) WORLD [-f FILE \| -] |
|---|---:|---:|---:|---:|
| Pike persona | `2 / 1 / 1` | `0 / 0 / 1` | `0 / 0 / 2` | `0 / 0 / 1` |
| Hickey persona | `2 / 3 / 3` | `0 / 0 / 3` | `0 / 3 / 6` | `0 / 0 / 3` |
| Cantrill persona | `2 / 1 / 1` | `0 / 0 / 1` | `0 / 2 / 2` | `0 / 0 / 1` |
| Evans persona | `2 / 3 / 1` | `0 / 1 / 1` | `0 / 3 / 2` | `0 / 1 / 1` |

四份都附了 12 次呼叫或等價的成功輪輸出。Pike persona 保存完整成功輪與 `cli-metrics.tsv`；Hickey persona 的每場 metric 與 ready→`aos exec`→ready 歸零放在同一 harness；Cantrill persona 的 `shape-matrix.txt` 記到 12 次全為 exit 0，另有 `exec-interop.txt`；Evans persona 逐列輸出 `caller_temp_files/ambiguities/required_parameters/count`，但沒有把 ready 再交給 aggregator。這四份數字的未收斂處是「歧義算一條規格缺口，還是每個呼叫現場各算一次」，以及相對 FILE／target 的基準是否已被草案暗中定義。

路線選擇方面，Pike persona 交 (b)；Hickey、Cantrill、Evans persona 交 (d)。Evans persona另交一個不在原四案內的修正版 `aos deliver <WORLD> (-f <FILE> | -)`，數字是 `0 caller temp / 0 未定歧義 / 2 必填參數值`。

#### 數字二：四次同 key 同內容重叫，有幾步答得出以前來過

| 回報者 | 答得出來 | ① 發布前 | ② 發布後、aggregate 前 | ③ aggregate 後 | ④ process 重開後 |
|---|---:|---|---|---|---|
| Pike persona | `2/4` | 是：volatile reservation | 是：queue file | 否：delivery 已刪 | 否：reservation 消失 |
| Hickey persona | `1/4` | 否：只有 uncommitted temp | 是：ready key bytes | 否：沒有 key binding | 否：沒有 persistent key fact |
| Cantrill persona | `1/4` | 否：只有 uncommitted temp | 是：ready file＋matching SHA-256 | 否：沒有跨刪除 witness | 否：沒有 durable receipt/ledger |
| Evans persona | `1/4` | 否：`.temp` 不是 publish 證據 | 是：ready 內有 key＋hash | 否：ready 與證據已刪 | 否：磁碟無 ledger、RAM 歸零 |

Pike persona 的原始 probe 是：

```text
$ python3 deliver-lab/key_probe.py
1 before-publish: seen_before=yes evidence=volatile reservation
2 published-not-aggregated: seen_before=yes evidence=queue file
3 after-aggregate-delete: seen_before=no evidence=none
4 restart: seen_before=no evidence=none
answerable=2 of 4 (restart answer is no)
```

Hickey persona 的 probe 使用既有 `aos exec` 做 aggregate，原文是：

```text
$ python3 deliver-contract/key_probe.py deliver-contract/runs/key-r2
init_exit=0
stage=pre_publish answer=unknown evidence=only_uncommitted_temp
stage=post_publish answer=already evidence=ready_key_bytes
aggregate_exec_exit=0 ready_after_exec=False
stage=post_aggregate answer=unknown evidence=ready_deleted_no_key_binding
stage=process_restart answer=unknown evidence=no_persistent_key_fact
CAN_ANSWER_PREVIOUSLY_SEEN=1/4
```

Cantrill persona 與 Evans persona 也各附 probe 輸出；Cantrill persona 另外以既有 `aos exec` 證明 ready 會被刪，Evans persona 的 key queue 是 toy queue。四路的分歧只在第 ① 步是否准許活 process 的 volatile reservation算「以前來過」；第 ②、③、④ 步的 yes/no 一致。四路都把缺的證據寫成跨 aggregate 保存的 key→content/hash 綁定、consumer acknowledgment 或 durable ledger。

#### 數字三：輸出契約設計幾個欄位、實際讀到幾個

| 回報者 | 設計／實讀 | 欄位 | 從未被讀的欄位 | 消費現場 |
|---|---:|---|---|---|
| Pike persona | `4 / 4` | `ok,count,code,at` | 無 | 6 行 shell＋假 tool caller，各讀五個 live case |
| Hickey persona | `6 / 6` | `result,count,error,where,kind,value` | 無 | 10 行 shell＋假 tool caller，各讀五份 fixture；另有 field audit |
| Cantrill persona | `18 / 14` | 五份 JSON 的不同 top-level 欄位名聯集 | `message,published,receipt,target` | 10 行 shell＋假 tool caller，兩邊都核對 JSON 與 exit；另跑 live case |
| Evans persona | `6 / 6` | `ok,delivery,count,code,pointer,message` | 無 | 10 行 shell＋假 tool caller，各讀五份手寫 fixture |

Pike persona 的退出碼是：

```text
0 = 成功
1 = I/O／操作失敗
2 = payload 錯（syntax/schema 由 code 細分）
3 = world／version 拒絕
```

Hickey persona 的退出碼是：

```text
0 = published
2 = payload rejected
3 = world／target contract rejected
4 = publish I/O failed
```

Cantrill persona 與 Evans persona 的退出碼分類相同：

```text
0 success
2 usage
3 JSON parse
4 instruction schema
5 world/version
6 I/O
```

Cantrill persona 的 `18/14` 是實驗版本，另交出「真正寫 C++ 前先刪四個未讀欄位，變成 `14/14`」；Evans persona 的 I/O case 是手寫 fixture，不是真 syscall。Pike、Hickey、Cantrill 三路各有實際 I/O 失敗製造方式或 mock live case。四份都展示兩種 consumer 的實際輸出；是否把手寫 fixture、mock syscall 與既有 C++ interop 視為同一層證據，本輪沒有合併成單一口徑。

### 5. 仍然不知道的

本輪仍沒有一個共同的 CLI 答案。(b) 與 (d) 的 caller temp 同為 0，但 FILE 缺席是否自動讀 stdin、來源是否必須明寫、相對 FILE 以 cwd 還是 WORLD 為基準，仍有三種跑法；(c) 的 target 基準與第二個 CPU caller 仍不存在。

本輪仍沒有測出無 ledger 時 publish 成功回覆遺失後，caller 可以怎麼安全重送。四份都沒有跑兩 producer 同時撞名、atomic no-replace、rename 成功但回覆未送達就被殺、fsync、斷電、consumer acknowledgment、ledger retention 或 GC。

本輪仍沒有把 canonical `read_all()` 接成 Deliver 可直接重用的 batch validation surface，也沒有答案說第二筆 schema error 的 record、JSON Pointer、expected/actual 要由哪個公開型別承載。world version 與 payload 同時錯時的錯誤優先序、多個 schema error 同時存在時回哪一個，也沒有跑。

本輪仍沒有共同的 machine output schema。成功與失敗走 stdout 還是分 stdout/stderr、退出碼是 subcommand-local 還是整個 `aos` 共用、`at` 要不要拆成 typed location、`message` 是否屬於穩定 machine ABI、`delivery/receipt` 沒有 query surface 時是否保留，都還有不同版本。

第 ④ 步「process 重開」本輪都按 aggregate 後再重開處理；Evans persona 另記到，若題意是發布後、aggregate 前重開，ready file 還在，答案會等同第 ② 步。真 MCP、真 coding agent protocol、PowerShell 與非 Linux caller 也都沒有在本輪跑。

## 第 1 輪評分與意見

我用三個命題判這一輪：成功是「整批輸入恰好變成一個可見的 ready delivery」；失敗是「沒有任何可見 delivery」；`Already` 若存在，意思必須是「這個 key 曾經成功 publish」，不是「某個 process 曾開始嘗試」。沒有固定這三句，同一個數字也可能在回答不同的問題。

| 參賽者 | 證據強度 | 誠實度 | 走了多遠 | 回答了三個數字 | 路線價值 | 總分 |
|---|---:|---:|---:|---:|---:|---:|
| Pike persona | 5 | 5 | 4 | 4 | 4 | **22/25** |
| Hickey persona | 5 | 5 | 5 | 5 | 5 | **25/25** |
| Cantrill persona | 5 | 5 | 5 | 5 | 4 | **24/25** |
| Evans persona | 4 | 5 | 4 | 5 | 4 | **22/25** |

### Pike persona

**講評：** CLI 與輸出實驗的證據完整，而且把 quoting 失敗留在現場，這是可信的。但「發布前可回答曾經來過」把 volatile reservation 當成 publish witness，悄悄更換了命題；單一 `at` 又沒有穩定的型別不變式。

**下一輪：** 先寫出 `Attempting → Visible → Aggregated → Forgotten` 狀態機，對每個狀態列出可觀測證據，再用「磁碟現狀相同、但 K 只在其中一段歷史 publish 過」的兩段歷史重跑 key probe；同時把 `at` 改成有 tag 的 location 後重跑兩個 consumer。

### Hickey persona

**講評：** `ready_deliveries=3` 經真 `aos exec` 後變成 `ready_after_exec=0`，再加上 key probe 的 `unknown/already/unknown/unknown`，是這輪最直接的狀態證據。`where.kind/value` 也比「什麼都叫位置」多了一個可檢驗的不變式；未完成的是並行 publish 與回覆遺失窗口。

**下一輪：** 做兩個 producer 的同名競爭，並在 rename 已成功、JSON 尚未回傳時殺掉 caller；對每個結果寫明「磁碟可見性」與「caller 知識」各是什麼，並證明 CLI 能直接重用 canonical `read_all()` 而不是再寫 parser。

### Cantrill persona

**講評：** 真 errno、真 aggregator interop，以及 consumer 同時核對 JSON 與 exit code，都是強證據。但 `18/14` 說明實驗契約尚不能凍結；將 parse、schema、world 與 I/O 各佔一個退出碼，還同時分 stdout/stderr，是兩套必須一致的分類介面。

**下一輪：** 先把輸出寫成有限的 tagged union，刪掉四個未讀欄位，然後用同一份錯誤優先序表重跑「world 版本與 payload 同時錯」與「第二筆有多個 schema 錯」；再驗證 shell 只靠 exit 大類、tool caller 靠 JSON tag 仍能做出同一決定。

### Evans persona

**講評：** 它找到 `(b)` 與 `(d)` 的真正使用者歧義：相對 FILE 的基準，以及 bare command 是否等 stdin；這對介面拍板有價值。但 `ready_files=12` 沒有證明現有 aggregator 接受它們，I/O 又只是手寫 fixture；`6/6` 只證明剛寫的 consumer 會讀 `message`，尚未證明 `message` 是必要 ABI。

**下一輪：** 把修正版 `(d')` 的 ready 檔交給真 `aos exec`，用真 syscall 製造 I/O 失敗，並分別在 TTY 與已關閉 stdin 下證明 bare invocation 是立即拒絕而非等待；再移除 `message` 重跑 consumer，看機器決策是否真的改變。

### 路線判斷

**最值得繼續的路是 Hickey persona 的 `(d)`，但要吸收 Evans persona 的「輸入來源必須明寫」。** 具體理由不是風格，而是 Hickey persona 的輸出已連起 `deliver → ready_deliveries=3 → aos exec → ready_after_exec=0`，而 key probe 也在同一條真 aggregate 路徑上得到 `1/4`。Evans persona 的 `aos deliver fixtures/world one.json` 實際讀 `./one.json`、但使用者可合理以為是 `fixtures/world/one.json` 的輸出，則證明來源若不明寫，成功也不等於投對。

**看起來好、但有隱藏成本的是細分退出碼與「每個欄位都被讀到」。** 消費者是為這場實驗剛寫的，要它讀某欄位很容易，這不證明真 caller 需要該欄位；同時凍結 3–6 與 machine code 會產生兩份 taxonomy，而 Evans persona 已證明 exit 3 在 `aos exec` 有別的意義。

**致命的坑是無 ledger 卻公開冪等 `--key`。** aggregate 後，「K 從未 publish」與「K 曾 publish 但 delivery 已刪」可以有完全相同的可觀測狀態；此時沒有程式能同時對兩段歷史正確回答 `Already`。另一個會擋住 C++ 方向的坑是複製玩具 parser：若 Deliver 與 canonical `read_all()` 對同一 batch 得出不同結果，介面的「接受」便沒有單一意義。

**只是麻煩、可繞過的，是要求每次多寫 `-f` 或 `-`、規定相對路徑以 caller cwd 為基準，以及 wrapper 擷取哪條 stream。** 這些都能用一句文法或單一 machine-output stream 消除，不需要新的持久狀態。

### 可信度判斷

沒有證據顯示哪位捏造了整份回報；但 **Pike persona 的「數字二＝2/4」不可信**。它的第 ① 步輸出自己寫的是 `evidence=volatile reservation`，這只能證明 attempt 存在，不能證明 publish 曾發生；將它計為 yes 是把「以前來過」改寫成「現在有人正在來」。這是命題錯誤，不是單純少一個測試；其餘 CLI 與輸出證據仍可信。

### 若現在就必須拍板

- **第 7 題：選 `(d)`**，但契約寫成 `aos deliver <WORLD> (-f <FILE> | -)`；來源不可省略，`FILE` 以 caller cwd 解析，單筆 object 與 batch array 都只產生一次 publish。
- **第 8 題：選「第一版沒有 key」**；正確數字是 **1/4**，只有 publish 後、aggregate 前有 committed witness。未付 ledger、retention、GC 與 acknowledgment 成本前，不公開 `Already`、`Conflict` 或暗示它們的名詞。
- **第 9 題：四個原案都不原封接受；選 Hickey persona 實測的最小 discriminated result**。成功只保證 `result=published,count=N`；失敗是 `result=rejected,error,where{kind,value}`；退出碼只分 `0=published`、`2=payload`、`3=world contract`、`4=I/O`，不公開 receipt/hash/message。若被限定必須從原表挑一列，這是「delivery＋count 版」的最小化，但 `delivery` 在它的唯一性、保存期與查詢面被定義前不出現。

**先做的第一步：** 先將 canonical batch validation 接到 Deliver 的 C++ 路徑，並寫一個只接受已驗證 bytes 的 publish primitive；它的首個不變式測試是「回傳 published 當且僅當整批 bytes 已成為選定 WORLD 中一個可見 ready file，其他結果的可見 ready file 為零」。這一步先保證 atomic visibility，不在尚未驗證 fsync 與斷電前偷換成 durability；上述是評委建議，最後仍由使用者拍板。

## 下一輪的資料包

### 1. 這輪卡住的清單

- **Pike persona** 卡在把 `Attempting → Visible → Aggregated → Forgotten` 各狀態的可觀測證據釘死、重做兩段不可區分歷史，以及讓 location 帶穩定 tag；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪評分與意見／Pike persona〉。
- **Hickey persona** 卡在同名雙 producer、rename 成功但 JSON 尚未回傳的死亡窗，以及 Deliver 如何直接使用 canonical `read_all()`；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪評分與意見／Hickey persona〉。
- **Cantrill persona** 卡在把 `18/14` 收成有限 tagged union、定義複合錯誤的優先序，並核對 shell 只讀 exit 大類與 tool caller 讀 JSON tag 是否仍作出同一決定；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪評分與意見／Cantrill persona〉。
- **Evans persona** 卡在讓 `(d')` 的 ready 檔被真 `aos exec` 接走、用真 syscall 取得 I/O 失敗、分別驗 TTY／關閉 stdin 的 bare invocation，以及移除 `message` 後重跑 consumer；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪評分與意見／Evans persona〉。
- **四位共同**仍卡在第二筆 schema 錯誤由哪個公開型別承載 record／JSON Pointer／expected／actual、world 與 payload 同時錯時先回哪個，以及 machine JSON 與退出碼是否形成一套或兩套 taxonomy；彙整在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪紀錄／5. 仍然不知道的〉。

### 2. repo 裡已經有答案的

- `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉與子節〈彙整的規則〉已寫明 `.temp`／ready 的可見邊界、ready 只在 aggregate 發布成功後刪除，以及投遞順序不得被 caller 假設；同檔〈十二、留給實作決定的／仍然開著的〉另明列投遞尚未實作與 `renameat2(RENAME_NOREPLACE)`／`link`＋`unlink` 的既有 TOCTOU 坑。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉已實測直接寫 ready 會讓半份 JSON 被 aggregate 隔離，且同一 PID 連投兩次時第二次 POSIX `rename` 會靜默覆蓋第一份，這是雙 producer 前已有的單 producer 基線。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 2 輪紀錄／2. 坑的總表〉與〈5. 評委上一輪要他們做的事，做到了沒〉已踩過 same-target 雙 producer：Publish v1 兩方 exit 0 且 B 覆蓋 A，v2 則得到一份 published 與一份 conflict，另有 2,000 件 shared-slot／global-ID 對照。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／2. 坑的總表〉已跑過 publish-success-before-receipt 與 consumer-delete-before-retry，並製造兩段 producer 可見 manifest 相同的歷史；同一 Deliver 重試在兩案都只能回 `Unknown`，consumer ack 出現後才回 `Already`。
- `wf/workflows/hackathon/records/core-scope/verdicts.md`〈第 2 輪評分與意見／p4（Thompson persona）〉把 publish-success-before-receipt 指定成上一場的下一刀，〈第 3 輪評分與意見／p4（Thompson persona）〉記到修正版 `diff_exit=0` 與兩歷史同回 `Unknown`，可核對 Hickey／Pike 下一輪的死亡窗與不可區分歷史不是第一次有人踩。
- `core/inst/docs/cxxapi.md`〈函式〉、`core/inst/include/aos/inst.hpp` 的 `read_all()` 宣告，以及 `core/inst/tests/test_format_read.cpp` 的 `read_all accepts a single instruction object`、`read_all accepts a formatted array of instruction objects`、`read_all is atomic and reports a one-based record number` 已給出 canonical C++ batch parser、整批原子失敗與 one-based `error_record` 的現成行為。
- `core/inst/docs/capi.md`〈讀取、寫入與執行〉已明寫 C ABI 的三個 read 入口只接受單筆 object、不接受 batch array；`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／2. 坑的總表〉又已有 private validator 對 canonical object parser 的 `4` 案錯放、`2` 案錯擋與 `3` 案 batch API gap 實測。
- `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 與 `core/inst/tests/test_handoff.cpp` 的 `handoff aggregates deliveries in filename order and flattens batches` 已有 `read_all()` 驗證、發布 aggregate、再刪 accepted deliveries 的現行順序；`core/inst/docs/handoff.md`〈公開 API 與錯誤資料〉另列 `HandoffResult`／`HandoffIssue` 已有的 `published`、path、`InstState` 與 errno 資料。
- `wf/workflows/workshop/records/tool-interop.md`〈退出碼還沒有共同編號〉已記 world 與 payload 都錯時的先後仍未定，〈給模型看的錯誤訊息〉則已有 code、JSON Pointer／欄位路徑、expected／actual 與 machine-readable detail 的共同語意，但欄位名尚未收斂。
- `docs/aos-folder.md`〈八、退出碼〉、`docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉與 `wf/workflows/common/gotchas.md`〈使用 aos〉已釘死現有 `aos exec` 的 `0/1/2/3` 是回合層契約、不是 child 結果，因此 Deliver 若另編 `3–6` 並不能援引這套號碼作全域 taxonomy。
- `docs/aos-folder.md`〈四、路徑基準：一律是 `<folder>`〉已回答 instruction 內 `cwd`、stdin／stdout／stderr／exit 與 `$ref` 的相對路徑基準；它沒有寫 Deliver 的 `-f FILE`，所以只能用來分清「既有 world 內路徑規則」與「本輪新增 input FILE 規則」不是同一件事。
- `wf/workflows/workshop/background/delivery-contract.md`〈Publish〉〈Deliver〉〈correlation ID〉〈receipt〉與 `wf/workflows/workshop/background/reliability.md`〈idempotency key〉〈ledger〉〈`unknown`〉已把可見發布、queue handoff、串接編號、單次完成證據與長期歷史分開，對得上本輪 `1/4` 與 aggregate 後失憶的命題邊界。

### 3. 兄弟專案裡可以抄的

- `/home/lorkhan/repo/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉已有同目錄 temp、write-all、file fsync、atomic rename、directory fsync，以及 intent 已存在但完整結果缺失時維持 `unknown` 的文字基線。
- `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish()`／`fsync_directory()` 已有唯一 temp、`O_EXCL`、完整寫入、file fsync、`os.replace`、directory fsync、同內容既有 target 直接返回與異內容拒絕的可執行樣本；`/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉同時明列它沒有 multiwriter、power loss、NFS 與 GC 證據。
- `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/README.md`〈由小到大：一次呼叫〉與 `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`／`_terminal()`／`recover()` 已把完整 receipt、receipt-ready 與 terminal 分階段；`/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/test_p0.py` 的 `test_recover_receipt_without_terminal_only_projects_terminal()` 正是結果已保存、最後回覆標記尚未完成的可重跑樣本。
- `/home/lorkhan/repo/simple_tools/agent-machine/archived/2026-08-13-snapshot/COMMANDS.md`〈waiting、send 與 skip〉已有 controlling TTY 時從 `/dev/tty` 讀、沒有 TTY 時不讀 pipeline stdin 的明示分流；它是封存的 AgentOS 指令契約，不是現成 Deliver 行為。
- `/home/lorkhan/repo/simple_tools/agent-machine/archived/2026-08-13-snapshot/OUTPUT.md`〈`--json` machine mode〉〈最小 JSON objects〉〈exit code〉已有單一 JSON stdout、預期拒絕仍回 JSON＋non-zero、穩定 `code` 與可變人類 `message` 分離，以及 `0/1/2/130` 小集合的 machine contract 實例。
- `/home/lorkhan/repo/simple_tools/arc_agi_tweets/arc_tweets/storage.py` 的 `_atomic_write()` 已有同目錄 `NamedTemporaryFile`、完整寫入、`os.replace` 與 finally 清殘留 temp 的輕量原子寫入樣本，但沒有 fsync、no-replace、receipt 或 multiwriter 契約。
- `/home/lorkhan/repo/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉與〈整個實例被強制終止〉已明寫工具失敗不代表外部副作用 rollback、整個 process 被殺時只保留當時已保存狀態；`/home/lorkhan/repo/simple_tools/freepy/agentloop/CONTROLLER.md`〈明確不負責〉則明列它不處理持久化、queue 與副作用 recovery。
- `/home/lorkhan/repo/simple_tools/dcap/tool/README.md`〈失敗時會怎樣〉已有成功走 stdout、失敗固定 exit 1 並走 stderr、既有目標拒絕覆蓋的簡單 CLI 對照，但它沒有 JSON 結果、typed location 或 batch validator。

### 4. 還是查不到的

- `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪紀錄／5. 仍然不知道的〉與 `wf/workflows/workshop/records/tool-interop.md`〈退出碼還沒有共同編號〉都只記到 world／payload 誰先驗尚未定，repo 與 `/home/lorkhan/repo/simple_tools/agent-machine/`、`/home/lorkhan/repo/simple_tools/freepy/`、`/home/lorkhan/repo/simple_tools/dcap/`、`/home/lorkhan/repo/simple_tools/arc_agi_tweets/` 都沒有「world 版本同時錯＋payload 同時錯」及「第二筆同時多個 schema 錯」的共同優先序實測，**這條沒有現成資料**。
- `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪評分與意見／Evans persona〉只提出 TTY 與已關閉 stdin 的驗收，而 `/home/lorkhan/repo/simple_tools/agent-machine/archived/2026-08-13-snapshot/COMMANDS.md`〈waiting、send 與 skip〉只是另一支 CLI 的類似規則，四個兄弟專案都沒有 bare `aos deliver` 在這兩種 stdin 現場立即拒絕的輸出，**這條沒有現成資料**。
- `core/inst/docs/cxxapi.md`〈函式〉的 `read_all()` 只回 `InstState`＋one-based record，`wf/workflows/workshop/records/tool-interop.md`〈給模型看的錯誤訊息〉又明記 `path/field/at/pointer` 尚未收斂，因此 byte offset、JSON Pointer、world version 與 filesystem path 共用哪個 tagged location 公開型別，**這條沒有現成資料**。
- `wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪評分與意見／Evans persona〉指出 `6/6` 尚未證明 `message` 必要，`/home/lorkhan/repo/simple_tools/agent-machine/archived/2026-08-13-snapshot/OUTPUT.md`〈最小 JSON objects〉只提供「程式比 code、message 可改」的另一專案契約，尚無 Deliver consumer 移除 `message` 前後的決策差異輸出，**這條沒有現成資料**。
- `core/inst/docs/capi.md`〈讀取、寫入與執行〉與 `core/inst/include/aos/inst.h` 都只有 single-object C 入口，`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉也確認 array 三案仍是 API gap，因此「只用現有 C ABI 驗完整 object／array batch」**這條沒有現成資料**。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉與 `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉都排除 power loss、NFS、非 Linux filesystem 與 multiwriter GC，因此這些環境下的 Deliver durability、portable no-replace 與 orphan temp 清理數據，**這條沒有現成資料**。

## 第 1 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人各做了一個臨時版本，把手動送一筆、前一支程式接著送、一次送多筆三種情況都實際走過。結果顯示東西能完整放進去，也能被現有程式拿走；但東西被拿走後，系統就認不出同一件事以前是否送過。命令怎麼寫、要不要記住重送、成功或失敗要回什麼，這輪都縮小了範圍，還沒有替你定案。

### 2. 冒出來的新詞

**Publish／Deliver**  
**白話**：見 BACKGROUND。  
**在 aos 裡具體是什麼**：見 BACKGROUND。

**idempotency key／ledger**  
**白話**：見 BACKGROUND。  
**在 aos 裡具體是什麼**：見 BACKGROUND。

**no-replace／visibility atomicity／power-loss durability**  
**白話**：見 BACKGROUND。  
**在 aos 裡具體是什麼**：見 BACKGROUND。

**ABI／schema／共用檢查器**  
**白話**：見 BACKGROUND。  
**在 aos 裡具體是什麼**：見 BACKGROUND；`core/inst/include/aos/inst.hpp` 的 `read_all()` 已能檢查整批，Deliver 要怎麼直接沿用仍未實作。

**JSON Pointer**  
**白話**：像一份表格裡的格子地址；`/1/argv/0` 是「第二筆的 `argv` 裡第一格」。  
**在 aos 裡具體是什麼**：本輪錯誤輸出的提案，用來指出哪一格寫錯；公開契約還不存在，見 BACKGROUND。

### 3. 看到的錯誤訊息各是什麼意思

- `SyntaxError: f-string: expecting a valid expression after '{'`：測試腳本的引號把一段 Python 句子弄殘了，壞的是測試接線，不是 Deliver。
- `aos init: cannot open .../world-a: No such file or directory`：測試以為 `aos init` 會順手建立 `world-a` 資料夾，但它要求資料夾先存在。
- `Traceback ... FileNotFoundError: .../world-a/.aos/version`：上一個初始化已失敗，測試仍往下讀根本沒產生的版本檔，所以這是連帶錯誤。
- `./build/bin/aos: unknown command 'deliver'`：現有 `aos` 還沒有 `deliver` 子命令，正好確認本題是在試一個尚未實作的介面。
- `fatal: not a git repository (or any of the parent directories): .git`：那份比賽場地沒有可用的 Git 紀錄，所以不能用 `git status` 查改了什麼；不是程式本身壞掉。
- `JSON_PARSE`／`json_syntax`：收到的文字連合法 JSON 都不是，要先修逗號、括號或引號。
- `SCHEMA`／`schema`，位置 `/1/argv/0`：JSON 本身讀得懂，但第二筆指令的第一個命令項不是字串。
- `WORLD_VERSION`／`world_version`：目標資料夾的 `.aos/version` 不是這支程式認得的版本，所以沒有投遞。
- `ENOTDIR`：程式要當資料夾走的路徑其實是普通檔案，因此無法在裡面建立投遞檔。
- `errno 13`／`io_eacces`／`Permission denied`：作業系統不准往目標位置寫，通常是權限不足。
- `USAGE`：命令的參數寫法不符合這份草案；這是呼叫方式錯，不是內容或目標壞掉。

### 4. 所以呢

**第 7 題：`aos deliver` 怎麼寫。**

- (a) 只交檔案：手打最短；但從管線或工具送資料時要先多造檔，檔案夾在兩個 world 裡時還要另定到底送去哪個。
- (b) `FOLDER [FILE]`：三種現場都不用多造檔；代價是沒寫 FILE 時可能默默等輸入，相對 FILE 到底從目前位置還是 FOLDER 起算也要拍板。
- (c) `WORLD --target X`：日後可投給別種目標；代價是現在每次都要多填一個尚無第二位使用者的 X，還得先定 X 是名字還是路徑、從哪裡起算。
- (d) `WORLD [-f FILE | -]`：world 與資料來源分開寫；來源若可省略，仍可能默默等輸入，若改成必填則每次都要多打 `-f` 或 `-`。

**第 8 題：`key` 承諾什麼。** 四份實驗對「投遞檔被拿走後就沒有舊證據」一致；發布前是否算一次則是 `2/4` 與 `1/4` 的唯一分歧。

- 第一版沒有 key：不會暗示重送安全；代價是回覆遺失時，呼叫者無法放心再送一次。
- 只作串接編號：能把一次請求與輸出對起來；代價是不能防止重做，也必須避免讓人把它誤認成防重號碼。
- 只在待辦檔仍存在時防重：不用多存一本帳；代價是同一個 key 會隨檔案是否已被拿走而改口。
- 增加長期帳本：拿走檔案、重開程式後仍能回答 `Already`／`Conflict`；代價是要一起負擔保存多久、清理、容量、損壞與中斷後修復。

**第 9 題：成功、錯誤與退出碼。** 這輪證明 4 欄、6 欄與較細的 14 欄都能被測試用的 shell 與工具讀取，但「剛寫的讀取者有讀」還不等於真使用者需要。

- 4 欄 `ok/count/code/at`：最小；代價是 `at` 同時裝字數位置、資料格地址與檔案路徑，程式不容易分辨。
- 6 欄 `result/count/error/where{kind,value}`：每種錯誤位置有明確種類；代價是格式較深、要固定更多欄位。
- 6 欄平面版 `ok/delivery/count/code/pointer/message`：shell 好讀、人也有說明；代價是 `delivery` 目前無處查，`message` 一旦算固定介面就難改字。
- 細分到 14 個實讀欄位與 `0,2,3,4,5,6`：能精確指出每類錯誤；代價是欄位與號碼都較早定死，而且命令列號碼與 JSON 類別可能變成兩套要保持一致的規則。
- 成功與失敗都放同一條輸出：機器只收一處；成功走一般輸出、失敗走錯誤輸出：人在終端較自然，但包裝程式必須同時接兩邊。

## 第 2 輪紀錄

### 1. 各人做了什麼

Pike persona 這一路是**照著改，沒有整條重作**。它接受評委對 key 證據的糾正，把數字二從 `2/4` 改成 `1/4`，新增 `Attempting → Visible → Aggregated → Forgotten` 狀態機，讓成功歷史真的走既有 `aos exec`，並把單一 `at` 改成 `location:{kind,value}`、退出碼縮成 `0/1/2`。它保留原本的 `(b) FOLDER [FILE]`，用 caller cwd 與 world 各放一份不同的 `one.json`，實跑確認相對 FILE 取 caller cwd 那份。這也是四位裡唯一一條**明白不同意評委所選 CLI 路線**的回報：它不同意用 `(d')` 的 `-f`／`-` 明示來源，理由是來源規則本身已能消除歧義，多一個旗標不會增加明確性。四種 CLI 的三個現場重新全跑，完整輪次在 `p1/deliver-lab/run.nEMF4E`；未改 C++、未 build。

Hickey persona 這一路也是**照著改，沒有整條重作**。它沿用 `(d)`，但收緊成必須明寫來源的 `(d') WORLD (-f FILE | -)`；把普通 replace 改成 Linux `renameat2(RENAME_NOREPLACE)`，用 gate 實跑同名雙 producer，並在 rename 後、stdout 前精確 SIGKILL。它移除 Python acceptance parser，從現成 `libaos_inst.so` 直接呼叫 `aos::read_all()`，因此撤回上一輪自行產生的 `/1/argv/0`，第二筆錯誤只回 canonical parser 真有的 `FieldTypeMismatch＋error_record=2`。輸出從 `6/6` 收成 `5/5`，退出碼收成 `0/1/2`；人工檔、pipe、tool batch 都被真 `aos exec` 接走。ABI-local `ctypes` 接法只留作證據 shim，沒有當成產品方案；未改 C++、未 build。

Cantrill persona 這一路是**照著改，沒有整條重作**。它接受評委對 `18/14`、細分退出碼與 stdout/stderr 雙分類的診斷，把 CLI 收緊成 `(d')`，把輸出改成外層 `published/rejected/failed` tagged union，預期結果全走 stdout JSON，stderr 留給程式本身崩壞；exit 只是 outer tag 的 `0/2/1` 粗投影。它刪掉 `message,published,receipt,target`，實跑 world 與 payload 同錯、第二筆同時有三個 schema 錯、七行 exit-only shell、完整 tool caller，以及只讀 `result` 的負向對照 caller。有效現場在 `p3/wf/workflows/experiments/deliver-contract-p3/out/round5/`；成功 batch 交給真 `aos exec` 後執行兩筆並清掉 ready。它沒有接 canonical parser，也沒有重跑 key ledger；未改 C++、未 build。

Evans persona 這一路是**照著改，沒有整條重作**。它明寫接受評委指出的四個證據缺口，在原場地增加嚴格 `(d')`，讓一個兩筆 batch 只成為一個 ready，再交給預建的真 `aos exec` 執行；用實際 `open(...O_EXCL...)` 製造 `errno=13 EACCES`；在控制 TTY 與關閉 fd 0 的現場證明 bare invocation 都立即 exit 2；最後移除 `message`，把 `6/6` 收成 `5/5` 並重跑 shell 與 tool caller，前後 machine decision 相同。完整紀錄在 `p4/deliver-contract-lab/R2-RESULTS.md`。它仍使用 toy validator，普通 rename 也尚未換成 no-replace；未改 C++、未 build。

本輪沒有人宣告整條路線重作。Hickey、Cantrill、Evans persona 都把評委指定的 `(d')` 當成修正版繼續；Pike persona 接受 key、location 與 exit 的修正，但明白保留 `(b)`，並寫出不採 `(d')` 的理由。

### 2. 坑的總表

**四位獨立地都撞到：無 durable ledger 時，四個重叫位置只有 publish 後、aggregate 前有 committed witness。** 四份回報都給 `1/4`；發布前的 temp／reservation 只證明 attempt，aggregate 後 ready 已刪，process 重開後也沒有保存的 key 事實。Pike persona 另造出兩段磁碟內容完全相同、真相卻一個是 `NotAlready`、一個是 `Already` 的歷史：

```text
history=never truth=NotAlready disk_sha256=b417940964b539e5c797193fbd2b3cf4dcd8b5afe45e543891841bb7e9068992
history=published truth=Already disk_sha256=b417940964b539e5c797193fbd2b3cf4dcd8b5afe45e543891841bb7e9068992
disk_equal=yes
history-never: verdict=Unknown evidence=none
history-published: verdict=Unknown evidence=none
same_observation_requires_two_answers=yes
```

Hickey persona 把 rename 成功但回覆尚未送出的窗口實際殺掉，磁碟已有一份 ready，但 caller 沒收到任何 stdout/stderr：

```text
$ mock_deliver.py d .../world -  # SIGKILL after rename marker
kill_returncode=-9 shell_exit=137 caller_stdout_bytes=0 caller_stderr_bytes=0
disk_visibility=published visible_ready=1 ready_sha256=d2cabbd17b8513e0ee20ec57e53a9843f10ef76ee1751b70fc488c14b0086ef3 caller_knowledge=unknown
```

同一輸入盲重叫後出現兩份相同 ready，真 `aos exec` 執行兩次：

```text
blind_retry_exit=0
blind_retry_stdout={"count":1}
visible_ready_after_retry=2
identical_payloads=True

aos_exec_exit=0
effect_lines=2
stdout=receipt-loss-effect|receipt-loss-effect
ready_after_exec=0
```

**四位獨立地都撞到：canonical `read_all()` 現有錯誤面不足以直接產生完整 JSON Pointer。** Pike、Hickey、Cantrill、Evans persona 都寫到，現有 C++ batch parser能提供 `InstState` 與 one-based record，但不能直接提供 `/1/argv/0`、expected、actual。Hickey persona 直接呼叫 shared-library symbol 得到：

```text
case=second_argv0_type state=FieldTypeMismatch count=0 error_record=2
case=unknown_key state=UnknownKey count=0 error_record=1
case=json_syntax state=JsonSyntax count=0 error_record=0
```

它因此撤回 toy parser 的 pointer；另外三路仍把 pointer 或 typed location 保留為候選契約，同時明寫真 C++ 目前產不出同樣 detail。

**四位獨立地都把退出碼縮到三個大類，但實際映射有兩種。** Pike、Hickey persona 用 `0=成功、1=所有 machine failure、2=CLI 文法誤用`；Cantrill、Evans persona 用 `0=published、1=operation/I/O failure、2=caller input/payload/world rejected`。四路都不再把 JSON parse、schema、world 與 I/O 各編一個 Deliver-local exit number，細部原因留在 JSON。

**四位獨立地都明寫「欄位有被這輪 consumer 讀到」不等於長期必要。** Pike persona 的 `6/6`、Hickey persona 的 `5/5`、Cantrill persona 的 `11/11`、Evans persona 的 `5/5` 都是實際讀取數；四份回報都另外限制這個數字的含義。Cantrill persona 的負向對照 caller 只讀一個 `result`，仍作出相同的五個 coarse decision：

```text
fields=11 read=1 unread=10
read_names=result
unread_names=actual,count,errno,error,expected,kind,operation,record,value,where
same_decision=5/5
```

**三位獨立地都把 `(d)` 收緊成 `(d') WORLD (-f FILE | -)`；Pike persona 保留 `(b)`。** Hickey、Cantrill、Evans persona 都讓 bare `WORLD` 直接 usage error，不再以 FILE 缺席暗示 stdin。Evans persona 在 TTY 與 closed stdin 各跑一次；第一次 harness 沒有跑到 Deliver，原文是：

```text
zsh:3: no such file or directory: /usr/bin/time
exit=127
```

改用 `date +%s%N` 後才得到：

```text
$ timeout 2 script -qec ... /dev/null
stdin_tty=yes
{"ok":false,"code":"usage"}
exit=2 elapsed_ms=26

$ timeout 2 sh -c ... 0<&-
stdin_fd=closed
{"ok":false,"code":"usage"}
exit=2 elapsed_ms=15
```

Pike persona 則把 `(b)` 的相對 FILE 基準固定為 caller cwd，並用同名不同內容的檔案實跑：

```text
$ cd /home/lorkhan/aos-hack/deliver-contract/p1/deliver-lab/run.nEMF4E/source-rule/caller && /home/lorkhan/aos-hack/deliver-contract/p1/deliver-lab/drafts/b/aos deliver ../world one.json
{"ok":true,"count":1}
published_argv0=caller-cwd
```

**三位獨立地把錯誤位置做成帶 tag 的值。** Pike persona 是 `location:{kind,value}`，Hickey persona 是 `where:{kind,value}`，Cantrill persona 也是 `where:{kind,value}`；tag 名與種類尚不同。Evans persona 仍用平面的 `pointer`，而真 I/O machine JSON 只有 `{"ok":false,"code":"io"}`，path 與 `EACCES` 只存在 lab trace。

**兩位獨立地實跑複合錯誤並先回 world。** Hickey persona 的輸出是：

```text
case=bad_world_and_bad_payload
exit=1
stdout={"error":"world_version","where":{"kind":"world_version","value":"999"}}
visible_ready=0
priority=world_before_payload
```

Cantrill persona 的輸出是：

```text
case=world-and-json-bad exit=2 stdout_json={"result":"rejected","error":"unsupported_world","where":{"kind":"world","value":"wf/workflows/experiments/deliver-contract-p3/out/round5/world-compound"},"expected":"1","actual":"99"}
priority_world_vs_payload=unsupported_world
```

Evans persona 的 mock 也先驗 world，但它明寫這個順序沒有實驗支持；Pike persona 本輪沒有做複合錯誤優先序。

**同名雙 producer 的 no-replace 只有 Hickey persona 本輪實跑。** 舊 replace 基線讓兩個 caller 都回成功、磁碟只有一份：

```text
race=legacy-replace producer=A exit=0 stdout={"count":1} stderr=(empty)
race=legacy-replace producer=B exit=0 stdout={"count":1} stderr=(empty)
race=legacy-replace published_claims=2 visible_ready=1 temps=0 disk_payload=B reported_winner=B
```

改成 `renameat2(RENAME_NOREPLACE)` 後是一個成功、一個 `io_eexist`：

```text
race=noreplace producer=A exit=0 stdout={"count":1} stderr=(empty)
race=noreplace producer=B exit=1 stdout={"error":"io_eexist","where":{"kind":"target_path","value":".../.aos/inst.tempd"}} stderr=(empty)
race=noreplace published_claims=1 visible_ready=1 temps=0 disk_payload=A reported_winner=A
```

這份實驗只跑 Linux `renameat2`；其他三路沒有測同名 no-replace。

本輪另保留三個測試接線失敗。Pike persona 第一次測真 `aos init` 時沒有先建 world：

```text
aos init: cannot open /tmp/aos-r2.fc0efg/world: No such file or directory
init_exit=1
```

補 `mkdir` 後才得到 `init_exit=0`、`exec_exit=0`。Cantrill persona 第一次用 zsh 字串代替 array 傳五個 fixture，五條路徑被當成一個檔名：

```text
fixtures='a b c'
tool $fixtures
```

```text
FileNotFoundError: [Errno 2] No such file or directory:
'.../v2-success.json .../v2-json-syntax.json'
exit=1
```

改成 zsh array 後才跑通。Evans persona 的 `/usr/bin/time` 失敗如上，沒有把 `exit=127` 算成 Deliver 證據。

### 3. 好處／壞處

#### 好處

四條路都把 publish 的可見邊界放在 rename，並把 key 的 attempt、visible、aggregated、forgotten 分開記。Pike persona 的不可區分歷史與 Hickey persona 的 receipt-loss 現場都留下可重跑輸出；同 key 安全重叫不再只靠文字推論。

Hickey、Cantrill、Evans persona 都把人工檔、pipe 或 batch 的成功輸出接進既有 `aos exec`；Pike persona 的成功 key 歷史也走過真 `aos exec`。Evans persona 的兩筆輸入恰好成為一個 ready，之後兩筆依序執行；Hickey persona 的 no-replace race 讓成功 caller 數與可見 ready 數都變成 1。

四路都刪減了退出碼或 JSON 欄位。Pike persona 把 untyped `at` 換成帶種類的位置；Hickey persona 移除 `result` 並讓 acceptance 直接來自 canonical `read_all()`；Cantrill persona 把 outer result、exit 投影與 inner detail 分層；Evans persona 移除 `message` 後，兩個 consumer 的 machine decision 沒變。

#### 壞處

三條 `(d')` 路線每次都要明寫 `-f` 或 `-`；Pike persona 的 `(b)` 少一個 token，但 bare `aos deliver FOLDER` 在 TTY 會等 stdin。四種草案的「歧義」與「必填參數」計數口徑仍不一致。

Hickey persona 的 canonical parser 證據靠 ABI-local `ctypes` 手術，依賴 `libstdc++ vector layout = 24 bytes`、`sizeof(aos::inst_t) = 280`、固定 mangled symbol 與短命 process；它沒有提供正式 FFI。Pike、Cantrill、Evans persona 的候選 pointer/detail 又比 canonical parser 目前公開的資料更多。

無 key 時，rename 後回覆遺失沒有安全的自動重叫方法；有 key 但沒有 ledger 時，aggregate 後仍答不出 `Already`。no-replace 只處理同名覆蓋，沒有處理回覆遺失或 delivery 被刪後的歷史。

這輪只驗 visibility atomicity，沒有一條路完成 file fsync、directory fsync、power cut、NFS 或跨平台 no-replace。Hickey persona 的 no-replace 是 Linux-only；Pike、Cantrill、Evans persona 都沒有跑同名競爭。

machine output 還有 stream 分歧：Pike、Hickey、Cantrill persona 的預期 JSON 都走 stdout；Evans persona 的 live success 走 stdout、failure JSON 走 stderr。Evans persona 移除 stable `message` 後也保留了人類診斷要放哪裡的空缺。

### 4. 題目那三個數字

#### 數字一：四種 CLI 套三個真呼叫

Pike persona 重新跑完四種草案的三個現場，回報的三場合計口徑是「額外 caller temp／歧義／必填參數」：

| 草案 | Pike persona |
|---|---:|
| (a) | `2 / 1 / 1` |
| (b) | `0 / 0 / 1` |
| (c) | `0 / 0 / 2` |
| (d) | `0 / 0 / 1` |

跑後計數原文是：

```text
published_files=14
leftover_protocol_temps=0
caller_temps_a=2
caller_temps_b=0
caller_temps_c=0
caller_temps_d=0
```

它選 `(b)`；三個現場各需的 temp 從實跑計數可見，歧義與必填參數以草案整體各列一次，沒有交出逐現場 12 格的不同數值。

Hickey persona 交出完整 12 格；每格依序是「額外臨時檔／歧義／必填語意值」：

| 草案 | 人工檔案 | pipe 單筆 | agent 批次 | 三場合計 |
|---|---:|---:|---:|---:|
| (a) | `0/1/1` | `1/1/1` | `1/1/1` | `2/3/3` |
| (b) | `0/0/1` | `0/0/1` | `0/0/1` | `0/0/3` |
| (c) | `0/1/2` | `0/1/2` | `0/1/2` | `0/3/6` |
| (d') | `0/0/2` | `0/0/2` | `0/0/2` | `0/0/6` |

它選 `(d')`。這一路實跑 `-f FILE`、pipe 與 tool caller，三者共 `ready_deliveries=3 temp_deliveries=0`，再由真 `aos exec` 執行四筆並清空 ready。

Cantrill persona 回報草案整體數字，沒有逐現場拆成 12 格：

| 草案 | Cantrill persona |
|---|---:|
| (a) | `2 / 1 / 1` |
| (b) | `0 / 0 / 1` |
| (c) | `0 / 2 / 2` |
| (d') | `0 / 0 / 2` |

它本輪改選 `(d')`，把上一輪原始 `(d)` 的 `0/0/1` 改成 `0/0/2`；實跑集中在 `(d')`、複合錯誤與 consumer。

Evans persona 保留原四案 12 格，並另列嚴格 `(d')` 的草案整體數字：

| 草案 | 人工檔案 | pipe 單筆 | agent batch | 三現場合計 |
|---|---:|---:|---:|---:|
| (a) | `0/1/1` | `1/1/1` | `1/1/1` | `2/3/1` |
| (b) | `0/1/1` | `0/0/1` | `0/0/1` | `0/1/1` |
| (c) | `0/1/2` | `0/1/2` | `0/1/2` | `0/3/2` |
| (d) | `0/1/1` | `0/0/1` | `0/0/1` | `0/1/1` |

它給 `(d') = 0 / 0 / 2`，並選 `(d')`。這輪的真 aggregator、真 I/O、TTY 與 closed-stdin 實跑都集中在 `(d')`；原四案 12 格沿用上一輪計數。

四份的 caller temp 對 (a) 與其餘三案一致：三場合計 (a) 為 2，其餘為 0。歧義與必填參數則使用不同口徑：Hickey persona 把每個現場的值相加；Pike、Cantrill persona 按草案列一次；Evans persona 的「三現場合計」也保留每次呼叫的必填值，不做三次相加。CLI 選擇是三份 `(d')`、一份 `(b)`。

#### 數字二：四次同 key 同內容重叫

四位現在都答 **`1/4`**：

| 位置 | 四份回報 |
|---|---|
| ① 發布前 | 答不出曾 publish；只有 reservation／temp／未 commit attempt |
| ② 發布後、aggregate 前 | 答得出；matching ready delivery 還在 |
| ③ aggregate 後 | 答不出；ready 已刪，aggregate bytes 沒有 durable key 綁定 |
| ④ process 重開後 | 答不出；沒有 ledger／receipt 保存歷史 |

Pike persona 把上輪 `2/4` 改成 `1/4`，並用真 `aos exec` 與相同 disk hash 的兩段歷史補證據。Hickey persona 保留 `1/4`，新增 SIGKILL receipt-loss、盲重叫與真 `aos exec` 的兩次 effect。Cantrill persona 保留 `1/4`，本輪沒有重跑 key ledger。Evans persona 重跑 toy queue 得到 `answerable_steps=1`。四份都寫首版不公開 `--key`；Pike、Hickey persona 另明寫 no-replace／receipt-loss 不會改變這個數字。

#### 數字三：輸出契約設計幾個欄位、實際讀到幾個

| 回報者 | 設計／實讀 | 欄位 | 未讀欄位 | 本輪實際消費 |
|---|---:|---|---|---|
| Pike persona | `6 / 6` | `ok,count,code,location,kind,value` | 無 | 6 行 shell＋假 tool caller，各讀五個 live case |
| Hickey persona | `5 / 5` | `count,error,where,kind,value` | 無 | 10 行 shell＋假 tool caller，各讀五份新版輸出 |
| Cantrill persona | `11 / 11` | `actual,count,errno,error,expected,kind,operation,record,result,value,where` | 無 | exit-only shell＋完整 tool caller；另有只讀 `result` 的 `11/1` 負向對照 |
| Evans persona | `5 / 5` | `ok,delivery,count,code,pointer` | 無 | 10 行 shell＋假 tool caller，移除 `message` 前後決策相同 |

Pike persona 的成功／失敗輸出是 `{"ok":true,"count":2}` 與 `{"ok":false,"code":...,"location":{"kind":...,"value":...}}`，exit 是 `0/1`，只有 CLI 文法誤用為 2。Hickey persona 的成功是 `{"count":2}`，失敗是 `{"error":...,"where":{"kind":...,"value":...}}`，exit 也是 machine success/failure `0/1`、usage 2。Cantrill persona 的 outer `result` 映成 `published→0`、`rejected→2`、`failed→1`；完整 tool caller 讀 11 欄，但只讀 `result` 的 caller 也做出相同五個 coarse decision。Evans persona 用 `ok/code` 配 `0/1/2` 大類，成功另有 `delivery,count`，schema case 才有 `pointer`；`message` 已刪。

### 5. 仍然不知道的

CLI 還沒有共同答案。Hickey、Cantrill、Evans persona 選 `(d') WORLD (-f FILE | -)`，Pike persona 選 `(b) FOLDER [FILE]`；bare invocation 應立即拒絕還是以 FILE 缺席表示 stdin，仍是兩種契約。四份對「歧義」與「必填參數」也仍用不同加總口徑，12 格尚未變成一張共同可直接比較的表。

canonical validation 的落地面仍缺一塊。Hickey persona 證明現有 shared library 的 `read_all()` 可被直接叫到，但 ABI shim 不是產品 API；現有回傳只有 `InstState＋error_record`，尚不知道 Deliver 是否只公開 record、擴 canonical error type，或放棄 JSON Pointer／expected／actual。Pike、Cantrill、Evans persona 的候選錯誤 detail 尚未與 canonical parser逐案對齊。

輸出 schema 仍有四種：`ok/code/location`、`error/where`、`result` tagged union、`ok/code/pointer`。預期錯誤 JSON 全走 stdout，或 success stdout／failure stderr，也未共同。退出碼雖都縮成三個值，`2` 只代表 CLI usage，還是代表所有 caller 可修正的 rejection，仍有兩種。

world 與 payload 同時錯時，Hickey、Cantrill persona 實跑的是 world first，Evans persona 只把它當 mock 選擇；這個優先序是否成為公開契約仍不知道。第二筆同時多錯時，Cantrill persona 的 mock 先回 unknown key；canonical parser 是否公開凍結相同欄位優先序也仍不知道。

同名競爭只有 Hickey persona 在 Linux `renameat2(RENAME_NOREPLACE)` 跑過一次。多輪競爭、非 Linux、NFS、orphan temp cleanup、cleanup 本身失敗時回哪個錯，以及 no-replace collision 應回隨機名重試還是 stable target conflict，仍沒有共同資料。

回覆遺失已實際重現，但沒有安全重叫方案；durable ledger、stable intent、consumer acknowledgment、retention 與 GC 都沒有做。四份都選首版不公開 key，沒有回答若日後公開 key 要付哪一組持久狀態成本。

仍未測 file fsync、directory fsync、power loss 與 durability。空 batch 被 canonical `read_all()` 接受為 `count=0`，但公開 Deliver 應成功、拒絕或 no-op 尚未定。ready bytes 是 caller 原始 bytes、何時 canonicalize，也只有 Hickey persona 明寫，沒有共同契約。

`delivery`／receipt 沒有 query surface 時是否保留仍不知道。Evans persona 移除 stable `message` 後 machine decision 不變，但人類診斷要放 optional message、stderr prose、另做 renderer，或另設 machine/human mode，仍未跑出共同答案。

## 第 2 輪評分與意見

### Pike persona

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5 / 5 |
| 誠實度 | 5 / 5 |
| 走了多遠 | 4 / 5 |
| 回答了三個數字 | 5 / 5 |
| 路線價值 | 4 / 5 |
| **總分** | **23 / 25** |

講評：最有價值的不是把 `2/4` 改成 `1/4`，而是用相同 `disk_sha256` 的兩段歷史證明：相同可觀測狀態需要分別回答 `NotAlready` 與 `Already`，所以沒有 ledger 的實作不可能正確回答。你也誠實指出 `location` 的 6/6 是自寫 consumer 的弱證據，且 `/1/argv/0` 不是現有 canonical parser 能產出的事實。

下一輪：先做你提出的兩個 publish 接縫；每個接縫都列出操作序列、允許的終態與不變式，尤其要驗證「兩個 producer 不得都成功」及「rename 後失去回覆時只能回 Unknown」，不要再擴 JSON 欄位。

### Hickey persona

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5 / 5 |
| 誠實度 | 5 / 5 |
| 走了多遠 | 5 / 5 |
| 回答了三個數字 | 5 / 5 |
| 路線價值 | 5 / 5 |
| **總分** | **25 / 25** |

講評：`legacy-replace` 的「2 個成功 claim、1 個 ready」與 `RENAME_NOREPLACE` 的「1、1、winner payload 一致」直接檢驗了 publish 成功命題；SIGKILL 後 `visible_ready=1`、caller 無輸出，再盲重叫並由真 `aos exec` 產生兩次 effect，則把 Published 與 caller-known-success 明確分開。你沒有把危險的 ABI shim、Linux-only no-replace 或缺少 fsync 說成產品方案，這份回報的主張與證據邊界一致。

下一輪：把競爭測試擴成多輪，逐輪核對 `successful claims = visible ready = 1`、零覆蓋及孤兒 temp 數；再補 rename 前死亡與 cleanup 失敗，明定哪些失敗可保證「未發布」，哪些只能回 Unknown。

### Cantrill persona

| 項目 | 分數 |
|---|---:|
| 證據強度 | 4 / 5 |
| 誠實度 | 5 / 5 |
| 走了多遠 | 4 / 5 |
| 回答了三個數字 | 4 / 5 |
| 路線價值 | 4 / 5 |
| **總分** | **21 / 25** |

講評：外層 `published/rejected/failed` 與 exit 的投影是一個可檢查的有限狀態模型，複合錯誤也有實跑；但你沒有交出逐現場的 12 格，而且最豐富的錯誤位置仍來自 mock，不是 canonical `read_all()`。`11/1` 仍能作出 5/5 相同 coarse decision，反而是這輪最有用的刪減證據：其餘十欄尚未取得凍結資格。

下一輪：照你提出的 `InstState` 對照表做，但輸出必須逐格標成「現有 API 可產生／只能由第二次 parse 猜出／需要擴充 canonical type」；凡屬第二類的欄位，直接從首版契約刪掉。

### Evans persona

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5 / 5 |
| 誠實度 | 5 / 5 |
| 走了多遠 | 4 / 5 |
| 回答了三個數字 | 4 / 5 |
| 路線價值 | 4 / 5 |
| **總分** | **22 / 25** |

講評：TTY 與 closed stdin 都在 26 ms／15 ms 自行回 usage，以及真 `EACCES` 留下零 ready、零 temp，是支持 `(d')` 與失敗不發布的直接證據；第一次 `/usr/bin/time` 失敗也原樣揭露，誠實度沒有問題。可是第一個數字的表沿用舊計數且加總口徑自相矛盾，`delivery` 又沒有 query surface，所以這兩部分不能直接凍結。

下一輪：不要再美化 wrapper；用同一套 corpus 對 toy validator 與 canonical `read_all()` 逐案比對，報出分叉數，並用一個非量身訂做的 caller 檢驗刪除 `delivery` 後是否失去任何可觀測能力。

### 路線判斷

最值得繼續的是 Hickey persona 的「canonical validation＋exclusive publish＋明確輸入來源」路線。具體證據是 canonical probe 的 `batch_two state=Ok count=2` 與 `second_argv0_type state=FieldTypeMismatch error_record=2`，以及 no-replace race 的 `published_claims=1 visible_ready=1 disk_payload=A reported_winner=A`；前者避免第二套合法性定義，後者真正驗到了「成功」所必須保持的不變式。

看起來漂亮但有隱藏成本的是 Cantrill persona 的 11 欄 tagged union。它的負向對照已經顯示只讀 `result` 仍有 `same_decision=5/5`，而 `json_pointer/expected/actual` 又不是現有 canonical error type 能提供；若現在公開，實作者只能擴大 canonical API，或偷偷再解析一次，兩者都是長期契約成本。

致命的坑是把無 ledger 的 `--key` 說成冪等保證。Pike persona 的兩段不可區分歷史證明這不是「較難實作」，而是輸入給實作的證據相同、正確答案卻不同；Hickey persona 的 reply-loss 現場又證明 caller 甚至不能從沒收到 stdout 推知未發布。普通 rename 的靜默覆蓋、明示 `-` 多一個 token、人類診斷另做 renderer、孤兒 temp 清理則是麻煩：都需要工程與文件，但有可陳述、可測試的繞法，不構成不可能性。

沒有一份回報整體像捏造；不可信的是 Evans persona 回報中的「數字一」作為比較依據。它一方面說是三現場合計，另一方面把每次呼叫都必須有的參數仍合計成 1 或 2，且四案數字沿用前輪而非本輪重跑；在統一「每個現場各自計數，再逐欄相加」之前，不能用那張表判定 `(b)` 與 `(d)` 的勝負。這不扣它的誠實度，因為它明說沿用；扣的是答案硬度。

### 如果現在就得拍板

第 7 題選 **(d) world＋stdin／檔案**，但在寫 C++ 前把括號收緊成已實測的 `(d')`：`aos deliver WORLD (-f FILE | -)`。其契約是先完整驗證 CLI grammar 才碰 stdin，相對 FILE 以 caller cwd 解；一次成功呼叫使整批恰好成為一個 ready delivery，任何回傳的拒絕或 publish 前失敗不得產生 ready。

第 8 題選 **第一版沒有 key**。`delivery` 若暫時存在也只能是非持久 correlation，不得出現 `Already`、`Conflict` 或「可安全重試」的暗示；沒有 ledger 時，四個位置只能可靠回答 `1/4`。

第 9 題若必須在原四案選一個，選最接近本輪證據的 **delivery＋count 版**，但不照抄它原來的細分退出碼：exit 固定為 `0=published`、`1=operational failure`、`2=rejected/usage`，細因只在 JSON 出現一次。成功首版先只凍結 `count`；`delivery` 要等有查詢或對帳 consumer 才取得資格，失敗只公開 canonical parser 現在能誠實產生的 `error` 與 one-based `record`，不承諾 JSON Pointer、`expected` 或 `actual`。

第一步先寫並測 **私有 Publish 原語**，不是先寫完整 CLI：已驗證 bytes 寫入同目錄 exclusive temp，以 no-replace 語意發布，絕不覆蓋既有 ready。它必須把三件事分開：rename 前失敗＝NotPublished，rename 完成＝Published，rename 後尚未回覆便死亡＝caller Unknown；這三個狀態與不變式寫進測試後，才把 canonical `read_all()` 與上面的 CLI／JSON 薄層接上。以上是評審建議，最後拍板仍由使用者決定。

## 下一輪的資料包

### 1. 這輪卡住的清單

- **Pike persona** 卡在同 target 雙 producer 與 rename 後、回覆前死亡兩個 publish 接縫，尚未逐一列完操作序列、允許終態與不變式；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪評分與意見／Pike persona〉。
- **Hickey persona** 卡在把一次 Linux no-replace 競爭擴成多輪計數、補 temp 寫完但 rename 前死亡，以及 cleanup 自己失敗時留下什麼；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪評分與意見／Hickey persona〉。
- **Cantrill persona** 卡在逐個 `InstState` 分清現有 `read_all()` 能直接產生的資料、只能第二次 parse 猜出的資料，以及必須擴 canonical type 才有的資料；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪評分與意見／Cantrill persona〉。
- **Evans persona** 卡在用同一 corpus 量 toy validator 與 canonical `read_all()` 的分叉，並用非量身訂做的 caller 查刪除 `delivery` 是否真的損失能力；評委原話在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪評分與意見／Evans persona〉。
- **四位共同**仍卡在四案 12 格的「歧義／必填參數」統一計數口徑、canonical error 能公開到哪一層，以及成功 JSON 裡 `delivery` 是否有任何既有查詢面；彙整在 `wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪紀錄／5. 仍然不知道的〉與〈第 2 輪評分與意見／路線判斷〉。

### 2. repo 裡已經有答案的

- `core/inst/docs/format.md`〈驗證狀態〉已列完 canonical `InstState` 的全部拒絕類別；`core/inst/docs/cxxapi.md`〈函式〉又明寫 `read_all()` 對物件驗證錯只另給 one-based `error_record`，JSON syntax、成功與 invalid pointer 的 record 都是 0，沒有 JSON Pointer、expected、actual 或 byte offset。
- `core/inst/include/aos/inst.hpp`〈format：唯一懂得 JSON 文件 schema 的分層〉的公開宣告只有 `InstState read_all(..., std::size_t *error_record)`；同檔 `ResolveResult` 雖有 field、argv index、env key、pointer 等欄位，那是 resolve 層的型別，不是 format／Deliver parse error 的既有輸出。
- `core/inst/src/format.cpp` 的 `decode()` 已寫出現行單筆多錯順序：先掃 unknown key，再驗 `argv`，接著依字串欄位、`stderr`、`env`、`timeout_ms`、`parallel` 處理；`core/inst/tests/test_format_malformed.cpp` 的各個 `TEST_CASE` 覆蓋每種 `InstState`，但沒有一個測試把完整 JSON Pointer、expected 或 actual 當公開結果。
- `core/inst/tests/test_format_read.cpp`〈read_all is atomic and reports a one-based record number〉與〈read_all reports a non-object array element〉已有第二筆失敗、整批輸出清空、`error_record=2` 的 canonical fixture；〈read_all accepts an empty array and rejects an empty document〉另已回答空 batch 是成功且 count 0、空文件才是 `JsonSyntax`。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／2. 坑的總表〉已有一份可直接沿用的 parser conformance corpus 與分類口徑：16 案得到 3 個共同接受、4 個共同拒絕、4 個 private 錯放、2 個 private 錯擋及 3 個 C ABI batch gap，並列出 unknown key、錯型別、directive、duplicate key 與 array 的實際分叉。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 2 輪紀錄／2. 坑的總表〉已跑 same-target 雙 producer與各 1,000 件的 shared-slot／global-ID 壓力；同節記下普通 replace 會出現兩個成功 claim 卻只留一個 target，no-replace 路線則把一方變成 conflict。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／2. 坑的總表〉已有 publish-success-before-receipt、consumer-delete-before-retry、相同 producer-visible manifest 與 consumer ack 的實測；沒有 ack 的兩段歷史都只能回 `Unknown`，可直接核對本輪 rename 後回覆遺失不是新坑。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉已給普通 POSIX rename 的基線：直接寫 ready 會讓半份 JSON 被隔離，同一 PID 連投兩次會讓第二份靜默覆蓋第一份；批次若包在同一 JSON array，現有 aggregate 會保留批內順序。
- `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉與〈十二、留給實作決定的／仍然開著的〉已寫 visible 邊界、發布成功後才刪 accepted deliveries，以及現有 TOCTOU 可用 `renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink` 處理；同節也明列 `.bad`／`.runi` 殘存清理目前未做。
- `core/inst/docs/handoff.md`〈公開 API 與錯誤資料〉與 `core/inst/include/aos/inst.hpp` 的 `HandoffResult` 已列現有 handoff 可觀測面只有 `published`、path、errno 與逐檔 issue；repo 內現成型別沒有 delivery ID、receipt 或用 ID 查詢狀態的入口。
- `wf/workflows/workshop/records/tool-interop.md`〈退出碼還沒有共同編號〉與〈給模型看的錯誤訊息〉已留下 code、record／field／pointer、expected／actual 的候選來源，也明寫欄位名及 world／payload 複合錯誤的優先序當時沒有共同答案；它不是 canonical API 已提供這些欄位的證據。
- `wf/workflows/workshop/background/questions-deliver.md`〈題目：`aos deliver` 第一版要採哪一組 WORLD、輸入檔／stdin、單筆／批次與旗標介面？〉已固定要對四草案逐一套三個現場、每格分別數 temp／歧義／必填參數；它沒有規定三場合計要把每次呼叫的必填值相加或只列草案 arity。

### 3. 兄弟專案裡可以抄的

- `/home/lorkhan/repo/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉已有同目錄 temp、完整寫入、file fsync、atomic rename、directory fsync 的發布點，以及 intent 已在但可信結果缺失時維持 `unknown` 的文字基線。
- `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish()` 已有唯一 temp、`O_EXCL`、write-all、file fsync、異常時 unlink temp、rename 與 directory fsync；它用 `os.replace` 且標明 single-writer，能抄寫入／收尾骨架，不能當 no-replace 或 multiwriter 證據。
- `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_accept_recover.py` 的 `test_failpoint_matrix_exact_97_marker_and_recovery` 已有逐 failpoint 重開、第二次 recovery byte-stable 的測試形狀；`test_planned_folder_cleans_crash_temps_before_remaining_transitions` 另造 62／63 個 stale temp，驗 recovery 清掉後再次重跑不變。
- `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉已把 power loss、device cache、NFS、multiwriter、GC 與 portable checkpoint 明列為沒有證據，能直接拿來核對 Publish 測試不能外推的邊界。
- `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/README.md`〈由小到大：一次呼叫〉已有 receipt 完整但 ready／terminal 未發布時只補同一投影、只有 partial output 或 temp 時轉 `outcome_unknown` 且不自動重跑的 recovery 樣本。
- `/home/lorkhan/repo/simple_tools/agent-machine/archived/2026-08-13-snapshot/OUTPUT.md`〈`--json` machine mode〉與〈最小 JSON objects〉已有預期拒絕仍輸出單一 stdout JSON、stable code 與可變 human message 分離的 contract；同檔〈預設輸出〉另有 `start -b` 因後續可直接 `status`，所以成功不必回 ID 的兄弟專案對照。
- `/home/lorkhan/repo/simple_tools/arc_agi_tweets/arc_tweets/storage.py` 的 `_atomic_write()` 已有同目錄 `NamedTemporaryFile`、完整寫入、`os.replace` 與 `finally` 清殘留 temp 的最小 cleanup 樣本；它沒有 fsync、no-replace、failpoint 或 cleanup-failure 測試。
- `/home/lorkhan/repo/simple_tools/dcap/tool/README.md`〈失敗時會怎樣〉已有「目標已存在就 exit 1、拒絕覆蓋或合併」的 CLI 行為對照；它沒有競爭測試、JSON 結果或 receipt／query surface。

### 4. 還是查不到的

- `wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪紀錄／5. 仍然不知道的〉與 `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉都停在單次 Linux no-replace 或既有 multi-producer 原型；repo 與 `/home/lorkhan/repo/simple_tools/agent-machine/`、`/home/lorkhan/repo/simple_tools/freepy/`、`/home/lorkhan/repo/simple_tools/dcap/`、`/home/lorkhan/repo/simple_tools/arc_agi_tweets/` 都沒有多輪 `renameat2(RENAME_NOREPLACE)` 的成功 claim／ready／覆蓋／孤兒 temp 精確總數，**這條沒有現成資料**。
- `docs/aos-folder.md`〈十二、留給實作決定的／仍然開著的〉只記殘存檔清理方向，`/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_accept_recover.py` 的 `test_planned_folder_cleans_crash_temps_before_remaining_transitions` 也只測 cleanup 成功；unlink cleanup 自己回 EACCES／EIO 時 Publish 應保留哪個錯誤、temp 如何記帳，**這條沒有現成資料**。
- `core/inst/docs/cxxapi.md`〈函式〉與 `core/inst/include/aos/inst.hpp` 的 `read_all()` 都只提供 `InstState＋error_record`，`wf/workflows/workshop/records/tool-interop.md`〈給模型看的錯誤訊息〉又只保存候選欄位；每個 `InstState` 對應的 JSON Pointer、expected、actual、byte offset 公開型別，**這條沒有現成資料**。
- `wf/workflows/workshop/background/questions-deliver.md`〈題目：`aos deliver` 第一版要採哪一組 WORLD、輸入檔／stdin、單筆／批次與旗標介面？〉要求 12 格但未定合計口徑，`wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪評分與意見／可信度判斷〉又確認四份算法不一致；可跨四案直接比較的統一計數表，**這條沒有現成資料**。
- `core/inst/docs/handoff.md`〈公開 API 與錯誤資料〉沒有 delivery ID 或查詢入口，`wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪評分與意見／Evans persona〉也只指出 `delivery` 沒有 query surface；repo 與四個兄弟專案都沒有會拿 aos Deliver 的 `delivery` 去查詢、對帳或恢復的非量身訂做 caller，**這條沒有現成資料**。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉與 `/home/lorkhan/repo/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉都明列 power loss、NFS、非 Linux filesystem、部分 fsync 失敗、portable no-replace 與 orphan temp GC 未驗，**這條沒有現成資料**。

## 第 2 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人把上輪被抓到的漏洞真的跑了一遍：有人同時送同名東西，有人在東西放好卻還沒回話時把程式殺掉。結果是不覆蓋別人可以做到，但回話丟了便不能安心重送；四人也一致承認，目前四個時點只有一個能判斷「以前送過」。命令寫法仍剩兩路，回話格式則變少了，還沒有合併成同一份。

### 2. 冒出來的新詞

**no-replace／`unknown`／ledger**  
**白話**：見 BACKGROUND。  
**在 aos 裡具體是什麼**：見 BACKGROUND；這輪的 no-replace 只是 Linux 場地實驗，`aos deliver` 與長期帳本都還是提案。

**JSON Pointer／ABI／schema**  
**白話**：見 BACKGROUND。  
**在 aos 裡具體是什麼**：見 BACKGROUND；現有 `core/inst/include/aos/inst.hpp` 的 `read_all()` 只能說「第幾筆」和「哪一類錯」，不能直接給 `/1/argv/0`。

**`read_all()`（共用檢查器）**  
**白話**：像入口與後場都請同一位驗票員，免得前門說可以、後門卻說不行。  
**在 aos 裡具體是什麼**：已存在於 `core/inst/include/aos/inst.hpp` 與 `core/inst/src/format.cpp`；這輪只在場地從 `libaos_inst.so` 驗證真的叫得到，Deliver 尚未實作。

### 3. 看到的錯誤訊息各是什麼意思

- `truth=NotAlready` 與 `truth=Already`，但兩邊都是 `verdict=Unknown`：眼前的檔案完全一樣，系統卻應該回兩種不同答案，表示沒另外記帳就無從判斷。
- `kill_returncode=-9`／`shell_exit=137`／輸出 0 bytes：程式在東西已放好、回話尚未送出時被強制停掉，所以呼叫者不知道到底成功了沒有。
- `blind_retry_exit=0` 但 `visible_ready_after_retry=2`、`effect_lines=2`：不確定時盲目重送看似成功，但同一件事實際被做了兩次。
- `FieldTypeMismatch`／`field_type_mismatch`：JSON 讀得懂，但某個值的種類寫錯；`error_record=2` 只能指出是第二筆，還不知道是哪一格。
- `UnknownKey`／`unknown_key`：某筆資料多了 aos 不認得的欄位名。
- `JsonSyntax`／`json_syntax`／`json_parse`：輸入連 JSON 的括號、引號或逗號規則都還沒過。
- `world_version`／`unsupported_world`：目標資料夾的 `.aos/version` 不是這支程式認得的版本；當目標與輸入同時錯，這兩份假件都先報這個。
- `io_eexist`：目標名稱已經被另一個送件者佔用，這次為了不覆蓋對方而停下。
- 舊寫法出現 `published_claims=2` 卻只有 `visible_ready=1`：兩邊都對呼叫者說成功，但後來那份實際蓋掉了前一份。
- `errno=13 EACCES`／`io_eacces`／`code=io`：作業系統不允許往目標位置寫，這次實驗後沒有留下可見投遞檔或半成品。
- `code=usage`／`exit=2`：命令少寫了資料來自檔案還是前一支程式，因此直接拒絕，沒有悄悄等輸入。
- `zsh:3: no such file or directory: /usr/bin/time`／`exit=127`：量時用的外部工具不在這台機器上，壞的是測試接線，不是 Deliver。
- `aos init: cannot open .../world: No such file or directory`／`init_exit=1`：`aos init` 不會幫你建 world 資料夾，要先建好再初始化。
- `FileNotFoundError: .../v2-success.json .../v2-json-syntax.json`：zsh 把五條路徑合成了一個檔名，壞的是測試如何傳清單，改用陣列後就正常。

### 4. 所以呢

**OPEN-QUESTIONS 第 7 題：`aos deliver` 第一版命令長什麼樣。**

- (a) `aos deliver FILE`：手動送檔案最短；賠掉管線與一次送多筆時各要多造一份檔，且 FILE 可能推出不只一個 world。
- (b) `aos deliver FOLDER [FILE]`：三種場景都不用多造檔，又少打 `-f`／`-`；賠掉的是沒寫 FILE 就會讀前一支程式或在互動視窗等待，並必須凍結相對 FILE 從目前資料夾起算。
- (c) `aos deliver WORLD --target X`：可以先留下投給其他目標的位置；賠掉現在每次要多填一個還沒有真實使用者的 X，也還得定 X 是名字還是路徑。
- (d') `aos deliver WORLD (-f FILE | -)`：三種場景也都不用多造檔，而且不會猜資料從哪來；賠掉每次都必須多寫 `-f FILE` 或 `-`。
- 這輪對 (a) 與其餘三案所需的額外檔已經一致，但四份回報對「必填數量是每次算、還是三場合計」仍用不同算法，數字尚不能直接互比。

**OPEN-QUESTIONS 第 8 題：Deliver 的 key 保證什麼。**

- 第一版沒有 key：不會讓人誤以為可以安心重送；賠掉回話遺失後沒有安全的自動重試。
- key 只當串接編號：可以把一次請求與紀錄對起來；賠掉防重送能力，而且現在沒有用編號查詢的入口。
- key 只在待辦檔還在時防重：不用另存長期紀錄；賠掉前後一致性，因為檔案被取走後同一個 key 就認不出來。
- 增加長期帳本：四個時點都可以查閱並安全回答「送過／內容不同」；賠掉帳本何時清、留多久、壞掉怎麼修，以及中斷時怎麼對帳的成本。

**OPEN-QUESTIONS 第 9 題：成功、錯誤與退出碼。**

- 用 `ok/count/code/location{kind,value}`：成功與錯誤外形直接，位置也有種類；賠掉固定 6 個欄位，而真檢查器目前不一定產得出這麼細的位置。
- 用 `count/error/where{kind,value}`：共 5 個欄位，不重複回「成功／失敗」；賠掉 shell 必須同時看退出碼才知道這份 JSON 屬於哪邊。
- 用外層 `published/rejected/failed` 再附細節：只讀外層就能在五個現場做出同樣的粗分類；賠掉最完整版要固定 11 個欄位，其中十個尚未證明是真呼叫者必需。
- 用 `ok/delivery/count/code/pointer`：平面、5 個欄位，shell 容易讀；賠掉 `delivery` 目前沒有地方可查，`pointer` 也比真檢查器能提供的資訊更細。
- 退出碼都已縮成 `0/1/2`；可選 `2` 只代表命令寫錯，也可選 `2` 包含資料或 world 被拒絕。前者賠掉 shell 不能光看數字分出「可修正的輸入」與「環境失敗」；後者賠掉 `2` 不再是單純的參數用錯。
- 所有機器 JSON 都放 stdout：包裝程式只接一邊；或成功放 stdout、失敗放 stderr：人在終端看較直覺，但包裝程式要同時接兩邊。
