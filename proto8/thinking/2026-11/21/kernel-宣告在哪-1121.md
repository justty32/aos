kernel 的宣告大部分不在 interfaces.json：只有 llm kernel 有這份檔、只宣告 aos-ledger 一格且沒程式讀；hook 點宣告在程式夾、清單在 kernel.json、請求與錯誤代號只在文件（11-21，線 top-1121-kdeclhtml，只讀）。

← [2026-11-21](README.md)｜桌面頁：`~/Desktop/aos-kernel的宣告-1121.html`｜前情：[hook-points-格式-使用者審-1121](hook-points-格式-使用者審-1121.md)、[aos-pylib-kernel入口-1121](aos-pylib-kernel入口-1121.md)

## 原話

使用者 11-21：「對了，kernel的宣告也是在interfaces.json嗎？也整理一份html放到桌面吧」

背景原話（頂層轉）：「hook體系的唯一約定，就是要在interfaces.json中宣告，有宣告就能用」（11-21 早）；interfaces.json 的定位是「想看這個agent/kernel/...有提供啥界面，就去看interfaces.json，找自己想看的」（11-20 晚）。

## 一句話答案

**部分**：llm-kernel、llm-team、start-api/llm 有 `interfaces.json`，內容同一行 `{"description": …, "aos-ledger": {"file": "ledger.jsonl"}}`；procs-kernel、daemon-kernel、start-api/perm、kernel-python 沒有。其他對外的東西都不經 interfaces.json。

## 查到的事實（HEAD 87ad225a5）

| 對外的東西 | agent | kernel | 宣告在檔裡／只在文件 |
|---|---|---|---|
| 宣告檔 | 每個範本都有 interfaces.json | 只有 llm 三夾有，只一格 aos-ledger | 部分 |
| hook 點 | interfaces.json `hook_points` | 程式夾 `py/tools/aos/kernel/hook_points.json`（kernel、kernel_llm 共用，`hooks.py` 固定路徑讀）；loop 四點寫在 loop.json argv 的 `--points` | 在檔裡，但定義夾沒指過去 |
| hook 清單 | interfaces.json `hooks` → hooks.json | kernel.json 的 `hooks` 鍵；loop 四點在 `loop_hooks.json`（loop.json 指，三夾都沒有此檔＝沒 hook） | 固定位置 |
| 設定檔 | `tools`／`llm`／`system` 檔名在 interfaces.json | kernel.json，固定名，由 daemon.json／loop.json argv 帶 | 固定名 |
| 可設的鍵 | `llm_keys` | kernel.json 各鍵見 README | 只在文件 |
| 請求 body | — | 一般 kernel：daemon 的 body（`procs_added`…）；llm kernel：`endpoint`、`reasoning_effort`、`request`、`priority` | 只在文件，無 schema |
| 可挑的模型 | — | kernel.json `endpoints`（混 url、exec 等內部鍵）→ 每輪算出 stack 的 `endpoints.json`，`aos-llm ls` 讀；`ls` 自動辨識靠「有 endpoints.json＋requests/」 | 內部設定＋執行時窗 |
| 錯誤代號 | _tooldef＋文件 | 程式自己的錯在 `_tooldef.json` `errors`；拒信代號（NameUnknown、SlotMissing、BudgetMissing…）只在 README／知識庫 | 部分 |
| 帳 | history、aos-observed，有讀者 | aos-ledger，**沒有程式讀**（附錄 4 原文） | 在檔裡、沒人讀 |
| 給外面寫的 | stack 覆蓋層，名字照 interfaces.json | `decisions/<信名>.json` 只在 README | 沒宣告 |
| 掛上時查宣告 | `ctl add` 要 aos-agent 那格 | `aos-daemon-ctl add` 不讀 | — |

