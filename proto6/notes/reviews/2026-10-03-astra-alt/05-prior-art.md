# 外部先例對照：借狀態、收據與工作槽（astra，2026-10-03）

## 一段話結論

**原提案最值得保留的是：政策在 tick 裡，daemon 只做機制。**
外部先例沒有讓我找到值得整套換上的底座。
但有三個值得並排試的替代方案。
第一是借 Kubernetes 的「期望狀態與觀察狀態分開」，讓 grant 不再依賴某一封信。
第二是借 Temporal、LangGraph 與 qmail 的部分觀念，讓昂貴結果與外部效果留下可接續的工作單。
第三是借 batch 系統，把 LLM 呼叫交給固定數量的 tick 工作槽。
若只選一個先試，我選第一個。
若最在意「一次計算如何被分配」，第三個更能直接驗證 aos 的方向。

本文所有外部系統敘述均為**憑記憶**。
未上網核對，也不主張涵蓋各產品最新版本。
aos 現況另以程式核對。
全程唯讀，未改檔、未 commit、未跑測試。
下列實驗均為提議，尚未執行。

## 替代方案

先固定三個現況，避免把外部系統的能力算到 aos 頭上。

- **合併叫醒不等於合併訊息。**
  daemon 仍逐封複製信件。
  `take` 直接清空該項信箱。
  見 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 90–112 行。
  叫醒只是設定一個布林旗標。
  見 [aos_daemon_ctl.py](../../../src/py/lib/aos_daemon_ctl.py) 第 173–176 行。

- **程序結果不等於工作結果。**
  daemon 的 `status` 只有執行、暫停、待補與上次結束資訊。
  見 [aos_daemon_ctl.py](../../../src/py/lib/aos_daemon_ctl.py) 第 179–183 行。
  tick 記錄任務失敗後仍繼續，最後可以回 0。
  見 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 178–188 行。

- **現行零件提供執行機制，沒有提供下列工作契約。**
  daemon 會同步等一項結束，再安排下一次。
  見 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 16–65、88–128 行。
  以下的狀態版本、效果收據與工作槽管理，都需要新寫任務程式。

### 外部先例對照

表中「解法」與「典型坑」全部憑記憶。
「aos 可以借」是本報告的提案。

