← [agent-access 提案](README.md)

# 環境變數怎麼流到工具

## 現在的流向（proto5 現行規範與程式）

```
你的終端（export 了什麼就有什麼：PATH、AOS_DAEMON_HOME、AOS_KERNEL_HOME、可能還有 OPENAI_API_KEY、SSH_AUTH_SOCK…）
 │  aos-daemon boot            ← 這一刻的環境整包凍結（之後再 export 沒用）
 ▼
daemon ──拉──► 每顆 cpu：daemon 的環境 ＋ K/cpus/<c>/inst.json 的 envs（kernel.json 的 cpus.<c>.envs 抄進去；只加不減，除非寫 clear）
                 │
                 ├─ default 池的 cpu ─► aos-exec ─► 【aos-agent tick】 環境 ＝ cpu 環境 ＋ tick.json 的 AOS_KERNEL_HOME
                 │                                     │ 解工具 _meta 的 $env 用的是「這裡」的環境
                 │                                     ▼ 寫 work/N.inst.json（envs 已解成字面）
                 ├─ tool_pool 的 cpu ─► aos-exec ─► 【工具】 環境 ＝ 那顆 cpu 的環境 ＋ _meta.envs（沒 clear 就整包繼承）
                 │
                 └─ llm 池的 cpu ────► aos-exec ─► 【aos-llm call】 環境 ＝ cpu 環境（含 AOS_LLM_CONFIG）
                                                     金鑰在 llm.json 的 api_key（檔案），或 cpu 環境裡
```

要點：
- 工具**整包繼承它那顆 cpu 的環境**（tick.json 的 `envs` 只加在那一格 tick 身上，不會傳給工具）。但照 proto5 README 的開機步驟，`AOS_KERNEL_HOME`、`AOS_DAEMON_HOME` 在開 daemon **之前**就 export，所以每顆 cpu、每支工具通常都有；你開 daemon 時終端裡的任何金鑰也一樣（[實驗 2](experiment.md#2-路徑逃不逃得出去exp2sh) 模擬這個情況：bash 工具印得出 `AOS_KERNEL_HOME` 和 `OPENAI_API_KEY`）。
- aos-exec **不注入**任何 `AOS_*`（inst-posix §3.2）；工具看到的都是一路繼承下來的。
- 金鑰就算只寫在 llm.json，路徑也寫在 `K/cpus/llm/inst.json` 裡；工具只要碰得到 K 就找得到。

## 哪些該給工具、哪些不該

| 變數／東西 | 給工具？ | 為什麼 |
|---|---|---|
| `PATH`（系統的，`/usr/bin:/bin`，外加工具自己要的） | 給 | 不給連 `python3`、`sh` 都找不到 |
| `HOME` | 給一個**牢裡的**（例如 `/work/ws`），不給真的家目錄 | 真的 `~` 下有 `.ssh`、各種 token |
| `LANG`／`LC_*`、`TZ`、`TERM` | 給 | 無害、影響輸出格式 |
| 工作根目錄（`AOS_TOOL_ROOT`，base 工具包用） | 給 | 工具靠它知道「project directory」在哪；牢裡固定是 `/work`（或 `/work/ws`） |
| `AOS_KERNEL_HOME`、`AOS_DAEMON_HOME` | **不給** | 拿到就能往 `K/requests/` 丟任意工作——等於叫 kernel 在**任何池**（含 llm 池）替它跑任何指令，所有邊界都繞過 |
| `AOS_LLM_CONFIG`、`OPENAI_API_KEY` 這類模型金鑰 | **絕對不給** | 使用者明定 |
| `SSH_AUTH_SOCK`、`GITHUB_TOKEN`、雲端憑證 | 不給 | 同上；真要 git push 另開題 |
| agent 家的路徑 | 不給（除非開放 `self`，那也給別名 `/work/self`） | 別名的意義就在模型不知道真路徑 |

## 建議的流向

```
工具的 _meta.envs = {"$opt": "clear", "$val": {PATH, HOME=/work/…, LANG, AOS_TOOL_ROOT}}   ← 最小版就這樣寫，現有指示詞做得到
                    ＋（完整版）aos-jail 在 bwrap 裡再 --clearenv 一次，只 setenv 上面幾個
```

- **最省的一道**：每支工具的 `_meta.envs` 寫 `clear`。`tools add` 裝的時候就寫好，使用者不用管。
- 另一條路（proto5／proto5-2 都通）：給工具開一個專用池 `tool_pool: "tools"`，那個池的 cpu 在 `kernel.json` 的 `envs` 寫 `clear`。好處是一次管全部工具；壞處是改了要重拉那幾顆 cpu（proto5：已建好的 cpu 家不會照 kernel.json 重寫，要 `aos-kernel halt`、等 cpu 退出、改 `K/cpus/<c>/inst.json`、再 boot——[kernel §1.1](../../spec/kernel/home.md)；proto5-2 改池的 `envs.json`）。建議以 `_meta` 為準、專用池當選配。
- **環境變數擋不住知道路徑的人**：`clear` 之後 bash 仍然可以 `cat /tmp/aos-try/K/cpus/llm/inst.json`（路徑猜得到）。真的要擋 K 與金鑰檔，得靠 bwrap 不掛那些資料夾——這是[完整版](README.md#6-建議方案)要 jail 的第二個理由。
