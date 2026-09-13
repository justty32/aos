# 任務書 4：kernel module 機制 ＋ 把 llm-cpu 的排程層裝成第一個 module

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改**：`proto4-3/aos_kernel.py`、`aos_kernel_tick.py`、`aos_kernel_syscall.py`、`aos_kernel_init.py`、新檔 `proto4-3/aos_kernel_module.py`、`proto4-3/test/test_kernel.py`（或新檔 `test/test_module.py`）、`proto4-3/test/fx/`（新增假 module）、`proto4-3/README.md`、`proto4-3/docs/kernel.md`、`proto4-5/` 底下（新檔 `llm_cpu_module.py`、`README.md`、`test/`）。**不要 git commit、不要 push。** 不要開其他 agent。不要打真網路。開工前兩邊測試先跑一次確認綠的。

## 先讀

`proto4/notes/22-llm-cpu.md` §22.6–§22.8（為什麼排程層是 kernel module、機制定案）；`proto4/notes/16-19-kernel.md` §19.5（`aos-kernel <什麼>`＝syscall 入口）；`proto4-3/aos_kernel_tick.py`（`tick()` 六步）、`aos_kernel_syscall.py`（rm 那張單怎麼收、怎麼回音 `syscalls/done/`）、`aos_kernel.py`（`KHome.config()` **目前只留 int 值**——要改）、`docs/kernel.md`；`proto4-5/llm_cpu_tick.py`（`tick(directory)`）、`llm_cpu_home.py`（`init_home`、`submit`、`show`）、`README.md`。

## A. 機制（proto4-3，`aos_kernel_module.py`）

- `config.json` 多一個選填欄 `"modules": ["/abs/path/xxx_module.py", …]`（預設 `[]`）。`KHome.config()` 改成：int 照舊、`modules` 若是字串陣列也留下。`aos-kernel-init --module PATH`（可重複；存絕對路徑）。
- `aos_kernel_module.load_modules(cfg) -> list`：用 `importlib.util.spec_from_file_location` 逐個載入；載不起來（檔不在、語法錯、缺必要屬性）→ 回傳裡略過它、附一句 note（kernel 不會因此死）。
- 一個 module 是一個 Python 檔，約定五樣（缺的當沒有）：
  - `NAME`（字串）、`OPS`（tuple，它認得的 syscall op）；
  - `handle(h, cfg, st, ticket) -> (ok: bool, msg: str)`：處理一張 op 在 `OPS` 裡的單；
  - `tick(h, cfg, st) -> list[str]`：每回合跑一次，回幾句 notes；
  - `status(h, cfg) -> str|None`：給 `aos-kernel ls` 印一行；
  - `cli(h, cfg, argv) -> int`：`aos-kernel <NAME> [K] …` 轉給它。
- 接線：
  - `handle_syscalls`：op 不是 `rm` 時，找 `OPS` 含它的 module 叫 `handle`；沒人認 → 照舊「看不懂這張單」。module 丟例外 → `(False, "module X 壞了：…")`，一樣回音、刪單。
  - `tick()`：在 `handle_syscalls` 之後、`check_queue` 之前加一步 `run_modules`（每個 module 的 `tick`，例外只記 note）。
  - `cmd_ls`：佇列那幾行之後，每個 module 的 `status` 有回就印一行。
  - `aos_kernel.main`：不認得的子命令先看 `here_or_die`／位置參數規則跟 `ls` 一樣拿到 K 與 cfg，再找 `NAME == cmd` 的 module 叫 `cli(h, cfg, rest)`；都沒有才印「不認得的子命令」。注意 `aos-kernel <NAME> [K] …` 的 K 解析：第一個參數若是資料夾且裡面有 `config.json` 就是 K，否則 K＝cwd（跟 `add` 一樣）。
- 測試（`test/fx/echo_module.py` 假 module：`OPS=("echo",)`，`handle` 把 ticket 的 `text` 寫到 `K/echo.txt` 回 `(True, "echoed")`；`tick` 回 `["echo tick"]`；`status` 回 `"echo: ok"`；`cli` 印 argv 回 0）至少 6 條：init `--module` 寫進 config、config 讀回來有 modules；tick 的 log 有 `echo tick`；丟一張 `{"op":"echo","text":"hi"}` 的單 → 下一 tick `echo.txt` 是 hi、done 回音 ok；不認得的 op 還是「看不懂」；`ls` 有 `echo: ok`；`aos-kernel echo K a b` 退出 0；modules 指到不存在的檔 → tick 照跑、log 有一句、退出 0。

