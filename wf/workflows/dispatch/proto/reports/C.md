# 隊 C 回報：刪舊三個小專案、`.aos/every/` 進 loop、一個資料夾一隻 agent

← [交接書 proto-C-consolidate](../done/proto-C-consolidate.md)｜[PROTOCOL](../PROTOCOL.md)｜[dispatch](../../README.md)

**終局 STATUS：`DONE`**（6 條驗收全部有證據，`ctest` 6/6 全綠，含真的打 LM Studio 的那一條）

## 做了什麼

三條線，三個 commit。

| # | 線 | 內容 |
|---|---|---|
| ① | 刪除 | `core/inst`／`core/llms`／`core/tooljson` 整個刪掉，`core/` 只剩五個 |
| ② | every | loop 多一個常駐投遞匣 `.aos/every/`；`<folder>` 參數變成可選 |
| ③ | agent | agent 改用 every 活著、一個資料夾一隻、cwd 即世界、四條頂層子命令 |

### 核心形狀的改變，一句話

**agent 不再自我投遞。** 它現在只是 `.aos/every/agent-<name>.json` 這一個檔——loop 每回合把它複製成
`agent-<name>-<turn>`，`step` 自己什麼都不投。原本最脆的那一段（`step` 丟例外時要在 catch 區塊裡「補投」
下一個自己，補不成就靜默死亡）整段消失了：現在 agent 死不掉，除非有人刪掉 every 裡那個檔。

**cwd 就是世界。** `aos::loop::find_folder()` 從 cwd 往上找最近含 `.aos/` 的目錄，
`current_folder()` 再疊上 `AOS_FOLDER` 優先。所以人待在 `bob/` 裡打 `aos say ...` 就會說給 bob 聽，
不必打路徑、不必打名字——因為一個資料夾只准住一隻。

## 6 條驗收的證據

### 1. 全新 configure＋build＋ctest 全綠，`ls core` 只剩五個

`rm -rf build && cmake --preset default && cmake --build --preset default && ctest --preset default`：

```text
100% tests passed out of 6
  aos_exec_tests / aos_wire_tests / aos_loop_tests / aos_llm_tests
  aos_agent_tests / aos_agent_fake_loop
```

（10 → 6 是因為 `aos_inst_tests`／`aos_inst_capi_tests`／`aos_tooljson_tests`／`aos_llms_tests` 隨小專案一起刪掉。
`aos_loop_tests` 新增了 every 三案與 `find_folder` 兩案。）

```text
$ ls core
agent  CMakeLists.txt  exec  llm  loop  README.md  wire
```

### 2. `aos --help` 沒有 `exec`／`init`，八條都在

```text
  run          推進一個資料夾 N 回合
  deliver      把一條指令原子投遞進 inbox
  llm          呼叫 OpenAI 相容端點並回傳文字
  agent        建立並推進回合制資料夾 agent
  say          對這個資料夾的 agent 說一句話
  listen       跟讀這個資料夾 agent 的對話記錄
  talk         跟這個資料夾的 agent 逐行對話
  state        印出這個資料夾 agent 的 status.json
```

### 3. 空資料夾 `W` 裡 `aos agent init` 不帶參數

```text
$ cd $W && aos agent init
$ cat .aos/every/agent-W.json
{ "argv": [ "aos", "agent", "step" ] }
$ ls -A .aos/inbox        # 0 個檔
$ ls .aos/agents
W                         # 名字＝資料夾名
```

### 4. `aos run --step 3`：每回合一條來自 every 的 step，inbox 始終沒有 step 檔

```text
turn 1: 1 insts, 3 ms      batch/1/insts: agent-W-1.json
turn 2: 1 insts, 3 ms      batch/2/insts: agent-W-2.json
turn 3: 1 insts, 3 ms      batch/3/insts: agent-W-3.json
inbox 檔數=0
state.json.agents = {'W': {'detail':'等待訊息','status':'idle','turn':3,'updated_at':'2026-08-30T08:56:46Z'}}
```

### 5. `aos say` → `aos run --step 1` → `aos listen`（真的打 LM Studio）

```text
$ aos say "你叫什麼名字"
$ aos run --step 1
turn 4: 1 insts, 1315 ms
$ aos listen --once
## turn 4 user
你叫什麼名字

## turn 4 assistant
W

$ aos state
{ "detail": "等待訊息", "status": "idle", "turn": 4, "updated_at": "2026-08-30T08:56:57Z" }
```

端點 `http://localhost:1234/v1`、模型 `qwen/qwen3.5-9b`（JIT）。**全程沒有 load／unload。**
（模型回答自己叫 `W`——因為 agent 名預設＝資料夾名，persona 裡就是這麼寫的。）

### 6. `W/sub/` 往上找得到；重複 init 報錯

```text
$ cd $W/sub && aos state
{ "detail": "等待訊息", "status": "idle", "turn": 3, ... }

$ cd $W && aos agent init
aos agent: /tmp/tmp.XcMrm5lGsn/W 已經住著 agent W；一個資料夾只住一隻
退出碼=1
```

