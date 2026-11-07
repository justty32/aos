家機 codex 開著 workspace-write 沙箱也能連 LiteLLM（localhost:4000）：多帶一個 `-c sandbox_workspace_write.network_access=true` 就行，不用改使用者的 config；推薦 A，待使用者在看板裁。

← [2026-11-08](../README.md)｜派工指令現況 [aos-teams/02「codex 呼叫與沙箱」](../../../../../wf/workflows/dispatch/aos-teams/02-指令沙箱與試玩.md#codex-呼叫與沙箱)

## 使用者原話

11-07 檢討點 5（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md#11-07-檢討使用者答六點)）：「沒關係，sol還算可靠，只要交代清楚就還行。只是未來還是要找時間做沙盒。」

## 結論

**現況**：家機派 codex 要連 LiteLLM 時不帶 `-s`，等於照用 `~/.codex/config.toml` 的 `sandbox_mode = "danger-full-access"`——檔案系統、網路全開。光帶 `-s workspace-write` 時，沙箱裡開 socket 直接被擋（`Operation not permitted`），所以連不到 4000。

**實測**（11-08，codex-cli 0.167.0，Linux bwrap 沙箱；`codex sandbox` 直接跑探針＋`codex exec -m gpt-5.6-terra` 真跑一次，都在 scratchpad、沒動使用者 config）。探針看五件事：curl 打 4000、curl 打外網、Python `http.client` 直連 4000（aos 的 `lib/base/llm_http` 就是這樣連的）、Python `urllib` 打 4000、能不能寫家目錄：

| 做法 | curl→4000 | 外網 | `http.client`（llm_http） | `urllib` | 寫家目錄 |
|---|---|---|---|---|---|
| 現況（不帶 `-s`＝全權限） | 通 | 通 | 通 | 通 | **可以** |
| 只帶 `-s workspace-write` | 不通 | 不通 | 不通 | 不通 | 不行 |
| **A**：`-s workspace-write -c sandbox_workspace_write.network_access=true` | 通 | 通 | 通 | 通 | 不行 |
| A'：同 A，改用權限 profile（`-c permissions.<名>.extends=":workspace"`、`network.enabled=true`、`default_permissions`） | 通 | 通 | 通 | 通 | 不行 |
| **B**：A' 再加 `network.mode="limited"`、只放行 `127.0.0.1`／`localhost`、`features.network_proxy.enabled=true` | 通 | **擋** | **不通** | 通 | 不行 |

- **A 放行了什麼**：寫只限 `-C` 指的工作目錄、`/tmp`、`$TMPDIR`（加 `--add-dir` 可多給），其餘全唯讀；網路整個打開（外網、本機每個 port 都連得到）。比現況少了「能改家目錄和 repo 外的檔」，網路跟現況一樣。
- **B 放行了什麼**：檔案同 A；網路只能走 codex 起的代理，代理只放行本機名字，外網被擋。但沙箱裡是另一個網路空間，**不看代理環境變數、直接開 socket 的程式連不到**——aos 自己的 `llm_http` 就是這種，所以 B 下 aos 問腦會失敗；curl、`urllib`、npm 這類照代理變數走的才通。另外撞到被擋的網域時，codex 把那整條指令當失敗回報給模型。這功能文件標「實驗性」。
- **B 的副作用**：`allow_local_binding=true` 反而讓 curl 也連不到本機（推測是改成繞過代理直連、在隔離的網路空間裡撲空），不要開。代理的放行以主機名為單位，**放 `127.0.0.1` 等於整台本機的每個 port 都放**（LM Studio、進度看板也連得到），擋不了「不碰 LM Studio」，那條仍只能靠任務書交代。
- **共同的風險**：A、B 都沒驗過「在沙箱裡建 impls」——vcpkg 在 `~/dev/vcpkg`、快取在 `~/.cache/vcpkg`，缺套件要下載編譯時可能因寫不進去而失敗；碰到就加 `--add-dir`，或照舊由隊長在沙箱外建。隊員本來就不 commit，`.git` 唯讀不影響。

**推薦 A**：今天就能用、不必改使用者 config、不必改程式，從「全開」降到「只能寫工作目錄」，連 LiteLLM 的路一條都沒斷。要連網路也圍起來（B）得先讓 `llm_http` 認代理環境變數（改一個 aos 基礎函數），而且是實驗性功能，等需要再說。

## 待使用者裁

看板 `codex-sandbox` 線的 ask（11-08）：A＝派工指令改帶 `-s workspace-write -c sandbox_workspace_write.network_access=true`（推薦）；B＝連網路也只放行本機，先改 `llm_http` 認代理；C＝照現況不帶 `-s`。裁完才改 aos-teams/02。

## 派工指令改寫草稿（選 A 時）

改 [aos-teams/02「codex 呼叫與沙箱」](../../../../../wf/workflows/dispatch/aos-teams/02-指令沙箱與試玩.md#codex-呼叫與沙箱)的「家機」那段，改成：

> 要寫檔用 `-s workspace-write`。**家機**：要連 LiteLLM（localhost:4000）時再加 `-c sandbox_workspace_write.network_access=true`——沙箱照開（只能寫 `-C` 的目錄與 `/tmp`），網路打開（11-08 實測，[codex-sandbox](../../../../../proto8/thinking/2026-11/08/codex-sandbox/README.md)）。不要再靠不帶 `-s` 吃使用者 config 的 `danger-full-access`。要在沙箱裡建 impls 碰到 vcpkg 寫不進去，加 `--add-dir ~/dev/vcpkg --add-dir ~/.cache/vcpkg`。

寫碼那行範例改成：

```
codex exec -m gpt-6.1-sol -s workspace-write -c sandbox_workspace_write.network_access=true -C <worktree> -o <out.md> '/goal <完成條件>' < task.md
```

審查的 `-s read-only` 不動（它不寫檔；真要連 LiteLLM 再另議）。
