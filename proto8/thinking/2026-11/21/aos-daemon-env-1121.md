aos agent 這一塊對 `AOS_DAEMON` 的依賴盤點（11-21，線 top-1121-daemonenv，唯讀調查、沒改程式）。

# aos agent 這塊用到 `AOS_DAEMON` 的地方

← [2026-11-21](README.md)｜明細：[aos-daemon-env-1121.json](aos-daemon-env-1121.json)（36 列）、[搬家](aos-daemon-env-1121-搬家.json)（13 列）｜相關：[default-stack-1118](../18/default-stack-1118/README.md)、[05-使用者補充-1120](../18/default-stack-1118/05-使用者補充-1120.md)

## 使用者原話（11-21）

「目前來說，aos agent這塊，他是很多東西都要用到AOS_DAEMON嗎？去幫我統整一下，跟我簡單報告。」

## 一頁結論

1. **是，用得很多，但幾乎都走同一個路口。** `AOS_DAEMON`＝daemon 自己的 stack 資料夾（絕對路徑、結尾 `/`）。daemon 起每個子行程時都設好它（`cpp/aos-daemon/src/child/child.cpp`），daemon 自己的身體也設成自己。`env.sh` 不設，只清掉；`aos-exec` 不設；`using-aos-agent.sh` 沒設時設成 `$PWD/.stack`。
2. agent 這塊共 **36 列**（明細 json；`self_*` 這類同做法的工具併成一列，拆開約 45 處）：**甲 非 daemon 不可 12 列、乙 其實只要自己的 stack／定義 14 列、丙 路標・顯示・照傳 10 列**。編譯程式庫（`agent_spec*`）與 hook 引擎（`agentlib/hooks.py`、`apps/hook`）**不讀** `AOS_DAEMON`。
3. 幾乎全部經 `py/aos/daemon_ctl/table.py` 的 `find_daemon`：`--daemon` ＞ `AOS_DAEMON` ＞ cwd 的 `./.stack`，都沒有就 `DaemonMissing`。設了 `AOS_KERNEL` 時查表改問 kernel、不看 `AOS_DAEMON`。
4. **乙類為什麼也要 daemon**：工具要先知道「我是哪隻」，做法是 `aos-agent ctl who`——拿 `$AOS_STACK` 去 daemon 的表裡反查名字，再 `aos-agent --target 名字` 回頭查表拿 stack。結果最後只改自己 stack 裡的檔（覆蓋檔、history、goal、信箱）。aos-agent 的 say／listen／history 等也是「名字→查表→stack」。
5. **沒有它會怎樣（暫存樹實測，假腦）**：
   - 人在樹外打 `aos-agent -t ann say hi` → `DaemonMissing`；站在樹根打 → 退回 `./.stack` 照通。
   - agent 的工具（`self_tools`、`mailbox_peek`、`self_state`、`goal`、`do_task`、`subagent`）在**沒有 `AOS_DAEMON`、工作區＝`work/`** 時全部 `DaemonMissing`；補上就通。
   - 同樣沒有 `AOS_DAEMON`、但**工作區＝樹根**（start-api 預設 `-w .`）時 `self_tools` 照通——因為工具在 `$AOS_WS` 跑、那裡剛好有 `.stack`。也就是說缺變數會被這條退路蓋掉，換個工作區才露出來。
   - `todo` 不受影響。
   - daemon 起的子行程一定有 `AOS_DAEMON`，所以上面這些平常碰不到；會碰到的是人自己開的殼、或手動 `aos-exec` 跑工具。
6. 寄信本身**不經 daemon 轉**：信直接放進對方 `stack/mailbox`。要 daemon 的只是「名字→對方 stack」那一步（寫 `--box` 路徑就不用）。

## 跟 `AOS_DAEMON` 一起出現的 `AOS_*`

| 變數 | 管什麼 | 誰設 |
|---|---|---|
| `AOS_DAEMON` | daemon 的 stack（表 `procs_state.json`、ctl 信箱都在裡面） | daemon 給每個子行程；人自己 export |
| `AOS_STACK` | 這支行程自己的 stack（工具被叫時＝agent stack 底下的 `tools/<工具>/`） | daemon（子行程的小格）、`aos-exec --stack` |
| `AOS_WS` | 工作區；工具在這裡跑、相對路徑從這裡算 | daemon（列上有 ws 時）、`aos-exec --ws` |
| `AOS_CD` | 正在跑的那個資料夾程式自己的資料夾 | `aos-exec` |
| `AOS_CF`／`AOS_CO` | 正在跑的設定檔與 JSON 指標 | `aos-exec` |
| `AOS_KERNEL` | 起停請求先寄這裡；查表也改問它 | 人或 `.env` 設；沒設＝直接寄 `AOS_DAEMON` 的 ctl 信箱 |
| `AOS_LLM_KERNEL` | 腦的請求寄哪個 llm kernel | 根的 `.env`（`${AOS_STACK}/procs/llm`） |
| `AOS_CLOCK` | 時鐘檔 | 根的 `.env` |
| `AOS_AGENT` | aos-agent 沒給 `-t` 時的對象名 | 人 export，或 `using-aos-agent.sh 名字` |
| `AOS_HOME` | proto8 那份（lib、範本、知識庫） | 人一台設一次 |