## commit

| hash | 內容 |
|---|---|
| `0c798f1` | `core: 刪掉舊世代的 inst／llms／tooljson——core 只剩 exec wire loop llm agent 五個`（130 檔，-13548 行）|
| `e04bf5a` | `loop: 常駐投遞匣 .aos/every/ 與可選的 <folder>——世界不必再靠自我投遞活著` |
| `7aca466` | `agent: 一個資料夾一隻 agent——靠 .aos/every/ 活著，cwd 就是世界` |

`git add` 全程只加明確路徑；使用者未提交的 `wf/` 改動（40+ 個檔）原封不動。**未 push。**

## 團隊

| 誰 | 做了什麼 |
|---|---|
| codex gpt-5.6-sol ×3 條線 | ①刪除與登記、②`core/loop` 的 every＋folder 解析、③`core/agent` 的 every＋頂層指令 |
| 隊長（我） | 三份子任務書、審 diff、兩處文字修正、全新 clean build、6 條驗收親自重跑、三個 commit |

**三條線是循序跑的，不是並行。** 理由見下面裁決 1。

## 隊長裁決

1. **三條線循序跑，不並行。** 交接書建議三條並行，但它們共用同一個 working tree 與同一個
   `build/`：①在 ②build 到一半時把 `core/inst` 刪掉，②的建置就會以看不懂的方式爆掉，
   而且兩個 codex 同時 `make` 同一個 build dir 本身就會互相踩。三條各自 5–10 分鐘，不值得為此開三個 build dir。
2. **`find_folder`／`current_folder` 放 `core/loop` 的公開 API，`core/agent` 私有相依 `aos::loop`。**
   `.aos/` 版面的知識歸 loop，複製一份到 agent 會變成兩份會漂移的真相。代價是多一條
   `agent → loop` 的私有相依邊（不外流到匯出介面）。
3. **`aos deliver` 的 folder 靠「第一個參數是不是一個存在的目錄」判斷。**
   `aos deliver <folder> <inst.json>` 與 `aos deliver <inst.json>` 天生分不開，這是最小原型下最好懂的一條線。
   `aos run` 則是看「第一個參數是不是以 `--` 開頭」。
4. **舊形式 `aos agent say|listen|talk|state <folder> <name>` 全部保留，不改成可選。**
   `aos agent say <folder> <name> <text...>` 如果讓前兩個變可選就徹底無法分辨了。
   要省參數就用新的頂層 `aos say`——它一個位置參數都不吃。`aos agent init`／`step` 沒有這個歧義，所以照交接書改成可選。
5. **`every/` 檔案自帶的 `id` 一律被覆蓋成 `<stem>-<turn>`。** 不覆蓋的話每回合都是同一個 id，
   `batch/<turn>/out/` 會撞名，工具往返讀回結果那條路就斷了。
6. **`aos deliver --every` 沒做**（交接書說可選）。要放常駐指令就自己寫檔進 `.aos/every/`。
7. **`fake_loop.py` 留著，不換成 `aos run`。** 它讓 `core/agent` 的測試完全不依賴 `aos` 在 PATH 上。
   跟著加了 every 支援。
8. **`code-map/inst.md`／`tooljson.md`／`llms.md` 三冊不刪，只在路由表註明「已刪 2026-08-30，本冊為歷史存檔」。**
   `wf/salvage/`、`wf/workflows/digest/`、`wf/workflows/hackathon/` 有連結指著它們，刪掉會製造一批 BROKEN，
   而交接書明說歷史文件不重寫。
9. **`docs/` 只改 `README.md` 與 `subprojects.md` 兩個檔，參考範本從 `core/inst/` 換成 `core/llm/`。** 其餘照交接書不重寫。

## 已知不管（留給使用者裁）

- **22 條指向 `core/inst/docs/` 的死連結**——`wf/` 裡 5 條（`wf/workflows/use-aos.md` ×3、
  `wf/workflows/ideas/call-format/format-gaps.md` ×2）、`docs/` 裡 17 條
  （`usage.md` ×6、`aos-folder.md` ×4、`inst-directives.md` ×4、`overview.md`、`roadmap/decisions.md`、`roadmap/situation.md`）。
  **這兩批檔案都在交接書的禁區裡，我刻意沒動。** `wf/` 那 5 條會讓 `wf-lint` 報 BROKEN。
  `docs/usage.md`／`aos-folder.md`／`overview.md` 講的是 `aos init`／`aos exec` 那一代的東西，
  整份已經過時，該重寫還是該刪，是使用者的事。
- **沒有鎖**：兩個 `aos run` 推同一個資料夾仍會互搶。
- **兩隻 agent 的世界目前無法用頂層指令操作**（`resolve_name` 會報「不只一隻」）。
  一個資料夾一隻是使用者裁決的形狀，所以這不是缺陷；真要多隻就用舊形式 `aos agent say <folder> <name>`。
- **`every/` 裡的壞檔**每回合都會在 stderr 印一次、每回合都留一份現場證據在 `insts/`。沒做去重。
