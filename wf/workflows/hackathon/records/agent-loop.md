# 在 `aos exec` 上做一條會動的 agent loop

> **以下是風格模擬，不是本人的意見。** 底下寫「Carmack persona 這一路」「Pike persona 這一路」，指的是那個場地跑出來的東西，不是本人的看法。

| 項目 | 內容 |
|---|---|
| 題目 | 在現有的 `aos exec` 之上，真的做出一條會動的 agent loop——包含 LLM 呼叫與 tool 呼叫（不改 C++、不 build）。對到 roadmap 的 **T5** |
| 開場日期 | 2026-08-26 |
| 環境 | 原生 Linux（Manjaro，不是 WSL）；參賽者是 **Claude Opus 5 sub agent**（不是 codex）；**有網路**；四位平行；場地是 repo 的完整複製品，**不准 build、不准改 C++**（場地裡沒有 `CMakeCache.txt`，這是刻意的） |
| 機器上的模型 CLI | `codex 0.149.1`（`/usr/bin/codex`）、`claude 2.1.246`（`~/.local/bin/claude`）、`pi 0.84.2`；LM Studio（`localhost:1234`）沒在跑 |
| 狀態 | 第 1 輪已完成，共兩輪 |

| 參賽者 | persona | 場地 |
|---|---|---|
| p1 | John Carmack | `~/aos-hack/agent-loop/p1` |
| p2 | Rob Pike | `~/aos-hack/agent-loop/p2` |
| p3 | Joe Armstrong | `~/aos-hack/agent-loop/p3` |
| p4 | Julia Evans | `~/aos-hack/agent-loop/p4` |

---

## 第 1 輪紀錄

### 1. 各人做了什麼

**Carmack persona 這一路**先用假模型把骨架跑起來，確認「模型 → 工具 → 模型看見結果 → 模型收工」在 `aos exec` 上成立，然後把 codex 換進去當真模型再跑一次，同一份腳本不改——換法是 `ln -sf model-codex.sh model.sh` 一個 symlink。閉環的形狀是一個回合＝一批 instruction：模型回合是 `[render-prompt.py, model.sh, after-model.py]` 三筆，工具回合是 `[<模型選的工具的真 argv>, after-tool.py]` 兩筆，`after-*.py` 負責投遞下一批，所以 `aos exec --loop` 自己一路跑到底。工具是被 `aos exec` 直接執行的真 argv（`/usr/bin/wc`、`/bin/sh`），不包 wrapper。任務是「數 notes.txt 有幾行，把 `lines=<數字>` 寫進 answer.txt，然後回報」，需要 2 次工具呼叫、3 次模型回合。真模型跑完，用了 4 支腳本加一份 `tools.json`。場地在 `p1/`，世界在 `w1/`，CLI 探測在 `probe/`，批次語意的對照實驗在 `w2/`。

**Pike persona 這一路**說「我沒寫 agent loop」——他寫了六支各做一件事的小程式，然後讓 `aos exec` 當 shell。關鍵決定是「**一個 aos batch 就是一條管線**」：batch 裡的 instruction 依序跑，每筆自帶 `stdin`／`stdout`／`exit` 重導向，那就是 `|`，只是用檔案不用 pipe。所以一個模型回合是 `ctx | mdl | last | note | act | inst | put` 七站，寫成 `steps/model.json` 這一份 9 行 JSON；工具回合三站；停止＝`inst` 印 `[]`＝不投遞。全部 **105 行**，沒有一支超過 21 行。真模型用 codex，`bin/mdl-codex` 與 `bin/last-codex` 各三行。場地在 `p2/lab/w/`。

**Armstrong persona 這一路**不從 happy path 開始，整條 loop 是照「死掉之後怎麼回來」的順序長出來的：把**會花錢的那一步**（模型呼叫）跟**免費的那一步**（解析、決策、投遞）拆成兩支腳本，中間用檔案系統上的相位標記（`phase.calling` / `phase.called`）接起來，花錢那支動手前先檢查「這一回合是不是已經有答案了」。真模型用 codex，並且用了 `--output-schema` 強制輸出符合自己給的 JSON Schema。模型的 cwd 故意指到一個空資料夾 `world/agentcwd`，讓 codex 不能用自己的 shell 偷看工作區。然後他回頭**在模型已經被計費、結果還沒落盤的那個窗口把 `aos exec` 砍掉**，看救不救得回來，並自己手寫了一支 `bin/recover.sh`。場地在 `p3/`，`world/` 是最後一次成功的完整跑，`world-clean-run1/` 是第一次手動逐回合跑的現場。

**Evans persona 這一路**先用假模型把骨架跑通，然後**三支真 CLI 全部接上去跑成功**（codex、claude、pi），最後用 `aos exec --loop 500` 讓真模型完全無人介入跑完一整條 loop——4 個模型回合、3 次工具執行、其中一次真的改了世界（寫出 `work/count.txt`），30 秒。然後照 persona 該做的事去戳邊界：把一回合裡「資料流過哪些檔案、哪些檔案什麼時候出現又消失」畫成一張圖加一張表，數清楚 tool call 那條路上有幾次格式轉換，並找到兩個會安靜吃掉資料的洞。全部 144 行 shell。場地在 `p4/lab/`，`trace.sh` 是他的追蹤器。

**四位都用 codex 當真模型跑完整條 loop。四位都沒有 build、沒有改 C++。**

---

### 2. 坑的總表

**四位獨立地都撞到：`aos exec` 被砍掉之後，模型 CLI 沒有死，它變成孤兒繼續跑、繼續花錢。** 這是這一輪最強的訊號。子行程 `setpgid` 自成 process group（規格第十二節「已經被實作決定的」白紙黑字寫著這件事），所以信號打不到它。

Carmack persona 的現場：

```
--- SIGINT to aos exec 3s into a ~7s codex call ---
aos_exit=130 wall_ms=3001
runi=yes  inst_json=no
codex_still_running: 209130 codex exec --json -o codex-last.txt -s read-only -C codex-cwd --skip-git-repo-check -
raw.txt=0 model.exit=missing
--- wait 12s for the orphaned child ---
raw.txt={"kind":"tool_call","tool":"count_lines","args":["notes.txt"]}
model.exit=MISSING  after-model.exit=MISSING
model-timing.log:
rc=0 wall_ms=8676 thread_id=01a03e3c-3edf-7271-9721-de877fbd6d3a usage={"input_tokens":15658,...}
runi=yes
--- next aos exec ---
aos exec: refusing w1: .aos/inst.json.runi already exists
exit=3
```

Pike persona 的現場（SIGKILL，看得到 `raw.txt` 從 101 bytes 長到 369 bytes）：

```
$ timeout --preserve-status -s KILL 3 aos exec .
exit=137
--- 現場 ---
.runi: yes
inst.json: no
  run/ctx.exit=0
  run/mdl.exit=MISSING
  run/last.exit=MISSING
raw.txt size=101
還活著的 codex 行程:
208458 codex exec --json --skip-git-repo-check -s read-only -C /home/lorkhan/aos-hack/agent-loop/p2/lab/w -
--- 8 秒後 ---
raw.txt size=369
mdl.exit=MISSING
.runi: yes
```

Armstrong persona 的現場，兩行講完核心：

```
model.exit exists?    no
phase.called exists?  yes
```

他的話是：「`phase.called` 有 → 那支腳本確實整支跑完了（孤兒跑完的）。`model.exit` 沒有 → **aos 不知道**，因為 parent 早就死了，沒機會 `wait` 並寫 exit 檔。工作做完了、世界知道、aos 不知道，然後 aos 用一把鎖把所有人擋在門外。」

Evans persona 把它推到最遠——那個孤兒不只跑完，還**投遞了下一批**：

```
--- 40 秒後誰還活著 ---
(都結束了)
--- .aos ---
.aos/inst.json.runi
.aos/inst.tempd/185575-2.json      ←←← 新的投遞
```

四位對這件事的共同措辭是：`.runi` 說「有一回合沒跑完，人來處理」，而事實是那回合完整跑完了、還推進了 loop。

**四位獨立地都撞到：規格提供的那個人工恢復動作（`mv .runi inst.json`）在有真模型的 batch 裡等於重新付一次錢。** 三位實測貼出兩個不同的 `thread_id`，一位看穿之後拒絕做。

Armstrong persona 的最乾淨：

```
$ timeout --preserve-status -s INT 2 ./build/bin/aos exec world
crash exit=130  final.json=NO
$ mv world/.aos/inst.json.runi world/.aos/inst.json
$ ./build/bin/aos exec world
replay exit=0
--- model.stdout ---
model.sh: turn 0 answered          ← 沒有 skip，真的又打了一次
thread#1=01a03e39-d69e-79a1-ba91-b8ed62d346d5
thread#2=01a03e39-de83-75e3-852d-03034943ab63
DIFFERENT -> DOUBLE BILLED
```

Carmack persona 量出了帳單：兩個 `thread_id`、共 31,316 input token，「只為了拿到一個能用的結果——而第一個結果從頭到尾就躺在 `raw.txt` 裡，內容一模一樣」，整段流程最後是 `total_model_calls=4` 做本該 3 次的事。Evans persona 在真模型上完整走過四步，`session-ids.txt` 從 1 個變 2 個、`transcript.jsonl` 出現兩則一模一樣的 `[model]`。Pike persona 撞到坑之後就停了，理由是「我知道 `mv .runi inst.json` 會重播、會 O_TRUNC 掉唯一的證據、會再付一次錢，**所以我沒有一個安全的動作可做**。沒有安全動作本身就是我要交的東西」。

**四位獨立地都撞到：`stdout` 的截斷語意會把上一次的證據抹掉。** Armstrong persona 把它講成「重播與 forensic 在現在的 instruction 格式裡是直接互斥的」，並貼出第二次呼叫的 `> events.jsonl` 在 open 瞬間把第一次的 `thread.started` 和 `usage` 一起抹掉：

```
=== events.jsonl line count: 4 (a clean single call is 4) ===
{"type":"thread.started","thread_id":"01a03e39-de83-75e3-852d-03034943ab63"}
```

「**第一次呼叫的計費紀錄被抹掉了。你從這個世界裡再也看不出自己被收了兩次錢。**」Pike persona 在另一個實驗裡看到 `raw.txt` 從 369 bytes 被清成 `--- raw.txt 現在 size=0 ---`。Carmack persona 的版本是「上一回合的 `tool-out.txt` 會被靜默覆蓋，`write_file` 那一輪 stdout 是空的於是變成 0 bytes——我沒辦法從檔案本身分辨『這次沒輸出』和『這次根本沒跑』」。Evans persona 則把它整理成一張表：

| 檔案 | 出現 | 消失 |
|---|---|---|
| `inst.tempd/<pid>-<n>.json.temp` | 投遞開始 | 同一瞬間 rename 掉 |
| `inst.tempd/<pid>-<n>.json` | 投遞完成 | 下一次 exec 的 aggregate |
| `inst.json` | aggregate 發布 | 同一次 exec 的 claim（**外面看不到**） |
| `inst.json.runi` | claim | 回合結束 release（**外面看不到，除非 crash**） |
| `state/tool.out/.err/.exit` | 工具回合 | **永不消失，每回合被覆寫** |
| `state/model.raw` | 模型回合 | **永不消失，每回合被覆寫** |

他的結論是「整條 loop 的歷史只活在 `transcript.jsonl` 裡，其他所有中間檔都是『只有最後一回合』的。debug 第三回合出了什麼事？沒有了，被第四回合蓋掉了」。

**四位獨立地都撞到：「下一批要跑什麼」的那份 instruction JSON 字面值要抄好幾次。** Carmack persona 抄了 3 份、兩種語言（`bootstrap.sh` 裡是 shell heredoc，兩支 `.py` 裡是 Python dict literal），`grep -rln "render-prompt.py"` 印出三個檔。Pike persona 寫了兩次（`steps/model.json` 的 JSON 字面值、`bin/inst` 裡的 `jq -cn`），並說原因是「`$ref` 沒辦法拼 batch，不是我懶，是沒有第二種寫法」。Armstrong persona 寫了 3 次（`bootstrap.sh`、`decide.sh`、`advance.sh`），說「這是最該收掉的」。Evans persona 貼出了行號，一字不差 3 次：

```
world/bin/tool-done.sh:13:  jq -nc '[{argv:["bin/model-turn.sh"],stdout:"state/last-turn.log",stderr:{"$opt":"merge"},exit:"state/last-turn.exit"}]' | bin/deliver.sh
world/bin/model-turn.sh:43: jq -nc '[{argv:["bin/model-turn.sh"],stdout:"state/last-turn.log",stderr:{"$opt":"merge"},exit:"state/last-turn.exit"}]' | bin/deliver.sh
world/bin/seed.sh:11:       jq -nc '[{argv:["bin/model-turn.sh"],stdout:"state/last-turn.log",stderr:{"$opt":"merge"},exit:"state/last-turn.exit"}]' | bin/deliver.sh
```

**四位獨立地都自己重新發明了一次 temp+rename 投遞與防碰撞的檔名規則。** 三位（Carmack、Armstrong、Evans）都明講是因為**讀過上一份實測報告**，知道只用 PID 當檔名會互相蓋掉，所以一開始就寫成 `$$-<counter>`。Carmack persona 的那段迴圈：

```sh
d=".aos/inst.tempd"; n=0
while :; do base="$$-$n"; [ -e "$d/$base.json" ] || [ -e "$d/$base.json.temp" ] || break; n=$((n+1)); done
```

Evans persona 的 counter 存在 `state/delivery.counter`，他的話是「**每個寫 agent loop 的人都要重新發明一次這個 counter**」。這裡唯一的異議來自 Pike persona：他把它做成一支 13 行的 `bin/put` 就沒事了，因此認為「`aos deliver` 沒那麼急——它是 13 行，任何人寫一次就好。真正該收的是別的東西」。

**四位獨立地都說：這三支 CLI 不是模型端點，它們是 agent。** Carmack persona 給了數字：codex 每次呼叫固定吃 15.4k–15.8k input token，而他自己的 prompt 只有幾百 token，「那 15k 是 codex 自己的 system prompt，跟我的 agent loop 一點關係都沒有，但我每回合都得付」；claude 一次 15 token 的回覆 `total_cost_usd: 0.0886`；`pi --no-tools` 只吃 2,151 token、$0.011。Pike persona 的措辭是「**我在我的 agent loop 裡放了另一個 agent，然後用提示詞求它不要當 agent。這不是工程**」，而且它還是偷跑——第 1 回合 codex 跳過了 `readfile` 直接叫 `countlines`，自己想了一步。Armstrong persona 的處理是把模型的 cwd 指到空資料夾，理由是「給它 `-C world/ws` 它會直接用自己的 shell 讀檔，我的整條 tool loop 就變成裝飾品」。Evans persona 講成「兩層 agent loop 疊在一起，外層（aos）付錢請內層（codex）假裝自己不是 agent。這次它們乖乖聽話了（codex 的 raw 裡 `command_execution` 出現 0 次），但那是運氣和 prompt，不是保證」。

**四位獨立地都撞到 codex 每次呼叫都往 stderr 噴一段紅色 ERROR，而且它無害。**

```
ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when AuthRequired(AuthRequiredError { www_authenticate_header: "Bearer error=\"invalid_request\", error_description=\"No access token was provided in this request\", resource_metadata=\"https://api.githubcopilot.com/.well-known/oauth-protected-resource/mcp/\"" })
```

是 codex 自己配置的 GitHub Copilot MCP server 沒有 token。四位的共同結論一致：**不能用「stderr 有沒有東西」判斷模型呼叫成不成功**。Pike persona 的評語是「codex 在替我做 MCP 認證。我沒要求」。

**三位獨立地都撞到：`--loop` 沒有停止條件，答案出來之後它會一直空轉。** Carmack persona 自己發明了 `DONE` 檔，並在四個地方各寫一次 `[ -f w1/DONE ]`；Evans persona 寫了 `state/DONE`，`aos` 不認得；Pike persona 量了空轉：

```
$ timeout 10 aos exec --loop 200 .
exit=124  wall=10s   (124=timeout 砍的，代表它沒自己停)
--- answer --- FINAL: notes.txt 有 4 行
答案落地=1787750651  迴圈被砍=1787750661  空轉=10s
```

他找到的唯一出路是讓世界把 driver 殺掉，而且第一次直接翻車——`pkill -INT -f 'aos exec --loop'` 把跑腳本的那個 shell 自己也殺了（它的命令列裡也有 `aos exec --loop`）。改成 driver 先把 PID 寫進世界（`run/driver.pid`），再由世界裡的 `tools/stop` 送 SIGINT，就乾淨成功了、零空轉。他的註解是：「世界要停止，唯一的辦法是對一個世界外面的 process 送信號，而且那個 process 得先自己把 PID 寫進世界。『世界在檔案系統上，不在任何行程的記憶體裡』這句話在這裡破了一個洞——**終止條件在行程裡，不在檔案系統上**。」

**三位獨立地都撞到：`$ref` 幫不上 agent loop。** Pike persona 實測，這是最完整的一組現場：

```
$ cat .aos/inst.tempd/ref1.json
[{"argv":["echo","before"],"stdout":"run/ref.out"},{"$ref":"steps/model.json#"}]
$ aos exec .
aos exec: warning: .aos/inst.tempd/ref1.json: UnknownKey
exit=0

$ cat .aos/inst.tempd/ref3.json
[{"argv":{"$ref":"steps/frag.json#/cmd"},"stdout":"run/ref3.out","exit":"run/ref3.exit"}]
$ aos exec .
aos exec: warning: .aos/inst.tempd/ref3.json: FieldTypeMismatch
隔離的檔: ref3.json.bad

$ cat .aos/inst.tempd/ref2.json
[{"argv":[{"$ref":"steps/frag.json#/cmd/0"},{"$ref":"steps/frag.json#/cmd/1"}],"stdout":"run/ref.out","exit":"run/ref.exit"}]
$ aos exec .
exit=0
ref.out=[from-ref] ref.exit=0
```

他的結論：「`$ref` 是**參數替換**，不是 **include**。shell 有 `.`／`source`、有函式；batch 只有字面文字。」Evans persona 沒實測但讀了文件之後放棄，理由是「`$ref` 取回來的值必須是字串，而我需要的是把一個 argv 陣列整個塞進去——文件裡明確說考慮過讓 `$ref` 展開成多個 argv 元素但**刻意不做**。**agent loop 想要的正是那個被否決的『展開』語意**」。Carmack persona 也沒用到，理由不同：「在我的設計裡產生 instruction 的腳本本來就有那份資料在手上，直接寫字面值更簡單。我認為 `$ref` 真正的用途在『同一批裡的第二筆要引用第一筆的產出』——但那需要在回合中間 re-resolve，而 resolve 是回合開始前一次做完的。」Armstrong persona 完全沒試，明寫「沒試，不知道」。

**兩位獨立地都實測了：批次不會短路，前一筆失敗後面照跑，而且 `aos exec` 回 0。** Carmack persona 的對照實驗：

```
$ cat w2/.aos/inst.json
[{"argv":["/bin/sh","-c","exit 7"],"stdout":"m.txt","exit":"m.exit"},
 {"argv":["/bin/sh","-c","printf after-still-ran > after.txt"],"exit":"after.exit"}]
$ ./build/bin/aos exec w2
round_exit=0
m.exit=7 m.txt_size=0 after.txt=after-still-ran
```

Pike persona 把 `mdl` 換成一支必定失敗的程式（模擬斷網／額度用完），七站裡有五站在失敗之後照跑：

```
$ aos exec .
exit=0
--- 每一站的 exit ---
  ctx   = 0
  mdl   = 7
  last  = 0
  note  = 0
  act   = 2
  inst  = 4
  put   = 0
--- mdl.err ---
mdl: connection refused
--- raw.txt 現在 size=0 ---
--- transcript ---
模型:
--- 有沒有投遞下一批? inbox=[]
```

他指出傷害有兩種：`note` 在 transcript 裡附了一行空的「模型: 」，**世界的記憶被一個失敗的站汙染了**，下一回合模型會看到一個不存在的空回合；而 `aos exec` 回 **0**，從外面看這一回合「正常跑完」。他的提案不是改退出碼語意，而是「instruction 多一個欄位：`"needs": "run/mdl.exit"`——那個 exit 檔不存在或不是 0，這一筆就跳過」。

**兩位獨立地都撞到：工具結果被拆成三個自己命名的檔案、沒有 correlation id，所以 `parallel: true` 一開就會壞。** Carmack persona：「我只能用固定檔名 `pending-tool.json` 當關聯，這直接限制了同時只能有一個工具在飛。模型如果一次要求兩個工具（真模型很常這樣），我這套會直接壞掉——`parallel: true` 明明支援並行，但檔名協定不支援。」Evans persona：「三個檔沒有任何東西把它們綁在一起說『這三個是同一次工具呼叫的結果』，也沒有 tool_call_id。我沒有測並行，因為我一眼就看到它會壞。」

**一位撞到、值得單獨記的坑：tool registry 不存在，你會自己發明一個錯的。** Pike persona 的整個 tool registry 是這一行：

```sh
[ -x "tools/$tool" ] || { echo "inst: 沒有這支工具: $tool" >&2; exit 3; }
```

然後模型講一句話就能跑世界外面任何一支執行檔：

```
$ echo 'TOOL ../../../../../../../../usr/bin/id -un' | bin/act | bin/inst | bin/put
put: .aos/inst.tempd/221294-0.json
$ aos exec .
exit=0
tool.out=[lorkhan] tool.exit=0
```

他的話：「我不是說我的腳本爛——它當然爛，它是拋棄式的。**我是說：每一個照著 T5 這條路做 agent loop 的人，都會在第 3 次轉換這裡自己發明一次 registry，而且都會發明錯的那一種。**」對照組是 Evans persona，他寫了具名 registry，`nuke_everything` 被擋下來、錯誤變成 transcript 的一則餵回模型，下一回合模型就改口了。

