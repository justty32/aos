# 工具包接口

這份給後面做各包的 codex 看。工具包只改自己的 `packs/<包>.py`、`tests/<包>.sh`、`docs/<包>.md`、`notes/play/<包>.md`。

## 1. 一包長什麼樣

一個包就是一個 Python 檔。只用 Python 3 標準函式庫。

```python
PROMPT = "一句給模型看的用法。"
TOOLS = [{"name": "hello", "description": "打招呼。",
          "parameters": {"type": "object", "properties": {}}}]

def run(name, args, ctx):
    return {"text": "你好"}
```

`run(name: str, args: dict, ctx: Ctx) -> object`：執行工具，回傳值會轉成 JSON 放進工具結果。

最小例子：`return {"ok": True}`。

## 2. 怎麼載入

`tools.json` 的 `packs` 列到包名才會載入。先找 `<home>/packs/<包>.py`，再找內建的 `proto2/packs/<包>.py`。舊名字 `shell` 會改載 `fs` 並提醒。

```json
{"packs": ["mailbox", "my_pack"], "tools": []}
```

加一包時，只加自己的四個檔。README 只加工具包表的一行。

包與掛勾都照 `tools.json` 的 `packs` 順序。工具同名時，前面的包贏，後面的跳過並印一句提醒。`tools[]` 排在所有包後面。

## 3. 共用接點

### 基本資料

`ctx.world: str`：世界資料夾的絕對路徑。

```python
path = os.path.join(ctx.world, "notes.txt")
```

`ctx.home: str`：agent 本體資料夾的絕對路徑。

```python
path = os.path.join(ctx.home, "my-pack.json")
```

`ctx.name: str`：世界資料夾名，也是寄信時的自己名字。

```python
who = ctx.name
```

`ctx.state: dict`：這一格共用的狀態；可直接增刪欄位，工具離開後 agent 會寫回。

```python
ctx.state["my_count"] = int(ctx.state.get("my_count") or 0) + 1
```

### JSON 與日誌

`ctx.read_json(path: str, default: object) -> object`：讀不到或不是 JSON 就回 default。

```python
data = ctx.read_json(os.path.join(ctx.home, "mine.json"), {})
```

`ctx.write_json(path: str, obj: object) -> None`：先寫 `.tmp` 再換名，讀者不會看到半個檔。

```python
ctx.write_json(os.path.join(ctx.home, "mine.json"), {"ok": True})
```

`ctx.log(text: object) -> None`：在 stderr 印 agent 與包名的前綴。

```python
ctx.log("開始整理")
```

`ctx.truncate(text: str, n: int = 4000) -> str`：把太長的文字截短。

```python
short = ctx.truncate(output)
```

### 信件與通訊錄

`ctx.put_mail(target: str, source: str, content: object, **extra) -> str | None`：用世界路徑或通訊錄名字寄信；找不到就記 log 並回 `None`。

```python
path = ctx.put_mail("bob", "review", "請看一下", thread="t1")
```

信固定有 `from`、`to`、`time`、`content`。檔案落在對方 `<home>/inbox/<source>/<時間>.json`。

`ctx.contacts() -> dict`：讀 `<home>/contacts.json` 的「名字 → 世界路徑」。

```python
known = ctx.contacts()
```

`ctx.add_contact(name: str, path: str) -> bool`：新增或更新一個聯絡人。

```python
ctx.add_contact("bob", "/tmp/world-bob")
```

### 父子

`ctx.parent() -> dict | None`：讀自己的 `parent.json`。

```python
parent = ctx.parent()
```

`ctx.kids() -> dict`：讀自己的 `kids.json` 名冊。

```python
for name, kid in ctx.kids().items():
    pass
```

`ctx.kids_dir() -> str`：回 `<home>/kids` 路徑。

```python
box = ctx.kids_dir()
```

