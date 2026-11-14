<!-- 草稿 v1，只給本機看。宣傳句標 copy:ID（出處：release-1114 文案表 zh 欄）。docs/ 還不存在，連結是預定位置。 -->
# 資料夾，就是函數。 <!-- copy:H1 -->

[license: TBD] [status: prototype] [docs](docs/zh/get-started.md)  ·  [English](README.draft.md) | 繁體中文

aos 把 AI agent 當成一般的 Linux 行程，住在資料夾裡。每個工具、每隻 agent、每封信，都是你可以 ls、可以讀、可以設權限的資料夾或檔案。 <!-- copy:P1 -->

## Quickstart（快速開始）

不用任何模型，先試試。 <!-- copy:TRY --> 需求：Linux（WSL2 可以）、git、bash、Python 3.11 以上、CMake 3.21 以上、支援 C++20 的編譯器、nlohmann-json（用 vcpkg 或系統套件；vcpkg 這條是實測過的）。

```sh
git clone <REPO_URL> ~/aos            # 很大：就算加 --depth 1 也約 150 MB（多半是 archive/）
cd ~/aos/proto8/impls && cmake -B build && cmake --build build -j
export AOS_HOME=~/aos/proto8
export PATH=$(ls -d "$AOS_HOME"/impls/*/bin "$AOS_HOME"/cmd/*/bin | tr '\n' ':')$PATH
export PYTHONPATH=$AOS_HOME/py:$AOS_HOME/lib

mkdir -p ~/aos-demo/llms ~/aos-demo/tree
cd ~/aos-demo/llms
cp -r "$AOS_HOME/kernel/llm-kernel" def
nohup aos-exec --stack stacks/llm def > llm.log 2>&1 &
cd ~/aos-demo/tree
cp -r "$AOS_HOME/templates/daemon-root" defs
cp -r "$AOS_HOME/templates/agent-fsm" defs/ann
nohup aos-exec --stack stacks/root defs > root.log 2>&1 &
sleep 2

aos-agent -d stacks/root ctl add -w . defs/ann
aos-agent -d stacks/root -t ann say "hello, who are you?"
timeout 60 aos-agent -d stacks/root -t ann listen
tail -n 3 stacks/root/procs/ann/history.jsonl | cut -c1-200

aos-daemon-ctl -d ~/aos-demo/tree/stacks/root shutdown
aos-daemon-ctl -d ~/aos-demo/llms/stacks/llm shutdown
```

預期結果：`listen` 印出假腦的回答，`history.jsonl` 最後一行是同一句：

```
FAKE ANSWER to: hello, who are you? (tool said: 2026-11-14T04:06:55Z)
{"role": "assistant", "content": "FAKE ANSWER to: hello, who are you? (tool said: 2026-11-14T04:06:55Z)"}
```

（時間會不同。假腦會先叫一次工具 `peek_now_time`，再回答。）aos 除了 `~/aos` 和 `~/aos-demo`，不寫你家目錄的任何地方（建置時 vcpkg 會在 `~/.cache/vcpkg` 放下載快取）。卡住了請看[疑難排解](docs/zh/manual/troubleshooting.md)。

<details><summary>clone 很大？老實說大在哪</summary>

完整 clone 很大：`git clone --depth 1` 實測仍約 150 MB，大部分是 `archive/`（舊原型）。產品各夾本身很小（約 6 MB，批 0 實測）。更小的 sparse clone 寫法還沒量過，所以這裡不給。
</details>

## What you just ran（剛才跑了什麼）

- `llms/` 是腦的 kernel：每個「問模型」的請求都從這扇門過。
- `tree/` 是你的樹：一個根 daemon 加底下的 agent。
- `stacks/root/procs/ann/` 是 agent 的家：它的狀態、佇列、階段。
- `history.jsonl` 是對話，就是一個普通檔案。

## Next steps（下一步）

1. [安裝](docs/zh/install/index.md)：完整建置說明（vcpkg 或系統套件、`install.sh`）。
2. [Get started](docs/zh/get-started.md)：同樣的步驟，加上解說。
3. [教學 01](docs/zh/tutorials/01-first-tree.md)：資料夾當函數。

接真腦、把你自己的 Claude Code 當 agent：下一批才有（coming in the next batch）。

## Why folders（為什麼是資料夾）

- 資料夾＝函數。資料夾裡放一個 _entry 就能被呼叫，說明和資料就放在旁邊。 <!-- copy:C1 -->
- 模型本來就懂。模型天生會讀寫檔案與資料夾，不用另學一套框架。 <!-- copy:C2 -->
- 站在 Linux 上。權限就是檔案權限；工具用什麼語言寫都行。 <!-- copy:C3 -->
- 小零件，unix 風格。幾支各做一件事的小程式：exec、loop、daemon。 <!-- copy:C4 -->
- 腦和身都自己帶。先用假腦試、接任何 OpenAI 相容端點，或把你的 Claude Code 掛進樹裡當一隻 agent。 <!-- copy:C5 -->

## How small（多小）

- `proto8/impls/` 底下 12 個 C++ 專案（aos-daemon、aos-exec、aos-loop、aos-fsm、aos-llm……）。 <!-- count: `ls -d proto8/impls/aos-*/ | wc -l` = 12，與 aos-*/CMakeLists.txt 數量相同 -->
- Python 的部分只 import 標準庫和 aos 自己的模組。 <!-- count: 對 proto8/py、lib、cmd 全部 import/from 行做 grep，沒看到第三方套件名；只是 grep，不是依賴稽核 -->

## Status（現況）

aos 還是原型：檔案格式和指令還會變。只支援 Linux（WSL2 可以）。一棵樹住一台機器；樹和樹之間現在還不會互相連線。 <!-- copy:S1 -->

## Repository layout（資料夾佈局）

| 資料夾 | 是什麼 |
|---|---|
| `proto8/` | 產品：程式、範本、知識庫、概念條文 |
| `docs/` | 文件站（規劃中） |
| `wf/`、`archive/`、`impl_cpp/`，以及 `proto8/` 底下的 `thinking/`、`user-advice/`、`notes/` | 開發歷程與工作筆記，不是產品的一部分（development history and working notes, not part of the product） |

根目錄的 `AGENTS.md`、`CLAUDE.md` 是給 agent 的入口。

## Security（安全）

agent 會用你的帳號執行程式。請在拋棄式帳號、容器，或丟了也不心疼的資料夾裡試。沙箱是實驗功能。 <!-- copy:SEC -->

## License（授權）

待定（TBD）。
