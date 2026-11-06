← [入口](README.md)｜涵蓋：子題 1 能借的 7 處（判官不排隊、依賴順序、runlevel、優先序反轉、aging 單位、stack 大小、三型＝s6-rc）——各 2～3 選項＋後果、推薦＋判準、落點、排在哪｜上一份 [01-OS與kernel-對照表](01-OS與kernel-對照表.md)｜下一份 [03-韌體與定義-對照表](03-韌體與定義-對照表.md)

# 子題 1 能借鑒的

原則：大重構＝行為不變，這裡全是新行為或條文，**不插 S 步**；排程對照 [apply-ideas 02](../apply-ideas/02-排程.md)（T1～T8、P6～P9、條文日）。每處推薦放第一；零程式的「寫一句條文」優先。

### 1. 判官不排隊：「拒了你自己重寄」寫成條文 → README 方向題 1

- **白話**：RTOS 沒格會讓任務等；aos 判官 `max_running` 滿了直接 `SlotMissing`，寄件人自己重試（agent 生 agent 件 4 就撞這個）。
- **選項**：① **條文一句「判官＝準入、不排隊；要排隊＝寫一個 kernel 身體（llm kernel 是範例）」**——零程式，兩種 kernel 分工清楚。② 判官 `judge.json` 加 `queue: true`：滿了把信留 `requests/`、有格再轉——判官變排程器、模式 1 在 daemon 圈內要記隊列，約 2 h，兩隻 kernel 開始長得一樣（違 N-42「不併成一支」的精神）。③ 判官回 `SlotMissing` 時附 `retry_after_ticks`——加回信欄、寄件人要懂。
- **推薦 ①**；判準：P9 試驗場同一寄件人一分鐘內重寄 >3 次才回頭看 ②。
- **落**：`kernel/docs/02` 「判官怎麼判」旁、N-42 (2) 旁一句。**排**：條文日。

### 2. 依賴順序不給 daemon：「要等誰 ready 自己讀它的窗」

- **白話**：systemd `After=`、s6-rc 等 ready 才起下一個；aos daemon 照 `procs` 順序起、不等。
- **選項**：① **N-28 旁一句「daemon 不排依賴；要等誰＝讀它 `state.json` 的 `counter_runs ≥ 1`，或寄 ping」**——零程式；P8 食譜示範一次。② procs 列加 `after: ["name"]`、daemon 等那列 `counter_runs ≥ 1` 再起——約 30 行 C++，但父要讀子的 state＝擴大 C-52 的例外（no-pid 06 衝突 3 只放行「判 stuck」）。③ 用 `{"daemon": …}` 子樹分層：先起的放上層——結構代替順序，零程式但樹變深。
- **推薦 ①**；判準：P8 食譜若要寫 `sleep 2` 以上才能起下一個，再考慮 ②。
- **落**：N-28 ④ 旁、P8 食譜。**排**：條文日＋P8。

### 3. runlevel／target＝一份 `procs-<名>.json`

- **白話**：runlevel 3／5、`multi-user.target`＝一組服務；aos 已有 `procs: {"$ref": [...]}` 合成，只差慣例。
- **選項**：① **N-54 旁一句「target＝一份 procs 檔；切 target＝procs_ctl 的 `procs` 換 `$ref`（宣告式：拿掉的收、多的起）」**＋P8 食譜寫「`procs-demo.json`／`procs-full.json` 兩份切換」——零程式。② daemon.json 加 `targets` key＋ctl `target` 動詞——多規則、多信型。
- **推薦 ①**；判準：一份 target 檔 ≤ 20 列；超過就是該拆子 daemon。
- **落**：N-54 旁、P8。**排**：條文日＋P8。

### 4. 優先序反轉：不搶位、不保留格，先靠 deadline