`ctx.spawn(name: str, persona: str, clock="shared", template=None, packs=None, task=None, depth=None) -> tuple[bool, str]`：建立子 agent，並一次寫好工具包、第一封工作信、深度、父子名冊與通訊錄。`packs` 明講時優先；沒明講時保留模板工具包；沒有有效模板才抄父的工具包。

```python
ok, msg = ctx.spawn("reader", "你負責讀文件", template="coder",
                    packs=["mailbox", "fs"], task="先讀 README")
```

模板找 `proto2/templates/<名字>/`。目錄不存在時直接略過。

`ctx.self_depth() -> int`：沿 `parent.json` 往上數自己在第幾層；頂層是 0。

### LLM

`ctx.find_llm() -> str | None`：找 LLM 資料夾，找不到回 `None`。

```python
where = ctx.find_llm()
```

`ctx.llm_dir() -> str`：找 LLM 資料夾，找不到就用白話錯誤結束這格。

```python
where = ctx.llm_dir()
```

`ctx.llm_request(body: dict, kind="side", priority=None, engine=None, requester=None, schedule_kind=None, deadline=None) -> str`：丟非阻塞請求，登記到 `state["pending"]`，回請求檔名。`kind` 是收件分流；`schedule_kind` 才是排程的 `chat/tool/think/background`。

```python
name = ctx.llm_request({"messages": [{"role": "user", "content": "檢查這段"}]},
                       kind="review", schedule_kind="background")
```

檔名前綴是 `<agent>-<kind>-`。pending 每筆有 `name`、`kind`、`since_step`、`pack`。`kind="main"` 留給 agent 主線。

### 時鐘

`ctx.register_clock(dir: str, interval=None, no_wait=False) -> tuple[bool, str]`：請 daemon 替世界開鐘。`no_wait=True` 只投遞，不等 kernel 回話。

```python
ok, msg = ctx.register_clock("jobs/one", interval=2, no_wait=True)
```

`ctx.unregister_clock(dir: str) -> tuple[bool, str]`：請 daemon 收掉一個鐘。

```python
ok, msg = ctx.unregister_clock("jobs/one")
```

`ctx.pause_clock(dir: str) -> tuple[bool, str]`：暫停一個鐘。

```python
ok, msg = ctx.pause_clock("kids/bob")
```

`ctx.continue_clock(dir: str) -> tuple[bool, str]`：讓暫停的鐘繼續。

```python
ok, msg = ctx.continue_clock("kids/bob")
```

四個接口都包 `aos-daemon`。沒設 `AOS_DAEMON_DIR` 時回 `(False, "沒設 AOS_DAEMON_DIR")`。

### 回話

`ctx.reply(text: object, **extra) -> str`：寫 outbox，接著叫所有包的 `on_reply`，回檔案路徑。

```python
ctx.reply("做完了", task="t1")
```

一般工具不必自己叫它。agent 的主線回答會統一走這裡。
子 agent 的回答也會在這裡自動轉寄到父的 `inbox/kid-<名字>/`，不依賴任何工具包。

### 信箱舊把手

這些接口讓 mailbox 包讀信，先保留原樣。

`ctx.sources() -> list[str]`：列來源。最小例子：`ctx.sources()`。

`ctx.unread(source: str) -> list[str]`：列未讀檔名。最小例子：`ctx.unread("team")`。

`ctx.read_done(source: str) -> list[str]`：列已讀檔名。最小例子：`ctx.read_done("team")`。

`ctx.mail_of(source: str, name: str) -> list[dict]`：讀一個信件檔。最小例子：`ctx.mail_of("team", "m1.json")`。

`ctx.mark_read(source: str, name: str) -> None`：把信搬進 `read/`。最小例子：`ctx.mark_read("team", "m1.json")`。

`ctx.preview(mail: dict) -> str`：取一行短預覽。最小例子：`ctx.preview(mail)`。

`ctx.status() -> dict`：回 self 包使用的自我狀態。最小例子：`ctx.status()`。