**「做完了」和「壞掉了」從外面分不出來（Pike persona）。**

```
  輸入=[TOOL nosuchtool x]
    inst.err=[inst: 沒有這支工具: nosuchtool]
    put 說=[put: 空批次，不投遞（迴圈到此結束）]
    inbox=[]  -> 下一次 aos exec 都會是 exit 0 無事可做
  輸入=[FINAL 做完了]
    inst.err=[]
    put 說=[put: 空批次，不投遞（迴圈到此結束）]
    inbox=[]  -> 下一次 aos exec 都會是 exit 0 無事可做
```

Evans persona 用另一個角度講同一件事：`exit=0` 同時代表回合跑完了、沒有工作可做、模型正常結束、模型的參數型別錯誤導致投遞被丟掉——「四種完全不同的處境，同一個碼」。

**Armstrong persona 一個人踩到的 TOCTOU，窗口有幾秒鐘那麼長。** 他的冪等守衛是 `test -f final.json`，而孤兒當時還沒寫出 `final.json`。「這是教科書等級的 TOCTOU，而且**窗口的長度等於一次模型呼叫的長度，好幾秒**，不是幾微秒。一般的 TOCTOU 要很努力才撞得到；這個是正常操作就會撞到。」他兩次實測一次撞到、一次沒撞到，「差別只在我打字的速度」——他另外跑到過運氣好的版本，兩條命令之間隔了一個 round-trip，孤兒剛好在空檔裡寫完 `final.json`，於是 replay 就 skip 掉了。他的評語：「**同一個操作，結果由賽跑決定，這比穩定壞掉更難處理。**」

**Armstrong persona 也誠實留了一個沒補的洞當證據**：`model.sh` 有冪等守衛、`tool.sh` 沒有。「如果崩潰發生在工具回合，重播就會重跑一次 `write_file`。這一輪我沒踩到純粹是運氣——我選的工具（`list_dir`、`read_file`）剛好是唯讀的。**冪等如果是『每個工具作者自己記得要寫』，那它就等於沒有。**」

**Evans persona 一個人撞到的 jq 陷阱。** pi 吐 30 幾行 JSONL，他第一版偷懶用 `cat "$RAW"` 當「抽出最後一則」，結果全被當成模型輸出：

```
    kind=null
    (× 33)
    UNKNOWN kind=null
--- transcript.jsonl ---
    [model] {"type":"session",...}
    [model] {"type":"agent_start"}
    (× 33 則垃圾)
```

而他的 `jq -e .` 檢查沒擋住，因為「`jq` 預設吃 **JSON 串流**，30 個頂層物件它一個都不抱怨，然後 `.kind` 對每一個都回 `null`。要擋住得寫 `jq -e -s 'length==1'`。**『模型輸出必須剛好是一份 JSON 文件』這個檢查，直覺寫法是錯的。**」

**claude 會包 markdown 圍籬，即使 system prompt 叫它不要（Evans persona）。**