## B. LLM module（proto4-5，`llm_cpu_module.py`，薄）

- `NAME="llm"`、`OPS=("llm",)`。家＝`K/llm/`（`h.dir + "/llm"`）：`tick` 第一次看到沒有就 `llm_cpu_home.init_home(K/llm)`（範例 endpoints.json，使用者自己改），note 一句「llm module：建了 K/llm/，去改 endpoints.json」。**`K/llm/inst.json` 不要建**（它不再是獨立行程），`init_home` 若一定會寫就寫完刪掉或加參數跳過。
- `handle`：ticket `{"op":"llm","id":ID|null,"request":{…}}` → `llm_cpu_home.submit`（用記憶體物件寫進 `K/llm/requests/`；沒 id 就自動配）→ `(True, "排進去了：id=…；結果會在 K/llm/results/<id>.json")`；驗證失敗 → `(False, 原因)`。
- `tick`：`llm_cpu_tick.tick(K/llm)`，回 `["llm: queued N running M"]`（從它的 state.json 讀）。
- `status`：`"llm: queued N  running M  done K  endpoints: local 0/1, deepseek 0/2"` 一行。
- `cli`：`aos-kernel llm [K] REQ.json|- [--name ID] [--wait SECS]`：讀 REQ、寫一張單進 `K/syscalls/`（照 `cmd_rm` 的寫法，等 `syscalls/done/` 回音、印 msg）；`--wait N` 時再輪詢 `K/llm/results/<id>.json` 最多 N 秒，出現就把整份印到 stdout、`ok` 真退出 0 假退出 1；等不到印「還沒好：結果會在 …」退出 3。**--wait 需要 kernel 真的在 tick**（daemon 在跑）——README 講清楚。
- `llm-cpu` 這支 CLI 保留（獨立行程的用法還能跑），README 改成「第二層有兩種掛法：獨立行程（`llm-cpu tick`）或 kernel module（推薦）」。
- 測試（`proto4-5/test/test_module.py`，用既有假 server；kernel 用 `proto4-3/aos-kernel-init` 建暫存家＋`--module <abs llm_cpu_module.py>`，**不開 daemon**：直接呼叫 `aos-kernel-tick`，poll_cpus 會記「插上失敗」但照跑）至少 6 條：第一次 tick 建出 `K/llm/`；改 endpoints.json 指到假 server；`aos-kernel llm K req.json --name t1` → 回音 ok；tick 兩次後 `K/llm/results/t1.json` 有 `ok true`、text；`ls` 有 `llm:` 行；壞請求（有 model）→ 回音 ok false；`--wait 5` 搭配背景執行緒每 0.3 秒跑一次 tick → 印出結果、退出 0。

## C. 文件

- `docs/kernel.md`：新節「kernel module」（config 的 `modules`、五個約定、每回合第 2.5／2.6 步、`aos-kernel <NAME>` 轉給 module、第一個 module 是 llm）；家的清單加 `llm/`（module 自己的家，慣例＝`K/<NAME>/`）。
- `proto4-3/README.md`「怎麼跑」補一行 `./aos-kernel-init K --ncpu 2 --module /abs/proto4-5/llm_cpu_module.py`（註：LLM 排程當 kernel module）；300 行以下。
- `proto4-5/README.md`：第二層那節改寫成 module 用法：init 帶 `--module` → 改 `K/llm/endpoints.json` → `aos-kernel llm K req.json --wait 60` → 或不等、之後看 `K/llm/results/`。200 行以內。

## 驗證

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -2
cd /home/lorkhan/repo/simple_tools/aos/proto4-5 && python3 -m unittest discover -s test 2>&1 | tail -2
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
```
`aos_kernel_tick.py`／`aos_kernel.py` 超過 300 行就拆。

## 回報（十二行以內，大白話）

A／B／C 各一行；三邊測試數與最後一行；自己決定的事、坑、沒做到的。
