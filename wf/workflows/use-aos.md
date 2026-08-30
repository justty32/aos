# use-aos — 幫使用者用 aos（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

**使用者說**「幫我用 aos 做 X」「把 aos 接進我這個專案」「aos 這個指令怎麼下」
→ 走這條。

完整說明在 [`docs/usage.md`](../../docs/usage.md)（給人讀的）。
**本檔是給你（agent）的執行順序**，重點在「先分辨要走哪一條路」與「哪些地方會踩坑」。

---

## Step 0：先分辨是哪一種需求

| 使用者其實想要 | 走哪一節 |
|---|---|
| 跑一批指令、批次執行某些工作 | [A. 當命令列工具用](#a-當命令列工具用) |
| 在他自己的 C++ 專案裡呼叫 aos 的功能 | [B. 接進別的專案](#b-接進別的專案) |
| 在 aos 裡面新增功能 | 不是這條 → [add-subproject](add-subproject.md) 或 [feature-dev](feature-dev/README.md) |

分不出來就問。這兩條路的產出完全不同。

---

## A. 當命令列工具用

### 先確認 aos 在不在

```bash
aos --help          # 裝好了的話會列出所有子命令
./build/bin/aos --help   # 或是 repo 裡剛建好的
```

沒有的話先照 [testing 工作流](testing.md) 建起來，或 `cmake --install build --prefix ~/.local`。

### `aos run`／`aos deliver` — 投遞指令並推進世界

```bash
mkdir -p world
aos deliver world -- echo hi
aos run world
```

`aos deliver [folder] <inst.json>` 讀一份指令 JSON；`aos deliver [folder] -- <argv...>`
直接從 argv 做成一條指令。兩者都會原子投遞到 `.aos/inbox/`，等 `aos run` 後續執行。
`aos run [folder] --step N --interval MS` 推進 N 回合；`--step 0` 持續執行，預設每
100 毫秒推進一回合。

`folder` 省略時依序使用 `AOS_FOLDER`、從 cwd 往上找到的最近一個 `.aos/` 世界、目前
目錄。`.aos/` 不存在時會由 `run` 或 `deliver` 建立，不再有獨立的 init 指令。完整用法見
[`docs/usage.md`](../../docs/usage.md)。

### `aos llm` — 直接呼叫 OpenAI 相容端點

```bash
echo '只回一個字：好' | aos llm
aos llm --messages messages.json
```

prompt 從 stdin 進、回覆從 stdout 出。端點、模型與選填 token 分別由 `AOS_LLM_URL`、
`AOS_LLM_MODEL`、`AOS_LLM_KEY` 設定；預設連本機 LM Studio 相容端點。

### `aos agent` 與頂層對話指令 — 建立並操作 agent

```bash
mkdir bob && cd bob
aos agent init
# 另一個視窗也進入 bob：
aos run --step 0
# 回到第一個視窗：
aos say "你叫什麼名字"
aos listen
```

`aos agent init` 建立世界裡唯一的 agent；`aos agent step` 通常交給 loop 呼叫。
頂層 `aos say`／`aos listen`／`aos talk`／`aos state` 會自動解析目前世界與唯一的 agent。
需要在世界外操作或明確指定名字時，才用
`aos agent say|listen|talk|state <folder> <name>`。

### 要跟使用者講清楚的點

1. `.aos/` 全部是本機執行狀態，整個資料夾都不進 git。
2. `aos run` 沒有鎖；兩個行程同時推進同一個 folder 會互搶 inbox、互蓋 `state.json`。
3. `.aos/inbox/` 是一次性投遞；`.aos/every/` 的檔案每回合都會被複製執行。agent 靠
   `agent init` 放進 `every/` 的常駐 `step` 指令活著，不是每回合自我投遞。
4. 一個 folder 只能住一隻 agent；需要多隻時用不同 folder。

---

## B. 接進別的專案

### 前提：aos 要先裝出去

```bash
cd <aos repo>
cmake --preset default && cmake --build --preset default
cmake --install build --prefix ~/.local        # 或使用者指定的 prefix
```

### CMake 那側

```cmake
find_package(aos CONFIG REQUIRED)
target_link_libraries(myapp PRIVATE aos::loop)
```

prefix 不在預設路徑的話，configure 時給 `-DCMAKE_PREFIX_PATH=<prefix>`。

挑 target：

| target | 什麼時候用 |
|--------|-----------|
| [`aos::exec`](../../core/exec/README.md) | POSIX 批次執行器 |
| [`aos::wire`](../../core/wire/README.md) | 指令、結果與 state 的 JSON 轉換 |
| [`aos::loop`](../../core/loop/README.md) | folder 回合機與投遞功能 |
| [`aos::llm`](../../core/llm/README.md) | OpenAI 相容 client |
| [`aos::agent`](../../core/agent/README.md) | 回合制 LLM agent |
| `aos::core` | 要 aos 的基本功能（`core/` 全部），不要擴充 |
| `aos::modules` | 只要擴充（`modules/` 全部）。沒有擴充存在時這個 target 不會被匯出 |
| `aos::aos` | 全部小專案，懶得挑 |
| `aos::merged` | 想單檔部署。aos 那邊要以 `-DAOS_BUILD_MERGED_LIB=ON` 建 |

通常優先挑一個實際需要的單一小專案，不要無條件連整把傘狀 target。target 的組成見
[`docs/subprojects.md`](../../docs/subprojects.md)，安裝細節見 [`docs/build.md`](../../docs/build.md)。

如果使用者要的功能來自 `modules/` 底下的擴充小專案，確認 aos 建置時**沒有**帶
`-DAOS_BUILD_MODULES=OFF`——關掉的話那顆函式庫根本不會產出，`find_package` 會說
找不到 target。

### 程式碼那側

```cpp
#include <aos/loop.hpp>
```

公開標頭按小專案命名：`<aos/exec.hpp>`、`<aos/wire.hpp>`、`<aos/loop.hpp>`、
`<aos/llm.hpp>`、`<aos/agent.hpp>`。只 include 與 link 實際使用的那一個。

### 不透過 CMake

```bash
c++ -std=c++23 x.cpp -I<prefix>/include -L<prefix>/lib -laos_loop
```

### 驗證（不要只是寫完就交）

寫完之後真的建起來跑一次。使用者的環境**不會有 vcpkg**，所以測的時候要
`env -u VCPKG_ROOT`，否則 configure 期的相依問題會被 vcpkg 蓋掉、到使用者手上才爆。

---

## 回報時要包含什麼

- 實際跑過的指令與輸出，不要只說「應該可以」。
- 走 A 的話：如果使用者需要知道子指令的結果，說明你查看了哪一份
  `.aos/batch/<turn>/out/<id>.json`，以及其中的 `exit`／`signal`／`stdout`／`stderr`。
- 走 B 的話：說清楚你連了哪個 target、為什麼，以及有沒有在無 vcpkg 的環境驗過。
- 需要使用者自己驗（實機、外部服務、權限）的記到 [WAIT_USER](../WAIT_USER.md)。
