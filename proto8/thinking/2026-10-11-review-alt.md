← [thinking](README.md)｜Fable 獨立設計（未看 PLAN），2026-10-11

# proto8 最小可跑的形狀——只照 restart.md §2 與九月草稿

依據：[restart §2](2026-10-11-restart.md)（最高）、`thinking/2026-09-19.md`（檔案系統當 list、eval 短促、大操作丟別的資料夾）、`09-23`（systemd 起 daemon、`init`／`register`／`say`、沒輸入就每 tick 沒事）、`09-24`（tick＝取下個時間點的狀態；變換＝POSIX 呼叫；空間＝資料夾）。沒看 PLAN.md、a-day.md、review-*.md、proto7-2 程式。

## 1. 一句話

**aos proto8 是一支 `aos tick`：每跳一下，替世界資料夾裡每個「資源」掃一遍排隊的任務，叫排序器挑出前幾個、以 POSIX 行程跑起來、把結果落回任務自己的資料夾——任務、資源、排序器、agent 全是帶一個 JSON 的資料夾，核心不知道「agent」是什麼。**

## 2. 磁碟上長什麼樣

### 2.1 一個世界資料夾

```
world/
├── tick.json                     ← 現在第幾 tick；要不要停
├── stop                          ← （有這個檔＝請停；aos stop 寫的）
├── tasks/                        ← 計算任務，一個資料夾一個，編號就是 id
│   ├── 0001-hello/
│   │   ├── task.json             ← 誰提交的就誰寫；核心只讀不改
│   │   ├── run.json              ← 核心寫：第幾 tick 起跑、佔哪個資源
│   │   └── out/                  ← stdout、stderr、exit（有 exit＝做完）
│   ├── 0002-ask-human/
│   │   ├── task.json
│   │   ├── run.json
│   │   └── out/stdout …
│   └── 0003-scout-step0/         ← agent 的一步也只是一個任務
├── resources/                    ← 資源，一個資料夾一個
│   ├── cpu/resource.json         ← {"capacity": 4}
│   ├── human/resource.json       ← {"capacity": 1, "sorter": [...]}
│   └── brain-local/resource.json ← 一顆 LLM＝一個資源
├── sorters/                      ← 排序器：任何可執行檔，stdin JSON 進、stdout JSON 出
│   └── by-priority.py
└── agents/                       ← agent 的「家」；核心從不進來
    └── scout/
        ├── agent.json            ← 函式簽名：腦、人格、記憶、手腳
        ├── plan.json             ← S 表示式：節點是 run（寫死）或 llm（問模型）
        ├── cursor.json           ← 狀態機走到第幾個節點
        ├── system.md             ← 核心人格
        ├── memory.json           ← 近期記憶（messages 陣列）
        └── inbox/0001.json       ← 人說的話（aos-agent say 寫的）
```

任務的狀態**不存欄位、用檔案推**：沒 `run.json`＝排隊中；有 `run.json` 沒 `out/exit`＝正在跑；有 `out/exit`＝做完。`ls` 一眼看得出來，也沒有第二份真相要同步。

### 2.2 每種 JSON 一個樣本

`tick.json`（核心寫）
```json
{"tick": 17}
```

`tasks/0002-ask-human/task.json`（提交者寫；核心只認 `argv`、`needs` 兩個鍵）
```json
{
  "argv": ["sh", "-c", "until [ -f answer ]; do sleep 1; done; echo 人說: $(cat answer)"],
  "needs": "human",
  "tags": {
    "side_effect": false, "deterministic": false, "touches_files": true,
    "priority": 3, "style": "現代", "whoever": "人加的隨便什麼"
  }
}
```
`tags` 核心完全不看——九個軸和人加的特性都放這，給排序器看。

`tasks/0002-ask-human/run.json`（核心寫）
```json
{"resource": "human", "started_tick": 5, "pid": 48213}
```