- **白話**：fast 包 `slots: 1` 被 low 佔住，high 來了只能等它跑完（錢已花、不殺）。RTOS 解法是繼承／天花板；aos 的在飛任務是 HTTP 呼叫，升級無意義。
- **選項**：① **aos-llm-kernel docs/02 排隊段寫一句「不搶位、不保留格；要保證 high 不等＝寫短 deadline 或多開一包」**——零程式。② 包加 `reserved: {"high": 1}`，低於 high 的補位時少算這幾格——kernel 約 1 h，等於 priority ceiling。③ 搶位殺 low——已否（feat-proto 03 代定 5）。
- **推薦 ①**；判準：P9 量 high 的等待 > 它自己 `timeout_ms` 的 2 倍才做 ②。
- **落**：`impls/aos-llm-kernel/docs/02` 「一次」第 5 步旁。**排**：之後另排（P9 後）。

### 5. aging 的單位跟 kernel 樹的鐘走（併 T4）→ README 方向題 2

- **白話**：現在「等 10 拍升一級」，拍＝daemon `interval_ms`（300 ms）；改 interval 就改了排程行為，凍住再醒也沒道理瞬間全升級。11-06 已裁「kernel 內部計時用自己樹的鐘」（daemon-board 題 1），aging 正是內部計時。
- **選項**：① **T4 順手把「等了幾拍」改「等了幾 tick（兩鐘規則、沒 tick 退牆鐘）」，預設 `aging_ticks: 3`（≈ 現在 3 秒），寫 kernel.json 選填**——T4 本來就在改同幾行，+0.5 h；凍住不升級。② 不動（feat-proto 03 順帶題代定「先不動」）——零改，但排程速度綁 daemon 節奏。③ 改成毫秒 `aging_ms`——違「內部計時用 tick」。
- **推薦 ①**；判準：T4 commit 不增加新錯誤碼；預設行為換算成秒跟現在差 <20%。
- **落**：`impls/aos-llm-kernel` 排隊處、docs/02 第 5 步、N-42 (1)「級數＋aging」那句。**排**：**併 T4**。翻的是 fable 代定、不是使用者裁定。

### 6. 堆疊溢位＝stack 資料夾長太大：不管、寫一句

- **白話**：RTOS 有 stack guard／high-water mark；C-38 說 kernel 參照物含「每檔不超過幾 KB」，但沒人量 stack 資料夾。
- **選項**：① **aos-daemon docs/09 末一句「stack 總量 aos 不量；單檔用 `file_mb`、總量用檔案系統 quota 或人 `du`」**——零程式。② 父每圈 `du` 子 stack、超 `stack_mb` 標 reason——daemon 讀子目錄（C-52）、每圈 I/O 大。③ `limits` 加 `stack_mb` 由 aos-exec 寫檔前查——aos-exec 不該長旗標。
- **推薦 ①**；判準：P9 試驗場跑一天任一 stack >100 MB 才回頭。
- **落**：`impls/aos-daemon/docs/09`。**排**：條文日。

### 7. 三型＝s6-rc 三類（零程式，T8）

exec 型＝oneshot、loop 型＝longrun、`{"daemon": …}`＝bundle（會帶一群）。N-28 ④ 旁一句，給人對 init 系統的直覺；不進附錄1 名詞表（已裁 ≤12 行、那欄是板子）。

## 跟既有原則／已裁的關係

- § 5 翻 feat-proto 03 順帶題的 fable 代定「aging 先不動」：那是 AI 代定、使用者沒裁；翻的理由是 11-06 使用者裁「kernel 內部計時用自己樹的鐘」。寫明、不算違裁。
- § 2 選項 ② vs **C-52**（daemon 不讀子項狀態）、**no-pid 06 衝突 3** 只放行「為判 stuck」：選 ② 就要再開一個例外。推薦不選，所以不衝。
- 疑似衝突、其實不是：**C-11／C-12**「排序＝kernel 的事、一切都是計算任務」vs **C-47 加嚴**「kernel＝管掛不掛」——是原生定義（寬）與實作定義（窄）兩層；lift-to-norms 那隊在 C-47 旁可加一句「排序由 kernel 的身體做，掛不掛由 daemon 做」免得人以為衝突（本夾只提、不改）。