| 先例 | 它怎麼解同一個問題 | 典型坑 | aos 可以借的具體長相 | 不適合直接搬的部分 |
|---|---|---|---|---|
| Erlang／OTP supervisor、actor mailbox | 工作狀態由 actor 持有。監督者另管程序失敗與重啟。 | 信箱積壓。重啟風暴。程序重開後重做外部效果。監督樹也不一定等於業務組織樹。 | 一個狀態檔只有一個寫入者。summary 分開呈現程序、格與工作的狀態。 | 不直接加「失敗就重啟全隊」。本輪救援行為會重開 [POC 不處理異常](../../verdicts/11-tick-as-unit/03-1001-POC默認一切正常.md)。actor 身分隔離也不是現行 mq 的保證，後者刻意允許報別項名字取信，見 [第二十五批](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)。 |
| systemd | 用服務生命週期與資源邊界管理程序。服務可用與程序已啟動可以分開描述。 | 啟動成功不代表工作成功。服務依賴也不等於一筆工作的資料依賴。 | `process_running`、`tick_finished`、`work_done` 分開。停止派工與終止程序分開。 | 整套交給 systemd 會翻 [初版不使用 systemd](../../verdicts/05-dependencies/02-追加與B1-B2.md)。本報告只借語意，不增加執行期依賴。 |
| djb daemontools | 監督者主要管程序是否在跑。工作語意留給被監督的程式。 | 程序可以一直重啟，業務卻一直沒進展。重啟無法判斷工作是否已對外生效。 | 保留笨 daemon。工作進度放 agent 自己的工作單。 | 不把重新執行 inst 當成恢復工作。這正是原提案已做對的分工，符合 [最核心 daemon](../../verdicts/11-tick-as-unit/07-1001-最核心daemon.md)。 |
| Kubernetes controller／reconcile loop | 保存期望狀態，再反覆比對觀察狀態。事件主要縮短下一次比對的等待。 | 舊狀態造成抖動。多個 controller 搶寫。每次比對都重做昂貴操作。 | kernel 寫 `desired/bob.json`。bob 寫 `observed/bob.json`。通知只說有變化。 | 不搬 API server、etcd 與常駐政策迴圈。後者會翻 [政策只在 tick 執行](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。 |
| cron 與 batch 系統 | cron 解決何時啟動。batch 系統另管工作佇列、執行名額與結果。 | 到點不代表有容量。工作可能重疊、餓死或卡住整個佇列。 | 保留 daemon 管啟動時機。kernel 管 `queued → assigned → done`。固定幾個工作槽執行計算。 | 不把佇列政策塞回 daemon。那會擴大 [笨 cron 的角色](../../verdicts/11-tick-as-unit/07-1001-最核心daemon.md)。 |
| 作業系統排程器 | 把可執行工作與執行資源分開。時間片與優先權決定誰先使用 CPU。 | 優先權反轉、餓死、切換成本。這些機制依賴可搶占的計算。 | 分清「有信」「可做事」「獲得計算名額」。先借有界工作槽與簡單輪流分配。 | 遠端 LLM 不能像 CPU 指令一樣暫停後原地續跑。應沿 [09 的特殊計算方向](../../verdicts/09-special-computing-os/01-方向與審稿裁定.md) 另定計算邊界，不照搬時間片。 |
| Temporal／工作流引擎 | 保存工作流歷史。決策接續與外部活動分開。已有結果可直接取回。 | 外部活動仍可能重複。重播要求、程式版本與歷史膨脹都要管理。 | 保存 LLM 原始回應。工具執行另有 `effect_id` 與結果收據。 | 不讓 tick 成為重播引擎。完整常駐工作流服務也會碰 [tick 唯一基準](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。 |
| qmail／磁碟佇列 | 接受信件與完成投遞分開。投遞程式從佇列取得工作。 | 成功回覆丟失會造成重送。磁碟滿、重試與清理也是工作。落盤不等於恰好執行一次。 | 回答先成為 `outbox/<id>.json`。分清「待送」「daemon 已接受」「對方已接手」。 | 不默默把 mq 改成可靠佇列。那會翻 [第二十五批第 8 條](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md) 的信不記進狀態檔。 |
| LangGraph | 用顯式狀態、節點與 checkpoint 表達模型和工具循環。 | checkpoint 沒對齊副作用邊界，接續時仍會重做。圖與狀態格式也要維護。 | 五項 tasks 保留。另加一張小型 `turn.json` 表示接到哪一步。 | 不把 DAG、路由與 needs 搬進 tick 核心。依賴應留在任務層，見 [11 的疑點裁定第 2 條](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。 |
| AutoGen、CrewAI | 前者可用對話與回合選擇組合 agent。後者可用角色、任務與流程分派工作。 | 接話很多卻沒有進展。主管增加模型成本。角色名稱代替了可驗的成果契約。 | 每張工作單寫交付物、完成條件與 `ref`。kernel 排工作，不因「收到一句話」就必須再叫模型。 | 不讓 daemon 理解主管、人格或團隊流程。各層抽象應可不同，見 [09 方向第 3、5 條](../../verdicts/09-special-computing-os/01-方向與審稿裁定.md)。 |
| Plan 9／Inferno | 以檔案服務與 namespace 組合程序可見的服務。名稱可以與實際服務位置分開。 | 介面變成檔案後，仍須定義提交、取消與服務失效。跨檔更新也不自然形成交易。 | 固定服務路徑。讓同一份 LLM 請求能接假模型或真模型。工作結果可保留成目錄。 | 不必為此先做 FUSE。常駐 LLM 檔案服务需要另開 [背景服務例外](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。隱藏路徑也不會改掉 [現行 socket 權限粒度](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)。 |

### 方案 A：kernel 每格核對期望狀態，信只負責提醒

借 Kubernetes 的 reconcile。
白話就是：**每次醒來看「現在應該怎樣」，不必重建每一封指令的來龍去脈。**

- **長相**

```text
team/
  .aos/tasks.json
  config/policy.json
  exchange/
    desired/bob.json       # kernel 寫，bob 讀
    observed/bob.json      # bob 寫，kernel 讀
  agents/bob/
    .aos/tasks.json
    state/usage.json
```

`desired/bob.json`：

```json
{
  "version": 1,
  "generation": 12,
  "mode": "run",
  "window": "team:1200",
  "calls_total": 3
}
```

`observed/bob.json`：

```json
{
  "version": 1,
  "observed_generation": 12,
  "window": "team:1200",
  "calls_used": 2,
  "phase": "waiting_tool"
}
```

kernel 一格讀公開摘要與 daemon 狀態。
算出新目標後，只在內容改變時換檔。
再寄 `{"type":"changed","generation":12}` 提早叫醒成員。

成員開格時讀最新目標。
同一窗口重讀五次，仍然只有三次總額。
成員只寫自己的觀察檔與用量。

成員保留低頻週期。
因此通知未到時，下個週期仍有機會讀到目標。
這個版本取消「永久 paused」。

現有 daemon 已有週期與提前叫醒。
見 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 69–85、113–123 行。
新造的是兩份檔案的契約與比對任務。

- **比原提案好在哪**

[原 kernel 提案](../../proposals/2026-10-02-kernel/03-推薦方案.md) 把 grant 內容與叫醒放在同一封信裡。
本方案拆成「政策狀態」與「提醒」。

舊通知晚到，成員仍讀最新檔案。
重複通知不會增加額度。
人可以直接比對「要求什麼」與「做到哪裡」。

它也讓多層管理更容易只交換摘要。
上層不必讀下層 history 或工具細節。

- **代價與邊緣狀況**

低頻空格是明確代價。
成員很多時，全掃摘要也是線性成本。

每份檔案只能有一個寫入者。
上下層不能同時改同一個 `desired`。
同帳號部署只能靠約定維持這件事。

檔案要放在双方都能按需讀寫的位置。
改成跨機後，必須另外提供讀取介面。

kernel 寫檔後、通知前中斷，成員會延遲到週期開格。
成員若已被 `stopped`，週期也不會救它。
低頻輪詢不是自動恢復保證。

`observed` 可能過時。
因此它要帶版本，且不能取代 daemon 的程序狀態。

撤回政策在成員下一次檢查時才生效。
已送出的 HTTP 不會因此撤回。
上層停止推進後，舊窗口如何關閉也仍須定義。
不能讓成員用自己的 `seq` 冒充上層格數。

這個方案沒有解决「工具已成功，觀察檔尚未寫入就中斷」。
那是方案 B 的問題。

- **要翻的裁定**

**基礎版本不必翻既有裁定。**

政策仍在 tick 任務裡。
符合 [11 的方向與追答](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。
daemon 不理解額度。
mq 仍是記憶體訊息。

要改的是尚未拍板的提案選項。
包括永久 paused、grant 本體走私門，以及只 push 摘要。
見 [kernel 待決第 3、6 題](../../proposals/2026-10-02-kernel/06-待決問題.md)。

若進一步承諾重啟後必定恢復工作，就要重開 [POC 不處理異常](../../verdicts/11-tick-as-unit/03-1001-POC默認一切正常.md)。
本方案第一輪不作這個承諾。

- **最小實驗**

一天。
一個 kernel，兩個只增加計數器的假 agent。

並排比較原提案與本方案。
送五次相同通知。
再讓舊版本通知晚到。
最後切成 `mode:"idle"`。

記錄開格數、模擬計算數與停止新計算所需格數。
驗同窗口額度不因通知次數增加。
再省略一次通知，量低頻週期帶來的延遲。

若只有兩個 agent 就明顯被空格干擾，原提案的 paused＋grant 比這版好。

### 方案 B：agent 保留工作單，外部效果另留收據

借 Temporal 的結果接續。
借 LangGraph 的顯式階段。
借 qmail 的「接受與完成分開」。

**先保存昂貴結果，再討論自動恢復。**

- **長相**

```text
agent/
  .aos/tasks.json
  state/
    turns/<turn-id>/
      input.json
      request.json
      response.json
      turn.json
      effects/<effect-id>/
        intent.json
        result.json
    outbox/<message-id>.json
  work/current-turn
```

五項任務仍然保留。
`inbox` 接受工作。
`think` 選一張工作單。
`llm` 產生並保存回應。
`act` 執行尚未完成的效果。
`remember` 更新 history 與工作階段。

已有該次呼叫的回應，就直接使用。
需要下一次模型推理時，建立下一筆呼叫。
這不由 tick 判斷。

工具呼叫前先保存意圖：

```json
{
  "effect_id": "turn-7/tool-2",
  "tool": "create_issue",
  "state": "intent",
  "retry": "manual"
}
```

取得結果後才保存收據。
如果中斷後只剩意圖，狀態是 `unknown`。
不能直接推論外部沒有執行。

工作 ID、模型呼叫 ID、工具效果 ID 分開。
tick `seq` 只表示執行位置。

- **比原提案好在哪**

[原 agent 提案](../../proposals/2026-10-02-agent/04-一格做什麼.md) 以本格 `work/` 接力。
本方案改以跨格工作單接力。

模型已回覆，後面的工具失敗，就不必重新問模型。
工具已留下結果，history 尚未更新，也能知道做過什麼。

這保住的是昂貴成果。
它不要求把整段 agent 程式做成可確定重播。

現行 tick 紀錄只有執行數、結束碼與格狀態。
見 [aos_tick_record.py](../../../src/py/lib/aos_tick_record.py) 第 125–142 行。
它不是外部效果收據。

`aos-exec` 也在子程序結束後才寫 `exit`。
見 [aos_exec_run.py](../../../src/py/lib/aos_exec_run.py) 第 189–205 行。
該檔無法消除外部成功與本地記錄之間的空隙。

- **代價與邊緣狀況**

每個工具要選恢復政策。

| 工具性質 | 接續方式 | 剩下的代價 |
|---|---|---|
| 可安全重做 | 再執行一次 | 外部資料可能已變 |
| 支援冪等鍵 | 用同個效果 ID 重送 | 仍受對方的去重範圍與期限限制 |
| 能查結果 | 先查再決定 | 查詢可能暫時看不到剛完成的效果 |
| 不能去重也不能查 | 留在 `unknown` | 人或上層承擔是否重做的判斷 |

LLM 也可能已收費，卻沒回到本地。
自己編一個 request ID，不會自動讓供應商去重。

普通回答同樣是外部效果。
outbox 可以留下待送內容。
但 mq 回 `ok` 不等於對方已處理。

本方案仍有收信缺口。
`take` 清空信箱後，agent 寫 `input.json` 前若中斷，仍可能丟信。
見 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 93–103 行。
所以只能稱為「已保存工作可接續」。
不能稱為端到端可靠投遞。

收據增加檔案數、保留成本與版本問題。
同帳號自己寫的收據也不是防竄改證據。
長工具仍會占住該格。
保存接續點不等於背景執行。

- **要翻的裁定**

**只保存回應與收據，不必翻核心裁定。**

若本輪要做中斷後自動接續，就要局部重開：

1. [11／03：POC 默認一切正常](../../verdicts/11-tick-as-unit/03-1001-POC默認一切正常.md)。
   新方案會正式處理 agent 的中斷狀態。
2. [11／27：B-625 當機恢復暫緩](../../verdicts/11-tick-as-unit/27-1002-第二十六批.md)。
   只開 agent 層的有限實驗。
   不復活舊 tick 核心恢復機制。

mq 本身不改，所以不翻 [第二十五批的記憶體信箱](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)。

- **最小實驗**

一天半。
一個假模型，兩個假工具。
一個工具可安全重做。
另一個模擬建立不可撤回物件。

在四處中斷：

1. 模型回應保存後。
2. 工具意圖保存後。
3. 外部物件建立後、收據保存前。
4. 回答送出後、outbox 標記前。

驗已有回應不重問模型。
驗已有結果不重跑工具。
驗不確定效果停在 `unknown`。

成功標準是把確定與不確定分清。
不是讓所有中斷都自動成功。

### 方案 C：LLM 是批次工作，固定工作槽各跑一格

借 batch 系統的工作與執行名額分離。
借作業系統的「可執行工作不等於已取得資源」。
也借 Plan 9 的服務替換觀念，但先使用普通檔案。

**agent 提交一次計算，kernel 分配工作槽。**
LLM 呼叫在工作槽自己的 tick 裡完成。

- **長相**

```text
team/
  kernel/.aos/tasks.json
  llm/
    requests/<request-id>.json
    assignments/slot-0.json
    assignments/slot-1.json
    results/<request-id>.json
    slots/
      slot-0/.aos/tasks.json
      slot-1/.aos/tasks.json
  agents/bob/
    state/pending-call.json
```

請求是資料，不是任意 argv：

```json
{
  "version": 1,
  "request_id": "bob-call-17",
  "requester": "bob",
  "model": "fake",
  "input_ref": "bob-call-17.input.json"
}
```

kernel 一格收請求。
它按政策把請求分給空槽。
先記 assignment，再叫醒該槽。

每槽一格最多執行一筆 LLM 呼叫。
HTTP 期間停留在這一格內。
完成後寫結果，再用 mq 通知。

agent 下一格讀結果、做工具、更新記憶。
agent 不在自己的格裡等待工作槽。
kernel 也不等待它完成。

槽數先固定為二。
同一槽的 assignment 在交還前不能覆寫。
kernel 必須把「已分配但尚未開跑」也算占用。
不能只看 daemon 的 `running`。

現行同一 inst 的執行迴圈會等上次結束。
見 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 88–128 行。
但 assignment、工作結果與占用記錄都要新寫。

- **比原提案好在哪**

[原 agent 提案](../../proposals/2026-10-02-agent/04-一格做什麼.md) 在 agent 自己的一格裡同步叫模型。
本方案讓 agent 的收信與模型計算分開。

固定兩槽就能直接展示「最多兩筆受管 LLM 計算」。
長模型呼叫不會占住 agent 工作資料夾的 tick 鎖。
agent 可以在別格收取消、補資料或查看狀態。

相較 [Plan 9 的 `/llm/clone`](../../proposals/2026-10-02-plan9/05-agent與kernel的namespace.md)，它先驗排程與結果契約。
不用同時驗 FUSE、fd 生死與阻塞讀取。

- **代價與邊緣狀況**

一次回應至少跨提交、執行、收結果幾個階段。
延遲比同步直連高。
快模型可能反而更不划算。

固定槽會被慢請求占滿。
第一輪可以先用 FIFO。
若要短工作優先、公平分配或重試，就新增了政策。

工作槽當掉，assignment 不可立刻當作空閒。
舊程序可能仍在執行。
第一輪可標為 `unknown`，交人處理。
不能偷偷引入自動租約回收。

殺掉本地 HTTP client，不代表供應商取消計算或收費。
取消應分成「未派發撤回」與「已派發停止等待」。

結果需核對 request ID 與 assignment 版本。
晚回的舊結果不能覆蓋新工作。

固定槽只限制經過這條路的計算。
agent 若仍持有直連 key，仍可繞過。
若要硬強制，必須另外保護 key、工作槽程式與設定。
也不能讓 agent 取得可任意操控受信任工作槽的 daemon 入口。
現行控制與取信沒有分項驗身分。
見 [aos_daemon_ctl.py](../../../src/py/lib/aos_daemon_ctl.py) 第 131–155 行，以及 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 90–103 行。

這不是萬 agent 的擴展解法。
agent 若仍各登記一項，daemon 仍各開執行緒。
見 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 181–182 行。

- **要翻的裁定**

**受信任、同機、固定槽的版本不必翻 tick 基本裁定。**

政策仍只在 kernel tick 執行。
HTTP 仍在某個 tick 的任務裡。
符合 [11 的方向與追答](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。

要改的是 [agent 提案](../../proposals/2026-10-02-agent/README.md) 的「一格完整完成一次模型呼叫與工具」及「LLM 直連」選項。
改成一個 agent 步驟可以跨多格等待。

歷史上的 [LLM 呼叫池裁定](../../verdicts/04-late-day-directions/02-LLM呼叫池.md) 有相近方向。
但不能據此把舊 node、JSON-RPC 與池協議直接復活。
[第二十七批](../../verdicts/11-tick-as-unit/28-1002-第二十七批.md) 已把那些舊設計封存。
此處是重新提出一個小契約。

若增加自動回收故障工作槽，就需重開 [POC 不處理異常](../../verdicts/11-tick-as-unit/03-1001-POC默認一切正常.md)。
若改現行共用 socket 來做分項驗身分，就需翻 [第二十五批](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)。
最小實驗兩者都不做。

- **最小實驗**

兩天。
兩個 agent、兩個工作槽、二十筆假模型請求。
假模型混合短等待與長等待。

量四件事：

1. 受管模型呼叫的同時數是否始終不超過二。
2. 等模型的 agent 能否在別格接收取消。
3. submission 到 agent 取得結果多花幾格。
4. 某槽中斷後，是否留下可辨識的未知工作。

和同步直連版比較。
若排隊與接續成本大於解放 agent 的價值，就保留原提案。

## 不換方向的改良

1. **分開三種完成。**
   程序退出、tick 結束、工作完成各有欄位。
   借 supervisor 的分工即可。
   不必引進自動重啟。

2. **讓 summary 表示最新狀態。**
   加狀態版本。
   內容沒變就不寄。
   收到一封 summary 本身不是再次 grant 的理由。
   同時記訊息數與 bytes。
   現行合併叫醒仍會保留每封信，不能只量開格數。

3. **工具配置附重試政策。**
   先用 `safe`、`query`、`manual` 三類就夠。
   放在 agent 的工具設定。
   不加進 inst 核心。
   即使不做自動恢復，也能讓人知道中斷後該怎麼處理。

4. **先保存模型原始回應。**
   再交給 `act` 解讀。
   解讀器修正後可重解同一份資料。
   不必重新付一次模型計算成本。

5. **把 Plan 9 的收益拆開驗。**
   固定路徑、替換服務、限制可見入口、改成檔案協議是四件事。
   原提案的 [bwrap 最小實驗](../../proposals/2026-10-02-plan9/09-最小實驗.md) 適合驗前幾件。
   不把 FUSE 成功掛起來當成額度、身分與取消也已解决。

6. **內部重試仍算安排者的格。**
   HTTP timeout 與供應商限流才用外部時間。
   不因借了 batch 或工作流概念，就順手改成牆鐘 lease。
   這沿用 [11 的時間裁定](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。

## 試過但放棄的想法（各一兩句）

- **整套 OTP supervisor。**
  重啟策略比目前要驗的政策分工更早長大。
  也沒有解決外部效果是否已成功。

- **aos 只產 systemd unit。**
  能減少部分程序管理程式。
  但會改變首版依賴方向，也讓 aos 的政策與外部服務管理設定分散。

- **縮小版 Kubernetes。**
  這裡最有用的是單一寫入者與狀態比對。
  不需要順便造 API server 與通用資源模型。

- **整套 Temporal 當底座。**
  會多一個執行與恢復體系。
  若目的是試 aos 的 tick 模型，應先借結果記錄，不先換底座。

- **mq 全面落盤。**
  能改善部分丟信窗口。
  但工具成功後失聯的問題仍在，不能用它取代效果收據。

- **每個 agent 都是常駐 actor。**
  事件反應會直接。
  但會繞過 tick，且把 mailbox、程序與工作生命週期綁在一起。

- **把 LLM 當可搶占的 CPU 工作。**
  本地停止等待不等於遠端停止計算。
  先做執行名額，比模仿時間片更貼近實際控制能力。

- **先做完整 `/llm/clone` 檔案服務。**
  檔案介面有獨立價值。
  但若這輪想驗排程，普通工作目錄與固定槽能更直接隔離問題。

## 問使用者的問題

| 題 | 選項與後果 | 建議 |
|---|---|---|
| 第一個對照實驗要回答什麼？ | A：政策應是訊息還是持續狀態。B：中斷後能否保住昂貴成果。C：計算是否應從 agent 拆出來排。 | 先 A。若最想驗「特殊計算 OS」，先 C。 |
| grant 要不要成為可直接查看的期望檔？ | 保留私門 grant：空格少、接線接近原案。改期望檔：版本清楚，但增加讀檔與低頻空跑。 | 兩個假 agent 並排一天，用開格數與可理解性決定。 |
| 這輪是否放寬「先不處理異常」？ | 不放寬：只保存回應與收據。局部放寬：加入工作單接續與 `unknown`，增加工具恢復政策。 | 先留收據。自動接續另做一天半實驗。 |
| LLM 先直連還是經固定工作槽？ | 直連：少接力、延遲低。工作槽：能單獨排計算，但跨格延遲與工作狀態更多。 | 先用假模型比較。不要同時加入 FUSE 與硬額度強制。 |
| 外部效果不確定時怎麼辦？ | 自動重做：較快前進，但可能重複。留 `unknown`：需要判斷，但保留事實界線。 | 預設 `unknown`。只有工具明確允許時才重做。 |