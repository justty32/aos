# 題 2：一些 agent 共用 cpu

← [本題 README](README.md)｜規範：[agent info](../../spec/agent/info.md)（三個池、工具檔 §3.3）、[agent 送件](../../spec/aos-agent/send.md)、[登記](../../spec/aos-agent/register.md)、[cpu 範式](../../spec/cpu/methods.md)、[proto5-2 scale](../../../proto5-2/spec/scale.md)

（astra 審查後改：必修 6～8、10 與建議 14～16 已併進來，見 [review-astra.md](review-astra.md)）

## 1. 現況：其實已經全部共用

- **agent 沒有自己的 cpu，也沒有常駐的行程。** 一個 agent＝一個資料夾＋kernel 帳本裡一份反覆行程 `agent-<名>`。
  只有 kernel 把它的 tick 派出去的那一下，某顆 cpu 才跑一支短命的 `aos-agent tick`，做完一小步就退出。
- **`start` 就是進現有的池**（aos-agent 已拍板前提 2；aos-llm 前提 2 也寫「不給 agent 開專屬 cpu」）。三種工作的去處：

  | 工作 | 池 | 怎麼共用 |
  |---|---|---|
  | agent 自己的每一格 | `tick.pool`（預設 `default`） | 所有 agent 的 tick 輪流在 default 池的幾顆 cpu 上跑，一顆一次一格 |
  | 問模型 | `llm.pool`（預設 `llm`） | 所有 agent 的問題排同一條隊，llm 池有幾顆就同時問幾件 |
  | 跑工具 | `tool_pool`（預設 `default`） | 所有 agent 的工具跟所有 agent 的 tick 搶 default 池 |

- **「一個 agent 一顆」的東西只有**：kernel 帳本那一筆行程紀錄、家裡的 `.tick.lock`（同一個家同時只一格）。沒有哪顆 cpu 是某個 agent 專用的。
- 所以使用者說的「共用 cpu」三種可能意思，逐一看：

| 可能的意思 | 現況 | 要不要改 |
|---|---|---|
| (i) 多個 agent 的工具跑在同一批 exec cpu 上 | **已經是**：預設全擠在 default 池 | 不用 |
| (ii) 多個 agent 的 tick 由同一顆 cpu 驅動 | **已經是**：default 池一顆 cpu 會輪流跑好幾個 agent 的 tick | 不用 |
| (iii) agent 不再各有自己的行程 | **已經是**：沒有常駐行程，只有帳本一筆 | 不用；上千個時另論（§4） |
| (iv) **「這幾個 agent」專用一組 cpu**，跟其他 agent 隔開 | 做得到：開一個池，那幾個 agent 的池都指過去（跟題 1 的 (c) 同招） | 不用改程式 |
| (v) **某一支工具**（不是某個 agent 的全部工具）固定跑在某顆 cpu 上，好幾個 agent 共用 | **做不到**：池只能設在 agent 一級（`tool_pool`），工具檔 §3.3 沒有「這支工具走哪個池」 | 要改，很小（§3） |

我猜使用者想要的多半是 (iv) 或 (v)：例如一張 GPU、一個瀏覽器、一個會被搶的外部資源，要讓好幾個 agent 排隊輪流用。
**一個只有一顆 cpu 的池，就是一把排隊的鎖**：經過它派的工作一件一件做，照 queue 順序。但它只管得到「經這個池派出去的」——
外部程式、別的池的工具、沒清乾淨的子行程要碰同一個資源，它擋不住。
另一個折衷是「工具自己拿鎖」（工具程式裡 `flock` 一個檔再做事）：不用改任何東西，但等鎖時佔著一顆 exec cpu，也不保證先到先拿。

## 2. 使用者的猜想對不對

> 「只需要把某個 agent 的 tool 弄成 aos-exec 之類的就好，不用動 kernel 和 daemon」

