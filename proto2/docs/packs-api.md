# 工具包接口

給寫 packs/<包>.py 的人。proto2 只用 Python 3 標準函式庫。

## 一包長什麼樣

~~~python
PROMPT = "一句給模型看的用法。"
TOOLS = [{"name": "hello", "description": "打招呼。",
          "parameters": {"type": "object", "properties": {}}}]

def run(name, args, ctx):
    return {"text": "你好"}
~~~

run(name, args, ctx) 的回值會轉成 JSON 工具結果；最小回值是 {"ok": true}。
tools.json 的 packs 有列才載入：先找 <home>/packs/<包>.py，再找 proto2/packs/<包>.py；
舊名 shell 會改載 fs 並提醒。新增一包只加包、測試、文件和 README 表格各一處。

同名工具只有一條規則：tools.json 的包排前面的贏；tools[] 排在所有包後面。

## Ctx

基本資料：

- ctx.world、ctx.home：世界與本體的絕對路徑。
- ctx.name：工作室成員名；一般世界是資料夾名，也是寄件名。
- ctx.state：這格共用狀態，可直接改，格末會寫回。
- ctx.read_json(path, default)：讀不到或壞 JSON 時回預設。
- ctx.write_json(path, obj)：先寫 .tmp 再原子換名。
- ctx.log(text)：把 agent／包名加在 stderr 前面。
- ctx.truncate(text, n=4000)：截短文字。

路徑、身份與鐘只在這裡解：

- ctx.world_of(name_or_path)：通訊錄名字、相對世界路徑、絕對路徑都回世界絕對路徑。
- ctx.home_of(world)：解析該世界 .aos/inst 後回 home。
- ctx.clock_of(world)：只讀 daemon clocks/ 與父世界 inst，回
  {"kind":"own|shared|none","state":"..."}；找不到不猜。
- ctx.depth()：沿 parent.json 算深度，頂層是 0。

建世界：

- aos_agent.create_world(world, home=".", template=None, tools=None, persona=None, prompts=None,
  llm=None, parent=None) 是 new、spawn、team 共用的唯一底層。
- ctx.spawn(name, persona, clock="shared", template=None, packs=None, task=None, depth=None)
  建子 agent，回 (ok, message)；明給 packs 最優先，否則保留有效模板的包，再否則抄父。
  它也寫第一封工作信、深度、父子名冊與雙向通訊錄。不存在的模板當作沒給。

## 旁線生命週期

包只用這一套：

~~~python
request_id = ctx.send("review", {
    "messages": [{"role": "user", "content": "檢查這段"}]
}, engine="deepseek-flash", priority=0, schedule_kind="background",
   deadline=None, timeout_s=600)
ctx.sleep_until("review", request_id)
~~~

- ctx.send(kind, body, **opts) -> id：預設送 LLM；target=世界 可送一般 requests/ 生產者；
  mail_reply_to=id 可等回信。LLM 選項還有 engine、priority、requester、schedule_kind、
  deadline。預設逾時 600 秒。
- ctx.pending() -> list[dict]：只讀尚未完成的請求。
- ctx.cancel(id) -> bool：取消後照正常結果路徑回
  {"error":"...","kind_of_error":"cancelled"}。
- ctx.sleep_until(kind, id)：agent idle 時不叫主線 LLM；該結果或新信來才醒。

只有 agent 共用層能拿走生產者的 results/。它把結果保存到
<home>/side/<kind>/<id>.json，再只叫原包：

~~~python
def on_result(ctx, kind, request_id, result):
    if result.get("error"):
        return
    return "檢查完成：" + result["summary"]
~~~

on_result 回文字就當成新的 user 訊息喚醒主線。LLM 失敗、缺鐘、逾時與取消都會先叫
on_result，再各寫一則 error: true 的 outbox 人話；錯誤種類只有 llm、timeout、
no_clock、cancelled。`no_clock` 表示這筆請求的目標沒有鐘在跑。包不建自己的
waiting/pending，也不讀、搬、刪 results/。

## 信、家族、LLM 與 daemon

- ctx.put_mail(target, source, content, **extra)：target 可用名字或路徑；成功回檔案路徑，
  找不到記 log 並回 None。信固定有 from/to/time/content，落到對方
  <home>/inbox/<source>/<時間>.json。
- ctx.contacts()、ctx.add_contact(name, path)：讀寫通訊錄。
- ctx.parent()、ctx.kids()、ctx.kids_dir()：父資料、子名冊、<home>/kids。
- ctx.find_llm() 找不到回 None；ctx.llm_dir() 找不到就用人話結束該格。
- ctx.register_clock(dir, interval=None, no_wait=False)、unregister_clock、pause_clock、
  continue_clock 都回 (ok, message)；沒 AOS_DAEMON_DIR 回固定錯誤。
- ctx.reply(text, **extra) 原子寫 outbox，接著叫所有 on_reply。一般工具不用自己叫；
  子 agent 回話也會自動轉寄到父的 inbox/kid-<名字>/。

mailbox 暫留的把手是 sources()、unread(source)、read_done(source)、
mail_of(source,name)、mark_read(source,name)、preview(mail)。ctx.status() 回
aos-user status 的九欄快照。

## 掛勾

掛勾沒定義就跳過；壞掉只記 log，不弄死 agent。

- on_idle(ctx)：每個 idle 格，必須短。
- on_act(ctx, tool, args, result, took_ms)：按包順序串接；回 None 不改，其他回值取代
  工具結果，後面包與模型都看新值。
- on_reply(ctx, msg)：每次 outbox 寫好後。
- on_result(ctx, kind, id, result)：只收該包自己的旁線，規則見上節。
- on_main_result(ctx, id, result)：主線 LLM 收回時每包都能看；cost 用它補工具後用量。
- on_system_prompt(ctx) -> str：每次主線請求前附加動態 system prompt。

<home>/prompt-overrides/<包>.md 會取代靜態 PROMPT；空檔代表不放。動態
on_system_prompt 仍會加上。

## 測試與仍缺的接點

在 tests/<包>.sh 寫測試；共用 helper 在 test.sh，例子見
[tests/_example.sh](../tests/_example.sh)。從 repo 根跑：

~~~sh
bash proto2/test.sh
~~~

仍缺：bigmem 的安全 history_read/history_replace；送主線 LLM 前的通用攔截掛勾；
branch 的 adopt「別追加舊工具結果」旗標；code 的 project_path/undo_dir；首封信自動建
thread；cost 取得原始參數字串；MCP 指定來源投信；review 的 task key／起始格。
