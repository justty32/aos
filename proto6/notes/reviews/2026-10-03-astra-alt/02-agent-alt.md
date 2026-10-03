# agent 的替代：把身分、對話與執行單位拆開（astra，2026-10-03）

## 一段話結論

**原提案適合當小隊原型，但「一個資料夾、五項程序、一次 LLM」不必綁成一包。**
最值得先試的小改良是三項程序：準備、LLM、收尾。
較大的替代有三條：一格完成有上限的連續回合、記憶跟著對話案卷走、少量 worker 承接大量 agent。
它們分別改善往返延遲、記憶混雜、冷 agent 的管理成本。
`paused` 已經提供事件喚醒，暫時沒有必要另造事件迴圈。
kernel 契約則可以先把 `request` 併入 `summary`。
以上都是選項，不代表方向已定。
本次全程唯讀，未改檔、未 commit、未跑測試。
以下實驗都是後續可做的對照。

## 替代方案

### 方案 A：一格跑完有上限的完整回合

- **長相**

一格仍由 tick 執行。

表上放三項：

```text
prepare → turn → publish
```

`prepare` 收信、選定對話、整理 context。

`turn` 在同一個短命程序裡重複：

```text
呼叫 LLM → 保存回應 → 執行工具 → 保存結果
```

遇到最終回答、需要等待別人、額度耗盡，或本格次數用完，就退出。

例如：

```json
{
  "max_llm_calls": 2,
  "max_tool_ops": 4
}
```

這些數字是實驗參數。

每次操作各自留證據：

```text
state/runs/r42/
  calls/1/request.json
  calls/1/response.json
  calls/2/request.json
  calls/2/response.json
  tools/t1/args.json
  tools/t1/result.json
```

外部工具仍交給 `aos-exec`。

kernel 每格派一次機會，agent 回報本格實際用了幾次 LLM。

現行 tick 可以承載這種程序。
它依序執行任務，沒有辨識任務內部的 LLM 次數。
證據是 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 161–181 行，以及 [aos_tick_run.py](../../../src/py/lib/aos_tick_run.py) 第 75–88 行。

- **比原提案好在哪**

「查字數 → 取得結果 → 回答」可以在一格收尾。

少一次 summary、kernel 排程、grant 的往返。

短工具鏈比較接近使用者理解的一輪工作。

把 `max_llm_calls` 設成 1，就能直接比較原提案的節奏。

原提案把 B 評成「LLM 藏在程式裡，kernel 管不到」。
這個缺點成立，但不是全有全無。
每次呼叫仍可經過統一的額度檢查函式。
差別是檢查由 agent 程式負責，不再由每個 tick 任務邊界負責。

- **代價與邊緣狀況**

一格變長。

同一 agent 的新信可能等兩次慢 LLM 才被處理。
整格持有工作資料夾的鎖，見 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 129–141 行。

kernel 少了兩次呼叫之間的重新排程機會。

`tasks-blocked` 只能擋整個 `turn`，不能插進它內部的第二次呼叫。
若需要保留逐次 kind hooks，可以預先在表上列兩組 `prepare → llm → settle`。
這會換回更多程序與接力檔。

每次回應與工具結果要立即保存。
不能等整格結束才一次記憶。

工具已成功、結果尚未保存時被殺，仍會留下「不知道做完沒有」的窗口。
多寫一個 `started` 檔也不能消除它。
有外部效果的工具不能一律自動重跑。

次數有上限，不代表 token 費用已有硬上限。
逾時也不代表供應商完全沒執行。

權限沿用執行帳號。
額度檢查仍是配合式限制。

- **要翻的裁定**

**不用翻「所有行為在 tick 裡做」的裁定。**
這個程序每格結束就退出。
它保留 [裁定 11／方向與追答](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md) 的排程位置與上層格數。

**也不必把 T-06 改掉。**
[裁定 09／方向第 1 條](../../verdicts/09-special-computing-os/01-方向與審稿裁定.md) 把計算描述為任意表達式。
[現行 T-06](../../../spec/terms.md) 同時列「一次 LLM 呼叫、一輪 agent」。
它沒有要求兩者必須一對一。