- **結論對**：不用動 kernel、daemon。
- **但前提要更正**：工具**現在就是** aos-exec 跑的——agent 把每個 tool call 寫成一份 posix inst，`add --once` 給 kernel，kernel 派一張 `aos-exec` 單給 `tool_pool` 的某顆 exec cpu。
  沒有另外一種「aos-exec 工具」要做。
- **`kind=aos` 不是一種工具**：它是 aos-exec 回音的分類，意思是「aos-exec 自己失敗、程式根本沒跑」（inst 讀不到、壞掉）。
  跟它相對的是 `kind=child`（程式真的跑了）。任務書裡的「kind=aos 的工具」在規範裡不存在。
- 若「弄成 aos-exec」指的是**工具本身再去叫 kernel**（工具程式裡跑 `aos-kernel add --once --pool X --wait-ms …`，把真正的活丟到 X 池）：
  照規範做得到，但工具那顆 cpu 會**一直佔著等**；X 如果就是它自己所在的池、而池裡的 cpu 都被這種工具佔滿，就會互相等到 `--wait-ms` 逾時
（CLI 逾時**不取消**裡面那件，它之後照跑、回音沒人收）；不給 `--wait-ms` 上限就是真的卡死。不建議。

### 例子：amy、bob 共用一支 `gpu-run` 工具、一顆 cpu（照規範應該可以，沒真跑）

1. `K/info.json` 的 `cpus` 加一顆：`"gpu": {"pool": "gpu"}`（下一格 kernel 就拉，不用 boot）。
2. 寫一份共用工具檔 `/abs/shared/gpu.json`：

   ```json
   [{"type": "function",
     "function": {"name": "gpu_run", "description": "在 GPU 上跑一個腳本",
                  "parameters": {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}},
     "_meta": {"argv": ["/abs/shared/bin/gpu-run"], "stderr": {"$opt": "append", "$val": "log/gpu.err"}},
     "_timeout_ms": 600000}]
   ```

3. amy、bob 的 `info.json`：`"tools": ["tools/base.json", "/abs/shared/gpu.json"]`，**`"tool_pool": "gpu"`**。
   `tool_pool` 在送件那一刻才讀，下一批就生效，不用 stop／start。
4. 兩人叫 `gpu_run` 時，工作都排到 gpu 池那一顆，一件一件跑。一批裡有很多件時，別人要等整批跑完，但有限時的工作不會讓人永遠卡住
   （agent 等回音時自己的 tick 會退出，不會一直佔著 gpu 那顆）；真的會永遠等的是：工具不限時（`_timeout_ms: 0`）卡住、cpu 起不來、池被拿掉。

**缺點就是 (v) 的洞**：`tool_pool` 是整個 agent 的，第 3 步之後 amy、bob 的 `read`／`bash` 那些工具也全擠到 gpu 那一顆。
現在的繞法是「共用工具的 agent 只裝這一支」，或把 gpu 池開成跟 default 一樣多顆（那就不是一把鎖了）。

## 3. 建議與最小版

- (i)～(iv)：**不用改**，缺的是文件——教程 05 補一節「讓幾個 agent 共用／專用一組 cpu」，就是上面的例子。
- (v)：**工具檔加一欄 `_pool`**（跟現有的 `_timeout_ms` 同一種寫法）：寫了就用它、沒寫照舊用 `tool_pool`。
  - 規範：agent info.md §3.3（多一欄、型別字串、可省）、aos-agent send.md §5.2（「act 的池＝那個工具的 `_pool`，沒寫才是 `info.tool_pool`」一句）、essentials.md 提一句。
  - 程式：`aos_agent_home.py` 驗 `_pool` 型別（跟 `_timeout_ms` 的檢查放一起，幾行）、`aos_agent_batch.py` 選池那一行（`pool = (tool or {}).get('_pool', run.info['tool_pool'])`）、
    `aos_kernel_check.py`（agent 的檢查實際寫在這裡，`aos_agent_check.py` 只是叫它）查 `_pool` 與沒寫時用的 `tool_pool` 在不在 K 的池裡、不能是 `kernel`。
    **粗估、沒驗證**：十幾行＋測試。
  - kernel、daemon、aos-llm、帳本都不動；工具檔只加底線開頭的鍵，送模型前本來就會拿掉，模型看不到。
  - 這樣上面的例子改成兩個動作：`/abs/shared/gpu.json` 裡 `gpu_run` 那一個元素加 `"_pool": "gpu"`；amy、bob 的 `tool_pool` **改回 `default`（或拿掉）**。
    其他工具就照舊在 default，只有 `gpu_run` 走 gpu 那一顆。

