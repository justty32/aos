aos-exec 讀 .env 的規則，範本自帶的 .env 可以帶什麼、不該帶什麼，以及使用者最後還得自己 export 哪幾個。

← [入口](README.md)｜上一份 [02 實測](02-實測.md)｜下一份 [04 刪 copy-out 前要解決的](04-刪copy-out前要解決的.md)

# .env 這條路（使用者 11-10：「.env可以帶一些東西」）

**一句話**：範本 `.env` 帶 `AOS_CLOCK`、`AOS_LLM_KERNEL` 的預設，再加一行 `AOS_HOME` 必填檢查，使用者就只剩 `AOS_HOME` 要自己給，在殼裡 export 或寫進自己專案的 `.env` 都行。用真模型的話，金鑰另外 export。

## aos-exec 怎麼讀（程式：`impls/aos-exec/src/env/dotenv.cpp`、`find/find.cpp`）

- **何時讀**：aos-exec 每「走進」一個資料夾就讀那裡的 `.env`。走進去的情形有三種：定義資料夾本身、`$AOS_ENTRY` 沿路經過的子夾、入口是檔時檔所在的資料夾。讀的時間點在 `AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO` 都設好、也已經 cd 進去之後。入口檔如果是指到別處的 symlink，那邊的 `.env` 不讀。
- **格式**：一行一個 `[export ]名字=值`；`#` 開頭是註解；引號只剝一對；**只展開 `${名字}`**，而且名字沒設就報錯 `DotenvBad … line N (variable referenced by ${...} is not set)`（只印檔名和行號、不印值）。**沒有 `${X:-預設}`**。
- **相對路徑不會被解**：值照字面放進環境。`AOS_HOME=../..` 會變成字串 `../..`，之後每支程式從自己的 cwd 去解，結果各不相同。要錨定就寫 `${AOS_CD}`（這份 `.env` 所在的資料夾）、`${AOS_WS}`（起的人站的地方，或 `--ws`）、`${AOS_STACK}`、`${HOME}`。
- **預設不蓋**：開始讀這份 `.env` 時環境裡已經有的名字，那一行會跳過（格式照驗）。**殼裡 export 的贏**；`aos-exec --dotenv-override` 反過來。所以 `.env` 裡寫的就是預設值，殼裡 export 會蓋過它。反面是殼裡殘留的舊值會默默贏，而且沒有提醒（cli-sweep 03 E4，這就是「起之前先 unset」的由來）。
- **會傳給子項**：`.env` 設的值直接 `setenv` 進 aos-exec 這個行程，之後它起的東西全部繼承。根 `defs/.env` 設的值，每隻 agent、每個工具都看得到（r5）。daemon 起 agent 時又會走進 agent 資料夾，再讀一次 agent 自己的 `.env`（r6）。
- 另有一條：沒有 argv 的 JSON 入口可以帶 `.env` key（值能放指示詞），範本現在沒用到。

## 範本 `.env` 可以帶什麼

| 變數 | 寫法 | 相對於誰 | 放哪份範本 | 備註 |
|---|---|---|---|---|
| `AOS_CLOCK` | `AOS_CLOCK=${AOS_STACK}/clock` | 根的 stack | daemon-root（**現在就有**） | 子 daemon 會繼承 |
| `AOS_LLM_KERNEL` | `AOS_LLM_KERNEL=${AOS_WS}/../llms/stacks/llm` | 起根時站的地方（`AOS_WS`） | daemon-root | 照 two-machines 一頁說明的擺法（專案旁邊放 llms、`--stack stacks/llm`）。擺法不同就在殼裡 export，會蓋過去。注意：起根時不站在專案裡，就會算錯（cli-sweep 03 E3） |
| `AOS_HOME` 必填檢查 | `AOS_HOME=${AOS_HOME}` | — | daemon-root、kernel/llm-kernel（這兩份是會被 `aos-exec` 直接起的根） | 沒設就在起根當下報 `.env line N`（r8）。上面加一行註解 `# AOS_HOME=${HOME}/repo/aos-tools/proto8   (uncomment to set it here)`，讓人知道也可以寫在這裡 |
| 想寫在 `.env` 的 `AOS_HOME`（使用者自己寫，不是範本出廠就有） | `AOS_HOME=${HOME}/repo/aos-tools/proto8`，或 `${AOS_WS}/../aos/proto8` | `HOME`，或專案所在的位置 | 使用者專案的 `defs/.env` | 兩台都把 repo 放在 `~/repo/aos-tools` 的話，`${HOME}` 這種寫法**進 git 也沒關係**。「大修改版直接換」＝改這一行或在殼裡 export |

agent 範本（agent-fsm、eca-claude、reviewer）**不用帶 `.env`**：它們會從根繼承。真要讓某隻 agent 用不同的 `AOS_HOME`（例：一隻試新版 proto8），寫在那隻自己的 `.env` 就會生效（r6）。不過「殼裡的贏」這條規則照樣成立：只要殼裡 export 了，那隻的 `.env` 就失效；要它生效就得用 `--dotenv-override` 或不在殼裡 export。

## 不該放的

- **金鑰**（`LITELLM_KEY` 等）：範本和專案都會進 git，history、ws 也會進 git，而且沒有掃描在擋（two-machines 11「金鑰只放 llms 專案」）。只放在殼裡，或放在不進 git 的檔（`aos-tools add --env-file` 那種、自己 gitignore）。
- **機器專屬的絕對路徑**（`/home/guanyu/...`）：換一台就錯。而且 `.env` 輸給殼裡的 export，所以「這台對、那台錯」時很難察覺。要寫就寫 `${HOME}/…` 或 `${AOS_WS}/…`。
- **`AOS_HOME=${AOS_CD}/../..` 這種只在 repo 原位才對的預設**：抄出去以後默默變成錯的地方，錯誤訊息是 `PathMissing …/proj/lib/agent/agents`，完全沒提 AOS_HOME（r7）。在原地跑的測試和 demo，應該自己設 `AOS_HOME`，不要靠範本的 `.env`。
- `AOS_WS`、`AOS_STACK`、`AOS_DAEMON`：這些是 aos-exec 和旗標在管的。寫進 `.env` 會碰到已知的設計-45（改了 `AOS_WS`，stack 不會跟著變）。

## 使用者最後非自己 export 不可的

| 情況 | 要 export 的 | 個數 |
|---|---|---|
| 假腦、照一頁說明的擺法、範本 `.env` 照上表帶 | `AOS_HOME` | **1** |
| 同上，但把 `AOS_HOME` 寫進自己專案 `defs/.env` 和 `llms/def/.env` | — | **0**（r5） |
| llms 不放在專案旁邊 | 再加 `AOS_LLM_KERNEL` | +1 |
| 用真模型（llms 那邊） | 再加 `LITELLM_KEY`（金鑰） | +1 |
| 在殼裡自己打 `aos-tools call／ls`、`aos-agent tools ls` | 那個殼要有 `AOS_HOME` | （同一個） |

`unset AOS_CLOCK AOS_DAEMON AOS_STACK`（清掉殘留的舊值）照舊建議做，不算 export。

**換台時**：殼裡 export 的那台照自己的值；`.env` 寫 `${HOME}/…` 的，兩台都把 repo 放在家目錄底下同一個位置就通；寫成絕對路徑的，另一台不 export 就錯，錯誤是 `PathMissing`（指到不存在的 lib），不是「沒設」。