`resources/human/resource.json`
```json
{"capacity": 1, "sorter": ["python3", "../../sorters/by-priority.py"], "note": "一次只能煩我一件事"}
```
沒寫 `sorter` 就照編號先來先跑。`resource.json` 整包會餵給排序器，所以畫家「擅長人物、不擅長風景」這類話可以隨便加鍵，核心不管、排序器自己讀。

排序器契約（stdin → stdout，兩個 JSON）
```json
// stdin
{"tick": 17, "resource": {"capacity": 1, "...": "..."},
 "waiting": [{"id": "0002-ask-human", "task": {"argv": ["..."], "needs": "human", "tags": {}}}],
 "running": ["0001-hello"]}
// stdout：排好的 id，核心取前「空位數」個
["0002-ask-human"]
```

`agents/scout/agent.json`（§2.17 的簽名，一比一）
```json
{"brain": "brain-local", "system": "system.md", "memory": "memory.json",
 "tools": {"ls": ["ls", "-la"], "say": ["sh", "-c", "echo \"$1\" >> said.txt", "_"]}}
```

`agents/scout/plan.json`（§2.16 的 S 表示式；這版先是一條直線、不嵌套）
```json
[
  {"run": ["aos-agent", "inbox-to-memory", "."]},
  {"llm": true},
  {"run": ["aos-agent", "act", "."]},
  {"run": ["aos-agent", "inbox-to-memory", "."], "needs": "cpu"}
]
```
`run` 節點＝寫死的程式（可預測）；`llm` 節點＝問腦（不可預測，排到 `agent.json.brain` 那個資源）。可預測性可以量：`grep -c '"run"' plan.json`。

`agents/scout/cursor.json`
```json
{"node": 1, "round": 3}
```

`agents/scout/inbox/0001.json`
```json
{"from": "user", "tick": 12, "content": "hello"}
```

## 3. 核心程式只做什麼

一支 `aos`，五個子命令：`init`（建上面的空資料夾＋`cpu` 資源）、`submit`（mkdir＋寫 task.json 的語法糖）、`tick`（跳一下）、`run`（每隔幾秒跳一下，看到 `stop` 檔就跳完這下退出）、`stop`（寫 `stop` 檔）。

```
tick(world):
    t = read(world/tick.json).tick + 1
    for res in world/resources/*:
        cap, sorter = read(res/resource.json)
        running = [任務 | 有 run.json 指到 res 且 out/exit 不存在]
        waiting = [任務 | 沒 run.json 且 task.json.needs == res.name]
        free = cap - len(running)
        if free <= 0 or not waiting: continue
        if sorter:  order = json(stdout of 行程(sorter, stdin={tick,resource,waiting,running}))
        else:       order = sorted(waiting ids)
        for id in order[:free]:
            spawn(id, res)
    write(world/tick.json, {"tick": t})

spawn(id, res):
    d = world/tasks/id ; mkdir d/out
    pid = Popen(["sh","-c",'"$@" >out/stdout 2>out/stderr; echo $? >out/exit', "_", *task.argv],
                cwd=d, start_new_session=True)        # 脫離 tick 行程，tick 結束它還活著
    write(d/run.json, {resource: res.name, started_tick: t, pid: pid})

run(world, interval):
    loop: tick(world); if exists(world/stop): remove(it); break; sleep(interval)
```

**核心讀的欄位只有 `task.json.argv`、`task.json.needs`、`resource.json.capacity`、`resource.json.sorter`；寫的檔只有 `tick.json`、`run.json`、`out/`。** 不知道 agent、不知道信、不知道重試、不知道逾時、不知道標籤。

估行數（Python 3 標準庫）：`tick`＋`spawn` 約 50 行、`run`／`stop`／`init`／`submit` 約 40 行、參數解析 15 行 → **核心 ≈ 110 行**。核心之外的「使用者態」程式：`aos-llm`（讀 request.json 打 OpenAI 相容端點、寫 response.json）≈ 40 行；`aos-agent`（`init`／`say`／`step`／`inbox-to-memory`／`act`）≈ 100 行；範例排序器 ≈ 10 行。**全部 ≈ 260 行**，比 proto2（116 行）多一倍多，但多出來的那層就是 §2.7 的三定義。