## 4. 上千個 agent 時，共用卡在哪（對 proto5-2 scale.md）

（astra 審查後改：速率、帳本讀寫、輪詢三處原本講錯或漏掉）

| 瓶頸 | 為什麼 | 對到 proto5-2 |
|---|---|---|
| 閒著的 agent 也在跑 | 沒輸入的 agent 還是一直被派，起一支 Python、看一眼、退 101。`interval_ms` 是「收回後最早何時再派」，不是固定頻率；一顆工作 cpu 每格最多接一件、做完要等 kernel 下一格收回才能再接。所以實際速率≈每格可派的閒 cpu 數，1000 個 agent 會變成「每個 agent 被叫的間隔被拉長」，也把工具、問模型的派工擠慢 | 不在 scale.md 三題裡；**是 agent 這邊的新題**：要不要讓閒的 agent 睡久一點，或改成「有輸入才叫醒」 |
| 教程的經驗值「default 池 cpu 數 ≥ agent 數」 | 一顆 cpu＝一支常駐 Python，每支約 10～20 MB（**沒實測**，要分實際佔用與共用頁），1000 顆≈10～20 GB | scale.md §3 第 1 點／README 要拍第 3 題（一顆 cpu 一支行程） |
| 閒的 cpu 也在輪詢 | 現在 kernel 建的 cpu 每 **20 ms** 掃一次自己的 `requests/`（proto5-2 草稿才改 200 ms）；1000 顆＝每秒五萬次列目錄 | scale.md §3 第 2 點 |
| agent 讀整份 `K/state.json` | 不是每格都讀：閒著、沒送件的 tick 不讀；**送件時每個 call 查一次、清檔時也讀**。所以是「很多 agent、很多 call 同時送」時，讀的次數×帳本大小變成 O(N²) | scale.md §3 第 4 點／README 要拍第 2 題 |
| kernel 帳本整份重寫 | proto5 不是一格寫一次：每則 syscall、每則回音、每次派工、每筆出貨都整份存一次。一格的寫入量≈這格的事件數×帳本大小；每個 agent 至少一筆反覆行程＋在途的 once | README 要拍第 1 題 |
| kernel 派工掃 queue | 每顆閒 cpu 從 queue 頭掃到第一個能派的；queue 長、池多時每格 O(閒 cpu × queue 長) | proto5-2 改成每池 `ready` 已解 |
| 單一條 kernel 鏈 | 一格一格跑，一格的事越多越久，所有派工都等它 | scale.md §3 第 5 點 |
| 行程數、開檔數、磁碟 | 每顆 cpu 一支行程、daemon 每個孩子一個 fd；`cpu.log`、`kernel.log`、agent 的 `log/`、`work/` 都會長 | scale.md §3 第 3、6 點 |
| llm 池 | 一顆 llm cpu 同時只等一個回答。多開幾顆，在模型端點吃得下之前會變快；超過端點的並行能力之後，多的只是在端點那邊排隊 | scale 沒提；真正上限是端點的並行數 |

**共用 cpu 本身不是瓶頸**——池就是為共用設計的；卡的是「每一次都起一支新行程」「閒的也在輪詢」與「大家都讀寫同一份大帳本」。
「好幾個 agent 的 tick 合在一支行程裡跑」（一次 `aos-agent tick` 走好幾個家）能省起行程的錢，但一個家壞掉會拖到同批的；等真的上千再說，這版不提。