註：使用者 11-20 原話寫 `AOS_TARGET`，程式裡沒有這個名字，今天認的是 `AOS_AGENT`。

## 三類各是什麼（細目在 json）

- **甲 非 daemon 不可（12 列）**：寄 ctl 信叫 daemon 起停掛拆（aos-agent `ctl add/rm/start/stop/…`、工具 `agents_ctl`、`subagent`、`fork`、`self_ctl`、`gdb_trigger`），或讀 daemon 的表看別隻（`ctl ls/state/where`、`self_state`、`aos-mailbox --to 名字`、on_clock 鐘寫名字、Python 遙控器、eca 畫面看守）。
- **乙 只要自己的 stack／定義（14 列）**：aos-agent 的 `say/ask/listen/chat/history/goal/tools/llm/system/hook/open/close/watch/peek`、`ctl who`、寄件人名；工具 `self_tools/llm/system/hook/history`、`goal`、`do_task`、`mailbox_peek/read/send`（寄件人那半）、`user_send/verify`、`clock_register`（預設寄自己）、`kernel_gate`。今天都繞「查表」一圈，原因只是要用名字或定義。
- **丙 路標・顯示・照傳（10 列）**：`tool_io.place` 把路徑印成 `$AOS_DAEMON/…`；claude/codex 工具與沙箱照傳這個變數；agent-fsm `wait.py` 與 `aos-llm send` 拿它當相對路徑基準；guard 用它劃「不准碰」的範圍；daemon 寫進小格的 `{"$env":"AOS_DAEMON","$path":…}`（loop 型 proc 與 `ctl add --envs`，整棵樹搬家照起；普通掛上的 agent 如 ann 不用）；aos-loop 錯誤行縮寫；start-api `ann/.env` 一行註解。

## 跟使用者 11-20 方向對照（只列事實與量）

11-20 的方向：沒給 `-t`、沒設變數時，先試 `./.stack` 再試 `./` 當 agent 的 stack；agent 不記自己在哪個 daemon 底下；daemon 照舊由 `export AOS_DAEMON` 指定。

- **甲 12 列：不用改。** 方向本來就保留 `AOS_DAEMON`。
- **丙 10 列：不用改。**
- **agent 的工具（乙類裡的 9 列）：不用改。** daemon 照舊給子行程 `AOS_DAEMON`；而且工具在 `$AOS_WS` 跑、不在 stack 裡，「從 cwd 找對象」本來就幫不到它們。
- **要改的集中在 aos-agent 人用的那半（乙類 5 列）**，入口只有一個：`py/aos/apps/agent/common.py` 的 `target`／`find`（12 個子指令都經它）。要改的事實：
  1. 今天 `find` 一定讀表（名字→列）；照方向要能直接拿一個資料夾當 stack，不經表。
  2. 判斷「這是不是 agent 的 stack」目前沒有現成函式（stack 裡有 `queue/`、`history.jsonl`，但沒有一個標記檔）。
  3. **stack 自己沒記定義在哪、工作區在哪**：實測 ann 的 stack 裡只有 `interfaces.json`＝`{"aos-observed": …}`，定義與 ws 只在 daemon 表那一列。所以只靠 stack 時，`say/listen/history/goal` 能做（say 判斷 eca 要看定義，那一步會缺）；`tools/llm/system/hook/open/close/watch/peek` 要定義，做不到——要嘛還是查表（就又要 daemon），要嘛 stack 裡多記定義在哪（這等於 agent 記點東西，跟「不記 daemon」是兩回事，使用者沒說過）。
  4. 樹根有個 `./.stack` 是 **daemon 的** stack，不是 agent 的；`find_daemon` 的退路也看同一個 `./.stack`。同一個名字兩種意思，「看看符不符合目標」那一步得分得出來。
  5. 文字面：`using-aos-agent.sh`（沒設時把 `AOS_DAEMON` 設成 `$PWD/.stack`，在 agent stack 裡會指錯，1118 實測過）、aos-agent `--help`／README、規範 N-63 那一列、知識庫 `me.json`／`kernel.json` 的說法；`AOS_AGENT` 若改名 `AOS_TARGET`，程式約 10 個檔提到。
- **量**：程式核心一處（`common.target/find`）加上 `decl.def_of`、`sender.put` 兩處對「沒有表那一列」的處理；文件 5～6 份。工具與 C++ 不動。大小取決於第 3 點（定義從哪來）怎麼定——只做 say/listen 這類是小改；連 tools/llm/system/hook 都要就要先決定定義的來源。

## 追加：把 agent 的資料夾搬到別處、用另一個 daemon 跑（可遷移性）

### 使用者原話（11-21，頂層轉達）