## 4. §2 每一條對到哪

| 條 | 對到 | 說明 |
|---|---|---|
| 2.1 為 LLM 方便用的新 OS | 整個佈局 | 沒有資料庫、沒有 socket、沒有 pid 表；全是資料夾和 JSON，`ls`／`cat` 就是 API |
| 2.2 agent 能力＝資源、分任務＝排程 | `resources/<名>/resource.json` 的 `capacity`；`task.json.needs`；`sorter` | 「一次三四件」＝capacity；「誰優先」＝排序器 |
| 2.3 畫家＝CPU | `resources/human/`（demo 用人當資源） | 「擅長人物」「要散心」這類話放 resource.json 任意鍵，排序器讀。**快取／靈感這版不管**：還沒有第二個觀察得到的現象需要它 |
| 2.4 有多任意 | `tags` 任意、排序器任何可執行檔、資源任何資料夾 | 這版不回答，用實驗答：每多一種排序器就多知道一點邊界 |
| 2.5 第 0 層 Linux | `Popen` | 行程、cwd、stdout 全交 Linux |
| 2.5 第 1 層 daemon | `aos run` 這個迴圈行程 | **許可權／身份／記憶體這版不管**：單機單人，Linux 已經在管；等有第二個使用者再長 |
| 2.5 第 2 層 時空 | 空間＝`world/`；時間＝`tick.json` | 任務的 cwd＝自己的資料夾＝它的世界 |
| 2.5 第 3 層 排程 | `resources/`＋`sorters/`＋tick 迴圈的 for | 這就是整個第 3 層 |
| 2.6 fs／POSIX／JSON | 全部 | 任務＝argv；狀態＝檔案存在與否；設定＝JSON |
| 2.7 計算任務＝POSIX 行程 | `task.json.argv` | 唯一的「程式」定義 |
| 2.7 資源＝有限處理能力 | `resource.json.capacity` | 一個整數，就這樣 |
| 2.7 排序＝誰先給誰 | 排序器契約（stdin waiting → stdout 順序） | 「給誰」已經由 `needs` 定了；排序器只管「誰先」。**跨資源的「這個畫家也能畫風景」這版不管**：第一版 needs 指定一個資源，要多資源候選再加 |
| 2.8 排序本身是計算任務 | 排序器是一個 POSIX 行程 | 但它是 tick **同步**叫起來的、不進隊列。差在它沒被排程——第一版先這樣，不然排序器要被排序，雞生蛋 |
| 2.8 資源也是行程 | **這版不管** | 用「capacity 整數＋tick 代它掃隊列」得到一樣的可觀察行為（一次只接 N 件）。真做成常駐行程就要 IPC，是第一個會長肥的地方 |
| 2.9 九軸＋人加的特性 | `task.json.tags` | 核心不讀；只有排序器讀；人想加什麼鍵就加 |
| 2.10 JSON、模型生成排序器 | `sorters/`；排序器＝任何 argv | 「生成排序程式的程式」＝一個任務：argv 叫 `aos-llm`、把輸出寫進 `sorters/x.py`。**這版不寫它**，但位子空著、不用改核心 |
| 2.11 tick-tock 停下來、打包 | `aos stop` → `stop` 檔 → `run` 跳完這下退出 → `zip -r world-t17.zip world/` | 正在跑的任務不殺；zip 裡 `run.json` 有、`out/exit` 沒有＝「這件事正在跑」 |
| 2.12 agent 看到的時空 | cwd＋`cat ../../tick.json`；某個 tick 的世界＝那個 zip | **每 tick 存一份這版不管**：要就 `aos stop` 一下打包 |
| 2.13 agent＝狀態機＝計算任務 | `cursor.json`＋`tasks/00xx-scout-stepN/` | 一步一個任務；步完自己提交下一步 |
| 2.14／2.15 可預測性有主體性 | **刻意不存** | `tags` 有 `deterministic`（任務的屬性），**沒有** `predictable`（那是觀察者的事）。要記就記成「某排序器對某任務的看法」，放排序器自己的檔 |
| 2.16 S 表示式拆節點 | `plan.json` 的 `run`／`llm` | 把 `llm` 節點換成 `run` 就是提高可預測性；數得出來。**嵌套這版不管**：先直線 |
| 2.17 簽名 | `agent.json` 的 `brain`／`system`／`memory`／`tools` | 四個鍵一比一 |
| 2.18 誰先用大腦 | `llm` 節點的任務 `needs` = `agent.json.brain`；`resources/brain-*/` 的 `capacity` 與 `sorter` | 很多 agent 搶腦＝很多任務排在 `brain-local` 隊列；排序器看 `tags`（例如 `user_waiting`） |
| 2.19 agent 便宜、叫的東西貴 | 閒置 agent＝**零個任務**；只有 `llm` 節點進 brain 隊列；工具節點可自己標 `needs` | 09-23「沒輸入就每 tick 沒事」照做：沒人 `say`，`tasks/` 不長任何東西 |
| 2.20 agent 內部 | **這版不管** | `aos-agent` 是核心外的 100 行；plan 直線、沒重試、失敗就停等人看 |

