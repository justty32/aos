← [回入口 01-保證佈局入口.md](../01-保證佈局入口.md)｜段落：一、aos 保證的（不是慣例，是底）、二、佈局（每檔一句）｜上一份：—｜下一份：[02-三-入口-loop-fsm](02-三-入口-loop-fsm.md)

## 一、aos 保證的（不是慣例，是底）

aos 保證的底——六個環境變數（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`；§ 19）、`aos-exec [FLAGS...] XXX [args...]`（§ 15；旗標有 `--ws`、`--stack` 與 `--dotenv-override`）、aos-exec 只做那幾件事、WS 不存在或入口缺／壞時退 1、找入口的規則與 `#/` 尋址——已升成規範，見 NORMS：**P-01＝[N-57](../../NORMS/10-基礎設施-定義與工作區/01-N-57.md)、P-02＝N-58、P-03＝N-59、P-04＝N-60**；N-61（找入口與種類判斷）、N-62（`#/`）沒有對應的 P 號。這裡不重複正文，條號 P-01～P-04 只留給別處的引用。慣例（P-05 起）建立在這個底上。

## 二、佈局（每檔一句）

狀態表一律寫在 `fsm.json`（§ 10 使用者「好主意」）；每一格是一張單子，叫範本資料夾裡的一支程式檔（P-27）。fsm 停在哪格記在 stack 的 `stage.txt`（使用者 11-04 題 10「fsm改名，嘗試用同義詞」，[four-elements 07](../../../thinking/2026-11/04/four-elements/07-實作步驟.md) 步 3；fsm.json 的 `start`／`states` 不改），不寫 trace（N-39）。標準範本是走 queue 的 [templates/agent-fsm](../../../templates/README.md#agent-fsm)（P-27、P-08）：`_entry` 是沒 `+x` 的 JSON，四格 idle／think／wait／act 都是單子叫範本裡的 python，沒有資料夾格。下面這棵樹照那一夾現在有的檔寫（逐檔的完整說明在 [agent-fsm 說明](../../../templates/docs/02-agent-fsm.md)）。

```
agent-fsm/                 一個 agent＝一個資料夾程式（§ 1）
  _entry                   入口（預設 $AOS_ENTRY）：沒 +x 的 JSON 單子，aos-agent ctl add 這個資料夾（cwd＝$AOS_WS）＝把這隻掛上 daemon（C-73、P-40）
  body.json                身體的入口：["aos-loop", "loop.json"]（interfaces.json 的 entry 指它，掛上去之後 daemon 跑的是它）
  loop.json                {"exec": "fsm.json", "interval_ms": 300, "ctl": …, "state": …, "state_flux": …, "on_start": …, "on_stop": …}：
                           每次 aos-exec fsm.json（跑一次 fsm）；沒寫 max＝常駐，靠 ctl 收工（P-06）
  fsm.json                 整張狀態表（P-07、P-27）：_entry＝["aos-fsm", {"$env": "AOS_CF"}]（所以它本身就是 aos-exec 的入口）；
                           四格都是單子，直接寫在那格的 exec；next 是照結束碼分岔的物件（P-08、N-36）
  idle.py                  idle 格（收信）：$AOS_STACK/queue/ 的信全部收進 history.jsonl；有好信退 0、沒信退 10（P-12、P-19）
  brain.py                 think 格：帶 history（加 system、tools）組一份問腦的請求，寫 $AOS_STACK/think/request.json，不碰網路（P-23、P-10）
  wait.py                  wait 格：把請求寄給 llm kernel、逐拍收回信，信件名稱記在 think/pending.txt；回信接進 history（P-41）
  act.py                   act 格：依序 aos-tools call 腦要的工具、結果接進 history 退 0；腦沒叫工具（最後答案）退 10（P-24、P-41）
  cell_common.py           四格共用的開頭幾步（看時鐘、讀 history.jsonl、決定用哪份工具登記檔）
  atomic_file.py           idle、wait 共用的寫檔：先寫暫存再改名（N-05）
  llm_settings.py          腦設定怎麼變成請求信的 body（model 填 endpoint 欄、調整鍵放進 request）
  interfaces.json          宣告身體的入口、工具登記檔、腦設定、history、hooks、system 各是哪個檔
  tools.json               aos-tools 登記檔：一串 "$override" 疊 lib/packs 的工具包（P-41）
  llm.json                 腦設定：{}＝用 kernel 的預設（P-23、P-15）
  system.txt               system 訊息（每格從檔讀、不存進 history）
  hooks.json               這隻的 hook：timer、mail_notify 兩格（on_clock）
  subagents.json           工具 subagent 的配額：{"max_subagents": 4}
  _metainfo.json           自稱：summary、估時 cost.time_ms、資源 llm
  README.md                說明（怎麼複製、怎麼收緊工具）

workspace/                 ＝$AOS_WS，使用者的（§ 2）；範本不在裡面規定任何檔
  .stack/                  預設 $AOS_STACK（§ 2）＝這隻的 stack（P-16）；經 _entry 掛上 daemon 時 stack 預設在 <daemon stack>/procs/<名>/，裡面長一樣：
    stage.txt              fsm 停在哪格（P-07）
    queue/{tmp,new,cur}/   輸入的信箱（P-11）；idle 接進 history 就收掉
    history.jsonl          對話，一行一則訊息、只附加（P-41）
    think/request.json     think 組好的請求（P-10）；寄出後多 think/pending.txt、think/reply/
    hooks/<名>/on_clock.json   on_clock hook 上次看時鐘的記錄
    tools/<登記名>/        工具的小格＝它的 stack（P-17）；工具真的寫東西才建
```

上面 stack 那幾列是在空工作區實跑三拍（空 queue 一拍、投一封信後兩拍，停在 `wait`、還沒寄）看到的，加上 `wait.py`、`act.py` 檔頭寫的 `pending.txt`、`reply/`、`tools/<登記名>/`。測試不放在範本裡，在 [`templates/tests/agent-fsm/`](../../../templates/README.md)；範本裡沒有捷徑（symlink），工具都登記 lib 那格，`cp -r` 抄到哪都能跑（使用者 11-10「啊？範本不該有tests。有的話就跟着抄。」，[tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md) 題 5；[templates-cp](../../../thinking/2026-11/10/templates-cp/README.md)）。

stack 樹就是呼叫樹：工具的小格在 `.stack/tools/<登記名>/`，工具自己再叫別人就再往下長一層 `tools/<名>/`（P-38、P-17）。

被叫的沒給工作區就沿用呼叫方的 `AOS_WS`，要另放才明給 `--ws`（使用者「移除P-32」）。

**時鐘**只放在**根** daemon——根的 daemon.json `procs` 帶一列跑 `aos-clock` 的普通 proc（範本名 `_clock`）＋根定義資料夾 `.env` 一行 `AOS_CLOCK=${AOS_STACK}/clock`；`kernel/*` 等子 daemon 範本預設不帶，照繼承聽外層的鐘，有特殊需求的由人手動加。aos-daemon 程式不認時鐘、沒有 `clock` key。使用者 11-09「預設聽外層。然後開clock這個選項，daemon設定檔預設是不開。大家也通常只在root daemon才開，除非有特殊需求。」（[thinking clock-decouple](../../../thinking/2026-11/09/clock-decouple/README.md)；寫法見 [aos-daemon docs/02](../../../impls/aos-daemon/docs/02-看寫法決定怎麼起.md#時鐘普通一列)）。
