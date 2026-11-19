# 對照 Linux：Linux kernel 替每個行程記什麼、拿來分配什麼，aos 今天各有沒有對應（照 HEAD 308443eaf 的程式與假腦實跑）

← [README](README.md)｜上一份：[00-使用者原話](00-使用者原話.md)｜下一份：[02-記什麼-資源清單](02-記什麼-資源清單.md)

## 先講結論

- **「排程這塊我們已經有了」最可能指的是 llm kernel 的排隊**：問腦的信不是先來先做，而是照「級數（含等久了自動升級）→ 期限 → 同後端黏著 → 端點速度 → 等得久 → 先寄」排，還有總格數、保留給 high 的格、每個端點與後端的格數（`py/tools/aos/kernel_llm/order.py`、`slots.py`；使用者 11-06「不是先來先處理」，C-54 R14）。起停那邊另有框架站的 `max_running`、`queue`、`allowed`。這是推測，README 末尾請他對不上就直接說。
- **但「級數」今天沒人在用**：agent-fsm 的 `brain.py` 寄信不寫 `priority`，所以每封都是 normal，實際只靠「等得久」在排。旋鈕在、沒人轉。
- **aos 已經有 Linux 那張表的大半骨架，只是散在三個人手上**：daemon 管身分、狀態、rlimit／cgroup 份額；llm kernel 管 token 帳、額度、排隊；agent 自己記工具呼叫（`observed.jsonl`）。**沒有任何一處把它們收成「一個 proc 一筆」**。
- **最大的落差是「身分」**：Linux 的 pid／uid 是 kernel 發的、不能冒充；aos 的 kernel 認人靠信封上的 `sender`，那是寄件人自己寫的路徑、不驗（體檢 P15）。所以「依角色給優先」這種規則，今天任何一隻都能假裝自己是規劃者。
- **「角色」沒有地方標**：沒有任何檔寫「這隻是負責規劃的」。最接近的是 kernel.json 的 `budget.senders`——一張人手寫、以 stack 路徑為 key 的「每隻的設定」，今天只放額度。

## 一張對照表

燈號：● 有　◐ 有一部分／有機制沒人用　○ 沒有

| Linux 替每個行程記的 | Linux 拿它做什麼 | aos 的對應 | 誰持有、在哪 | 有沒有 |
|---|---|---|---|---|
| pid、父行程、uid、cgroup 歸屬 | 認人、算帳歸給誰 | daemon 表的一列（名、pid、stack、def、ws）；巢狀 daemon＝父子；`limits.user`／`sub:N` 換帳號 | daemon：`procs_state.json` | ● daemon 認得；**kernel 只認 `sender` 字串** ◐ |
| 狀態（R／S／D／Z） | 排程只挑能跑的 | `phase`（running／stuck／asleep／stopped）；agent 自己的 `stage.txt`（idle／think／wait／act） | daemon；agent stack | ● |
| 累計 cpu 時間、記憶體、I/O | 公平排程、OOM 挑誰、`top` 顯示 | 機器那份：rlimit 只設上限不記用量；cgroup（預設 off）開了才有累計。錢那份：`ledger.jsonl`、`used.json` 按 sender 記 token、次數、耗時 | daemon（上限）；llm kernel（token 帳） | 機器 ◐、token ● |
| nice／優先級 | CFS 照權重分 cpu | 問腦信的 `priority`（low／normal／high 或數字正負、`deadline`）＋ `aging_cycles` 等久升級＋ `reserved.high` 保留格 | llm kernel：`order.py`、`slots.py`；寄件人自己宣告 | ◐ 機制完整、寄件人都不寫 |
| rlimit | 單一行程的上限 | daemon 列上的 `limits`：`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`，`limits_max` 天花板 | daemon：daemon.json／`procs_state.json` 的 `limits` | ● |
| cgroup（cpu.weight、memory.max） | 一群行程共用一份 | 機器：daemon 的 `cgroup` 選項、`mem_total_mb`、`procs_total`。錢：**`llm-team` 隊 kernel**——一隊一台 kernel、自己的額度，再轉給主 kernel（`templates/kernel/llm-team`） | daemon；隊 kernel | ● |
| 配額用完（OOM、SIGXCPU） | 砍掉或擋住 | `BudgetMissing`：`spent: "refuse"` 回錯、`"wait"` 整列等下一窗；三層（總額、每端點、每寄件人）各有上限與窗 | llm kernel：`budget.py` | ● |
| 誰可以起、同時幾隻 | （fork 限制） | 框架站：`allowed`、`max_running`、`queue`；procs-kernel 範本；kernel 可以夾份額（`limits_clamped`） | 框架站 `py/tools/aos/kernel` | ● |
| 等人表態 | （沒有） | `hold`：規則放行的信先扣著，等一隻當 kernel 的 agent（`kernel_gate`）點頭 | 框架站 `hold.py`、`kernel_gate` | ● aos 獨有 |
| 誰先被喚醒 | 排程佇列 | 沒人排：每隻照自己的 `interval_ms` 自己醒、`on_clock` 自己看鐘 | — | ○ |
| 角色（核心執行緒、即時行程） | 即時排程類別 | 沒有欄位；只能人手在 kernel.json 以路徑列名單（`budget.senders` 那種） | — | ○ |

## 三個持有者各看得到什麼

```
 agent ──問腦信──► llm kernel ──掛 proc──► daemon
   │  （sender、endpoint、priority、     │（pid、phase、limits、
   │    完整 messages 都看得到）          │  counter_restarts）
   │                                      │
   └─ 自己記：observed.jsonl（每次工具：名、結束碼、耗時、bytes）
      history.jsonl（說過什麼）、stage.txt（在哪一格）
```

- **天然經過 kernel 的**：每次問腦（llm kernel 看得到寄件人、端點、整份 prompt、回來的 `usage`、等了多久）；每次起停睡醒（框架站、procs-kernel 看得到誰要起誰）。
- **不經過 kernel 的**：工具呼叫（agent 在自己行程裡跑，只有它自己的 `observed.jsonl` 記）；檔案讀寫；cpu／記憶體（daemon 與作業系統那邊）；**eca-claude 的所有花費**（claude CLI 自己連線，不寄問腦信）；使用者看了什麼（沒人記）；耦合度（不是一次「消耗」，是程式碼的性質）。
- 所以「kernel 多記一些」分兩半：經過它的，它自己記就好；不經過它的，要嘛有人報給它（agent 自報、量測程式報），要嘛它自己去讀別人的檔。

## 沒查到的

- 使用者說的「排程」若指別的機制（例如他心裡的是框架站、或 11-13 任意資源 OS 那輪談的東西），上表要重排——寫在 README 請他直接說。
- cgroup 開起來實際數字：公司 WSL 沒 systemd 委派，照 `cpp/aos-daemon/docs/09-份額.md` 寫，沒實測。