- **編譯 `defs`**（`py/aos/kernel_spec.py`）：`program="kernel"` 不寫 interfaces.json（loop 或 daemon 身體都一樣）；`program="kernel_llm"` 寫固定的 `LEDGER` 一格、每次整份蓋掉。編譯時用程式夾的 hook_points.json 驗 hooks，但編出的夾不記點宣告在哪。
- **讀 interfaces.json 的程式**：全是 agent 一家（aos-agent 各子指令、declared_files、agentlib/hooks、agent_hooks、hook_point.for_definition 只讀 `aos-agent` 格、cli_cfg、agent_spec）與 observed（只認 `aos-observed`）。aos-gdb 只對 agent。
- **aos-hook 實測**（unset AOS_* 後 `PYTHONPATH=py python3 -m aos.apps.hook.main`）：`points --points py/tools/aos/kernel/hook_points.json` 列出三點；`check … --list templates/kernel/llm-kernel/kernel.json` 回 `ok: 3 points from 1 declarations, 0 hooks from 1 lists`；`points --agent templates/kernel/llm-kernel` 退 0、無輸出，`check --agent templates/kernel/procs-kernel` 回 `ok: 0 points`。
- **規範**：NORMS「宣告介面 interfaces.json」（命名-續 01）只舉 aos-agent，沒提 kernel；N-42-1 ledger 條寫「定義夾 interfaces.json 以 aos-ledger 宣告」；附錄 4 的 interfaces.json 讀者只列 agent，ledger.jsonl 讀者「沒有程式讀」、出處路徑寫成舊的 `proto8/kernel/llm-kernel/`。知識庫 `knowledge/aos/kernel.json` 沒提 interfaces.json。

## 落差

1. kernel 的 hook 點有宣告檔，但從定義夾指不過去（在程式夾、靠同夾固定路徑）。
2. `aos-hook --agent` 對 kernel 夾默默給 0 點、不報錯。
3. hook_points.json 寫 `"provider": "kernel"`，`hook_point.PROVIDERS` 沒有 kernel，引用不到。
4. 同一份點宣告兩支程式共用、說法對不上：`before_reply` 宣告寫「only with reply_via_me」，llm kernel README 寫不用開；`hold` 只有一般 kernel 收。
5. aos-ledger 宣告了沒人讀。
6. 請求格式與拒信代號只在文字；兩種 kernel 拒信形狀不同（`{"applied": false, "error"}` 與 `{"error"}`）。

## 照「有宣告就能用」會碰到的邊緣狀況（只攤事實與後果）

- 點宣告在定義夾外：要從 interfaces.json 指過去得用指示詞或 provider 名，就是使用者今天嫌 `{"provider": "aos-loop"}` 看不出哪來的同一題。
- 四夾沒宣告卻能掛 hook：若「沒宣告＝不能用」也套 kernel，現況算違反。
- 清單不是獨立檔：只能宣告「清單在 kernel.json」，設定與清單同一份（`aos-hook --list` 本來收任何有 hooks 表的 json）。
- loop 身體多一家點、多一份清單（kernel 三點＋loop 四點；kernel.json＋loop_hooks.json）。
- 一份宣告兩種意思：要嘛拆成兩份，要嘛維持一份但不精確。
- endpoints.json 是執行時算出的 stack 窗（前例：agent 的 history 也相對 stack）。
- 宣告了也要讀者：aos-llm ls 現在靠檔案認 llm kernel，不看宣告。
- kernel_llm 重新編譯會整份蓋掉 interfaces.json，手加的格會不見；kernel 不寫，手寫的留著。
- `decisions/` 是給外面寫的地方（C-81 精神）卻沒宣告。

**材料，不是建議**：若要 kernel 也照 interfaces.json，大概多出 `aos-kernel`（requests、hooks→kernel.json、hook_points、decisions）、`aos-llm-kernel`（endpoints→endpoints.json）兩格；要動四夾新增＋三夾加格、`kernel_spec.py`、`hook_point.for_definition`／`PROVIDERS`、`aos-hook`（只有 --agent）、`kernel/hooks.py`、`cpp/aos-llm` ls、三份 README、知識庫 kernel.json、附錄 4。另一選項是維持現狀、文件寫明 kernel 不走 interfaces.json，後果是那句定位只對 agent 成立。