## 5. 五個具體問題

**兩個任務怎麼溝通。** 寫檔，沒有別的。甲任務要叫乙：在 `tasks/` 多開一個資料夾、寫 `task.json`（這就是「任務生任務」，agent 的下一步就是這樣來的）。甲要乙的結果：`cat ../0002-xxx/out/stdout`，看到 `out/exit` 才算有。要等乙做完再動：甲自己 `until [ -f ../0002/out/exit ]` 等（它佔著一個 cpu 格等，跟 §2.7 的 scanf 一樣——等待是在消耗資源，排序器看得見）。核心沒有 `after`／依賴欄位：第一版不加，等 demo 卡到才加。

**資源的「容量」誰管。** `resource.json.capacity` 寫數字；tick 每跳算 `capacity − 正在跑的數`，只放這麼多進去；任務退出（`out/exit` 出現）就自動還格。沒有 grant、沒有帳本、沒有 holder：**佔格這件事本身就是 `run.json` 存在且 `out/exit` 不存在**。要改容量就 `vim resource.json`，下一 tick 生效。

**排序器怎麼掛進來。** `resource.json.sorter` 寫一個 argv。tick 替這個資源拿 waiting 名單時，起這個行程、把 `{tick, resource, waiting, running}` 從 stdin 餵進去、讀 stdout 的 id 陣列、取前「空位數」個。排序器失敗或沒寫→照編號先來先跑。它是個普通 POSIX 行程：shell、Python、C、或模型剛寫出來的檔都可以；它看得到 `tags` 和 `resource.json` 整包，核心不解釋任何一個鍵。

**agent 的「S 表示式」在磁碟上是什麼。** `agents/<名>/plan.json`：一個陣列，每格一個節點，`{"run": argv}` 或 `{"llm": true}`。`cursor.json` 指現在第幾格。`aos-agent step .` 做一格：`run` 就跑那個 argv；`llm` 就拼 `system.md`＋`memory.json`＋`tools` 成 request，呼叫 `aos-llm`，回應接進 `memory.json`；然後 cursor+1，再往 `tasks/` 提交下一步（下一格是 `llm` 就 `needs: brain-local`，否則 `cpu`）。節點 argv 以 exit 10 表示「沒事了」→ 不提交下一步，鏈結束、agent 歸零成本；其他非 0 → 寫 `out/`、鏈停、等人看。`aos-agent say "hello"` 把信寫進 `inbox/`，若沒有在跑或排隊的 `scout-step*` 任務就提交第 0 步——這就是 09-23 的 `register`／`say`。