要改的是尚未裁定的 [agent 方案取捨](../../proposals/2026-10-02-agent/02-方案取捨.md) 與 [一格最多一次 LLM](../../proposals/2026-10-02-agent/04-一格做什麼.md)。

如果使用者要求「每次 LLM 之間，kernel 都必須能重新分配」，這個方案就不適合。

- **最小實驗**

時間盒一天。

用同一個假 LLM 劇本，比較每格一次與每格最多兩次。

讓十個 agent 同時做需要兩次 LLM 的字數問答。

記錄完成延遲、kernel 開格數、實際呼叫數，以及中途新信的最長等待。

在第二次呼叫後中止一次，確認第一次工具結果仍可查看。

判準是：少一輪排程帶來的收益，是否值得減少一次公平分配的機會。

### 方案 B：對話是案卷，agent 是處理案卷的人

- **長相**

保留 agent 的工作資料夾。

把一條共用 `history.jsonl` 改成每段對話各自的案卷。

```text
agents/alice/
  config/
  memory/notes.md
  cases/
    c17/
      events/000001.json
      events/000002.json
      context.json
      next.json
    c18/
      events/000001.json
  work/

shared/
  bob/
    artifacts/report-7/v1.json
    artifacts/report-7/v2.json
```

案卷保存收到的要求、模型回應、工具結果與回答。

`context.json` 只記這次選了哪些材料。

例如：

```json
{
  "case": "c17",
  "events": ["000001", "000002"],
  "artifacts": ["shared/bob/artifacts/report-7/v2.json"],
  "notes": ["memory/notes.md"]
}
```

一格選一個案卷，推進一步。

人格與长期記憶屬於 agent。

某件工作的經過屬於案卷。

合作成果放在產出者自己的目錄。
其他 agent 讀指定版本。
信只通知「哪份成果變了」，不必把整份成果複製進每個信箱。

也可以完全不寄通知。
消費者在已排定的下一格查看共享成果。

現行 mq 對每個訂戶複製信件。
共享大成果因此確實有機會減少重複資料。
程式證據是 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 104–111 行。

- **比原提案好在哪**

同一個 agent 同時處理兩件事時，不必把兩段工作塞進同一條 history。

「記下來」與「這次放進 context」變成兩個明確動作。

換模型、換整理策略，不必改寫原始經過。

工具輸出可以保留完整檔案。
context 只帶需要的片段或引用。

共享成果有明確版本。
回答可以指出當時讀的是哪一版。

git 可以記錄案卷的版本變化。
但不用讓 git 歷史同時負責判斷「這次該記得什麼」。

- **代價與邊緣狀況**

必須分清新訊息是在延續原案卷，還是開新案卷。

「改算第二份文件」不能只靠新檔名猜成另一件事。

案卷需要單一寫入者。
其他 agent 各寫自己的成果，再由案卷主人引用。
不能讓整隊同時追加同一個 JSON 檔。

tick 的鎖只保護自己的工作資料夾。
它不會自動保護共享案卷。
證據是 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 191–203 行。

共享路徑要有讀取權。
案卷中的路徑引用不會授予 Linux 權限。

共享內容也可能過期。
應引用固定版本，避免模型讀到一半來源被覆寫。

存檔本身不會叫醒目前的 daemon 項目。
現行收信叫醒是在 mq handler 裡明做的，見 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 104–111 行。
因此省掉通知，就要接受等待下一格。

小檔數量會增加。
大量案卷之後可能需要分段封存。

案卷保留證據，不等於整套當機恢復已完成。
尤其 `take` 會先清空記憶體信箱，見同檔第 93–103 行。
清空後、落檔前的窗口仍然存在。

- **要翻的裁定**

**基本版不用翻現行裁定。**

保留機械式 context 整理。
也可以保留原提案的 32000 token 預設。
改的是記憶的組織方式，不是強迫改用 LLM 摘要。