「agent記自己在哪個daemon底下...這個想法我覺得不行，agent不該和daemon耦合。這是爲了可遷移性，這樣我可以直接把相關資料夾複製一份丟到別的地方，用另一個daemon跑。這個也可以順便幫我調查一下可行與否。」

（11-18 暫定的丁「stack 裡加路標記 daemon」因此不算數了。）

### 結論

**現在就可行。** 實測四種搬法都在新 daemon 上跑起來、答得出話；逐檔明細在 [aos-daemon-env-1121-搬家.json](aos-daemon-env-1121-搬家.json)（13 列）。

- **現在就能搬**：定義夾（沒有絕對路徑）、stack 裡的對話／目標／信件順序、hook 與腦的執行時快取（新身體自己改寫）、`state.json` 的 pid（新 daemon 不會誤認舊行程）、全部環境變數（每次起身體由新 daemon 給）。
- **差一點（3 處，都小）**：
  1. stack 的覆蓋檔（`tools.json` 等）的 `$override` 是「從 stack 到定義的相對路徑」：兩者相對位置不變就沒事；換了名字或位置，會**安靜地**指到別的定義（實測 annB 仍指 `agents/ann`，不報錯）。
  2. 信箱裡信的 `reply_to` 存相對路徑：兩隻一起搬沒事，只搬一隻回信會寄錯地方。
  3. 正在等腦回信時搬，那一封回信留在舊的 llm kernel。
- **本來就綁 daemon、不跟著走（3 處，都是 daemon 自己的東西）**：daemon 表上那一列（名字、def、ws、auto_restart）＝到新 daemon 要 `ctl add` 一次；時鐘登記（存在 daemon 的 stack）要重新登記；子 agent 是舊 daemon 表上的列，父的 subagent 帳記著它們的絕對 stack，要手動重掛。
- **跟前面三類對得上**：agent 這塊讀 `AOS_DAEMON` 的 36 列都是**執行時從環境拿**，沒有一處把「我在哪個 daemon」寫進 agent 的定義夾或 stack。唯一把「相對 daemon 的位置」存進檔的是 `ctl add --envs` 才有的 `exec.json`（`{$env: AOS_DAEMON, $path: …}`），重新 `ctl add` 會重寫。所以搬家的阻力不在 `AOS_DAEMON`，而在上面「差一點」那三處相對路徑與「綁 daemon」那三樣掛接資料。
- 跟線 `top-1121-deft`（`-t` 可省略）有關的一句：今天沒有任何地方把 daemon 寫進 agent 的 stack，那條線也不需要；但 stack 裡沒有記定義在哪（只有覆蓋檔的 `$override` 間接指到），只靠 stack 找定義會缺。

### 實測（暫存樹，假腦）

舊樹 `tree/`（daemon 1）的 ann 先跑兩輪、設 goal、`tools rm todo` 留狀態；另起 `tree2/`（daemon 2，自己的根與 llm kernel）。

| 搬法 | 做了什麼 | 結果 |
|---|---|---|
| A 只搬定義＋工作區 | `cp -r tree/agents/ann tree2/agents/annA`；`aos-agent -d .stack ctl add -w . agents/annA` | 掛上、新 stack，`ask hi-A` 回 FAKE ANSWER |
| B 連 stack 一起、相對位置不變 | 定義抄到 `tree2/agents/ann`、stack 抄到 `tree2/.stack/procs/ann`，`ctl add -w . agents/ann`（預設 stack 撿到抄來的） | `listen --last 2` 看得到搬前的 #8 #9；goal 照舊 active 並繼續提醒；`tools get todo`＝ToolMissing（搬前拿掉的照樣不在）；`ask after-move` 有答；hook 的時鐘與腦的 kernel 路徑自動換成 tree2 的 |
| B2 連 stack、換名字 | 定義放 `agents/annB`、stack 放 `procs/annB` | 跑得起來、歷史接上；但 `tools.json` 的 `$override` 仍是 `../../../agents/ann/tools.json`，指到別隻的定義，不報錯 |
| C 活著直接抄（沒停） | ann 還在 daemon 1 跑時 `cp -r` 它的 stack 與定義，之後掛成 `annC` | 掛得上、`ask hi-C` 有答；新 daemon 起了新 pid，沒去碰舊行程。這次剛好閒著；若抄的當下正在寫 history 或等腦回信，可能抄到半行或少一則（沒實測到） |

## 實測怎麼做的

`git archive HEAD`（`19020832c`）抄到 `~/.aos/scratch/top-1121-daemonenv/src/`、複本裡 `install.py`，抄 `templates/start-api` 成 `tree/`，起根、掛 llm kernel 與 ann（假腦，`ask hello` 回 FAKE ANSWER）。每支腳本先 unset 全部 `AOS_*`。工具用 `aos-exec --ws W --stack <ann stack>/tools/<工具>/` 照 agent 叫法跑。搬家實測另起 `tree2/`。收尾兩棵都 `aos-daemon-ctl -d .stack shutdown`，確認兩個根行程不在、沒有殘留行程；夾留著沒刪。