**agent 和核心的關係。** 核心從不進 `agents/`。對核心而言，agent 只是一串 `needs` 不同的任務，恰好 cwd 都在同一個家。這是「agent 可以直接接進核心、不用特別處理」（§2.13）的字面實現。

## 6. 第一個能跑的 demo

```sh
aos init world && cd world                                  # tasks/ resources/cpu/ tick.json
mkdir resources/human; echo '{"capacity":1}' > resources/human/resource.json
aos submit hello    --needs cpu   -- sh -c 'echo hi; sleep 3'
aos submit ask-a    --needs human -- sh -c 'until [ -f answer ]; do sleep 1; done; echo 人說:$(cat answer)'
aos submit ask-b    --needs human -- sh -c 'until [ -f answer ]; do sleep 1; done; echo 人說:$(cat answer)'
aos run --interval 1 &
ls tasks/*/            # 0001 有 run.json＋out/；0002 有 run.json；0003 只有 task.json（human 滿了、排隊）
echo 好 > tasks/0002-ask-a/answer; sleep 2; cat tasks/0002-ask-a/out/stdout; ls tasks/0003-ask-b/  # 人說:好；0003 拿到格了
aos stop; cat tick.json; zip -qr ../world-t$(jq .tick tick.json).zip .   # 時間停了、打包
```

使用者用 `ls`／`cat` 看到：三種狀態各長什麼樣（只有 task.json／多了 run.json／多了 out/exit）、容量 1 真的只放一個、答完才換下一個、`tick.json` 數字停在哪就是哪、zip 就是那個時間點的世界。第二個 demo 才加 `brain-local` 資源與 `aos-agent init scout`／`say hello`，看 `tasks/` 裡長出 `scout-step0`、`step1`（needs brain-local）、`step2`，`memory.json` 多兩則。

## 7. 最可能弄複雜的三個地方與預防

1. **核心偷長欄位**（status、retry、timeout、priority、after、not_before……每個都「只是一行」）。proto2→7 就是這樣長的。預防：**核心只認四個鍵**（`argv`、`needs`、`capacity`、`sorter`）、只寫三種檔（`tick.json`、`run.json`、`out/`），寫在 README 第一段當憲法；想加任何東西先問「排序器能不能自己做」——優先級是排序器讀 tags 的事、逾時是任務自己 `timeout 30 cmd` 的事、依賴是任務自己 `until` 的事。核心行數封頂 150。

2. **資源變成真行程、排序器變非同步、任務之間長出協定**（信箱、ack、信件格式、掛載）。§2.8 說「資源也是行程」聽起來就該做常駐 daemon＋IPC；一做就有 proto7-2 那套 holder／grant。預防：第一版用「capacity 整數＋tick 代掃」得到相同可觀察行為，**等出現一個用整數做不到的 demo 才升級**；任務間溝通只有「寫檔、看檔」，核心沒有任何訊息格式；信箱格式只存在於 `aos-agent` 這 100 行裡，是 agent 的家規不是 OS 的法。

3. **agent 那層重演 proto2 的七格狀態機＋工具包＋重試**。預防：`aos-agent` 是核心外的獨立腳本、plan.json 直線、`tools` 是「名字→argv」的字典（一個工具就是一支程式，沒有包、沒有 TOOLS/PROMPT/hook）、**沒有重試**——節點失敗就停、人 `cat out/stderr` 再 `say` 一次。可預測性照 §2.16 用「run 節點數／總節點數」量，想讓它變好就把一個 `llm` 換成 `run`，不是加狀態。

另外一個不算設計、算紀律的：**每多一種檔，先在 demo 裡出現過**；`tasks/` 會一直長（這是刻意的，它就是日誌），垃圾清理等它真的礙事再寫 `aos gc`，不預先設計。