git 仍是可選的普通任務。
符合 [裁定 11／第十七批](../../verdicts/11-tick-as-unit/19-1001-第十七批.md)。
不恢復已暫緩的 `aos-git` 系統。

共享成果是應用層約定。
不改 [第二十五批](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md) 的 mq 複製與取信語意。

要改的是 [agent 一格與記憶提案](../../proposals/2026-10-02-agent/04-一格做什麼.md) 的單一 history 與接力方式。

如果增加常駐檔案監看服務來自動喚醒，就要重新處理 [裁定 11 的背景服務限制](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。
本方案不以它為前提。

- **最小實驗**

時間盒一天。

讓同一個 agent 交錯處理兩份文件。

中途更正其中一份要求。

另一個 agent 把共享成果從 v1 更新到 v2。

比較單一 history 與案卷版組出的 request。

驗三件事：兩案工具結果不混用、可以找到回答使用的來源版本、改 context 策略不必修改原始事件。

再測一次只存成果、不寄通知。
把增加的等待格數攤給使用者看。

### 方案 C：agent 不占固定執行項，只在需要時領一張工作票

- **長相**

把人格、對話與執行席位分開。

```text
team/
  kernel/.aos/tasks.json
  profiles/
    alice.json
    bob.json
  sessions/
    c17.json
    c18.json
  workers/
    w0/.aos/tasks.json
    w1/.aos/tasks.json
  dispatches/
    d42.json
```

只有 `w0`、`w1` 是 daemon 的執行項。

人格與會話是資料。

kernel 在自己的格內挑工作，寄到空閒 worker 的私門：

```json
{
  "type": "run",
  "dispatch": "d42",
  "profile": "alice",
  "session": "c17",
  "revision": 8,
  "limit": {"llm_calls": 1}
}
```

worker 一格處理一張票。

保存結果後回報：

```json
{
  "type": "done",
  "dispatch": "d42",
  "session": "c17",
  "revision": 9,
  "usage": {"llm_calls": 1, "llm_tokens": 1820},
  "next": {"ready": true, "after_ticks": null},
  "needs": []
}
```

grant 併進工作票。

summary 與 request 併進完成回報。

這是 kernel 與 worker 之間的兩種訊息。
不是宣稱整個系統只剩兩種訊息。

需要主動工作的 agent，由 kernel 保存下次到期的格數。
到期再產生工作票。

worker 仍可一直 `paused`。
睡著的會話則根本沒有 daemon 狀態。

- **比原提案好在哪**

冷 agent 不再各占一個 daemon 執行緒與私門。

現行 `start_item()` 每項建立一條執行緒。
證據是 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 181–182 行。

新增人格或會話，不必修改 daemon 設定。

也不用因為新增 agent 而處理新門。
現行重讀仍以啟動時的門集合驗設定，見 [aos_daemon_reload.py](../../../src/py/lib/aos_daemon_reload.py) 第 47–62 行。

人格數量與並行數量可以分開。

kernel 保存窗口帳本。
worker 只拿本次工作票的上限。
雙方不必長期各保存一份窗口扣帳狀態。

- **代價與邊緣狀況**

**隔離單位會改變。**

同一 worker 服務的會話共用 Linux 身分。
若按信任域分池，就只能承諾池與池之間的隔離。

現行帳號設定屬於 daemon 的一項。
它不會讀工作票再替其中的 persona 切帳號。
證據是 [aos_daemon_account.py](../../../src/py/lib/aos_daemon_account.py) 第 103–110 行。

若仍要求每個 agent 有自己的 UID，需要另外安排執行身分。
主要簡化會縮小。

會話要有自己的 `revision`。
worker 的 tick `seq` 不再等於某個 agent 的第幾步。

第一版可把會話固定分配給 worker。
這容易理解，但一個慢工作會拖住同席位的其他會話。

改成自由派工，就要增加跨 worker 的會話互斥。

每個 worker 先限制一張未完成票。
否則一次 `take` 收到多張票後，還得保存本格沒處理的部分。

完成回報丟失時，kernel 不能只因等太久就重派。
工具可能已經產生外部效果。
第一版應留下「結果未知」，讓實驗暴露這個成本。

工作票仍是配合式授權。
worker 握著金鑰時，票上的數字不是硬限制。

kernel 也變成工作入口。
這會增加集中轉送與排隊成本。

- **要翻的裁定**

**不必翻 tick 與 daemon 的現行核心邊界。**

worker 仍有工作資料夾。
排程仍在 kernel 的 tick 任務內。
daemon 仍只執行 inst。
符合 [裁定 11／方向與追答](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md) 與 [最核心 daemon](../../verdicts/11-tick-as-unit/07-1001-最核心daemon.md)。

**但要明確重評早期身分與 worker 方向。**

[09-28 方向摘要](../../README.md) 記有「一 agent 一 Linux 使用者」與「CPU worker 取消」。
本方案重新引入共用執行席位。
若一 agent 一帳號仍是使用者要守的部署方向，本方案的同信任域版本就要翻這項。

[裁定 09／方向第 3、5 條](../../verdicts/09-special-computing-os/01-方向與審稿裁定.md) 允許不同 kernel 定義不同抽象與隔離。
這讓方案有容納空間。
它不等於使用者已經同意共用帳號。

另外要改 [agent 資料夾提案](../../proposals/2026-10-02-agent/03-agent長相.md) 與 [kernel 契約草案](../../proposals/2026-10-02-kernel/04-agent介面.md)。

- **最小實驗**

時間盒一天半到兩天。

建兩個 worker、二十份會話與假 LLM。

先固定會話到 worker 的映射。

每個 worker 最多一張在途票。

觀察新增二十份會話時，daemon 的 worker 執行緒是否仍只有兩條。

驗同一會話的 revision 是否依序增加。

安排一個慢工作，量同席位其他會話的等待。

分別在保存前、保存後但回報前中止 worker。

驗收重點是能否清楚指出哪張票完成、哪張票結果未知。
不是先承諾自動恢復。

## 不換方向的改良

### 五項先縮成三項

```text
prepare＝inbox＋think
llm＝一次呼叫
settle＝act＋remember
```

summary 留在 `after_all`。

LLM 仍獨立成項。
`after_task.prepare` 仍可掛額度政策。

這保留原提案最有價值的邊界。
也減少兩組跨程序接力。

代價是核心紀錄看不到 inbox 與 think 各自的結束碼。
agent 可以在自己的操作紀錄中保留階段名稱。

合併程序不會自動形成交易。
工具成功後、記憶寫入前被殺，窗口仍在。

现行任務失敗後照跑下一項。
因此三項與五項都需要明確的資料有效性檢查。
證據是 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 178–188 行。

不用翻既有裁定。
改的是 [原提案 A／B 的取捨](../../proposals/2026-10-02-agent/02-方案取捨.md)。

半天即可用同一個假劇本比較三項與五項。
重點看接力檔數量、失敗後診斷是否仍清楚。

### request 併入 summary

保留 agent 資料夾、grant 與 paused。

上行改成一份狀態回報：

```json
{
  "type": "report",
  "version": 1,
  "from": "agents/bob",
  "seq": 42,
  "ready": true,
  "after_ticks": null,
  "usage": {"llm_calls": 0, "llm_tokens": 0},
  "needs": [{"kind": "llm_more", "tokens": 20000}]
}
```

`wake_me` 由 `after_ticks` 表達。

更多額度由 `needs` 表達。

kernel 一次看到用量、下一步與需求。
不用處理 summary 與 request 的到達順序。

`needs` 是需求快照。
重複收到不能當成每次再加一份額度。

「沒計算，但新增額度需求」也應回報。
「狀態沒變」才不寄。

收到 report 不代表 kernel 必須回 grant。
否則兩種信照樣互相叫醒。

不用翻裁定。
[三種信仍是提案](../../proposals/2026-10-02-kernel/04-agent介面.md)。
mq 不解讀應用層的 `type`，見 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 104–112 行。

半天可驗沒有 grant、額度耗盡、需求重複三種劇本。
判準是需求不漏，閒置後也不互叫。

### 保留 inst，但縮小它要承擔的範圍

啟動外部程序的工具繼續走 inst。

純粹整理字串、選 context、計算下一步，可以是程序內函式。

它們不必為了形式一致，各自變成工具目錄與程序。

代價是少了獨立程序的退出碼與中止邊界。
純函式通常不需要這兩項。

`aos-exec` 已承擔串流與執行設定。
全部改成 agent 自己寫 `Popen`，目前收益不足。
程式依據是 [aos_exec_run.py](../../../src/py/lib/aos_exec_run.py) 第 51–106 行。

### 接力檔帶上本次操作識別

request、response、工具結果都放在本次 run 目錄。

後項只接受同一次 run 的產物。

這能避免本格 LLM 沒產出時，誤讀上一格留下的 response。

它是接力契約。
不必因此恢復完整當機救援。
[裁定 11／第二十六批](../../verdicts/11-tick-as-unit/27-1002-第二十六批.md) 已把 B-625 當機恢復放進暫緩區。

## 試過但放棄的想法（各一兩句）

- **另造事件驅動 daemon。** 現行 `_next_run()` 先看 pending，再看 paused，已經能等事件才跑；見 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 69–85 行。新增事件模式主要改善名稱，沒有先解決更重要的工作與額度契約。

- **常駐 agent 自己跑無限工具迴圈。** 延遲較低，但必須翻 [裁定 11 的背景服務限制](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。有界回合先拿到部分收益，代價較小。

- **每格只做一次外部操作。** 保存點比較清楚，但一次模型要求多個工具時，會增加很多格與 kernel 往返。適合長工具或需要人工介入的流程，不適合當所有 agent 的預設。

- **git 歷史就是全部記憶。** 它能保存版本，卻沒有回答 context 該選哪些材料。每次都從 commit 差異重建對話，只是把記憶格式藏进版本歷史。

- **所有 agent 共改一份共享 JSON。** 省掉信件格式，卻增加覆寫、互斥與半套更新問題。各自寫成果，再引用固定版本，較容易交代責任。

- **kernel 只看退出碼，不收回報。** 退出碼無法表達用量、下一步與等待條件。現行 tick 也會在子任務失敗後正常回 0，見 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 178–188 行。

- **先把 LLM 換成 FUSE 檔案服務。** [Plan 9 提案的 `/llm` 路線](../../proposals/2026-10-02-plan9/05-agent與kernel的namespace.md) 值得獨立試，但還要處理服務生命週期與額度執行。它不會直接決定 agent 該拆幾項、記憶該跟誰走。

## 問使用者的問題（表格：題｜選項與後果｜建議）

| 題 | 選項與後果 | 建議 |
|---|---|---|
| 每次 LLM 之間都要重新排程嗎？ | 要：一格一次，控制點清楚。不要：一格可完成短工具鏈，新信可能等久一點。 | 先比較上限 1 與 2。把完成延遲與新信等待一起看。 |
| agent 的記憶是一本人生流水帳，還是一疊工作案卷？ | 單一 history：最簡單。案卷：多件事不混，但要定義訊息歸屬。 | 先試兩案交錯。人格與長期筆記仍保留在 agent。 |
| 一 agent 一 Linux 帳號是必要條件嗎？ | 是：保留獨立執行身分。否：可以按信任域共用 worker，冷 agent 成本較低。 | 這題先於工作池拍板。不要用會話 ID 假裝帳號隔離。 |
| 五項程序是否都需要獨立替換？ | 都需要：保留五項。主要只換模型與政策：三項已保留 LLM 邊界。 | 先做三項／五項對照，讓接線與診斷成本說話。 |
| kernel 需要獨立 request 嗎？ | 需要：可以另送命令。併入 report：需求與狀態同一份，但要當快照處理。 | 先合併。驗重複需求不加倍、無額度時不漏報、閒置後不互叫。 |