## 4. 可選掛勾

沒有定義就跳過。某一包的掛勾出錯，只記 log，不弄死 agent。

`on_idle(ctx: Ctx) -> None`：每個 idle 格叫一次；一定要短。

```python
def on_idle(ctx):
    ctx.state["idle_seen"] = True
```

`on_act(ctx: Ctx, tool: str, args: dict, result: object, took_ms: int) -> object | None`：每次工具跑完後照包順序串接。回 `None` 表示不改；回其他值會取代工具結果，後面的包與模型都看到新值。

```python
def on_act(ctx, tool, args, result, took_ms):
    ctx.state["last_tool_ms"] = took_ms
    return result
```

`on_reply(ctx: Ctx, msg: dict) -> None`：每次 outbox 寫好後叫一次。

```python
def on_reply(ctx, msg):
    ctx.log("剛回了：" + msg["content"][:20])
```

`on_result(ctx: Ctx, kind: str, name: str, result: dict) -> None`：收回這個包用 `llm_request` 登記的旁線結果。

```python
def on_result(ctx, kind, name, result):
    ctx.write_json(os.path.join(ctx.home, kind + ".json"), result)
```

包沒有 `on_result` 時，結果會變成一封自己的信，落進 `inbox/<kind>/`。旁線結果不推動主線狀態。

旁線只叫當初送出請求的那一包，所以 `think`、`branch` 同時開也不會互搶結果。

`on_main_result(ctx: Ctx, name: str, result: dict) -> None`：主線 LLM 結果收回時，照包順序每包都能看。`cost` 用它補上工具後一輪的 token。

`on_system_prompt(ctx: Ctx) -> str`：每次組主線 system prompt 時，回一段動態文字。

```python
def on_system_prompt(ctx):
    return "今天只處理一件事。"
```

## 5. Prompt 覆蓋

`<home>/prompt-overrides/<包>.md` 存在時，會取代那包的 `PROMPT`。空檔代表不放靜態 prompt。`on_system_prompt` 的動態文字仍會接上。

```sh
mkdir -p prompt-overrides
printf '回答再短一點。\n' > prompt-overrides/my_pack.md
```

## 6. 測試

在 `tests/<包>.sh` 定義並呼叫自己的測試。共用 helper 在 `test.sh`。看 [`tests/_example.sh`](../tests/_example.sh)。

```sh
bash proto2/test.sh
```

## 7. 各包想要但還沒有的接點

已補上同名工具優先權、可替換的 `on_act`、主線結果掛勾、`register_clock(no_wait)`、完整 `Ctx.spawn`、`self_depth`，以及排程參數版 `llm_request`。下面仍是欠帳。

- `bigmem`：記憶世界專用的 `mem_send`／`mem_take`。
- `bigmem`：安全的 `history_read`／`history_replace`。
- `bigmem`：送主線 LLM 前可以擋下請求的掛勾。
- `branch`：當格取回指定旁線結果的共用接口。
- `branch`：讓 `adopt` 明講「這次不要追加舊工具結果」的接口。
- `code`：安全解析世界內路徑的 `project_path`，以及統一的 `undo_dir`。
- `communication`：`put_mail` 自動把首封檔名當 thread。
- `communication`：用世界路徑反查通訊錄名字。
- `cost`：`on_act` 還拿不到模型送來的原始參數字串與統一錯誤種類。
- `kids`／`self`：只讀的 daemon 時鐘狀態接口；現在仍要讀 clocks 檔或父的 inst。
- `mcp`：指定來源投信進 agent inbox 的共用 CLI。
- `newagent`：`aos_agent.py` 裡可供 `new` 與 `spawn` 共用的頂層世界建立函式。
- `review`：目前任務編號、粗略 task key 與上次任務起始格。
- `think`：每格都會叫的 `on_tick`。
- `think`：旁線完成前暫停主線 LLM 的接口。