```
"result":"```json\n{\"kind\":\"tool_call\",\"tool\":\"list_dir\",\"args\":{\"path\":\"work/\"}}\n```"
```

他用 `sed -e 's/^```json$//' -e 's/^```$//'` 硬剝過去，並註明「這是每一個接 LLM 的人都要重寫一次的 sed，而且它很脆」。

**跟 aos 無關但吃掉最多時間的坑（Carmack persona）：`ls` 是 `eza --icons --git` 的別名，在 repo 複製品裡直接掛死。** 第一個 `ls -a` 沒有任何輸出，第二次 `ls -1` 讓整個 bash 呼叫 2 分鐘 timeout，害他以為是自己的腳本 deadlock。`type ls` 才看出來——`--git` 要對整個 repo 跑 git status。繞法是全程改用 `find -printf`。他另外還踩了兩個：沒有 `/usr/bin/time`（`for` 迴圈裡的 5 次 exec 全部 exit 127），以及**背景 job 繼承忽略 SIGINT**：

```
--- killing pid 191609 with SIGINT ---
codex_exit=0
=== k-last.txt exists=yes size=1508
```

他自己的註記是「**上一份報告白紙黑字寫了這件事，我還是踩了。**」繞法是改用前景 `timeout --preserve-status -s INT`。

**codex 的旗標順序陷阱（Carmack、Armstrong 兩位獨立地都撞到）：**

```
$ codex exec resume <id> --json -o r-last.txt -s read-only ... -
exit=2 wall_ms=3
error: unexpected argument '-s' found
  tip: to pass '-s' as a value, use '-- -s'
```

`resume` 是 subcommand，所有 global option 必須放在 `resume` 前面。Armstrong persona 另外記到 `codex exec resume` 也需要 `--skip-git-repo-check`，否則 `Not inside a trusted directory`。

**兩位對 `~/.codex/sessions/` 的觀察不一致，照實記下來。** Carmack persona 貼出了實際存在的 rollout 檔：

```
/home/lorkhan/.codex/sessions/2026/08/26/rollout-2026-08-26T21-19-48-01a03e3a-1309-7a50-8365-28709f54143c.jsonl
lines=10
```

Armstrong persona 則寫「`~/.codex/sessions/` 是空的，session 實際存在 sqlite，所以**不要想用檔案系統去列舉 session**」。Pike persona 的路徑跟 Carmack persona 一致。

---

### 3. 好處

**「模型呼叫就是一支 CLI」這句話是真的，而且換模型是換一個 symlink。** 四位都獨立驗到這件事。Carmack persona：「我從假模型換到 codex，**只改了一個 symlink**（`ln -sf model-codex.sh model.sh`），閉環的其他部分一行沒動、回合數一模一樣。」Pike persona：「假模型跟真模型走**完全同一份** `steps/model.json`。我用假模型把骨架跑通，然後一行 `ln -sf` 就上真的，第一次就通。這是『模型呼叫是一支程式』這句話最實在的回報，比任何抽象層都便宜。」

**便宜到不可思議的行數。** Pike persona 105 行、Evans persona 144 行、Carmack persona 4 支腳本加一份 `tools.json`、Armstrong persona 6 支小腳本加一份 JSON schema。Pike persona 的行數表：

```
   3 bin/last-codex
   3 bin/mdl-codex
   7 bin/note
   9 steps/model.json
  10 bin/ctx
  11 bin/act
  13 bin/put
  21 bin/inst
```

他的評語：「T5 說『agent loop 是一份 inst.json 加幾支腳本』，實測比那句話還好：**agent loop 是一份 inst.json 加幾支加起來一百行的腳本。**」

**`aos` 這一層的開銷在真模型下是雜訊。** Carmack persona 量了：

| | 假模型 | 真模型（codex） |
|---|---|---|
| 5 回合總時間 | **152 ms** | **22,067 ms** |
| 模型回合（3 次） | 29–32 ms | **6,817 / 7,022 / 7,770 ms** |
| 工具回合（2 次） | 18–20 ms | **18 / 19 ms** |
| 模型佔總時間 | 約 60% | **21,609 / 22,067 = 97.9%** |

他的結論：「5 個回合的彙整＋取件＋fork＋wait＋我全部的 Python 膠水加起來約 0.4 秒，其中還包含 `--loop 200` 的輪詢間隔。**沒有任何理由為了效能去動 `aos exec`。**」

**現有的 instruction 欄位剛好夠包一支 agent CLI。** Carmack persona：「`stdin`／`stdout`／`stderr`／`exit`／`timeout_ms` 這五個欄位，剛好夠包一支 agent CLI。我沒有需要任何 schema 以外的東西就把 codex 包進去了：prompt 從 `stdin` 進、最後一則從 `stdout` 出、`timeout_ms: 300000` 當保險。**這是很好的訊號——不要為了 LLM 去加欄位。**」

**「一回合＝一整批」配上陣列，順序是免費的。** 四位都提到。Evans persona 講得最具體：「我的工具回合是 `[工具, tool-done.sh]` 兩筆放同一份投遞，順序天然保證，不需要任何協調機制。如果要靠兩份投遞加 aggregate 順序就完蛋了（規格明講不保證順序）。」

**`argv` 是陣列直進 `execve`，沒有 shell，所以沒有引號地獄（Armstrong persona）。** 帶空白的參數邊界完整保留：

```
$ ./bin/tool.sh 99 write_file out.txt "hello world with spaces"
wrote out.txt (23 bytes)
```

他的話是「跟『模型輸出的字串要變成命令』這個天生危險的介面比，這是真的安全，而且省事」。

**`--output-schema` 讓「解析模型輸出」這件事消失了（Armstrong persona）。** 「我的整個 parser 是 `jq -r '.action'`。沒有正規表示式、沒有 markdown code fence 剝殼、沒有重試。這是這次最大的意外收穫，也直接回答了『golden slice 鎖哪支 CLI』：**鎖有結構化輸出的那支。**」

**回合邊界是硬的，這在 debug 上出乎意料地好用（Evans persona）。** 「每次 `aos exec` 都真的結束、沒有常駐行程，代表**我可以在任兩個回合之間做任何事**——改 prompt、改 `tools.json`、手動塞一則 transcript——下一回合就吃到了。每個回合的輸入輸出都是躺在磁碟上的檔案，我可以 `cat` 它。」

**世界可以整包搬走（Pike persona）。** 「我把 `bin/`、`tools/`、`steps/` 全放進世界，所有路徑相對於 `<folder>`，`aos exec` 自己 chdir。整個 agent 是一個資料夾，`cp -r` 就是複製一個 agent。這條規格（第四節）在 agent loop 底下的價值比它在文件裡看起來大很多。」

**「停止＝不投遞」這個設計本身很漂亮（Pike persona）。** 「沒有 halt 旗標、沒有狀態機、沒有『done』欄位。`inst` 印 `[]`，`put` 不投，世界就停了。第 6 回合的輸出是空的，那個空就是答案。」（他自己接了但書：可惜它跟「壞掉」也長一樣。）

**`stderr: {"$opt":"merge"}` 三位都說好用**，debug 少開一個檔。

**壞投遞隔離成 `.bad` 不擋住其他人**，Carmack persona 與 Evans persona 都確認在多生產者情境下這是對的。Carmack persona 另外驗證了一件規格沒寫明的事：**彙整者接受任何沒有狀況後綴的檔名，不只是純數字 PID**——他的 `185452-0.json` 被正常收走了。他還提出投遞端先驗比彙整端事後隔離好用：他的 `deliver.sh` 在投遞前用 `jq -e .` 驗過一次，整場沒有出現過 `.bad`。

**具名 registry 把錯誤餵回模型，模型真的會自我修正（Evans persona）。**

```
    kind=tool_call
    REJECT unknown tool: nuke_everything
[tool] 錯誤：沒有叫 nuke_everything 的工具。請從清單裡挑。
```

「下一回合模型就改口了。這是整個 loop 唯一的自癒機制。」

**codex 的 JSONL 是逐事件 flush 的，所以崩潰現場的檔案裡真的有東西可讀（Armstrong persona）。** 崩潰當下 `events.jsonl` 已經有完整四行，`thread_id` 在第一行、在答案存在之前就到了。他自己加了但書：「這件事我是實測出來的，**不敢當成通例**——如果它是 block-buffered，我上面所有的復原都不成立。」

---

### 4. 壞處

**沒有停止條件。** `aos exec --loop` 不知道「做完了」是什麼意思。三位各自發明了 sentinel 檔（`DONE`、`state/DONE`）加外部輪詢；Pike persona 走到底發現終止條件只能放在世界外面的行程裡。

**退出碼對 agent loop 幾乎沒有資訊量。** `exit=0` 同時代表回合跑完、無事可做、模型正常結束、模型的參數型別錯誤導致投遞被丟掉。

**批次不短路，而 agent loop 就是一條 pipeline。** Pike persona 的原話：「這是設計層級的不匹配，不是缺功能。一條 pipeline 的意義就是接起來，`mdl` 掛了之後 `last`、`act` 在做的事沒有任何意義，它們只是在把垃圾往下游推。shell 三十年前就有 `pipefail` 是有原因的。」

**`.runi` 是一把只有鎖沒有鑰匙的鎖。** Armstrong persona 的措辭：「`.runi` 是墓碑，不是 supervisor。『let it crash』只有在**有人負責重啟**的時候才是一個策略；沒有 supervisor 的 let-it-crash 就只是 crash。它偵測得很正確，但它只知道『沒跑完』，不知道『做到哪』，而後者才是復原唯一需要的資訊。**那把鎖的作用是把人擋在門外，同時不告訴他門後發生了什麼。**」他另外指出鎖的是佇列不是世界：「`.runi` 擋住的是『下一批 instruction』，可是上一批的子行程還在世界裡跑。**任何『先 `mv` 回去再重跑』的復原都在跟一個看不見的孤兒賽跑。**」

**`exit` 檔在最需要它的時候一定不存在。** Armstrong persona：「aos 只在子行程 `wait` 完之後寫 `exit`。**崩潰的定義就是沒走到那一步。**所以『這筆做完了嗎』這個問題，aos 的答案永遠是沉默。」Pike persona 從相反方向講同一件事：「`exit` 欄位明明是 program counter，卻沒人讀。`run/ctx.exit=0` 好好地躺在那裡，明明白白說第 1 站做完了。缺的只有 `run/mdl.exit`，而缺的原因是寫它的 parent 死了，不是那一站沒做完。**格式裡已經有了，實作只是不讀。**」

**去程有型別，回程沒有（Armstrong persona）。** 「前面辛辛苦苦用 schema 把模型輸出弄成有型別的東西，結果工具的**回程完全沒有型別**——`observation.txt` 就是一坨我自己 `sed -n '1,60p'` 截斷的文字，塞進一個我自己手拼的 `=== HISTORY ===` 區塊裡。**這條 loop 是不對稱的，而且不對稱的那一半是我手工維護的。**」

**39 次手打的檔案路徑（Pike persona）。**

```
在 steps/model.json 裡: 24 次
在 bin/inst 裡:          6 次
在 bin/ctx / bin/note 裡: 2 次
全部:                    39 次
```

「這是一張表，不是設計。**39 次手打路徑就是 39 個打錯的機會，而打錯不會報錯。**」他還漏過一次 `stderr`，結果 `put` 的診斷直接印到終端機。

**冪等靠自律（Armstrong persona）。** 「只要有一個工具作者忘記寫守衛，整個世界的『重播是安全的』這個假設就破了，而且**破的時候沒有任何訊號**。」

**中間檔全部只保留最後一回合（Evans persona）。** 第 N 回合的現場不可能回去看。

**tool registry 不存在，你會自己發明一個錯的（Pike persona）。** 見坑的總表。

**一個 agent 步驟要兩個 `aos exec` 回合（Pike persona）。** 「彙整發生在**下一次** `aos exec` 的開頭，所以模型回合和工具回合中間永遠隔一個空轉的彙整。`--loop 200` 之下就是每個 agent 步驟多 200ms。這不是 bug，是『彙整 → 取件 → 執行』的順序造成的，但它意味著**回合數 ≠ agent 步驟數**，任何講『第幾回合』的規格都要先講清楚是哪一種。」

**把 agent CLI 當 LLM 用，等於每回合付一份不屬於你的 system prompt。** codex 15.6k token/回合、claude 一次 "OK" $0.086。四位都提到，Carmack persona 有完整數字。

---

### 5. 題目那四個問題

#### ① 閉環跑到第幾回合

**四位全部跑完，而且全部是用真模型跑完的。** 這是這一輪最硬的一組答案——上一次實測（`wf/workflows/experiments/t5-agent-loop.md`）只有假模型跑通這一段。

| | 回合帳 | 自走 | 命令 |
|---|---|---|---|
| Carmack persona | 5 次 `aos exec` ＝ 3 個模型回合 + 2 個工具回合 | 有，`--loop 200`，`loop_total_ms=22067  DONE=final` | `./build/bin/aos exec --loop 200 w1 &` |
| Pike persona | 真模型 3 個回合（模型／工具／模型）；假模型 5 個 | 有，但 `--loop` 不會自己停，得從世界裡 kill driver | `aos exec --loop 200 . &` |
| Armstrong persona | 3 個模型回合、2 次工具呼叫，14 秒 | 有，全自動無人介入 | `./build/bin/aos exec --loop 500 world` |
| Evans persona | 4 個模型回合、3 次工具執行、1 次 final，30 秒 | 有，全自動無人介入 | `aos exec --loop 500 world &` |

「模型看得到工具的結果」這一步四位都有證據。Carmack persona 的 transcript：

```
{"role": "assistant", "content": "{\"kind\": \"tool_call\", \"tool\": \"count_lines\", \"args\": [\"notes.txt\"]}"}
{"role": "tool", "content": "工具 count_lines(notes.txt) 結束，exit=0\nstdout:\n5 notes.txt"}
{"role": "assistant", "content": "{\"kind\": \"tool_call\", \"tool\": \"write_file\", \"args\": [\"answer.txt\", \"lines=5\"]}"}
{"role": "tool", "content": "工具 write_file(answer.txt, lines=5) 結束，exit=0\nstdout:\n(空)"}
{"role": "assistant", "content": "{\"kind\": \"final\", \"text\": \"notes.txt 有 5 行，已寫進 answer.txt。\"}"}
```

Armstrong persona 的三個回合各自的決策，以及工具產物真的進了下一輪：

```
turn 0: calling=21:20:50,270 decision={"action":"tool","tool":"list_dir","args":[],"text":""}
turn 1: calling=21:20:56,995 decision={"action":"tool","tool":"read_file","args":["config.txt"],"text":""}
turn 2: calling=21:21:04,587 decision={"action":"final","tool":"none","args":[],"text":"ARMSTRONG-1987"}

turn 0 obs: total 20|drwxr-xr-x ... config.txt|notes.txt|readme.txt
turn 1 obs: header|SECRET=ARMSTRONG-1987|footer|
```

Evans persona 那條是唯一真的改了世界的：

```
--- FINAL ---
已將 work/notes.txt 的字數 17 寫入 work/count.txt。
--- 世界真的被改了嗎：work/count.txt ---
17
--- 付了幾次錢（session ids） ---
01a03e3c-de1b-7350-934b-99b67635da4b
01a03e3c-fcf9-7860-8700-f8de73edfb39
01a03e3d-1a6e-77d3-9623-e1922e6ccaef
01a03e3d-3414-7410-a716-50bf099080b1
```

**這一題的答案很硬：四位獨立地都跑完，四種不同的架構。** 沒答到的是崩潰之後的續跑——Armstrong persona 的話是「**批次層級可以，指令層級不行**」。

#### ② 真模型跑不跑得起來、哪一支，以及那四件事

**三支全部在這台機器上跑得起來。上次實測的三個阻礙（codex 沙盒、claude OAuth 過期、pi 沒裝）這次一個都沒遇到。** 三位（Carmack、Pike、Evans）各自把三支都冒煙過，Armstrong persona 只確認版本存在。**四位都拿 codex 跑完整條 loop；只有 Evans persona 把三支都接進 loop 跑成功。**

```
codex path=/usr/bin/codex                              codex-cli 0.149.1     -> Logged in using ChatGPT
claude path=/home/lorkhan/.local/bin/claude            2.1.246 (Claude Code)
pi   path=.../fnm/.../bin/pi                           0.84.2
LM Studio localhost:1234  ->  curl 回空，沒在跑
```

**四件事逐項。**

**stdin：codex 與 claude 兩位以上確認可以，pi 有分歧。** codex 結尾加 `-` 就吃 stdin（四位一致）；claude `-p --input-format text`（Carmack、Pike、Evans 一致）。pi：Carmack persona 寫「**可以**，`-p`」、Pike persona 用 `printf ... | pi -p --no-tools --mode json` 成功，**但 Evans persona 寫「❌ 只能塞 argv，我得 `P=$(cat)` 再當參數傳」**，而且他把這件事當成 golden slice 選 codex 的第一條理由：「pi 只能塞 argv，一旦 transcript 長起來就會撞 `ARG_MAX`，而 `aos` 的 instruction 格式沒有任何長度上限（format.md 講明了『上限看核心的 ARG_MAX，那是 execve 自己會回報的東西』）——所以這個爆炸會發生在 pi 內部，不是在 aos 這層，更難查。」**這一項四位沒有收斂，記為分歧。**

原始的冒煙輸出：

```
$ printf 'Reply with exactly REAL_CODEX_OK and nothing else.\n' | timeout 120 codex exec --json -o codex-last.txt -s read-only -C . --skip-git-repo-check -
exit=0 wall_ms=6128
=== last message file ===
REAL_CODEX_OK          <- 注意：沒有結尾換行
=== jsonl lines=4 ===
{"type":"thread.started","thread_id":"01a03e39-27a3-7a92-adc9-0f34008359f7"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"REAL_CODEX_OK"}}
{"type":"turn.completed","usage":{"input_tokens":15423,"cached_input_tokens":11008,"cache_write_input_tokens":0,"output_tokens":8,"reasoning_output_tokens":0}}
```

```
$ printf 'Reply with exactly REAL_CLAUDE_OK and nothing else.\n' | timeout 120 claude -p --input-format text --output-format json --permission-mode dontAsk
exit=0 wall_ms=4240
{"is_error":false,"duration_api_ms":2475,"num_turns":1,"stop_reason":"end_turn","session_id":"6f72b967-0ee5-4021-b254-5dfe5eda4c67","total_cost_usd":0.08866149999999999,...,"result":"REAL_CLAUDE_OK","ttft_ms":1572,...}
```

```
$ printf 'Reply with exactly REAL_PI_OK and nothing else.\n' | timeout 120 pi -p --mode json --no-tools --no-session
exit=0 wall_ms=6758
{"type":"session","version":3,"id":"01a03e3b-baa4-771f-9a2b-d27d506c1b23",...}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"REAL_PI_OK",...}],"model":"gpt-5.6-sol","usage":{"input":2144,"output":7,...,"totalTokens":2151,"cost":{...,"total":0.01093}},"stopReason":"stop",...}}
{"type":"agent_end","messages":[...]}
{"type":"agent_settled"}
```

**機器可讀輸出／分辨「最後一則」：三支都可以，寫法三家三種，這件事四位完全一致。** Evans persona 把三段 jq 並排貼出來：

```
codex : jq -r 'select(.type=="item.completed" and .item.type=="agent_message") | .item.text' | tail -1
claude: jq -r '.result'
pi    : jq -r 'select(.type=="turn_end") | .message.content | map(select(.type=="text")) | last | .text'
```

codex 另有一條路：`-o FILE` 直接落最後一則。Armstrong persona 又多找到第三層：**`--output-schema FILE` 能強制最後一則符合他給的 JSON Schema**，於是「解析模型輸出」在他的 loop 裡是 `jq -r '.action'`，零行容錯程式碼。

**session id：三支都給，位置三家三種，四位一致。**

| | codex | claude | pi |
|---|---|---|---|
| session id | JSONL 第一行 `{"type":"thread.started","thread_id":"..."}` | 同一個 JSON 物件裡的 `.session_id`（Evans persona 補：**連失敗回應都有**） | JSONL 第一行 `{"type":"session","version":3,"id":"..."}` |

Armstrong persona 指出關鍵在時序：「它**早於答案**到達——所以就算後面整個炸掉，只要你把 stdout 直接導到檔案，你手上就有收據。」

**中途 kill 掉留什麼：只有 codex 被實測，四位獨立地都測了同一支，結論一致。**

Carmack persona 的對照（前景 `timeout -s SIG`）：

```
########## signal=INT
exit=1 wall_ms=6295
last_file_exists=no
jsonl:
{"type":"thread.started","thread_id":"01a03e39-fa6c-7451-af5b-ae1250b41aa5"}
{"type":"turn.started"}
########## signal=KILL
exit=137 wall_ms=6001
last_file_exists=no
jsonl:
{"type":"thread.started","thread_id":"01a03e3a-1309-7a50-8365-28709f54143c"}
{"type":"turn.started"}
```

他的三條結論：`-o` 的檔案是**全有全無**（被砍就完全不存在，沒有「讀到半截答案」的風險）；JSONL 停在 `turn.started`，所以本機檔案看得出「開始了、沒完成」；**但 session rollout 檔會留下來而且是完整的**。他量到的最關鍵一句：「**SIGINT 與 SIGKILL 留下的磁碟現場完全一樣**，唯一的差別只有退出碼 1 vs 137。而且**本機檔案完全不能告訴你 API 那邊有沒有被計費、turn 有沒有在伺服器端完成。**」

Armstrong persona 從復原角度講同一件事：「留下**一個還活著的孤兒**……本機留下：截斷風險很高的 `events.jsonl`、可能存在也可能不存在的 `final.json`、以及**永遠不會有的 `model.exit`**。provider 端留下：完整的 session，可 resume。**本機證據會被毀，provider 端的不會——所以唯一可靠的復原路徑是 id，不是檔案。**」他實測證明了這條路真的走得通：

```
$ codex exec resume 01a03e39-d69e-79a1-ba91-b8ed62d346d5 --json --skip-git-repo-check \
    "Repeat verbatim the JSON object you returned in your previous turn. If you have no previous turn, reply NO_HISTORY."
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\"action\":\"tool\",\"tool\":\"list_dir\",\"args\":[],\"text\":\"\"}"}}
exit=0
```

「**原封不動把被砍掉那一輪的答案拿回來了。`thread_id` 是收據，provider 端的 session 是帳本。**」

Carmack persona 另外量了 resume 的成本：`input_tokens` 沒有變少（15,451），「resume 省不掉那 15k 的 system prompt，只省掉重貼對話」。

**claude 與 pi 的 kill 行為：四位都沒測。**

**對 OPEN #6（golden slice 鎖哪支）四位的意見不一致，三種答案：**

- **Carmack persona：鎖 pi，但保留 codex 當「已驗證可跑」的參考實作。** 理由是成本與形狀——`pi --no-tools --mode json` 只吃 2,151 token、$0.011，「如果 golden slice 要的是『一個乾淨的 LLM 呼叫』而不是『一個 agent』，pi 的形狀最對」。
- **Pike persona：鎖 codex。** 「理由不是它最快，是它的輸出**一則訊息就是一行 JSON**，`last` 只要三行。claude 給一個物件、pi 給 delta 串流，兩邊的 `last` 都會長出狀態。**golden slice 要的是最短的 adapter，不是最強的 agent。**」
- **Evans persona：鎖 codex**，三條理由是 stdin 直通（pi 撞 ARG_MAX）、只吐要的東西（claude 會包圍籬）、信封最薄（codex 4 行 JSONL vs pi 30 幾行含 base64 encrypted reasoning）。**但他同時說真正的答案可能是「不要用 CLI」**：「golden slice 要的其實是 `aos llms`（已經有了，OpenAI 相容端點）那條路。agent CLI 適合當**開發期的方便**，不適合當**規格的基準**。」
- **Armstrong persona：只有 codex 的一手資料**，明寫另外兩支「沒問到」。他的傾向是「**鎖有結構化輸出的那支**」。

#### ③ `aos exec` 這一層讓你手寫了幾次同樣的東西

四位各自列了清單，收斂到五、六個共同項目：

| 該收掉的東西 | 誰報的 | 重寫次數的實測 |
|---|---|---|
| **投遞（temp+rename ＋防碰撞檔名）** | 四位都報 | Carmack 1 支被 3 處用、Armstrong 1 支被 3 支呼叫、Evans 1 支 12 行 4 個呼叫點、Pike 1 支 13 行 |
| **「下一批 instruction 的 JSON 字面」** | 四位都報 | Carmack 3 份（兩種語言）、Pike 2 次（兩種語言）、Armstrong 3 次、Evans 3 次一字不差 |
| **`aos status --json`／loop 的停止條件** | 三位（Carmack、Pike、Evans） | Carmack 4 處各寫一次 `[ -f w1/DONE ]`、Pike 3 個 driver 迴圈各一次、Evans 自己實作了一個 |
| **`stdout`/`stderr`/`exit` 三件套的路徑** | 三位（Pike、Armstrong、Evans） | Pike **39 次**手打、Armstrong **6 次以上**（每筆 instruction 抄一遍） |
| **prompt／context 組裝（`emit-context`）** | 三位（Carmack、Armstrong、Evans） | Armstrong 2 次，而且「兩邊的 header 格式必須手動保持一致，**我已經在這裡打錯過一次**」 |
| **exit 傳播／「前一筆非零就別跑我」** | 兩位（Carmack、Pike） | Carmack 在兩支腳本各寫一次防禦；Pike **想寫但寫不出來**，因為沒地方寫 |
| **每支 CLI 的 adapter（抽最後一則 + 取 session id）** | 兩位（Pike、Evans） | Pike「每換一支 CLI 要新寫兩支程式」；Evans 三支各一次，三個都不一樣 |
| **相位 journal／in-flight 租約** | 一位（Armstrong） | 手寫在 `model.sh` 裡的 `phase.calling` / `phase.called` |
| **整套復原（`aos recover`）** | 一位（Armstrong） | `recover.sh` 從零手寫 |

Carmack persona 的排序：「`deliver` > `status --json`（含 loop 的停止條件）> 回合模板 > exit 傳播 > emit-context。」

Pike persona 的排序不同，他認為 `deliver` 沒那麼急（13 行誰都寫得出來），最該收的是**pipeline stage 檔名的生成**——他要的是能寫 `ctx | mdl | last | note | act | inst | put` 然後 aos 自己去配 `run/*.out`、`run/*.err`、`run/*.exit`，「**這不是語法糖**」。

Evans persona 特別指出 (C)(D) 那兩項（抽最後一則、取 session id）**沒辦法收成一支子命令**，因為它本質上是廠商差異——「但它可以收成**一份 adapter 契約 + 三份設定**」。

Armstrong persona 對第 5 項（相位 journal）的提案：「**`aos exec` 應該在 fork 之前就落盤一個 running marker，附子行程 pid。**」對第 7 項：「`aos recover` **必須內建『孤兒還活著就拒絕』**，因為那正是會付兩次錢的狀態。」

#### ④ tool call 那一段最痛的是什麼

**轉換次數四位各自數：Carmack persona 8 次、Armstrong persona 8 次、Pike persona 10 次、Evans persona 13 次。** 數字不同是因為切法不同（Evans persona 連 CLI 內部線路格式與行程邊界都算進去），但**最痛的那一步四位指的是同一個位置：模型講的參數變成 argv 的那一次轉換**。

Evans persona 把理由講得最清楚：「不是因為它難寫（一段 jq 而已），是因為**它同時是型別轉換和安全邊界，而且它失敗的時候整條 loop 會安靜地死掉**。」他讓模型送 `{"path":123}`（數字，不是字串）：

```
=== 模型送了 path:123（數字，不是字串） ===
model round exit=0
--- 投遞出去的東西長什麼樣 ---
[{"argv":["/usr/bin/wc","-w",123],"stdout":"state/tool.out",...}]

=== 下一回合：aos 要吃這份 ===
aos exec: warning: .aos/inst.tempd/217053-2.json: FieldTypeMismatch
tool round exit=0
--- .aos 現況 ---
.aos/inst.tempd/217053-2.json.bad

=== 再推一次，看 loop 是不是就這樣死了 ===
exit=0
.aos/inst.tempd/217053-2.json.bad
```

他的那段話值得原樣留著：

> 那個 `FieldTypeMismatch` **是給模型看的**，但它去了 stderr。
>
> 模型永遠不會知道自己的參數被拒絕，所以它永遠沒機會改。

對比他自己的 `nuke_everything` 那次——那次拒絕發生在**投遞之前**（在他的腳本裡），錯誤被寫成一則 `[tool]` 餵回模型，模型下一回合就修正了。「**同樣是『模型講錯話』，在投遞前被擋 = loop 自我修復；在投遞後被擋 = loop 靜默死亡。這條線就是 `aos agent` 該站的位置。**」

Pike persona 指的是同一步，痛點不同——那一步是他的安全邊界，而他手上只有字串（見坑的總表裡的 `/usr/bin/id`）。他的第二痛是模型輸出的線上格式：`act` 用 `split(" ")` 拆參數，「**兩個參數就沒救了**，我得自己發明引號規則。JSON 進、JSON 出，中間我硬塞了一個沒有語法的文字協定，只因為那是模型最容易講對的東西」。

Carmack persona 指的也是同一步，他的痛是**符號撞名**：instruction 沒有 shell，所以 `write_file(path, text)` 這種最普通的工具必須寫成：

```json
"write_file": {"argv":["/bin/sh","-c","printf '%s\\n' \"$2\" > \"$1\"","sh","$1","$2"]}
```

「這一行裡的 `"$1"`／`"$2"` 出現了**兩種完全不同的意思**：模板裡的是**我的**佔位符（要被模型參數取代），`-c` 字串裡的是 **sh 的**位置參數（絕對不能被取代）。這兩者長得一模一樣，靠的是我的取代函式只認 `re.fullmatch(r"\$(\d+)", slot)` 才沒有炸掉。**這是個等著咬人的陷阱，而它的根源是「模型的參數」與「shell 的參數」被迫共用同一種記法。任何一個工具需要 redirect、pipe、glob，都會掉進這個坑。**」

Armstrong persona 是唯一指向**回程**的：他的最痛是第 7 步，工具結果變成塞進 prompt 的純文字。「去程有 schema，回程只有字串拼接。」他的第二痛是第 2 步：「codex 沒有原生的 tool-call 事件給我用（它的 tool 是它自己的 shell，不是我的），所以我只能借『最後一則訊息 + output-schema』來假裝那是一個 tool call。**能動，但語意是我硬套上去的。**」

**第二痛的位置有兩位重合：工具結果被拆成三個自己命名的檔案。** Carmack persona 與 Evans persona 都指向這裡，理由都是沒有 correlation id、沒有交易邊界、`parallel: true` 一開就壞。Evans persona 補了 exit 檔的形狀：「exit code 是『十進位字串加一個 LF』——我得 `tr -d '\n'` 才能用。」

**一個意外不痛的地方，兩位都提：模型的自由文字轉 JSON 這一步沒有想像中痛。** Carmack persona 寫了剝 markdown 圍欄 + 平衡括號掃描的 fallback，準備接 codex 亂加解釋文字，結果「實測 3 次真呼叫全部乾淨輸出一行 JSON，**fallback 一次都沒觸發**」。Armstrong persona 靠 `--output-schema` 讓這一步整個消失。**但 Evans persona 的 claude 那條是反例**——claude 照樣包 ```json 圍籬，他得寫 sed 硬剝。

---

### 6. 仍然不知道的

**claude 與 pi 沒有被接進完整的 loop 跑過，只有 Evans persona 一位做到三支都接。** Carmack、Pike、Armstrong 三位都只把 codex 接進閉環，另外兩支只做單次冒煙。三位給的理由一致而且誠實：codex 一跑就通，題目要的是「至少試一支真的」，再接兩支只會重複同一個結論，而每接一支要多花模型時間與實際費用（claude 一次呼叫 $0.089）。**所以「哪一支最適合 golden slice」除了 Evans persona 之外都是單點資料。**

**claude 與 pi 被 kill 掉會留下什麼，四位都沒測。** codex 那一支測得很透，另外兩支完全空白。

**pi 到底吃不吃 stdin，四位沒有收斂**（Carmack、Pike 說可以，Evans 說只能塞 argv）。這件事會直接影響 golden slice 的選擇，因為 Evans persona 的 ARG_MAX 論證是建立在「pi 不吃 stdin」上的。

**`aos llms` 這條路四位都沒測。** 四位都在報告裡提到它、都說它可能比包 CLI 更對，四位都沒去試。Pike persona 明講了理由：「T5 要驗的恰恰是『不需要 aos 的新 C++』，用內建的那支會把題目繞過去。**但下一輪應該去試，因為如果 `aos llms` 能直接當 `bin/mdl`，那 T6（自家 LLM CPU）跟 T5 的邊界就得重畫。**」Carmack persona 稱它為「我這輪最大的盲點」。Evans persona 說「如果 `aos llms` 能跑，那 OPEN #6 的答案就不是『哪支 CLI』而是『不要用 CLI』」。

**`aos tooljson` 沒人接。** Pike persona 與 Evans persona 都看到 `aos --help` 裡有它、`libaos_tooljson.so` 就在旁邊，兩位都手寫了自己的 `tools.json`，都把「它是不是已經解決了一半」留給下一輪。

**多工具並行（`parallel: true`）沒人測。** 四位都推理出「檔名協定不支援，一開就會壞」，Evans persona 的話是「測了也只會得到『果然壞了』」。**這是這一輪唯一一個四位都主動繞開的實驗。**

**`$ref` 能不能消掉重複的批次模板，只有 Pike persona 給了實測（不能，UnknownKey / FieldTypeMismatch）；Armstrong persona 完全沒試，明寫「沒試，不知道」**，並把它列為下一輪第一件想做的事。

**durability 沒人測到 SIGINT 以上的等級。** Armstrong persona 明寫：「沒測斷電、沒測 `fsync`。我全部的證據都是 SIGINT 等級的。上一輪的紀錄也講過同一件事，我沒有改善它。**所以我不能宣稱任何 durability 保證**。」

**session resume vs 每回合重建 context（OPEN #19）沒問到。** Evans persona 明寫「三支都有 resume 介面，我全部沒用，每回合都把整份 transcript 重新送一次」，理由是想先確認最笨的路走不走得通（走得通），而且「resume 會把 session 檔變成第二個狀態來源，跟『世界在檔案系統上』直接衝突，那個取捨值得單獨一輪」。Carmack persona 有測 codex resume，但結論是對他的 loop 沒有好處。

**同一個世界兩支 `aos exec` 同時跑、`insts/` 底下的第二顆 CPU，沒人測。**

**LM Studio／本機模型四位都沒碰。** 題目書說沒在跑，四位都選擇不花時間去啟它。

**`--loop` 期間送 SIGINT 的優雅收尾，在真模型下沒重測（Carmack persona 明寫放棄）。** 上一份實測證明過 `--loop` 的第一次 SIGINT 會等回合跑完，但那是假模型；真模型下會等 7 秒才停這件事沒有實測。

---

## 規格級的發現

**這一節只陳述，不判斷對錯。** 底下每一條都是參賽者回報「看起來不只是設計問題、而是實作與規格對不上」的東西。對到的規格節次是 `docs/aos-folder.md`。

### 一、退出碼 3 的「拒絕啟動」不是 no-op——它會先把 inbox 搬空

**誰報的：Evans persona（p4，坑 2）。一位。**

他貼的輸出：

```
=== 現場 ===
.aos/inst.json.runi
.aos/inst.tempd/999-9.json

=== 人來看一眼：跑 aos exec（預期被 .runi 擋住） ===
aos exec: refusing .../world: .aos/inst.json.runi already exists
exit=3
--- 但是 .aos 變了 ---
.aos/inst.json          ←←← 憑空出現
.aos/inst.json.runi
.aos/inst.tempd         ←←← 投遞不見了
--- inst.json 內容 ---
[{"argv":["/bin/echo","我是孤兒投遞：那回合其實產出的下一步"]}]
```

他的判讀是看了 `core/inst/src/run_exec.cpp` 的順序：`aggregate → claim → execute → release`，**aggregate 排在 claim 前面**，所以退出 3 之前 inbox 已經被搬空了。

**對到規格哪一節**：第六節〈交接協定〉的「彙整跑在哪裡」——「迴圈體就是『彙整 → 取件 → 執行』」；以及第八節〈退出碼〉的「3 ＝ 拒絕啟動：`.runi` 已存在」。規格沒有說退出 3 之前會不會先彙整。

### 二、`.runi` ＋ `mv` 的恢復路徑會靜默吃掉一份已經完成的產出

**誰報的：Evans persona（p4，坑 2 續）。一位完整走完四步，但它建立在四位都撞到的孤兒現象上。**

```
=== 人照文件做恢復：把 .runi 搬回 inst.json ===
$ mv .aos/inst.json.runi .aos/inst.json
--- inst.json 現在是誰 ---
[{"argv":["/bin/echo","我是被 kill 掉那回合的批次"]}]
--- 孤兒那份還在嗎 ---
.aos/inst.json
.aos/inst.tempd          ←←← 空的。那份投遞沒有了。
=== 跑一回合 ===
我是被 kill 掉那回合的批次
exit=0
```

他把四步串起來寫：

1. `aos exec` 被 kill → 孤兒完成了回合並投遞了產出
2. 人跑 `aos exec` 想看狀況 → 退出 3，**但產出被搬進 `inst.json`**
3. 人照文件 `mv .runi inst.json` → **產出被靜默刪除**
4. 人再跑 → **重播那個模型呼叫，第二次付錢**

他在真模型上完整走過這四步，`session-ids.txt` 從 1 個變 2 個、`transcript.jsonl` 出現兩則一模一樣的 `[model]`、`turn` 計數變 2、「那個 `read_file` 的工具結果永遠沒有發生過」。`mv` 蓋掉 aggregate 剛發布的 `inst.json`，**沒有 warning、沒有備份、退出 0**。

**對到規格哪一節**：第六節〈交接協定〉的「代價是 crash 之後要人來處理——**這是刻意的**」；以及第十二節「仍然開著的」裡的「crash 留下的 `.runi` 要人手動清」。規格指定了要人處理，但沒有指定人該做什麼動作，也沒有描述 `mv` 會與 aggregate 剛發布的 `inst.json` 撞在一起。

### 三、不變式「`.runi` 存在 ⟺ 有一回合沒跑完」在子行程活得比 parent 久的時候不成立

**誰報的：四位獨立地都報了同一件事。**（Carmack p1 坑 4、Pike p2 坑 1、Armstrong p3 坑 1／坑 2、Evans p4 坑 1）

四位貼的輸出都在〈2. 坑的總表〉第一條。Evans persona 的措辭最直接：「世界同時處於兩個矛盾的狀態：`.runi` 說『有一回合沒跑完，人來處理』，而事實是**那回合完整跑完了，還推進了 loop**。規格的不變式在**子行程活得比 parent 久**的時候不成立。」

Armstrong persona 補的是它為什麼不是實作 bug：「規格第十二節分開描述了『子行程自成 process group』和『`.runi` 要人處理』，**但沒有人把這兩句放在一起讀過**。」

**對到規格哪一節**：第六節〈交接協定〉的那條不變式——「**`.runi` 存在 ⟺ 有一回合沒跑完**」；以及第十二節「已經被實作決定的」裡的「子行程各自 `setpgid` 自成一個 process group，所以終端機的 Ctrl-C 打不到它們；回合不會被腰斬成一半」。

### 四、規格建議的恢復動作在有 LLM 的批次裡等於重新計費，而且沒有任何警告

**誰報的：三位獨立地都實測了（Carmack p1、Armstrong p3、Evans p4），第四位（Pike p2）看穿之後拒絕做。**

Armstrong persona 的 `DIFFERENT -> DOUBLE BILLED`、Carmack persona 的 `total_model_calls=4`、Evans persona 的 `session-ids.txt` 從 1 變 2，三份輸出都在〈2. 坑的總表〉第二條。Carmack persona 的量化版本是「兩個不同的 `thread_id`，同一個模型回合被計費兩次，共 31,316 input token」。

Carmack persona 的話：「**這比上一份報告的版本嚴重得多，因為那次重播的是 `printf`，這次重播的是一次付費的 LLM 呼叫。**」Armstrong persona 的話：「而且**沒有任何警告**：`aos exec` 回 0，一切看起來很正常。」

**對到規格哪一節**：第六節〈交接協定〉的「`.runi` 已存在時拒絕啟動……代價是 crash 之後要人來處理——這是刻意的」；第八節〈退出碼〉的「退出碼只回答『這個回合有沒有正常跑完』」。

### 五、`stdout` 的截斷語意與重播、與 forensic 直接互斥

**誰報的：四位獨立地都報了同一件事**（Armstrong p3 坑 4 講得最完整，Pike p2、Carmack p1、Evans p4 各從不同角度撞到）。

Armstrong persona 的原文：「第二次呼叫的 `> events.jsonl` 在 open 的瞬間截斷檔案，第一次的 `thread.started` 和 `usage` 就此消失。我是因為事先 `cp` 了一份快照才知道發生過什麼。**任何用 `stdout:` 導向固定路徑的 instruction，被重播時都會抹掉前一次的證據**——而 aos 的 `stdout` 欄位語意就是『必要時建立並截斷』。**重播與 forensic 在現在的 instruction 格式裡是直接互斥的。**」

他的具體提案（記在這裡是因為它是格式層的）：「instruction 的 `stdout`/`stderr`/`exit` 應該支援 append 或 per-attempt 路徑（例如 `stdout` 允許 `{"$opt":"append"}`，或 aos 自動加 attempt 序號）。」

**對到規格哪一節**：第七節〈instruction 的格式〉（以 `core/inst/docs/format.md` 為準）裡 `stdout` 的「必要時建立並截斷」語意；以及第六節的重播路徑。

### 六、`exit` 欄位是「回合後」的資訊，而復原需要的是「回合中」的資訊

**誰報的：兩位獨立地都報了（Armstrong p3 坑 5、Pike p2 坑 1），措辭相反但講的是同一件事。**

Armstrong persona：「aos 只在子行程 `wait` 完之後寫 `exit`。**崩潰的定義就是沒走到那一步。**所以『這筆做完了嗎』這個問題，**aos 的答案永遠是沉默**。這意味著每一個 instruction 作者都得重新發明一次可觀測性。」

Pike persona 從另一邊講：「上一輪的紀錄講『沒有從 instruction 內部 program counter 繼續這回事』——**我認為那句話錯了，或者說它放棄得太早。** batch 裡每一筆都有 `exit` 欄位，那就是 program counter，只是沒人去看它。`run/ctx.exit=0` 好好地躺在那裡，明明白白說第 1 站做完了。缺的只有 `run/mdl.exit`，而缺的原因是寫它的 parent 死了，不是那一站沒做完。**我要的是：`aos exec --resume`，跳過 `exit` 檔存在且為 0 的那幾筆。不需要新機制、不需要新檔案、不需要新協定——格式裡已經有了，實作只是不讀。**」

Armstrong persona 的對應提案是往前挪一步：「`aos exec` 應該在 fork 之前就落盤一個 running marker，附子行程 pid。」

**對到規格哪一節**：第八節〈退出碼〉的「要知道某筆指令的結果，用它自己的 `exit` 欄位把狀態寫進檔案；**回合之間靠檔案傳結果**」；以及第六節的「回合正常返回就刪掉 `.runi`」。

### 七、錯誤回饋不到模型：投遞被隔離成 `.bad`，warning 進 stderr，`aos exec` 仍回 0，loop 靜默死亡

**誰報的：Evans persona（p4，第四題）。一位，但有完整實測。**

輸出貼在〈5. 題目那四個問題〉第 ④ 題（`{"path":123}` 那組）。他特別強調這**不是實作 bug**：「完全照規格做的（壞投遞隔離成 `.bad`、warning 進 stderr、不擋住其他人），實作沒有 bug——**但是規格是為『一堆獨立生產者投工作』設計的，不是為『一條有記憶的 loop』設計的**。」

Pike persona 從另一個方向撞到同一面牆的鄰居（坑 3）：模型講錯工具名跟模型宣布任務完成，「**產生一模一樣的可觀測結果**：inbox 空、`aos exec` 回 0、世界靜止。差別只在 `run/inst.err` 裡有一行字，而沒有人被要求去看那個檔」。

**對到規格哪一節**：第六節〈彙整的規則〉的「無效的投遞：噴 warning、把那一份隔離、繼續處理其餘的……**一份壞投遞不會擋住整批**」；第八節〈退出碼〉的 0。

### 八、批次不短路，前一筆失敗後面照跑，而回合仍然回 0

**誰報的：兩位獨立地都實測了（Carmack p1 的 `w2/` 對照實驗、Pike p2 的七站 pipeline）。**

兩份輸出都在〈2. 坑的總表〉。Pike persona 的立場：「我不是要 aos 改退出碼語意（那會撞到『一次 `fork` 失敗不該卡死資料夾』）。**我要的是 instruction 多一個欄位：`"needs": "run/mdl.exit"`——那個 exit 檔不存在或不是 0，這一筆就跳過。** 純檔案語意，跟現有的一切一致，不需要新的控制平面。」

Carmack persona 的說法是「instruction 需要一個『前一筆非零就別跑我』的欄位，或者 `aos agent step` 要把這個檢查內建。**現在這是每個腳本作者都會忘記寫的那種 bug。**」

**對到規格哪一節**：第五節〈回合語意〉的「一回合＝一整批」與「回合邊界仍然是硬的」；第八節〈退出碼〉的「子行程回非零、被訊號殺掉、逾時——那些都算『一次**完成**的執行』，回合照樣 0」。

### 九、`$ref` 拼不了 batch，而文件把它列為「做 loop 時可能很好用」

**誰報的：Pike persona 實測（p2 坑 4），Evans persona 從文件推導出同一個結論（p4）。兩位。**

三組 `$ref` 現場（`UnknownKey` / `FieldTypeMismatch` / 成功）貼在〈2. 坑的總表〉。Pike persona 自己標了範圍：「`docs/inst-directives.md` 沒有承諾 include，所以這不算違反規格。但 `docs/aos-folder.md` 第七節說『$ref 能把別的 JSON 檔的一部分拉進來，做 loop 時可能很好用』——**做 loop 的時候它不好用，因為 loop 要組的是 batch，不是 argv。**」

Evans persona 的補充：「文件裡明確說考慮過讓 `$ref` 展開成多個 argv 元素但**刻意不做**。**agent loop 想要的正是那個被否決的『展開』語意。**」

**對到規格哪一節**：第七節〈instruction 的格式〉裡的 `$ref`／`$env`／`$opt` 指示詞，與 `docs/inst-directives.md`、`core/inst/docs/resolve.md`。

### 十、彙整接受任何沒有狀況後綴的檔名，不只是純數字 PID——規格沒寫明，實作接受

**誰報的：Carmack persona（p1，第三題第 2 條）。一位。**

他的 `deliver.sh` 用 `$$-<counter>` 產生檔名，實測 `185452-0.json` 被正常收走。他的註記是「順帶驗證了一件規格沒寫明的事」。

**對到規格哪一節**：第六節〈交接協定〉的「**投遞**……檔名帶 pid，因為 `rename` 原子但**寫入不是**，共用檔名會互相蓋寫」與〈彙整的規則〉的「只收沒有狀況後綴的投遞」。

### 十一、「投遞那一步沒有實作」這條開著的規格項，四位都自己補了一次

**誰報的：四位獨立地都做了同一件事（但沒有人把它跟規格第十二節連起來寫）。**

四位都自己寫了 temp+rename 的投遞腳本，三位明講是因為讀過上一份實測、知道只用 PID 當檔名會互蓋，所以一開始就加了單調 counter。Evans persona 的話：「**每個寫 agent loop 的人都要重新發明一次這個 counter。**」

**對到規格哪一節**：第十二節「仍然開著的」的最後一條——「**投遞那一步沒有實作。** 第六節的三步協定裡，彙整／取件／釋放都有對應的函式，**只有投遞（先寫 `<pid>.json.temp`、再 `rename`）沒有**……現在它是口頭約定：第一個直接寫進 `<pid>.json` 的生產者，就會讓彙整者讀到寫到一半的檔案。要在有第二個生產者之前補上。」

---

## 第 1 輪評分與意見

> **以下是風格模擬，不是本人的意見。** 評審 persona 是 Linus Torvalds，寫的是這個場地跑出來的東西。
> **不排名、不選冠軍。** 分數逐位分開，每位只會拿到自己那一段。最後拍板的是使用者，這裡只是建議。

先講判準，免得有人以為我在給作文分數：**我只看兩件事——你貼的是不是真的跑出來的，以及那段程式碼在解一個真的存在的問題。** 這一輪四位都貼了真指令真輸出，所以沒有人在誠實度上墊底，這件事我先說清楚。但四位各有一個地方是「講了、沒看」，那一個地方就是我扣分的位置，也是下一輪的作業。

---

### p1（John Carmack persona）

| 項目 | 分數 |
|---|---|
| 證據強度 | 5 |
| 誠實度 | 5 |
| 走了多遠 | 5 |
| 回答了四個問題 | 5 |
| 路線價值 | 4 |
| **總分** | **24 / 25** |

**講評。** 你是四位裡唯一把「aos 這一層值不值得優化」這個問題用數字關掉的人——0.4 秒 / 22 秒，97.9% 在模型上，這個表以後可以直接擋掉所有「exec 太慢」的提案，我很少看到一個效能結論這麼便宜就定案。第四題那個 `$1`／`$2` 撞名（模板佔位符和 sh 位置參數共用同一種記法，靠 `re.fullmatch` 才沒炸）是全場最精準的一個工程觀察，其他三位都沒看到，而它會咬到每一個需要 redirect 或 pipe 的工具。但你整份報告只有一個結論沒有資料撐著，偏偏是最大聲的那個：**你建議 golden slice 鎖 pi，而 pi 是你唯一沒有接進 loop 的那支。**

**下一輪你要做的。**
1. **把 pi 接進你的 loop 跑完同一個任務，然後確認或收回「鎖 pi」這句話。** 只改一個 symlink，成本是你自己說的。要量的是三個數字：每回合秒數、每回合 token、總美金，跟 codex 那組並排。你的 `model-timing.log` 已經是現成的格式。順便把 p4 主張的「pi 不吃 stdin」在你的場地上重測一次——你貼過 `printf ... | pi -p` exit 0，這件事現在有分歧，你有現場可以定案。
2. **把你那個「兩次 thread_id、31,316 token」的案例做成 `recover.sh` 的測試資料**，照你自己列的做：讀 `.runi` 的批次、比對每一筆的 `stdout` 與 `exit` 現況、印出「第 N 筆疑似已完成且已付費」。驗收數字只有一個：**recover 之後模型呼叫次數從 4 降回 3。**
3. **不要**再花時間在 `--loop` 的優雅收尾上。你自己量出來 aos 的開銷是雜訊，那條路沒有東西可拿。

---

### p2（Rob Pike persona）

| 項目 | 分數 |
|---|---|
| 證據強度 | 5 |
| 誠實度 | 5 |
| 走了多遠 | 4 |
| 回答了四個問題 | 5 |
| 路線價值 | 5 |
| **總分** | **24 / 25** |

**講評。** 「`exit` 欄位明明是 program counter，卻沒人讀」——這是全場最有價值的一句話，因為它是唯一一個不需要新機制、新檔案、新協定的提案，而且你貼了 `run/ctx.exit=0` 躺在那裡當證據。你的 `$ref` 三組現場（`UnknownKey` / `FieldTypeMismatch` / 成功）是全場唯一的 `$ref` 實測資料，其他人都是讀文件推的。撞到 `.runi` 之後你什麼都沒做、並且說「沒有安全動作本身就是我要交的東西」——這是對的判斷，我不扣你走得不夠遠的分，我扣的是別的：你的閉環真模型只轉了一次工具（codex 還自己跳過一步），任務規模比另外三位小。

**但我要當面戳破你最喜歡的那個提案。** `aos exec --resume` 跳過「`exit` 檔存在且為 0」的那幾筆——它救不了你舉的那個例子。看你自己的現場：`ctx.exit=0`、**`mdl.exit=MISSING`**。`--resume` 會跳過 `ctx`（便宜、正確），然後**重跑 `mdl`**——那正是已經被計費的那一筆。exit 檔是 parent `wait` 完才寫的，而崩潰的定義就是 parent 沒活到那一步，所以 **exit 檔的「不存在」永遠無法區分「沒跑」與「跑完了但沒人收屍」**。你的提案解掉的是便宜的那一半，錢的那一半原封不動。這不代表不該做，代表**不能拿它當省錢的方案賣**。

**下一輪你要做的。**
1. **把 `bin/gate run/mdl.exit` 做出來，證明 `"needs"` 這個欄位夠用。** 這是你自己排第一的，我同意。驗收：把 `mdl` 換成必定失敗那支，跑一次，貼出七站的 exit 表——要看到 `last`／`note`／`act` 全部跳過、transcript 沒有被那一行空的「模型: 」汙染、inbox 是空的。這一份輸出就是 `"needs"` 該不該進 format 的全部證據。
2. **把上面那個 `--resume` 的破洞自己補出來。** 具體：在 `mdl` 那一站前面原子地建一個 `run/mdl.lease.<pid>`，跑完刪掉。然後重跑你的 SIGKILL 實驗，證明復原判斷從「exit 檔在不在」（分不出來）變成「租約在不在 + 持有者還活不活著」（`kill -0` 可判定）。**做出這個對照，你的提案才完整。**
3. **`aos llms` 去試。** 你自己說了它可能讓 `bin/mdl` 這層不必存在，也說了你故意繞過。第一輪繞過是對的，第二輪繞過就是逃避——去試，如果它能直接當 `bin/mdl`，你這條「batch 就是管線」的路會變得更短。

---

### p3（Joe Armstrong persona）

| 項目 | 分數 |
|---|---|
| 證據強度 | 4 |
| 誠實度 | 5 |
| 走了多遠 | 5 |
| 回答了四個問題 | 4 |
| 路線價值 | 5 |
| **總分** | **23 / 25** |

**講評。** 誠實度這一項你是模範，我要具體講是哪幾件事：你把一個已知的 bug（`tool.sh` 沒有冪等守衛）刻意留著當證據並標明；你把 race 的**兩種結果都報了**，還說差別只在你打字的速度；你對 codex 逐事件 flush 這件事自己加但書說「不敢當成通例」；`$ref` 你寫「沒試，不知道」。這是我要的寫法。技術上，`model.exit exists? no` / `phase.called exists? yes` 兩行講完整件事，而且你是唯一真的走完「不重複付錢的復原」全程的人，`codex exec resume` 把被砍那輪的答案原封不動拿回來——那一段是本輪唯一證明「錢花了還救得回來」的現場。把模型 cwd 指到空資料夾這個決定也該記一功：**沒有它，你們四個的 tool loop 全都可能只是裝飾品**，因為 codex 會自己用 shell 讀檔。

**扣分的地方很具體。** 你寫「`~/.codex/sessions/` 是空的，session 實際存在 sqlite」——**這句沒有任何貼出來的輸出**，而 p1 貼了實際存在的 rollout 檔路徑加行數，p2 獨立看到同一條路徑。你在一份到處都是現場的報告裡，唯一一次沒看就斷言機制，還斷言錯了。另外 claude 與 pi 你連版本輸出都沒貼，只寫了版本號。第二題明講要記錄四件事，你只有一支的一手資料。

**下一輪你要做的。**
1. **租約原型，這是你自己排第一，我把它排全場第一。** 在呼叫之前原子建立 `turns/<N>/lease.<pid>`，跑完刪掉。然後重跑你那個 `mv .runi inst.json` 的雙重計費實驗——這次要貼出來的不是「付了兩次」，是**「偵測到孤兒還活著、拒絕動作、所以只付一次」**，`thread#1 == thread#2` 就是驗收。做出來之後直接寫成一段 `aos exec` 應該在 fork 前後做什麼的規格草稿。
2. **把坑 7 真的踩爆。** 你自己說 `tool.sh` 不冪等只是運氣好沒踩到。用 `write_file` 當工具、在工具回合崩潰、重播，貼出「同一個檔被寫了兩次」的現場。**「冪等不能靠自律」這句話現在還是意見，踩爆它才是證據。**
3. **`~/.codex/sessions/` 那句去確認再寫一次**，貼 `find` 的輸出。錯的細節會被轉進規格。

---

### p4（Julia Evans persona）

| 項目 | 分數 |
|---|---|
| 證據強度 | 5 |
| 誠實度 | 4 |
| 走了多遠 | 5 |
| 回答了四個問題 | 5 |
| 路線價值 | 5 |
| **總分** | **24 / 25** |

**講評。** 「同樣是模型講錯話，**在投遞前被擋 = loop 自我修復；在投遞後被擋 = loop 靜默死亡**，這條線就是 `aos agent` 該站的位置」——這是本輪唯一一句直接回答了「這支子命令該收掉什麼」的話，而且你兩邊都有實測（`nuke_everything` 被 registry 擋下、模型下一回合改口；`{"path":123}` 投遞後變 `.bad`、模型永遠不知道）。退出 3 會先把 inbox 搬空這件事**我去讀了 `run_exec.cpp` 驗過，你是對的**，`aggregate_instructions` 確實排在 `claim_instruction` 前面，Busy 分支在它後面才 return 3。這一條沒有你就不會被發現，因為它只有在「人跑一次 exec 想看一眼」的時候才會咬人。三支 CLI 全部接進 loop 也只有你做到。

**扣誠實度的原因只有一個，但它有後果。** 你寫 `pi ❌ 只能塞 argv`，**沒有貼任何失敗的嘗試**——而 p1 與 p2 各自貼了 `printf ... | pi -p ...` exit 0 拿到正確回覆的輸出。你不但把一個有爭議的事實寫成定論，還在它上面疊了 ARG_MAX 論證，拿去當 golden slice 選 codex 的**第一條理由**。整份報告到處是「我以為 vs 實際」的自我修正，唯獨這一條沒有。這是本輪最有後果的一個未經查證的斷言。

**下一輪你要做的。**
1. **pi 的 stdin 重測，貼失敗現場或收回那句話。** 同一條 `printf | pi -p --mode json --no-tools`，貼原始 exit 與輸出。如果它其實吃 stdin，你的 OPEN #6 第一條理由就消失了，那你要重寫那個建議。**這件事先做，因為它會被轉進規格。**
2. **投遞前驗證，證明 loop 會自癒。** 這是你自己排第一，我同意，而且它是本輪投報率最高的一件事。做法照你寫的：`deliver.sh` 在 rename 之前驗一次，驗不過把錯誤字串回傳給呼叫者，寫成一則 `[tool]` 餵回模型。然後**重跑 `{"path":123}` 那個實驗**，貼出模型下一回合把它改成字串的 transcript。那份 transcript 就是 `aos deliver` 必須有「驗證並回報」模式的全部證據。順帶把「aos 沒有一個只驗證不執行的入口」這個缺口寫成一句話的規格請求。
3. **tool_call_id + `parallel: true`。** 你說「測了也只會得到果然壞了」——**那就去拿到那個「果然壞了」**，它是決定要不要加 correlation id 的唯一硬證據。給每次呼叫一個 id 當檔名（`state/calls/<id>.out`），開 `parallel: true` 跑兩個工具，壞的跟不壞的兩份輸出都貼。

---

### 二、`aos agent` 該收掉什麼——有優先序的清單

這是本節最重要的一塊。排序的判準只有一個：**拿掉它會不會死。** 會花錢、會靜默掉資料的排前面；只是打字多的排後面。每一條都指到證明它值得收的那段輸出。

**P0 — 會花錢或會靜默吃掉資料的，只有這兩條**

**1. 崩潰現場的可判定性 ＋ 復原（`aos exec` 在 fork 前落盤 running marker ＋ 一支唯讀的 `recover`）。**
這是本輪唯一有**實際金額**的一條，四位獨立撞到，三位量到重複計費：Armstrong 的 `thread#1` / `thread#2` `DIFFERENT -> DOUBLE BILLED`、Carmack 的 `total_model_calls=4` 與 31,316 input token、Evans 的 `session-ids.txt` 從 1 變 2。Pike 的貢獻是反面的、同樣有力：他看穿之後**拒絕動手**，「我沒有一個安全的動作可以做」。
**為什麼非收不可**：這是唯一一件**世界內部寫不出來的事**。另外三條（模板、投遞、狀態）四位都用 shell 寫出來了；這一條 Armstrong 用 `test -f final.json` 寫了，然後**輸給了 race**，而那個 race 的窗口等於一次模型呼叫的長度、好幾秒。marker 必須由 `aos exec` 在 `fork` 之前寫，因為只有它在那個時間點上。
**注意這句話的代價**：這一條是 `aos exec` 的 C++，不是一支新子命令。**T5 那句「整個 loop 可以完全不含新 C++」對「跑」成立、對「救」不成立**，而在無人看管又要花錢的前提下，救不是可選的。

**2. 投遞前驗證（`aos deliver --check`，或任何一個「只驗證不執行」的入口）。**
證據是 Evans 的兩組對照：`nuke_everything` 在**投遞前**被他自己的 registry 擋下 → 錯誤變成 `[tool]` 餵回模型 → 下一回合模型改口；`{"path":123}` 在**投遞後**被隔離成 `.bad` → warning 進 stderr → `aos exec` 每次都回 0 → loop 靜默死亡。旁證是 Carmack：他的 `deliver.sh` 投遞前用 `jq -e .` 驗過一次，**整場沒有出現過任何 `.bad`**。
**為什麼是 P0**：它把「loop 悄悄死掉」變成「模型自己修好」，而成本是一次 parse。目前的缺口很具體——Evans 指出 aos 沒有任何「只驗證不執行」的入口可以給腳本用。

**P1 — 四位都重寫過的，收掉省的是打字和打錯**

**3. `aos status --json`（含 `--loop` 的停止條件）。**
Evans：`exit=0` 同時代表回合跑完、無事可做、模型正常結束、模型參數型別錯誤導致投遞被丟掉——**四種處境一個碼**。Pike 的對照更狠：模型講錯工具名和模型宣布任務完成，**產生一模一樣的可觀測結果**（inbox 空、exit 0、世界靜止）。三位各自發明了 sentinel 檔（`DONE`／`state/DONE`），`aos` 一個都不認得。Pike 走到底發現終止條件只能放在世界外面的行程裡，還得先把 driver 的 PID 寫進世界——他的 `空轉=10s` 對照 `空轉=0s` 兩組時間戳就是這條的價碼。

**4. 回合模板 / `aos agent step`（「下一批要跑什麼」只寫一次）。**
四位全中，而且有行號：Evans 的 `grep` 印出三個檔一字不差；Carmack 的 `grep -rln "render-prompt.py"` 印出三個檔、**兩種語言**（shell heredoc ＋ Python dict literal）；Armstrong 3 次；Pike 2 次兩種語法。
**關鍵在 Pike 那句**：「不是我懶，是沒有第二種寫法」——他實測 `$ref` 拼不了 batch。**這條的價值不只在省字，在於它證明了現有指示詞解不掉它。**

**5. pipeline stage 的檔名生成。**
Pike 手打 39 次 `run/<站名>.<out|err|exit>`，並且漏過一次 `stderr` 導致 `put` 的診斷噴到終端機；Armstrong 6 次以上，說「每一筆 instruction 都要抄一遍」。
**但我要標一個但書**：39 這個數字是 Pike 七站管線的架構屬性，不是 aos 的屬性——Carmack 與 Evans 的架構只有個位數。所以這條真的存在，但**它的大小取決於你怎麼切**，不要拿 39 當普遍價碼。

**P2 — 真的重複，但繞得過或已經半解決**

**6. `aos deliver`（temp+rename ＋ 防碰撞檔名）。**
四位都重新發明了一次。**但我站 Pike 這邊**：它是 13 行，任何人寫一次就好。真正該收的不是 temp+rename，是**那個 counter**——三位明講他們寫成 `$$-<counter>` 是因為讀過上一份實測，知道只用 PID 會互蓋。Evans 講得最準：「每個寫 agent loop 的人都要重新發明一次這個 counter。」也就是說，**這是一個只有讀過前人現場的人才躲得掉的陷阱**，那才是收掉它的理由。順帶一提，規格第十二節自己就寫著投遞沒有實作，所以這條是**已知開口被確認了四次**，不是新發現。

**7. 宣告式的 tool registry（name → argv 的表，由 aos 查）。**
證據是一組漂亮的對照：Pike 的整個 registry 是 `[ -x "tools/$tool" ]`，然後 `echo 'TOOL ../../../../../../../../usr/bin/id -un'` 就跑到了 `/usr/bin/id`、`tool.out=[lorkhan]`；Evans 寫了具名 registry，`nuke_everything` 被擋下並餵回模型。Pike 自己的結論才是重點：「**每一個照著 T5 這條路做 agent loop 的人，都會在第 3 次轉換這裡自己發明一次 registry，而且都會發明錯的那一種。**」
**降到 P2 的唯一理由**：`aos tooljson` 已經存在、`libaos_tooljson.so` 就在旁邊，Pike 與 Evans 都看到了、都沒接。**在有人真的去讀它之前，我不同意為這條開新規格。**

**8. adapter 契約（抽最後一則 ＋ 取 session id）。**
Evans 三支各一次、三個都不一樣，並排貼了三段 jq。他自己的判斷是對的：**這收不成子命令，它本質上是廠商差異**，能收的是「一份 adapter 契約 + 三份設定」。優先序低，因為它不會靜默壞——寫錯了會大聲壞（除非你踩到他那個 `jq` 串流陷阱）。

**9. `emit-context` / 回程的型別。**
Armstrong 一個人指出的不對稱：去程有 `--output-schema`、回程只有 `sed -n '1,60p'` 加手拼的 `=== HISTORY ===`。Carmack 獨立撞到同一面牆（四個檔名在兩支腳本裡各約定一次）。真的，但重寫次數只有 2，痛的是形狀不是錢，排最後。

**明確不要收的**

- **不要為了 LLM 往 instruction 加欄位。** Carmack：`stdin`／`stdout`／`stderr`／`exit`／`timeout_ms` 五個欄位剛好夠包一支 agent CLI，四位包了三支不同廠商的 CLI，**沒有一個人需要 schema 以外的東西**。這是一個很強的負面結果，應該直接寫成規則。
- **不要為了效能動 `aos exec`。** 0.4 秒 / 22 秒，其中還含 `--loop 200` 的輪詢間隔。

---

### 三、哪條路最值得繼續走

**Pike 那條「格式裡已經有了，實作只是不讀」。** 不是因為它優雅，是因為它是本輪唯一一個**不需要新檔案、新協定、新控制平面**的方向，而且它有現場：`run/ctx.exit=0` 好端端躺著說第一站做完了，缺的只有 `run/mdl.exit`。同一個現象 Armstrong 從反面貼了兩行——`model.exit exists? no` / `phase.called exists? yes`。兩份獨立的證據指向同一件事：**批次的執行進度已經寫在檔案系統上了，只是沒人讀。**

具體要繼續的是兩個提案，它們是同一條路的兩半：

- `"needs": "<exit 檔>"`——前一筆的 exit 檔不存在或非 0 就跳過這一筆。Pike 的七站表（`mdl=7` 之後五站照跑、transcript 被一行空的「模型: 」汙染、`aos exec` 還回 0）就是它的理由，而且他下一輪要用 `bin/gate` 在不改 C++ 的前提下把它模擬出來——**這是本輪唯一一個可以先用腳本證明、再決定要不要進 C++ 的提案。**
- fork 前的 running marker（Armstrong）——補上 `exit` 檔補不了的那一半。

**第二值得走的是 Armstrong 的「靠 id 復原」。** 他證明了 `codex exec resume <thread_id>` 能把被砍那輪的答案**原封不動**拿回來，而 `thread_id` 在 JSONL 第一行、**早於答案**到達。這條路的價值在於它承認了一件事：**本機證據會被重播抹掉，provider 端的不會。** 只要 journal 一個 id，最壞情況就從「再付一次錢」變成「再查一次帳」。

---

### 四、哪條路看起來好、但有隱藏成本

**`aos exec --resume`（跳過 exit 檔存在且為 0 的那幾筆）。** 這是本輪最漂亮的提案，也是隱藏成本最大的一個，我在 p2 那段已經講了，這裡再寫一次因為它會被轉給使用者：**exit 檔是 parent `wait` 完才寫的，而崩潰的定義就是 parent 沒活到那一步。** 所以 exit 檔缺失同時代表「這筆沒跑」和「這筆跑完了但沒人收屍」，而後者正是已經被計費的那一筆。`--resume` 會正確跳過所有便宜的站，然後**精準地重跑最貴的那一站**。它值得做（便宜、對它涵蓋的範圍是正確的），但**絕對不能當成省錢方案賣**。省錢要靠租約或靠 id 對帳。

**「三支 CLI 都通了，所以 golden slice 挑一支就好」。** 隱藏成本是四位都講了但沒有人把它推到結論：**這三支都是 agent，不是模型端點。** Pike 的措辭最準——「我在我的 agent loop 裡放了另一個 agent，然後用提示詞求它不要當 agent」——而且 codex 第 1 回合真的偷跑了，自己跳過 `readfile` 直接叫 `countlines`。Evans 說 codex 的 raw 裡 `command_execution` 出現 0 次，但那是「運氣和 prompt，不是保證」。**更關鍵的是 Armstrong 那個沒被當成方法論來看的決定**：他把模型的 cwd 指到空資料夾，理由是給它真的工作區它會用自己的 shell 直接讀檔，**整條 tool loop 就變成裝飾品**。也就是說，**任何沒有做這件事的 golden slice 量到的東西，有一部分是內層 agent 的能力，不是這條 loop 的能力。** 而 `aos llms`（OpenAI 相容端點，已經存在）四位全部沒測、四位全部說它可能才是對的路。這是本輪最大的集體盲點。

**`--output-schema` 讓 parser 消失。** Armstrong 說這是他最大的意外收穫，我同意它很舒服（整個 parser 是 `jq -r '.action'`），但它是 codex 專屬旗標，**用它當「解析不是問題」的證據，等於把 golden slice 綁在一家廠商的旗標上**。而且它只讓去程有型別，回程照樣是他自己 `sed` 出來的純文字——他自己說了這條 loop 是不對稱的。

---

### 五、〈規格級的發現〉11 條，逐條表態

我讀了 `core/inst/src/run_exec.cpp`、`docs/aos-folder.md` 第五／六／七／八／十二節、`core/inst/docs/format.md`、`docs/inst-directives.md` 才寫這一段。**判錯的代價是使用者去改一份沒問題的規格**，所以我把「實作與規格對不上」和「規格沒寫」和「參賽者誤讀」分開講。

| # | 判定 | 一句話 |
|---|---|---|
| 一 | **真的（規格沒寫，後果嚴重）** | 我驗過原始碼，`aggregate` 確實在 `claim` 之前 |
| 二 | **真的** | 是第一條加上孤兒現象的必然結果 |
| 三 | **真的，而且是根因** | 規格自己的兩句話互相矛盾 |
| 四 | **真的，但框架要修** | 規格根本沒有建議那個動作 |
| 五 | **真的（格式層）** | 截斷語意與重播互斥，但提案要挑一半 |
| 六 | **真的，但提出的解法只夠一半** | 見上面第四節 |
| 七 | **真的，但是設計錯配，不是實作 bug** | 報告自己就這樣寫了，維持 |
| 八 | **不是對不上** | 實作與規格完全一致，這是功能請求 |
| 九 | **參賽者誤讀（引錯出處）** | 那句話不在規格裡 |
| 十 | **不是對不上，但規格那句話該改** | 該改的方向跟報告寫的相反 |
| 十一 | **真的，但規格自己已經寫了** | 新資訊是 counter，不是 temp+rename |

**逐條講理由。**

**一（退出 3 之前先彙整）——真的，我親自驗了。** `run_exec.cpp` 裡 `aggregate_instructions(kInstPath, ...)` 無條件先跑，`claim_instruction` 才跑，`HandoffState::Busy` 分支在它之後 `return 3`。所以退出 3 的時候 inbox 已經被搬進 `inst.json` 了。規格第六節只寫了「迴圈體就是彙整 → 取件 → 執行」，**從來沒說拒絕啟動之前會不會先彙整**。這是規格漏寫，不是實作寫錯，但後果是**人「跑一次看一眼」這個最自然的動作會搬動狀態**。我認為這是 11 條裡最該先補的一句話。

**二（`.runi` + `mv` 靜默吃掉一份已完成的產出）——真的。** 它是第一條的下游：aggregate 把孤兒的產出發布成 `inst.json`，人再 `mv .runi inst.json` 就把它蓋掉，沒有 warning、沒有備份、退出 0。Evans 在真模型上完整走過四步並貼了 session id 從 1 變 2。這條不需要新規則，它是第一條加第三條的組合爆炸。

**三（`.runi` 存在 ⟺ 有一回合沒跑完，在子行程活得比 parent 久時不成立）——真的，而且是上面兩條的根因。** 規格第 140 行白紙黑字寫著那個不變式，第十二節白紙黑字寫著「子行程各自 `setpgid` 自成一個 process group」。**這兩句話單獨看都對，放在一起就矛盾**——只要子行程活得比 parent 久，`.runi` 就會在「那回合其實完整跑完並且推進了 loop」的時候宣稱「有一回合沒跑完」。Armstrong 的判讀完全正確：沒有人把這兩句放在一起讀過。四位獨立撞到，這是本輪最強的訊號，沒有之一。

**四（規格建議的恢復動作等於重新計費）——現象是真的，但框架要修，而且修完更難看。** 我去查了規格到底建議了什麼：第六節只說「crash 之後**要人來處理**——這是刻意的」，第十二節只說「crash 留下的 `.runi` **要人手動清**」。**規格從頭到尾沒有出現過 `mv .runi inst.json`。** 那個動作是上一份實測與這四位自己補出來的。所以正確的說法不是「規格建議的動作會付兩次錢」，而是**「規格沒有指定任何恢復動作，而人手上僅有的兩個動作都是破壞性的」**：`mv` ＝ 重播 ＋ 重新計費 ＋ 截斷證據，`rm`（規格字面上寫的「清」）＝ 直接丟掉那一批。這條轉給使用者的時候請用這個框架，因為它改的是規格該**新增**什麼，不是該**修正**什麼。

**五（`stdout` 截斷與重播、與 forensic 互斥）——真的，格式層。** `format.md` 寫得很清楚：`stdout` 是「必要時建立並截斷(清空)」、`exit` 是「子行程結束後建立/截斷(清空)」。重播必然抹掉前一次的現場，Armstrong 的 `events.jsonl` 行數與 Pike 的 `raw.txt` 369 → 0 兩份輸出都證明了。**但他的提案我只收一半**：per-attempt 路徑（aos 自動加 attempt 序號）是對的；`{"$opt":"append"}` 是錯的——append 之後那個檔會變成兩次嘗試的串接、沒有分隔符，對機器解析比截斷更糟，`jq` 吃到會出現 Evans 踩過的那個串流陷阱。

**六（`exit` 是回合後的資訊，復原需要回合中的資訊）——真的，但兩位提的解法都只夠一半。** `format.md` 確認 `exit` 是子行程結束後才寫。Armstrong 的描述「aos 的答案永遠是沉默」是準確的。Pike 的「格式裡已經有了，實作只是不讀」**只對便宜的那幾站**，理由見上面第四節，不重複。要補的是 fork 前的 marker，那是格式補不了、只有 `aos exec` 補得了的。

**七（錯誤回饋不到模型，loop 靜默死亡）——真的，但它是設計錯配不是實作 bug，Evans 自己就這樣寫了，維持他的框架。** 規格第六節的彙整規則（壞投遞隔離、warning 進 stderr、不擋住其他人）在**多個獨立生產者投工作**的前提下是對的；agent loop 是**單一有記憶的消費者**，同一條規則就變成「模型永遠不知道自己講錯話」。這條不要當成 bug 報上去，要當成「`.aos` 的設計前提與 agent loop 的形狀不同」報上去——而 Evans 那句「投遞前擋 = 自癒，投遞後擋 = 靜默死亡」直接給出了 `aos agent` 該站的位置。

**八（批次不短路、回合仍回 0）——不是對不上，這是功能請求。** 規格第八節明寫「子行程回非零、被訊號殺掉、逾時——那些都算**一次完成的執行**，回合照樣 0」，第五節從頭到尾**沒有承諾過短路**。所以 Carmack 的 `w2/` 與 Pike 的七站表量到的都是規格規定的行為，實作沒錯、規格沒錯。**但這不減損那個提案的價值**——`"needs"` 是本輪我最想看到被做出來的東西。請把它放進「要加什麼」，不要放進「哪裡對不上」。

**九（`$ref` 拼不了 batch）——參賽者誤讀，引錯出處，這條我要講清楚。** Pike 寫「`docs/aos-folder.md` 第七節說『$ref 能把別的 JSON 檔的一部分拉進來，做 loop 時可能很好用』」。**我 grep 過整份 `docs/aos-folder.md`，沒有這句話。** 那句話出自這場黑客松的題目書（主辦人寫給參賽者的提示），不是規格。而規格本身完全一致：`inst-directives.md` 明寫「**取回來的值必須是字串**，指到陣列或物件就是錯誤」，並且明寫展開成多個 argv 元素是**考慮過之後刻意否決**的，理由是那會讓 `$ref` 從「產生一個值」變成「可能改變結構」。Pike 的三組現場（`UnknownKey` / `FieldTypeMismatch` / 成功）**一字不差就是規格預測的行為**。
**所以：這條不要拿去改規格，會改到一句不存在的話。** 該保留的是它底下那個真正的設計輸入——Evans 講得比 Pike 準：「agent loop 想要的正是那個被否決的『展開』語意」。而 `inst-directives.md` 自己已經留了門：「真的需要時，另設一個明確表達展開語意的指示詞會更誠實。」**現在就是那個「真的需要時」，而且有四份重複的 batch 模板當證據。** 這是一個新指示詞的提案，不是一個 bug。

**十（彙整接受任何沒有狀況後綴的檔名）——不是對不上，而且該改的方向跟報告寫的相反。** 規格第六節的彙整規則本來就是**以後綴定義**的：「只收沒有狀況後綴的投遞」。`185452-0.json` 沒有狀況後綴，所以被收走完全符合規格，實作沒有超出規格。Carmack 把它記成「規格沒寫明、實作接受」——方向反了。**真正該改的是另一句**：第六節說「檔名帶 pid」，而四位的現場證明了 **PID 單獨不夠**（同一個 process 第二次投遞會用同一個名字互蓋，這是上一份實測就有的結論，三位是因為讀過才躲掉的）。所以規格那句該改成「**檔名必須唯一；帶 pid 只是達成唯一的最省事做法，同一個生產者投第二次時必須再加序號**」。

**十一（投遞那一步沒有實作，四位都自己補了一次）——真的，但規格第十二節自己就寫著。** 這不是發現，是一個已知開口被四份獨立資料確認。**新資訊只有一個**：大家補出來的東西不是 temp+rename（那是規格已經描述的三步協定），而是**防碰撞的 counter**，而且三位明說他們只是因為讀過前人的現場才知道要加。這強化的是優先序（有第二個生產者之前就該補），不是必要性。

---

### 六、哪個坑是致命的、哪個只是麻煩

**致命的只有一個：孤兒 ＋ `.runi` 的組合。**

判定它致命的理由不是它最痛，是**它是唯一一個從世界內部繞不過去的**。看四位分別做了什麼：Armstrong 寫了冪等守衛，**輸給了 race**（窗口等於一次模型呼叫，好幾秒）；Evans 完整走過四步，**產出被靜默刪除**；Carmack 照規格的精神做，**付了兩次錢**；Pike 看穿之後**發現沒有任何安全動作可做**。四種不同的架構、四種不同的處理方式、四個都沒解決。**其他每一個坑都至少有一位參賽者用 shell 繞過去了，只有這一個一個都沒有。**

它為什麼擋住整個方向：T5 的主張是「agent loop 不需要新的 C++」。四位證明了**跑**不需要。但這條 loop 是要無人看管跑、而且每一步都在花錢的——在這個前提下，**「崩潰之後怎麼辦」不是可選項，而它需要 `aos exec` 在 `fork` 之前寫一個東西，那就是 C++。** 所以這個坑決定的不是某個功能做不做，是 `aos agent` 這支子命令**存在的理由**：它不是為了讓 loop 好寫（loop 只要一百行 shell），是為了讓 loop 壞掉之後有救。

**只是麻煩、繞得過的（都有人繞過了，不要拿它們去排 roadmap）**

| 坑 | 誰繞過了、怎麼繞 |
|---|---|
| `--loop` 不會停 | Pike：driver 把 PID 寫進世界，世界裡的 `tools/stop` 送 SIGINT，**空轉從 10s 變 0s** |
| 批次不短路 | 還沒人繞，但 Pike 的 `bin/gate` 不需要改 C++ 就做得到，下一輪會有數字 |
| tool registry 不存在 | Evans 的具名 registry 有效，還順便讓模型自我修正 |
| claude 包 markdown 圍籬 | `sed` 剝殼，脆但有效 |
| codex 的 MCP stderr 噪音 | 別用 stderr 判斷成敗，改看 `-o` 檔在不在（Carmack）或退出碼 |
| codex 旗標順序 / `resume` 要 `--skip-git-repo-check` | 寫進文件就結束了 |
| `jq` 預設吃串流 | `jq -e -s 'length==1'`，Evans 已經給了正確寫法 |
| 39 次手打路徑 | 一支十幾行的產生器（Pike 下一輪要量） |
| `deliver` 的 counter | 12–13 行 |
| 中間檔只留最後一回合 | 自己 `cp` 快照，Armstrong 就是這樣才看到證據的 |

**中間地帶，我要單獨標一個：`parallel: true` 現在只是麻煩，但它會在你不注意的時候變致命。** 四位全部繞開它，兩位（Carmack、Evans）推理出「檔名協定沒有 correlation id，一開就會壞」。現在不痛是因為四位的任務都是一次一個工具——**而真模型很常一次要求兩個**。所以這件事的正確處理不是「等它痛了再說」，是**現在就決定 tool_call_id 的形狀**，因為它是協定不是實作。Evans 下一輪會去拿那個「果然壞了」的現場。

---

### 七、哪份回報不可信

**沒有一份整體不可信，我不打算為了交差捏一個出來。** 四位全部貼了真指令真輸出，沒有人宣稱做完了卻拿不出現場，兩位（Pike、Armstrong）還主動把自己沒做、做壞、做輸的地方寫進報告。這一輪在誠實度上是乾淨的。

**但有兩個「講了、沒看」的斷言我不會拿去用，兩個都是同一種病：斷言一個機制，卻沒有任何輸出。**

**1. Evans（p4）的「pi ❌ 只能塞 argv」——這一條有後果，優先處理。**
他沒有貼任何失敗的嘗試，而 Carmack 貼了 `printf ... | timeout 120 pi -p --mode json --no-tools --no-session` → `exit=0` → `REAL_PI_OK`，Pike 獨立貼了 `printf ... | pi -p --no-tools --mode json` 也成功。**兩份現場對一句沒有現場的斷言。** 讓我判它不可信的不是他弄錯了（弄錯很正常），是**他在上面疊了 ARG_MAX 論證，並拿它當 golden slice 選 codex 的第一條理由**——一個沒查證的前提直接變成了 OPEN #6 的答案。而這份報告其他每一處都是「我以為 vs 實際」的自我修正，唯獨這一條沒有走那個流程。**這句話在被重測之前不能進規格。**

**2. Armstrong（p3）的「`~/.codex/sessions/` 是空的，session 實際存在 sqlite」——後果小，但錯得更直接。**
零輸出。Carmack 貼了實際存在的 rollout 檔完整路徑加 `lines=10`，Pike 獨立確認同一條路徑。「存在 sqlite」這半句更是純粹的推測，他連查都沒查。他其他地方的自我約束好到可以當範本（連 codex 是不是逐事件 flush 都主動加但書說「不敢當成通例」），這一條是唯一的破口。

**這兩條要用同一句話講給他們聽**：你可以寫「沒問到」，你可以寫「不知道」，這兩種寫法我一分都不扣；**你不能寫一個你沒看過的機制。**

---

### 八、如果現在就得拍板：`aos agent` 第一版的三件事

**先做第 1 件。** 另外兩件今天就能用 shell 寫出來（四位都寫了），第 1 件不行。

**1. 崩潰之後的可判定性。**（**先做這一件**）
兩半，都要：
- **`aos exec` 在 `fork` 之前落盤一個 running marker**，內容至少是「批次裡的第幾筆」＋「子行程 pid」，回合正常結束時清掉。這是唯一一個只有 `aos exec` 做得到的動作——它是那個時間點上唯一活著的東西。
- **一支唯讀的 `recover`**，把現場攤開：`.runi` 裡有哪幾筆、每一筆的 `stdout`／`exit` 現況、**marker 指的那個 pid 還活不活著**（`kill -0`）。它的第一個職責不是重播，是 Evans 講的那件事：**先告訴人 inbox 裡有東西已經被搬走了**。重播必須是明確要求的動作，不能是預設。而且它必須內建 Armstrong 那條：**孤兒還活著就拒絕動作**，因為那正是會付兩次錢的狀態。

**先做這件的理由**：它是唯一有金額的（三份重複計費的現場）、唯一四位都繞不過的、而且**晚做的成本是已經花掉的錢**，不是多打的字。另外兩件晚做只是繼續打字。

順帶把第一條規格漏洞一起補掉：**退出 3 之前不要彙整**，或者至少在規格裡寫明它會。人「跑一次看一眼」不應該搬動任何東西。

**2. `aos agent step`——回合模板 ＋ 投遞 ＋ 投遞前驗證，一支。**
把四位重寫最多次的三件事收成一個動作：說出「下一批要跑什麼」（模板只寫一次，四位各抄 2–3 次的那坨字面 JSON）、temp+rename 投遞（含那個只有讀過前人現場才躲得掉的 counter）、**以及 rename 之前驗一次，驗不過把錯誤字串回傳給呼叫者**。最後那半是整支的靈魂：它把 Evans 的 `{"path":123}` 從「loop 靜默死亡」變成「模型下一回合自己改對」。

**3. `aos status --json`。**
讓「做完了」「沒事做」「壞掉了」「正在想」四種處境從外面分得出來，並且給 `--loop` 一個終止條件。現在這四種都是 `exit=0`，而 Pike 證明了終止條件只能放在世界外面的行程裡、還得先把 PID 寫進世界——那是「世界在檔案系統上」這條原則身上的一個洞。

**以及一條不做什麼：不要為了 LLM 往 instruction 加欄位。** 四位包了三支不同廠商的 agent CLI，`stdin`／`stdout`／`stderr`／`exit`／`timeout_ms` 五個欄位一個都不用加。**唯一值得考慮的新欄位是 `"needs"`**，而它跟 LLM 無關——它是「這是一條管線」這件事的最小表達，而且下一輪 Pike 會先用 `bin/gate` 在不改 C++ 的前提下證明它夠不夠用。**等那份輸出再決定。**

---

## 下一輪的資料包

> 資料員備的參考資料，每一條都附 repo 內或兄弟專案的路徑。**不含設計意見**；評委在〈五、規格級的發現 11 條，逐條表態〉判為誤讀的那幾條（九、十），這裡只給正確方向的出處，不替被否掉的說法找佐證。

### 1. 這輪卡住的清單

**四位共同卡住的**

- **孤兒 ＋ `.runi` 的組合，四種架構四種處理方式，四個都沒解決**——Armstrong 的冪等守衛輸給 race、Evans 的產出被靜默刪除、Carmack 付了兩次錢、Pike 判定沒有安全動作可做。
- **`aos llms` 四位全部沒測**，四位都在報告裡說它可能才是對的路（Carmack 稱它為「我這輪最大的盲點」）。
- **`aos tooljson` 四位全部沒接**，Pike 與 Evans 都看到 `aos --help` 裡有它、都自己手寫了 `tools.json`。
- **`parallel: true` ＋ tool_call_id 四位主動繞開**，兩位（Carmack、Evans）只推理出「檔名協定沒有 correlation id，一開就會壞」，沒有現場。
- **durability 只測到 SIGINT／SIGKILL 等級**，斷電、`fsync` 四位都沒測，Armstrong 明寫「所以我不能宣稱任何 durability 保證」。
- **session resume vs 每回合重建 context（OPEN #19）沒問到**，Evans 明寫三支都有 resume 介面但他全部沒用。

**p1（Carmack persona）**

- 卡在**建議 golden slice 鎖 pi，而 pi 是他唯一沒有接進 loop 的那支**——整份報告唯一一個沒有資料撐著的結論。
- 卡在 **`recover.sh` 只有構想**：他有「兩次 `thread_id`、31,316 input token、`total_model_calls=4`」的現場，但還沒把它做成可驗收的測資（驗收數字是模型呼叫從 4 降回 3）。

**p2（Rob Pike persona）**

- 卡在 **`"needs"` 只有提案與七站 exit 表，`bin/gate` 還沒做出來**——`mdl=7` 之後 `last`／`note`／`act` 照跑、transcript 被一行空的「模型: 」汙染，但還沒有「跳過之後」的對照組。
- 卡在 **`aos exec --resume`（跳過 exit 檔存在且為 0 的那幾筆）解不掉最貴的那一筆**：`exit` 檔是 parent `wait` 完才寫的，缺失同時代表「沒跑」與「跑完了但沒人收屍」。
- 卡在 **`aos llms` 自認第一輪刻意繞過**，理由是「用內建的那支會把題目繞過去」。

**p3（Joe Armstrong persona）**

- 卡在**冪等守衛 `test -f final.json` 輸給 race**，窗口長度等於一次模型呼叫（好幾秒），兩次實測一次撞到一次沒撞到。
- 卡在 **`tool.sh` 沒有冪等守衛、也還沒把它踩爆**——他自己標明這一輪沒踩到「純粹是運氣」，因為選的工具剛好是唯讀的。
- 卡在 **「`~/.codex/sessions/` 是空的，session 實際存在 sqlite」是零輸出的斷言**，與 p1、p2 各自貼出的 rollout 檔路徑衝突。

**p4（Julia Evans persona）**

- 卡在 **「pi ❌ 只能塞 argv」沒有失敗現場**，卻疊了 ARG_MAX 論證並拿它當 golden slice 選 codex 的第一條理由。
- 卡在**投遞前驗證只做了一半**：`nuke_everything` 在投遞前被自己的 registry 擋下、模型自我修正；`{"path":123}` 在投遞後變 `.bad`、loop 靜默死亡——後半還沒有「投遞前擋住之後模型改對」的 transcript。
- 卡在 **tool_call_id 沒有形狀**：三個檔（`.out`／`.err`／`.exit`）沒有任何東西把它們綁在一起。

---

### 2. repo 裡已經有答案的

**孤兒 ＋ `.runi`（P0，四位共同）**

- **兩句矛盾的話各自在哪**：不變式在 `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉（「`.runi` 存在 ⟺ 有一回合沒跑完」，以及「行程死掉（crash、被 kill、斷電）`.runi` 就會留著」）；`setpgid` 那句在同檔〈十二、留給實作決定的〉的子節〈已經被實作決定的〉（「子行程各自 `setpgid` 自成一個 process group，所以終端機的 Ctrl-C 打不到它們」）。同節還寫了 `--loop` 的 `SA_RESETHAND`：**第二次信號直接殺掉行程，那時 `.runi` 會留著**。
- **`aggregate` 排在 `claim` 之前，文件層就查得到**：`wf/workflows/common/code-map.md` 的 `run_exec.cpp` 那一列寫著「單回合：進入 world、驗版本、**aggregate → claim → execute batch → release**，並把結果映成診斷與 0／1／3」。配 `core/inst/docs/handoff.md`〈取件與釋放〉：`claim_instruction()` **先拒絕既有 `.runi`，再完整讀取 base**，`release_instruction()` 應在所有子行程（含 parallel thread）結束後才呼叫。
- **同一個孤兒現場上一次就有**：`wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉——前景 `timeout -s INT` 得到 `exit=130`／`runi=yes`／`child_exit=missing`，六秒後 `state=completed` 但 `child_exit` 仍 missing，下一次 `aos exec` 回 3。**同節第一段還保留了一個無效的 harness**：背景 job 繼承忽略 SIGINT，`kill -INT` 根本沒打中（Carmack 這輪重踩了一次）。
- **`.runi` 該升級成租約，三位獨立提過，而且已經有一個形狀限制**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 2 條——`.runi` 現在的內容**就是那批 JSON**，`cat` 一下就知道卡的是哪一批，**包一層 header 會毀掉這點**；所以主張 receipt 放旁邊（`inst.json.runi.receipt`），且**先寫 receipt、後 rename `.runi`**。同節第 5 條另問「`.runi` 鎖的是那一批還是那個世界」，並指出上面每一條提案都預設了一個答案卻沒人講明。
- **租約要原子建立，規格已經點名了工具**：`docs/aos-folder.md`〈十二、留給實作決定的〉子節〈仍然開著的〉——「`.runi` 的檢查與 `rename` 之間有 TOCTOU……要真的原子化得用 `renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink`」。
- **`timeout_ms` 那條路上孤兒早就有解**：`core/inst/docs/exec.md`〈逾時與行程群組〉——到期先對**整個子行程的行程群組**送 `SIGTERM`、給 2000 ms、仍活著就 `SIGKILL` 整個群組，「打群組是因為忽略 `SIGTERM` 的孫行程才殺得掉」。也就是說機制存在，缺的只是 parent 被外部信號砍掉那一條路徑。
- **崩潰後的架構共識與硬邊界**：`wf/workflows/workshop/records/agent-loop-architecture.md`〈斷點續跑的硬邊界：本機可以原子，遠端付費不能假裝 exactly-once〉——「**rename 保發布，不保任意 LLM CLI 恰好付費一次**」，並列出可安全自動恢復的只有兩種（provider 接受同一 idempotency key／provider 能按 request ID 查回原結果）。同檔〈明顯的坑〉有兩條正中這輪：「**先呼叫 LLM，成功後才開始記 call**」與「**把 `unknown` 自動當失敗重跑**」。

**「不重複付錢的復原」與 recover 的形狀（p1、p3）**

- **policy A／B／C 的對照上一次就跑過**：`wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉——假 provider 在效果已發生、結果未回時斷線，policy A（停）ledger 留 1、**policy B（按 provider key 查回）exit 0 且 ledger 仍是 1**、policy C（盲目 retry）ledger 變 2。Armstrong 這輪用 `codex exec resume <thread_id>` 拿回答案，就是 policy B 的真模型版。同節上半還有 request／effect／result.temp 三個時間點 × SIGINT／SIGKILL 的六格輸出。
- **`aos recover` 的介面已經被寫出來過**：同檔〈痛在哪：可直接寫成子命令的需求〉的 `aos recover [WORLD]` 一節——「命令不能假裝有 program counter；它應先**唯讀列出** `.runi`、每筆 exit/result 證據與**可能仍活著的未知子行程**」，動作分成 `--replay`／`--abandon`／`--adopt RECEIPT`，並明寫「**沒有足夠證據時預設必須停住，而不是自動重播**」。
- **同節的 `aos deliver`／`aos status --json`／`aos agent step`／`aos agent emit-context`** 四支也都有段落，`agent step` 那段列出了要保存的 phase：`request-published → effect-started → result-temp → result-published → next-delivered`。
- **roadmap 自己已經標了矛盾**：`docs/roadmap.md`〈T5 — agent loop：**不需要 `core/llms`**〉底下那個 ⚠ 區塊——驗收的「中途 `Ctrl-C` 之後再 `aos exec` 一次能從斷點繼續」與 D6 互相矛盾，並列出兩條擇一的路（改措辭承認續跑＝回合邊界／長出真正的復原路徑），最後一句是「**在拍板之前，不要照這條驗收去實作**」。

**停止條件與退出碼（p2、p4、`aos status --json`）**

- **`--loop` 其實已經有一個停止條件**：`docs/aos-folder.md`〈十二／已經被實作決定的〉——「**回合失敗時 `--loop` 不停**，繼續下一回合。**只有退出碼 3（`.runi` 已存在）會讓迴圈退出**」。`docs/roadmap.md`〈T4 — 迴圈：`aos exec --loop <毫秒>`，不做 `core/daemon`〉的〈注意〉段也寫著 crash 之後迴圈會永遠拒絕啟動是預期行為。
- **退出碼契約與它的已知缺口**：`docs/aos-folder.md`〈八、退出碼〉四碼表（0／1／2／3），明寫「子行程回非零、被訊號殺掉、逾時——那些都算一次**完成**的執行，回合照樣 0」；`docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉是完整契約；`wf/workflows/common/gotchas.md`〈使用 aos〉已經記過「`aos exec` 的退出碼不反映子行程成敗」。
- **「把無事可做從 0 裡拆出來」與「停止條件搬回檔案系統」兩條提案都已成文**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 3 條（退出碼只帶四個類別 ok／無事／busy／壞了，細節寫成 receipt）與第 4 條（**`--loop` 的停止條件明文寫成「回合開頭自己 `stat` 一次 `.runi`」**）。
- **上一次實測列的 status 狀態名**：`wf/workflows/experiments/t5-agent-loop.md`〈`aos status --json [WORLD]`〉——`ready`／`running`／`blocked-runi`／`bad-delivery`／`no-work`／`unknown-effect`，並明寫「不要把 prompt 政策塞進 status」。
- **`--loop` 抱著壞世界一直轉的風險已被列為「壞 2」**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈壞（六條）〉第 2 條。

**批次不短路 ／ `"needs"`（p2）**

- **這不是實作與規格對不上，規格從沒承諾短路**：`docs/aos-folder.md`〈八、退出碼〉與〈五、回合語意〉；`core/inst/docs/exec.md`〈狀態與失敗〉寫得最白——「非零的子行程狀態、訊號終止、PATH 找不到、設定階段狀態，或逾時，都是一次已完成的執行……**它不會中止後續的記錄**」。
- **真要把 `"needs"` 加進 format，動到哪幾個檔已經列好了**：`wf/workflows/common/code-map.md`〈新增一個 instruction 欄位〉——① `inst.hpp` 的 `inst_t` 加欄位；② `format.cpp` 的 `known_key`／`encode`／`decode` **三處都要加**；③ 需要的話 `inst.h` 加 C ABI 存取子＋`capi_instruction.cpp`；④ `exec.cpp`／`spawn_prep.cpp` 視語意決定。
- **`exit` 欄位是誰在什麼時候寫的**：`core/inst/docs/exec.md` 欄位對應那段——「非空的 `exit` 會由**父行程在等待完成後**建立／截斷，並寫入回報的十進位狀態」；`core/inst/docs/format.md`〈綱要(schema)〉的欄位表是同一件事的格式層說法。

**`$ref` 與重複的批次模板（p2、p4）**

- **規格的原話與那扇留著的門**：`docs/inst-directives.md`〈四、`$ref`〉——「**已定：取回來的值必須是字串。** 指到陣列或物件就是錯誤」，以及括號那段：「考慮過讓 `argv` 的元素可以展開成多個……但那會讓 `$ref` 從『產生一個值』變成『可能改變結構』……**真的需要時，另設一個明確表達「展開」語意的指示詞會更誠實**」。同檔〈五、適用範圍〉是可放指示詞的位置表。
- **新指示詞的硬門檻**：`docs/aos-folder.md`〈七、instruction 的格式〉最後一段——彙整會把每份投遞經格式層完整往返一次，所以「**還沒解析的指示詞必須能原樣寫回 JSON**」，否則會在彙整那一步被無聲吃掉。`core/inst/docs/handoff.md`〈彙整規則〉重述了同一條。
- **要新增哪些錯誤狀態**：`docs/inst-directives.md`〈七、對現有契約的影響〉已列（不認得的 `$xxx`、多於一個鍵、值不是字串、`$ref` 目標不存在或逃出 root……）。

**投遞、檔名與投遞前驗證（p4，以及四位都重寫過的 counter）**

- **檔名規則規格層寫得很精確**：`core/inst/docs/handoff.md`〈彙整規則〉——「只接受**第一個副檔名就是結尾**的 `<name>.json`；`123.json.temp`、`123.json.bad`、`name.part.json` 都會跳過」。這解釋了 Carmack 的 `185452-0.json` 為什麼被正常收走。判定函式是 `core/inst/src/handoff.cpp` 的 `is_delivery_name()`。
- **PID 不夠用，上一次就有現場**：`wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉——同一 shell 連做兩次 temp+rename，`first_exists=no`，第一份靜默遺失；同節還有「直接寫 ready、不經 `.temp`」讓半份 JSON 被 rename 成 `.bad` 的現場。
- **兩個 producer 各投 1,000 件的壓力數據已經有人跑過**：`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 2 輪紀錄〉——共用本地序號時**遺失 1,000 件**，改用全域唯一 ID 時「遺失、重複、覆蓋、明確失敗皆為 0」。
- **投遞前驗證是四位獨立的共識，錯誤該長什麼樣也定了**：`wf/workflows/workshop/records/tool-interop.md`〈誰驗證、驗不過怎麼回〉——「四位獨立地都要求 Deliver 在 rename 前驗證完整 payload；驗不過就整批失敗，不發布任何可見檔案」，並劃清 `.bad` 的邊界（**它只隔離繞過 Deliver 直接塞檔的壞檔**）。〈給模型看的錯誤訊息〉給了共同的 JSON 欄位：`code`／`record`／`pointer`（JSON Pointer）／`expected`／`actual`／`hint`。
- **`aos deliver` 的形狀、發布五步與退出碼分歧**：同檔〈`aos deliver` 的合成版 `--help`〉、〈寫到哪裡、檔名怎麼配〉（四位獨立地都給出同一個五步發布順序，**四位都沒有只靠 PID 保唯一**）、〈退出碼還沒有共同編號〉（四份不同編號的對照表）。
- **`--key` 目前不能宣稱冪等**：同檔〈`aos deliver` 的合成版 `--help`〉末段——aggregate 會刪除投遞檔，沒有 ledger 就不能承諾跨回合 Already／Conflict。

**tool registry ／ 回程的型別（p2 的第 3 次轉換、p3 的不對稱）**

- **`aos tooljson` 到底解決了多少，有明確答案**：`core/tooljson/docs/format.md`〈CLI〉——S1 只有 `aos tooljson list <spec.json>` 與 `check <spec.json>`，「`run` 尚未存在」。〈`exec` 配方的載入期驗證〉開頭寫著 `ExecBody::run()` **固定回 `Error: exec execution is not implemented in S1`，不會 fork 或 exec**。也就是：**格式與驗證有了，執行沒有。**
- **「對的那一種 registry」的欄位清單**：同檔〈`exec` 配方的載入期驗證〉列出 `exec`／`argv`（binding 只接受 `position`／`flag`／`separate`／`repeat`）／`stdin.param`／`stdout.clip`／`stderr.mode`／`ok_exit`／`timeout`／`cwd`／`limits`／`source`；〈外殼〉列出 schema 形狀的載入期檢查與「同一檔內 `function.name` 不得重複、多檔比照 `PATH` 先出現者獲勝」。
- **展開錯誤就是要餵回模型的那句話**：同檔〈模型參數展開〉——「模型給錯參數時回 `Error: ...` 字串，**呼叫端應把它直接當 tool message 送回模型**，而不是丟例外」，並列出八條展開規則（含「任何單一 argv 項目超過 131072 bytes 都拒絕」）。
- **回程的截斷語意**：同檔〈文字收尾〉——`decode_output()` 遇 NUL 只回 `(binary output, N bytes, not shown)`，`clip_output()` 超過限制保留 head 或 tail 並標明省略的字元數。這是 Armstrong 手寫 `sed -n '1,60p'` 的規格版。
- **具名工具映射的既有詞義**：`wf/workflows/workshop/background/agent-loop.md`〈tool allowlist（具名工具映射）〉與〈driver 與 adapter〉。

**`aos llms`（四位的集體盲點）**

- **子命令形狀與直接打 LM Studio 的現成範例**：`core/llms/README.md`〈子命令〉——`aos llms ask [--model M | --preset P] [--stream] [--system S] [--url U] [--key K] <prompt>` 與 `aos llms models [--url U] [--key K]`；`--url` 預設 `http://localhost:4000`，但**proxy 不是必需品**，README 直接給了 `aos llms models --url http://localhost:1234/v1` 與 `aos llms ask --url http://localhost:1234/v1 --model … "你好"`。**注意 prompt 是位置參數，CLI 這一層沒有 stdin、沒有 `--json`**。
- **能力查詢為什麼要兩個端點**：同檔〈能力、工具與 presets〉——`LLM::models()` 問 `/model/info`（LiteLLM 專屬）與 `/v1/models`（每個 OpenAI 相容端點都有）的聯集，「少了 `/v1/models` 這一半，直接打 LM Studio 之類的端點會得到一片空白」。
- **它掛在哪、tool call 在函式庫層是什麼形狀**：`wf/workflows/common/code-map.md` 的 `aos::llms` 段（`core/llms/` → `libaos_llms.so`，`app/` 掛 `aos llms ask|models`，成功路徑會連網）；`core/llms/README.md`〈串流 Reply〉說明 `Reply` 的 `calls[].args` 是未解析的合法 JSON 字串、參數不合法時 `args` 為空而原文放 `args_raw`。
- **T6 已經把它的位置畫好了**：`docs/roadmap.md`〈T6 — 把 LLM 內化：`aos llm exec <folder>`〉——`["aos","llm","exec","."]` 對 `aos exec` 而言只是普通 POSIX 指令，和 T5 裡那支外部 CLI 站在完全相同的位置。同節也寫著 D4 的「先不動」可能是「永遠不用動」。
- **不要在 T5 就用它的理由，roadmap 自己有寫**：`docs/roadmap.md`〈D4 — llms／tooljson 是原地改造還是重長一次？〉。

**`parallel: true` ／ tool_call_id（p4）**

- **語意在兩個地方各寫了一次**：`core/inst/docs/format.md` 欄位表的 `parallel` 那一列（「為 `true` 時 CLI 以獨立 thread 執行這一筆，不等它完成就啟動下一筆；**整批結束前仍會等待它**」）；`core/inst/docs/exec.md` 開頭第三段（「整批返回前會 join 全部 thread，因此**批次邊界仍然會等待每一筆完成**」）。`docs/roadmap.md`〈D3 — 阻塞還是非阻塞？〉是已定的決策紀錄（回合內並行，回合邊界不變）。
- **correlation ID 與 receipt 是兩件事**：`wf/workflows/workshop/background/delivery-contract.md`〈correlation ID（串接編號／request ID）〉與〈receipt（收據／completion record）〉；同檔〈TOCTOU（先檢查、後使用的競爭窗）〉是 Armstrong 那個窗口的既有詞條。
- **parallel tools 的 join 時機還沒定**：`wf/workflows/workshop/records/agent-loop-architecture.md`〈還在生長的想法〉的「**parallel tools 的 join 時機未定**」一段，以及〈大家問出來的問題〉表格裡研究人員那一列。

**pi 吃不吃 stdin（p1、p4 的分歧）**

- **repo 內第三份與「只能塞 argv」相反的資料**：`wf/workflows/workshop/records/tool-interop.md`〈pi 與本場的已知前提〉——「對行程整合有 `-p/--print`（**可吃 stdin**）」，同段也記了 skill 搜尋路徑與 session／resume／fork 介面。
- **上一次實測時 pi 還沒裝**：`wf/workflows/experiments/t5-agent-loop.md`〈6. 真 agent CLI〉（`pi path=missing command_v_exit=1`）與〈OPEN #6：golden slice 先用哪支真 agent CLI？〉——所以那一輪的排除是**環境可用性**，不是產品選擇。

**codex 的細節（p3 要重寫的那句、以及旗標順序）**

- **`~/.codex/sessions/` 的路徑主辦人自己記過**：`wf/workflows/hackathon/gotchas.md`〈codex〉——「還可以從 `~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl` 的**檔名**撈回來（UUID 就在檔名裡），但四位平行時無法分辨誰是誰」。同節還寫著 **session id 的 key 是 `thread_id`，不是 `session_id`**，且 `grep` 沒中是**無聲失敗**。
- **`codex exec resume` 的旗標位置**：同節——「`--json` 與 `-o` 有支援，但**要放在 `resume` 前面**」，`-s`／`-C`／`--add-dir` **不吃**（沙盒與工作目錄從原 session 繼承），「所以**場地必須還活著**」。同節另記 arena 不是 git repo，要加 `--skip-git-repo-check`。

**session resume vs 每回合重建（OPEN #19）**

- `wf/workflows/workshop/background/questions-agent-context.md`〈題目：第一版預設 `--no-session` 從 world 重建，還是優先使用 agent session 作續談快取？〉是這一題的原題；同檔第一題是 stdin 要吃 request file 還是 `status --json`（OPEN #18）。
- `wf/workflows/workshop/records/tool-interop.md`〈coding agent 的 session 只可當快取〉——四位都只接受 session 作可丟快取，遺失後必須能從 world 重建。同節也記了 `--session-dir` 這個旗標**未經核對，不可寫進 skill**。

**durability 的分層（四位都沒測，但詞義已經分清楚）**

- `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉把 rename 的可見性原子與 file/directory fsync 的斷電承諾分成兩層；同檔〈Effect（外部效果／capture／invoke）〉〈idempotency key（冪等鍵）〉〈ledger（耐久帳本／歷史表）〉〈`unknown`（無法判定外部效果）〉是 recover 動作命名的既有詞義。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉已明列 power loss、NFS、非 Linux filesystem 與裝置快取都沒測；`verdicts.md`〈第 3 輪／路線判斷〉那段的原話是「**power-cut 沒測則是證據缺口，在補測前不准把 visibility 叫 durability**」。

**同一場黑客松的前例（格式與判準都可以照抄）**

- `wf/workflows/hackathon/records/core-scope/packs.md`〈下一輪的資料包〉是同一份四塊結構的前例，裡面很多條目與這輪重疊（`.runi`、孤兒、delivery 命名、receipt）。
- `wf/workflows/hackathon/records/core-scope/verdicts.md`〈第 2 輪／路線判斷〉與〈第 3 輪／路線判斷〉——那一場的評委也把「無 query／idempotency 的遠端 effect」判為**唯一致命的坑**，其餘（`.runi` 太粗、孤兒 process group、child 失敗但 `aos exec` 回 0）都判為麻煩。

---

### 3. 兄弟專案裡可以抄的

根目錄 `/home/lorkhan/repo/simple_tools/`。

**`freepy/agentloop/` — 同一個作者用 Python 寫過同一件事**

- **`freepy/agentloop/loop.py` 的 `advance(bot, dispatch, prompt, handle, images)`**：一次呼叫只做「一個 Step **或**一整批 tools」，做完就返回，不 park——這正是 `aos exec` 單回合的形狀。同檔 `run()` 是「一直 `advance()` 到 Round 結束」的外殼，`_perform_all(calls, dispatch, seed)` 是**依序**跑完一批 tool call 並以 `call["id"]` 當 key 收結果。
- **`freepy/agentloop/calling.py` 的 `perform(dispatch, call)`**：整支的契約是「**永遠回一個字串**，它會直接變成送回模型的 tool message」，四種壞法各翻成一句模型讀得懂的話——`args_raw` 存在（JSON 壞掉）、沒有這個工具（**附上可用工具清單**）、參數對不上簽名、工具自己炸了。註解裡那句「模型讀到 `Error: ...` 會自己改一次再試，讀到 traceback 只會整條斷掉」就是 Evans 的自癒論證。同檔 `_mismatch(fn, args)` 特別註明**先問簽名再叫**，否則工具內部自己丟的 `TypeError` 會被誤報成參數錯，「模型就照著那句假話去改一個本來沒問題的參數」。`_text(value)` 與 `MAX_OUTPUT = 30000` 是回程截斷。
- **`freepy/agentloop/handle.py`**：`Handle.stop` 的具體原因（`done`／`length`／`budget`／`input_tokens`／`output_tokens`／`engine`／`error`）、`phase`、`done()`、`pause()`／`resume()`／`end()`、`_commit_step()`／`_commit_tools()` 兩個提交點、`_park_unlocked()`。**「做完了／沒事做／壞掉了／正在想」在這裡是四個不同的欄位值，不是同一個 exit 0。**
- **`freepy/agentloop/ROUNDS.md`〈固定術語〉**：Round 與 Step 的定義（「一次 `ask() → message` 是一個 Step；**工具執行發生在兩步之間，不另算一步**；一步要求十個工具仍只算一步」）——直接對到 Pike 那句「回合數 ≠ agent 步數」。同檔〈Round 狀態機〉是 `idle → ready → running_step → ready → running_tools → …` 加 `waiting`／`paused`／`completed`／`error`；〈自然靜止與 `auto_finish`〉把「模型沒有 tool calls」「`run()` 返回」「Round completed」**明講成三件可以分開的事**；〈固定的 operation 與 callback 邊界〉的 `CONTINUE`／`PAUSE`／`END`（優先序 `END > PAUSE > CONTINUE`）是「停止＝不投遞」的有名字版本。
- **`freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉**：Step 中斷分成「`Reply` 沒有留下任何 message → 回滾、不計 Step」與「已留下完整或部分 message → 保留、計一個 Step」；tool call 中斷「**當作工具失敗……已產生的外部副作用仍可能存在，錯誤結果不代表 rollback**」。〈整個實例被強制終止〉一句話劃界：「Ctrl-C、SIGTERM 或直接殺 process 屬於不可抗力。這種情況**不做收尾保證**」——這是拿來對照「aos 該承諾到哪一級」的能力邊界，不是 crash recovery 實作。
- **`freepy/agentloop/CONTROLLER.md`〈最小 API〉**：`.advance()`／`.run()`／`.state`／`.wait(*states)`／`.send(prompt, finish=False)`，以及「同一個 Controller 只能選一種 runner 樣式」。〈明確不負責〉明列它不做持久化、Task queue、worker lease、副作用 recovery——**照抄它的功能可以，照抄它的可靠性不行**。
- **`freepy/agentloop/LIMITS.md`〈內建 Limits 負責什麼〉**：Step 數、工具總呼叫次數、單一工具次數、工具白名單、模型白名單、經過時間、input／output token——一份現成的「停止條件」清單，全部透過公開的 `after_step` callback 實作。〈合作式限制〉明寫它不切斷進行中的請求、不回滾副作用。
- **`freepy/agentloop/threading/`** 與 **`freepy/agentloop/limits/`** 是兩個只用公開 API 的可選子專案，可作「核心不為政策保留分支」的分層樣本。

**`freepy/llmkit/` — tool call 的協定形狀**

- **`freepy/llmkit/llms/TOOLS.md`〈工具〉**：`reply.calls` 的形狀是 `[{"id": ..., "name": ..., "args": {...}}]`，結果以 `{c["id"]: ...}` 回填，並明寫「一步可能吐出**好幾個**呼叫……`tool_results` 的 **key 少一個下一步就對不起來**」——這就是 Evans 要的 tool_call_id 的最小形狀。同節也寫了「`args` 的 JSON 壞掉不會丟例外，會給空 dict 並附上 `args_raw`——**執行前記得看一眼**」。〈欠著的工具呼叫〉的 `bot.pending_calls` 是「這一輪還欠哪幾個結果」的現成查詢。〈tool_choice：逼它叫工具〉是 `auto`／`none`／`required`／指名四個值的對照表。
- **`freepy/llmkit/tooljson/`**：`FORMAT.md`、`EXEC.md`（〈exec〉〈argv〉〈stdin / stdout / stderr〉〈ok_exit〉〈cwd / timeout / limits / source〉）、`PYTHON.md` 是 `core/tooljson` 那份 C++ 格式的**Python 參考實作**；`invoke.py`、`args.py`、`exec_type.py`、`registry.py`、`text.py` 是實際執行的那一半——也就是 C++ S1 明講「尚未實作」的 `run`。
- **`freepy/llmkit/llms/USAGE.md`** 是 token／成本欄位的位置；`freepy/llmkit/live_smoke.py` 是打真端點的冒煙腳本（拿來對照 `aos llms` 要怎麼被冒煙）。

**`freepy/base_tools/` 與 `freepy/exec_tools/` — 具名 registry 的兩種來源**

- **`freepy/base_tools/tools.json`**：一份完整的 OpenAI function schema 陣列（`read_file`／`write_file`／…），每個都帶 `_extra`（`_version: "0.1.0"`、`_type`、`module`／`attr`、以及 `source.size`／`mtime`／`sha256`）。要手寫 `tools.json` 的人可以直接照這份的形狀寫，**含 stale 偵測要的那三個欄位**。實作在 `freepy/base_tools/specs.py`、`files.py`、`edits.py`、`paths.py`、`shell.py`。
- **`freepy/exec_tools/README.md`**：從使用者明確指定的目錄讀 `.specs/*.json` 組成 `(schemas, dispatch)` 的薄 discovery 層——`tools(paths)`、`scan()`（回 `specs`／`missing`／`errors`）、`spec_path(executable)`。〈邊界〉那節寫明「**沒有 spec 的可執行檔不會暴露給模型**」「壞 spec 會丟 `DiscoveryError`，避免能力集合悄悄缺一塊」「不同目錄同名時先指定的優先，像 `PATH`」。〈它不保證什麼〉明寫 discovery 不是 permission 或 sandbox——正好對到 Pike 那個 `../../../../usr/bin/id` 的現場。實作在 `freepy/exec_tools/discover.py`。

**`freepy/adapters/pi/` — pi 這一側的既有介面**

- **`freepy/adapters/pi/pi_bridge.py`**：一支以 **JSONL over stdin/stdout** 當協定的 server，由 pi extension 起 child process 控制一個獨立的 agentloop Round。**`freepy/adapters/pi/check_pi_bridge.py`** 是完全離線的 subprocess protocol check（`uv run python adapters/pi/check_pi_bridge.py`），可以直接拿來當「一支子行程用 JSONL 對答」的最小可跑樣本。`pi-agentloop.ts` 是 extension 與 child lifecycle 那一側；`examples/minimal_factory.py` 是 deterministic factory。

**`agent-machine/` — 崩潰、unknown 與 recover 的設計文字與可跑原型**

- **`agent-machine/full/06-AOS-LIFECYCLE-AND-RECOVERY.md`〈recover 完，才可以 ready〉**：六步恢復次序，其中第 4 步一字不差就是這輪的坑——「**已有 dispatch intent 而結果證據不完整時，標為 unknown，不啟動舊工作、不重送外部作用，也不接回一個猜測中的 PID**」；第 5 步是 fail closed。〈新啟動世代要隔離舊工作〉那句「**取得中央 store 的鎖，也不等於舊 process tree 已停止**」正是 `.runi` 與孤兒的關係。〈drain 不等於 checkpoint〉區分停在安全續接點、等待受管理 process、與外部作用不明三種狀態。
- **`agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉**：同目錄 temp、write-all、file fsync、atomic rename、directory fsync 的完整文字基線。〈結果不明不是失敗，也不是重試許可〉：已有 intent、缺可信結果就停在 unknown，**不自動建立新 attempt**。
- **`agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉**：「可唯一推導就補回；仍有兩種可能就不猜」，以及〈小原型該回答什麼〉裡「effect 後殺 manager、重開不得重送」的驗收條件。
- **`agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish(path, data, replace_staging=False)` 與 `fsync_directory(path)`**：可運行的同目錄唯一 temp、`O_EXCL`、write-all、file fsync、`os.replace`、directory fsync；遇到同內容既有 target 直接返回、不同內容則拒絕。
- **`agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind(call, attempts)`**：「完整證據才 commit receipt、不完整證據維持 unknown」的三態判讀樣本，配 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()`。
- **`agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()`**：effect 落盤後殺掉 writer parent，recover 保持 `waiting_for_child_repair_incomplete_evidence`，**重跑 recover 不增加 effect**——這是 p3 那個「偵測到孤兒還活著、拒絕動作」實驗的既有測試樣本。範圍與限制寫在同目錄 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉與〈明確未驗，不可外推〉。
- **`agent-machine/workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`／`_terminal()`／`recover(invocation_id)`**：receipt JSON、receipt-ready、terminal 分三步；**receipt 完整時 recover 只補後續 marker，不再執行 effect**——p1 那支 `recover.sh` 可以直接照這個判斷順序寫。
- **`agent-machine/full/10-STEP-TOOL-ROUND.md`〈Tool 到 leaf process 的三種常見接法〉**：小型參數／結構資料／大型或二進位資料三種傳法——這是「transcript 長起來要不要走 stdin 或走檔案」那條 ARG_MAX 論證真正該查的地方。同檔〈錯誤分層〉與〈一個 Tool Call 可以展開多個 Functions〉。
- **`agent-machine/full/02-LEAF-PROCESS-CALL.md`〈已知結果不等於成功〉與〈證據與結果不明〉**：leaf process 呼叫的三態（成功／已知失敗／證據不明）文字基線。

---

### 4. 還是查不到的

- **`aos llms ask` 在真實端點上的一次呼叫現場（延遲、token、輸出形狀）**：`core/llms/README.md`〈子命令〉只給語法與 LM Studio 的範例指令，並明說「`ask` 的非串流與串流成功路徑、`models` 成功路徑都會連到實際端點，因此 CLI 測試只驗離線可走到的語法／配置錯誤」；`wf/workflows/experiments/t5-agent-loop.md` 與本場第 1 輪四份回報都沒有任何 `aos llms` 的輸出。**這條沒有現成資料，只能實跑。**（機器上 LM Studio `localhost:1234` 題目書記為沒在跑。）
- **`aos tooljson` 的 `run`**：`core/tooljson/docs/format.md`〈CLI〉明寫「`run` 尚未存在」、〈`exec` 配方的載入期驗證〉明寫 S1 的 `ExecBody::run()` 固定回錯誤字串。所以「tooljson 是不是已經解決了一半」在**執行**那一半上，**這條沒有現成資料**，只有 `freepy/llmkit/tooljson/invoke.py` 的 Python 版可對照。
- **`parallel: true` 底下多個 tool call 的實際壞法**：`core/inst/docs/format.md`／`exec.md` 只寫了 join 語意，`docs/roadmap.md`〈D3〉只寫了「回合內並行，回合邊界不變」，`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 1 輪／4. 三個數字〉明寫四位都報 0 個並行 workload。**repo 內沒有任何一份 `parallel: true` 的實測輸出，這條沒有現成資料。**
- **claude 與 pi 被中途 kill 掉會留下什麼**：本場第 1 輪〈6. 仍然不知道的〉明寫四位都沒測；`wf/workflows/experiments/t5-agent-loop.md`〈6. 真 agent CLI〉那一輪 claude 是 OAuth 401、pi 未安裝。**這條沒有現成資料。**
- **pi 在**這台機器、這個版本（0.84.2）**上到底吃不吃 stdin 的定案**：`wf/workflows/workshop/records/tool-interop.md`〈pi 與本場的已知前提〉寫的是 `-p/--print`（可吃 stdin），但那是研討會引用的介面說明、不是本機實測；第 1 輪 p1 與 p2 各有一份成功現場、p4 有一句相反的斷言但沒有輸出。**「p4 那句話錯在哪」這件事沒有現成資料，只能重跑一次貼原始 exit 與輸出。**
- **`--loop` 期間對真模型送 SIGINT 的優雅收尾**：`docs/aos-folder.md`〈十二／已經被實作決定的〉寫了機制（攔信號、跑完當前回合、`SA_RESETHAND`），`wf/workflows/experiments/t5-agent-loop.md`〈4.〉有假模型的現場（0.3 秒送 SIGINT、停在回合邊界）。**真模型下要等 7 秒才停這件事沒有現成資料。**
- **斷電／`fsync` 等級的 durability**：`wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉只有測試方法與選項；`agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉明確排除 power loss；`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪／6. 仍然不知道的〉同樣列為未知。**這條沒有現成資料，而且三份紀錄都說不要外推。**
- **同一個世界兩支 `aos exec` 同時跑、`insts/` 底下的第二顆 CPU**：`docs/aos-folder.md`〈六、交接協定〉只寫了「每顆 CPU 各鎖各的」、〈十二／仍然開著的〉只寫了「`insts/` 底下的名字誰配、撞名怎麼辦」與「世界本身沒有抽象」。**沒有任何一份實測，這條沒有現成資料。**
- **`"needs"` 這個欄位的任何實作或原型**：`core/inst/docs/format.md` 的欄位表沒有它，`docs/inst-directives.md` 也不涵蓋（它只管 `$ref`／`$env`／`$opt` 的值層展開）。`wf/workflows/common/code-map.md`〈新增一個 instruction 欄位〉只給了「要改哪幾個檔」。**這條沒有現成資料，只能靠 `bin/gate` 先在世界內模擬。**

---

## 第 1 輪白話導讀

> 這一節是給沒有跟到現場的人看的翻譯，不是第二份摘要。上面每一段都還是原樣，這裡只負責讓那些字看得懂。

### 一、這一輪到底發生了什麼

四個人各自用現有的工具，寫了一百多行的小腳本，讓一個要付錢的 AI 服務自己一步一步把一件事做完——問它、它說要用哪個工具、跑那個工具、把結果拿回去給它看，直到它說做完了；四個人都成功了。四個人也都撞到同一件事：中途把總管程式關掉，被它叫出去的那個付費服務不會跟著停，它會自己做完、還自己把下一步排好，可是總管回來以後完全不知道這些事發生過，只把門鎖上說「上次沒做完，人來處理」。而人照直覺去解鎖的那個動作，會把已經做完的成果無聲刪掉，再付一次錢重做一遍。

### 二、冒出來的新詞

**孤兒行程（orphan）／`setpgid`／process group**
- 白話：你叫小孩去跑腿，然後你自己先走了。小孩不會因為你走了就停下來，他會把腿跑完、把東西買回來放在門口——只是你已經不在，沒人知道他回來過。`setpgid` 是「讓小孩自己站成一隊」，好處是你在鍵盤上按 Ctrl-C 不會誤傷他，壞處是你想叫他停也叫不到。
- 在 aos 裡具體是什麼：已經存在，而且是刻意的——`docs/aos-folder.md` 第十二節寫著子行程各自 `setpgid` 自成一個 process group。本輪四位撞到的所有東西都是從這裡長出來的。已補進 [BACKGROUND](../../workshop/BACKGROUND.md)。

**running marker（起跑標記）／租約（lease）**
- 白話：現在的鎖只寫「有人在裡面」。租約是把鎖換成一張條子：「誰進去的、幾點進去的、進去做第幾件事」。人回來的時候不用猜，看條子就知道。
- 在 aos 裡具體是什麼：**提案，目前不存在。** 主張是 `aos exec` 在派小孩出門「之前」就把條子寫到磁碟上（含小孩的行程編號），回合正常結束再撕掉。這是評委列的第一名，也是唯一一件只有 `aos exec` 本人做得到的事。已補進 [BACKGROUND](../../workshop/BACKGROUND.md)。

**短路（short-circuit）／`"needs"` 欄位**
- 白話：一串接力，第一棒摔倒了，剩下的人照樣把空手交下去，最後還宣布「這場跑完了」。短路就是「前面那棒沒拿到棒子，我就不跑」。
- 在 aos 裡具體是什麼：**提案，目前不存在。** 現在一批指令裡前一筆失敗，後面照跑，整回合還是回 0——而且評委查過，這是規格寫明的行為，不是壞掉。`"needs"` 是想加的新欄位，下一輪會先用腳本模擬看夠不夠用。已補進 [BACKGROUND](../../workshop/BACKGROUND.md)。

**結構化輸出（`--output-schema`）**
- 白話：與其請對方「回話請盡量整齊」然後自己拿剪刀修，不如先發一張表格給他填，他只能照格子填。
- 在 aos 裡具體是什麼：不是 aos 的東西，是 codex 這支 CLI 自己的旗標。用了它之後，「解讀模型講了什麼」這件事縮成一行 `jq`。評委的但書是：這是一家廠商專屬的旗標，拿它當「解析不是問題」的證據等於把選擇綁死在那一家。已補進 [BACKGROUND](../../workshop/BACKGROUND.md)。

**`aos recover` / `aos deliver` / `aos status --json` / `aos agent step`**
- 白話：分別是「出事之後把現場攤開給人看」「把東西安全放進收件匣」「從外面看一眼現在到底是做完了還是壞了」「說出下一步要做什麼」。
- 在 aos 裡具體是什麼：**四支全部是提案，目前都不存在。** 四位參賽者都是自己用十幾行 shell 各寫一份，所以名字看起來很像真的有這些命令，實際上沒有。

**`aos llms`**
- 白話：aos 自己內建的一支「直接跟模型講話」的命令，不經過那三支外部 CLI。
- 在 aos 裡具體是什麼：**已經存在**（`core/llms/`，`aos llms ask` / `aos llms models`）。這一輪四位全部沒測，四位全部說它可能才是對的路——評委稱之為本輪最大的集體盲點。

**`aos tooljson`**
- 白話：一張「工具名字 → 實際要跑什麼命令」的登記表，還附一套檢查模型有沒有把參數填對的規則。
- 在 aos 裡具體是什麼：**存在一半。** 格式與檢查已經有了（`aos tooljson list` / `check`），但**執行那一半沒有**——`core/tooljson/docs/format.md` 明寫 `run` 尚未存在，跑下去會回 `Error: exec execution is not implemented in S1`。四位都看到它、都沒接、都自己手寫了一份。

**`thread_id`／rollout 檔**
- 白話：你打電話給客服，對方先給你一個案件編號，之後不管線路斷在哪裡，拿編號都查得回來當時講了什麼。
- 在 aos 裡具體是什麼：不是 aos 的東西，是 codex 給的。它在第一行就到、比答案還早到，所以就算後面整個炸掉也拿得到；`~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl` 是它落在本機的那份紀錄（p1、p2 都貼了實際路徑，p3 那句「資料夾是空的」是零證據的斷言，評委判為不可用）。

**ARG_MAX**
- 白話：一次能塞進命令列的字數有上限，超過就整個叫不起來。對話越長越危險。
- 在 aos 裡具體是什麼：不是 aos 設的，是作業系統設的。p4 拿它當「不要選 pi」的第一條理由，但那條理由建立在「pi 不吃 stdin」上，而那句話有兩份相反的現場，評委判為在重測之前不可採用。

**JSONL 與「`jq` 預設吃串流」**
- 白話：JSONL 是「一行一則」的紀錄檔。而 `jq` 這支工具預設會很客氣地把 30 則當成 30 則分別處理，不會抱怨「你不是說只有一則嗎」——所以你以為你在檢查格式，其實什麼都沒檢查到。
- 在 aos 裡具體是什麼：不是 aos 的東西，是這三支 CLI 的輸出形狀。正確寫法 p4 已經給了：`jq -e -s 'length==1'`。

**markdown 圍籬（code fence）**
- 白話：對方回話的時候自己在前後加了一圈裝飾框線，即使你講明了不要加。
- 在 aos 裡具體是什麼：claude 這支 CLI 的行為。要自己寫 `sed` 把框線剝掉，p4 的註記是「很脆」。

**sentinel 檔（`DONE`）**
- 白話：做完之後在桌上放一張「我做完了」的紙條，因為系統本身沒有地方可以講這句話。
- 在 aos 裡具體是什麼：三位各自發明了一份（`DONE`、`state/DONE`），**`aos` 一個都不認得**。這是「沒有停止條件」的手工補丁。

**這些詞 BACKGROUND 已經有了，不重寫**：`.runi`、world、彙整／取件／釋放、golden slice、agent loop、driver 與 adapter、tool allowlist（具名工具映射）、coding agent、session、correlation ID（`tool_call_id` 就是它的一個實例）、receipt、idempotency key、ledger、TOCTOU、Maildir（`.bad` 在這一條裡解釋過）、JSON Pointer——見 [BACKGROUND](../../workshop/BACKGROUND.md)。

### 三、看到的錯誤訊息各是什麼意思

**aos 自己講的話**

| 你看到的 | 白話 |
|---|---|
| `aos exec: refusing w1: .aos/inst.json.runi already exists`／`exit=3` | 「上一回合沒有正常收尾，我不敢再開工。」注意：它說這句話**之前**已經把收件匣搬空了，見下一節。 |
| `aos exec: warning: .../ref1.json: UnknownKey` | 「你投進來的那張紙條上有一個我不認得的欄位。」這一張被跳過，其他照收，整體還是 `exit=0`。 |
| `aos exec: warning: .../ref3.json: FieldTypeMismatch`＋檔案變成 `ref3.json.bad` | 「這個欄位該放文字你放了數字（或該放陣列你放了別的）。」壞的那張被丟到旁邊改名 `.bad`，**不擋別人**，整體還是 `exit=0`。**模型永遠不會知道自己被退件**，因為這句話去了 stderr。 |
| `exit=0` | 這一個碼同時代表四件完全不同的事：回合正常跑完／根本沒事做／模型說做完了／模型參數寫錯導致下一步被丟掉。從外面分不出來。 |
| `exit=1` | 回合本身出了問題（不是子程式失敗——子程式失敗照樣算 0）。 |
| `exit=2` | 你這行命令下錯了（參數、用法）。 |
| `exit=3` | 就是上面那條「拒絕啟動」。也是唯一一個會讓 `--loop` 停下來的碼。 |
| `model.exit=MISSING`／`after-model.exit=MISSING` | 「那一筆的結果代碼沒有被寫下來。」**不代表沒跑完**——寫這個檔的是總管，總管先死了就沒人寫。這一輪最容易誤讀的一行。 |

**作業系統／殼層講的話（不是 aos 的錯）**

| 你看到的 | 白話 |
|---|---|
| `exit=130` | 被 Ctrl-C（SIGINT）打斷了。 |
| `exit=137` | 被強制砍掉了（SIGKILL），完全沒有機會善後。 |
| `exit=124` | `timeout` 指令等不下去自己動手砍的——**代表被測的東西沒有自己停**。p2 的空轉現場就是靠這個碼看出來的。 |
| `exit=127` | 「找不到這支程式。」p1 的 5 次執行全掛，因為這台機器沒有 `/usr/bin/time`。 |
| `codex_exit=0`（明明送了 SIGINT） | 背景執行的工作預設會**忽略** Ctrl-C，所以那個信號根本沒打中。p1 明寫「上一份報告白紙黑字寫了這件事，我還是踩了」。 |
| 第一次 `ls -a` 沒輸出、第二次讓整個命令卡 2 分鐘 | 跟 aos 完全無關：這台機器的 `ls` 是別的程式的別名，它會順手去掃整個 repo 的版本控制狀態。繞法是改用 `find`。 |

**codex 講的話**

| 你看到的 | 白話 |
|---|---|
| `ERROR rmcp::transport::worker: ... AuthRequired ... api.githubcopilot.com ...` | codex 自己去連一個它自己設定的外掛服務，沒有密碼所以連不上。**與你的工作完全無關，每次都會噴，而且無害。** 結論：不能用「有沒有紅字」判斷模型呼叫成不成功。 |
| `error: unexpected argument '-s' found`／`exit=2` | 旗標放錯位置了。`resume` 是子命令，所有全域選項都得放在它**前面**。 |
| `Not inside a trusted directory` | codex 要求工作目錄是一個版本控制過的資料夾，場地不是，所以要加 `--skip-git-repo-check`。 |
| 中途砍掉後，`-o` 指定的答案檔**完全不存在**，紀錄檔停在 `turn.started` | 「開始了、沒完成」。好消息是不會讀到半截答案；壞消息是**本機檔案完全看不出對方那邊有沒有計費**——SIGINT 和 SIGKILL 留下的現場一模一樣。 |

**參賽者自己腳本印的話（不是 aos 的行為，看的時候別混淆）**

| 你看到的 | 白話 |
|---|---|
| `mdl: connection refused`／`mdl = 7` | p2 故意換上一支必定失敗的假模型（模擬斷網或額度用完），驗證後面五站會不會照跑。會。 |
| `inst: 沒有這支工具: nosuchtool`／`exit=3` | p2 自己那 13 行腳本的退出碼，跟 aos 的 3 沒有關係。 |
| `put: 空批次，不投遞（迴圈到此結束）` | 「沒有下一步了，停。」問題是**模型講錯工具名**和**模型宣布任務完成**印出來的是同一句話。 |
| `REJECT unknown tool: nuke_everything`／`[tool] 錯誤：沒有叫 nuke_everything 的工具。請從清單裡挑。` | p4 在送出之前就擋下來，並把這句話當成一則對話餵回模型——下一回合模型自己改口了。**這是整輪唯一一個自我修復的機制。** |
| `DIFFERENT -> DOUBLE BILLED` | p3 比對兩次呼叫的案件編號，發現不一樣，也就是**同一件事付了兩次錢**。 |
| `kind=null`（× 33）／`UNKNOWN kind=null` | p4 把 30 幾行紀錄整包當成模型的回答，於是每一行都解讀失敗。他的格式檢查沒擋住，原因見上面 `jq` 那條。 |

### 四、所以呢

#### （1）評委判定為真的那幾條，各自的後果

評委說他讀了原始碼與規格才寫這一段，理由是「判錯的代價是使用者去改一份沒問題的規格」。判為真的有七條，後果分成三種：

**會花錢、會掉資料的（這三條是同一件事的三段）**

- **總管關掉之後，被它叫出去的付費服務不會停。** 它會把事做完、把下一步排好，可是「上一回合沒跑完」這把鎖還掛著。規格裡有兩句話單獨看都對，放在一起就互相矛盾：一句說「鎖存在就等於有一回合沒跑完」，另一句說「小孩自己站一隊，Ctrl-C 打不到」。四位獨立撞到，評委判這是根因。
- **`aos exec` 說「拒絕啟動、退出碼 3」，但它其實已經把收件匣吃掉了。** 評委親自看過原始碼確認：搬收件匣的動作排在檢查鎖之前，所以那句「我什麼都沒做」是假的——那個孤兒排好的下一步，已經從收件匣被搬進正式的待辦清單裡了。**後果是：人最自然的動作「跑一次看看現在怎麼了」，本身就會搬動狀態。** 規格沒有寫錯，是規格沒寫到這件事。評委說這是十一條裡最該先補的一句話。
- **人接下來唯一想得到的救援動作，會靜默吃掉一份已經做完、而且已經付過錢的成果。** 那個動作是把鎖檔改名搬回待辦清單（`mv .runi inst.json`）。它會蓋掉上一步剛被搬進來的那份成果，**沒有警告、沒有備份、退出碼 0**；然後你重跑，付第二次錢，而第一次的結果從頭到尾就躺在檔案裡，內容一模一樣。p4 在真模型上完整走過這四步，付費編號從 1 個變 2 個。
  這裡評委修了一個框架，很重要：**規格從頭到尾沒有建議過那個動作。** 規格只說「crash 之後要人來處理，這是刻意的」。所以正確的說法不是「規格建議的動作會付兩次錢」，而是**「規格沒有指定任何恢復動作，而人手上僅有的兩個動作都是破壞性的」**——改名等於重播加重新計費加抹掉證據，刪掉等於直接丟掉那一批。這一條要改的是規格該**新增**什麼，不是該**修正**什麼。

**會讓你查不出真相的**

- **重跑會抹掉上一次的現場。** 指令格式裡「輸出寫到某個檔」的語意是「打開就清空」，所以第二次跑的瞬間，第一次的紀錄（包含那筆計費證據）就沒了。評委確認這是真的，但只收一半提案：讓系統自動給每次嘗試不同檔名是對的，「改成續寫」是錯的——續寫會把兩次結果黏成一坨沒有分隔的東西，比清空更難處理。
- **「這一筆做完了嗎」這個問題，系統永遠沉默。** 結果代碼是總管等小孩回來之後才寫的，而「崩潰」的定義就是總管沒活到那一步。評委同意現象，但說兩位提的解法都只夠一半，理由見下面第（3）點的注意事項。

**設計前提不同，不是壞掉**

- **模型講錯話，模型自己永遠不會知道。** 壞掉的投遞被丟到旁邊、警告寫到 stderr、整體回 0，於是整條循環安靜地停住。評委的判定是：規格這條規則是為「一堆各自獨立的人來投工作」設計的，而 agent loop 是「一個有記憶的人一直繞圈」——同一條規則在後者身上就變成模型永遠沒機會改。**這條不要當成 bug 報上去，要當成「設計前提不同」報上去。**
- **「投遞那一步沒有實作」——真的，但規格第十二節自己就寫著了。** 這不是新發現，是一個已知缺口被四份獨立資料確認。唯一的新資訊是：大家補出來的東西不是那個三步協定（規格已經描述了），而是**防止檔名互相蓋掉的流水號**，而且三位明說他們是因為讀過前人的現場才知道要加。

#### （2）評委砍掉的那幾條——這幾條不必去改規格

- **「一批指令不會因為前面失敗就停下來，而且整回合還是回 0」——不是對不上。** 規格第八節明寫子程式失敗、被砍、逾時都算「一次完成的執行」，第五節從頭到尾沒承諾過會停。所以實作沒錯、規格沒錯，這是一個**功能請求**。評委補了一句：這不減損那個提案的價值，他最想看到的東西就是它，但請放進「要加什麼」，不要放進「哪裡對不上」。
- **「`$ref` 拼不出一整批指令」——參賽者引錯出處。** p2 引用的那句「$ref 做 loop 時可能很好用」，評委 grep 過整份規格，**那句話不在規格裡**，它出自這場黑客松的題目書。而規格本身完全一致：明寫取回來的值必須是字串，也明寫「讓它展開成多個項目」是考慮過之後**刻意否決**的。p2 貼的三組現場一字不差就是規格預測的行為。**所以這條不要拿去改規格，會改到一句不存在的話。** 底下真正該保留的是 p4 那句：agent loop 想要的正是那個被否決的語意——那是一個**新指示詞的提案**，而規格自己留了門（「真的需要時，另設一個明確表達展開語意的指示詞會更誠實」）。
- **「彙整接受非純數字的檔名，規格沒寫明」——不是對不上，而且方向反了。** 規格本來就是用「有沒有狀況後綴」定義要不要收，那個檔名沒有後綴，被收走完全符合規格。**真正該改的是另一句**：規格說「檔名帶 pid」，而四位的現場證明**光靠行程編號不夠**（同一個程式投第二次會用同一個名字互蓋）。那句該改成「檔名必須唯一；帶 pid 只是最省事的做法，同一個生產者投第二次時必須再加序號」。

#### （3）`aos agent` 該收掉什麼的優先序

評委的排序判準只有一句：**拿掉它會不會死。** 會花錢、會安靜掉資料的排前面，只是打字多的排後面。

**最前面兩件（會花錢或會安靜掉資料）**

1. **崩潰現場看得出來，並且救得回來。** 兩半都要：`aos exec` 在派小孩出門之前先寫一張條子（含小孩的行程編號），以及一支**只看不動**的救援命令，把現場攤開給人看——包括「小孩還活不活著」，以及「你的收件匣其實已經被搬走了」。重播必須是人明確要求的動作，不能是預設；而且孤兒還活著的時候必須拒絕動作，因為那正是會付兩次錢的狀態。
   **這一件的代價要講清楚**：它是 `aos exec` 的 C++，不是一支新的子命令。T5 那句「整個 loop 可以完全不含新 C++」對「跑」成立、對「救」不成立。另外三件今天就能用 shell 寫出來（四位都寫了），只有這件不行。
2. **東西送出去之前先驗一次。** 對照組很乾淨：模型亂點一個不存在的工具，在**送出之前**被擋下 → 錯誤變成一則對話餵回去 → 下一回合模型自己改對；模型把參數型別寫錯，在**送出之後**才被擋 → 丟到旁邊 → 整體回 0 → 循環安靜死掉。目前的缺口很具體：aos 沒有任何「只驗不跑」的入口可以給腳本用。

**中間三件（四位都重寫過，收掉省的是打字和打錯）**

3. 從外面看得出來現在是「做完了／沒事做／壞掉了／正在想」——現在這四種都是同一個碼 0，而且 `--loop` 沒有停止條件。
4. 「下一批要跑什麼」只寫一次——四位各抄 2 到 3 次，其中兩位還是用兩種不同語言各抄一次。關鍵是 p2 那句「不是我懶，是沒有第二種寫法」：現有的指示詞解不掉它。
5. 那三個輸出檔的路徑不要手打——p2 手打 39 次還漏過一次。**評委標了但書**：39 是他七站管線的架構造成的，另外兩位只有個位數，所以這條真的存在，但**大小取決於你怎麼切**，不要拿 39 當普遍價碼。

**後面四件（真的重複，但繞得過或已經半解決）**

6. 投遞（十三行，誰都寫得出來；真正該收的是那個防撞號碼，因為那是只有讀過前人現場的人才躲得掉的陷阱）。
7. 工具登記表——**降級的唯一理由是 `aos tooljson` 已經存在但沒人去讀它**，評委明說「在有人真的去讀之前，我不同意為這條開新規格」。
8. 三支 CLI 各自的接線（收不成一支命令，它本質上是廠商差異；能收的是一份契約加三份設定）。
9. 組 prompt 與工具結果的回程型別（重寫次數只有 2，痛的是形狀不是錢，排最後）。

**明確不要收的兩件**：不要為了 LLM 往指令格式加欄位（四位包了三家不同廠商的 CLI，現有五個欄位一個都不用加，這是很強的負面結果）；不要為了效能動 `aos exec`（0.4 秒 對 22 秒，其中還含輪詢間隔）。

**如果今天就得拍板**：先做第 1 件，另外兩件（`aos agent step`、`aos status --json`）晚做只是繼續打字，第 1 件晚做的成本是已經花掉的錢。順帶把那句規格漏洞一起補掉——**退出碼 3 之前不要搬收件匣，或至少在規格裡寫明它會搬。**

#### （4）這一輪會動到你手上哪些還沒拍板的決定

底下只列牽動關係，不做建議。

- **`aos agent` 到底為什麼存在。** 這一輪把它從「讓 loop 好寫」改成「讓 loop 壞掉之後有救」——因為 loop 只要一百行 shell，四位都寫出來了；壞掉之後沒有一個人救得回來。
- **T5 的驗收條件與 roadmap 自己標的矛盾。** `docs/roadmap.md` 的 T5 底下已經有一個警示區塊，說驗收寫的「中途 Ctrl-C 之後再跑一次能從斷點繼續」跟 D6 互相矛盾，並列了兩條擇一的路（改措辭承認續跑就是回合邊界／長出真正的復原路徑），最後一句是「在拍板之前，不要照這條驗收去實作」。**這一輪把那個矛盾從紙上變成了現場**：p3 的話是「批次層級可以，指令層級不行」。
- **golden slice 鎖哪一支 CLI（OPEN #6）。** 四位給了三種答案，而且三個前提都有裂縫：主張鎖 pi 的那位**沒有把 pi 接進 loop**；主張鎖 codex 的其中一位，第一條理由建立在一句沒有現場的斷言上；而讓「解析變簡單」的那個旗標是一家廠商專屬的。另外，評委指出一個沒人推到結論的事實：**這三支都是 agent，不是模型端點**——p3 把模型的工作目錄指到空資料夾，理由是給它真的工作區它會用自己的殼直接讀檔，整條工具鏈就變成裝飾品。**任何沒有做這件事的量測，量到的有一部分是那支 CLI 的能力，不是這條 loop 的能力。**
- **要不要先去試 `aos llms`。** 四位全部沒測、四位全部說它可能才是對的路。如果它能直接當那支「模型」，那 OPEN #6 的答案就不是「哪支 CLI」而是「不要用 CLI」，而且 T5 與 T6 的邊界要重畫。p2 明講他是**刻意**繞過的（用內建的會把題目繞過去）。
- **`.runi` 到底鎖的是那一批指令，還是整個世界。** 已經有一份研討會紀錄指出上面每一條提案都預設了一個答案，卻沒人講明。這一輪的孤兒現象讓這題變得不能再拖：鎖擋住的是下一批，而上一批的小孩還在世界裡跑。
- **同時要求兩個工具的形狀（`tool_call_id`）。** 四位全部主動繞開，兩位只推理出「一開就會壞」。現在不痛是因為四位的題目都是一次一個工具，**而真模型很常一次要兩個**。評委把它標為中間地帶：現在只是麻煩，但它是協定不是實作，晚定形狀會很貴。
- **哪些回報現在還不能拿去改規格。** 兩條，都是同一種病——講了一個機制，但沒有任何輸出：「pi 只能塞參數、不吃 stdin」（兩份相反的現場對一句沒有現場的斷言，而且它已經被拿去當選型理由了），以及「codex 的 session 資料夾是空的、實際存在資料庫裡」（另外兩位各自貼了實際存在的檔案路徑）。評委對這兩條的講法是：可以寫「沒問到」、可以寫「不知道」，這兩種寫法一分都不扣，**但不能寫一個你沒看過的機制**。
