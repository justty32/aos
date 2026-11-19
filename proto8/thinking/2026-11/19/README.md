# proto8 討論紀錄：2026-11-19

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [公司WSL-環境-1119](公司WSL-環境-1119.md) | 公司 WSL 的 aos 程式裝到 repo 這層（install.py 退 0、28 支、暫存樹假腦過）；LiteLLM 查清兩台版本（家機 1.87.5、公司昨天裝的 1.109.1 還在但登入沒走完），沒起，版本待使用者拍板 |
| [aos-compile-庚](aos-compile-庚/README.md) | 庚的設計稿：一支 `agent.py` 宣告 SYSTEM／TOOLS／LLM／FSM 生出定義夾的 json；使用者答完六題，定調「好比C語言和.o之間的關係」——重生直接蓋、產出後的 json 照常能改、不記帳；第一刀只加 lib、骨架、測試，範圍說明已寫好；跟除錯線的接點與「插進 json 的東西重生就沒了」記著，沒改程式 |
| [litellm-1.109.1-實測](litellm-1.109.1-實測.md) | 公司 WSL 的 ~/litellm-proxy（1.109.1）起起來留著跑；三個 ChatGPT 模型非串流與串流都 200 回 ok、aos 整條線用 luna 回真字；登入是抄 codex 的同一份 token（續期時一邊會被登出）；附進 repo 的盤點，推薦併進 llm_proxy 當子夾，待使用者裁 |
| [subuid-1119](subuid-1119.md) | aos-daemon 認 `limits.user: "sub:N"`：免 root 把 proc 換成 subuid（linux-as-hw 乙案、kernel-limits-plan 段 3 最小一刀，commit 368719e7a）；公司 WSL 缺 newuidmap，真換身分等使用者 `sudo apt install uidmap` 後補驗；待拍板 Q1：家目錄 750 怎麼讓 subuid 穿過去（推薦 `setfacl -m g:160000:x ~`） |
| [aos-gdb-1119](aos-gdb-1119/README.md) | aos 的 gdb：使用者把斷點定義成「條件成立就停 loop／fsm 等檢閱」；實測今天不改程式就湊得出來（條件＝hook 或觀察者 proc，停＝ctl pause，續不丟東西），四案推薦先試乙（條件放 hook、庫幫裝），沒有要使用者先說的題；順手發現 fake_slow 模板路徑壞了，沒改程式 |
| [aos-compile-庚-第一刀](aos-compile-庚-第一刀.md) | 庚第一刀施工完：加 agent_spec.py、templates/agent-python 骨架、test_agent_spec；七條驗收在乾淨複本全過（含假腦 ctl add 有回），獨立審查兩條必修已修；沒動 agent_def／知識庫／現有範本；repo 裡還沒 install.py，等使用者點頭 |
| [aos-compile-庚-第三刀](aos-compile-庚-第三刀.md) | 庚第三刀施工完：agent.py 多 HOOKS（ag.stock_hooks 抄範本那組）、FILES、不宣告 FSM 的 eca 模式；reviewer 寫成一支 agent.py 跟手寫等價；test_agent_spec 24 支過、假腦實跑帶 hook 有回；沒動 agent_def／知識庫／現有範本；repo 還沒 install.py；兩題使用者 11-19 裁定維持現狀（骨架不帶 hook、stock_hooks 用抄） |
| [aos-compile-庚/12-Argon審與採納](aos-compile-庚/12-Argon審與採納.md) | 庚補正統流程的 Argon 審：設計稿、第一刀程式各送一次共 29 點，核實後多半已處理或不符事實；開著的六個小洞（META 鍵、by_hand agent.py、改名順序等）第三刀版仍在，列給施工線；第二刀使用者 11-19 裁定劃掉；除錯插入要不要落在 stack 還沒裁；沒改程式 |
| [aos-gdb-lib-第一版](aos-gdb-lib-第一版.md) | aos-gdb 第一版（乙案）：aos-gdb NAME 開接上 agent 的 Python REPL，aos.gdb 下條件觸發器（普通 hook，成立就 ctl pause 並留字條）、看為什麼停、檢閱、續；hook 與 cpp 沒動；Argon 審過沒推翻先乙；假腦實跑 6 個情境過 |
| [aos-ns-1119](aos-ns-1119/README.md) | 命名空間與標準庫調查設計稿：今天沒有全域名字表，工具名同名會悄悄蓋（實測）；使用者 11-19 選項框裁走 B 資料夾即命名空間（std 隨 aos 發、短名，別的庫工具帶 庫名_、撞了生成時報錯、執行期不動）、std 先不搬、照叫 std；別的庫放哪與包改成抄暫照推薦；C-74、C-87 加註待補；第一刀（只改 agent_spec）等使用者說開工 |
| [aos-gdb-lib-第二版](aos-gdb-lib-第二版.md) | aos-gdb 第二版：stop_before_tool 改成工具跑之前真的停住（觸發器在 hook 裡扣住等放行，續＝照原樣跑或跳過），另做丙（掛在 daemon 表上的觀察者 proc，輪詢目標、成立就 pause）；hook 與 cpp 沒動；Argon 審 A1～A10 八條照改；假腦實跑 12 個情境過；要拍板兩題 11-19 已裁（表上不顯示扣住＝解耦合、sh 退 10 規則維持） |
| [aos-ns-第一刀](aos-ns-第一刀.md) | 命名空間第一刀施工完（只改 agent_spec、執行期沒動、沒搬檔）：agent.py 改寫 std.pack／std.tool／std.fsm／std.hooks，別的庫 ag.lib(名, 根)；包生成時展開進 tools.json（不寫 $override），別的庫工具自動帶 庫名_、std 短名，撞名與讀不到庫根報 SpecBad；工作區小庫驗收與假腦起樹實跑都過、test_agent_spec 33 支過；第 6、7 題仍暫照推薦，C-74、C-87 加註待使用者點頭 |
| [aos-inherit-1119](aos-inherit-1119/README.md) | 繼承深挖調查設計稿：繼承在 aos 真正算數的只有「一份底＋一小份差異」的兩面（agent.py 重生時衍生、stack 執行時長出來）；實測五個意外；使用者 11-19 選項框裁：走乙（ag.load，第一刀未開工）、「繼承」進規範只限生成時（新增 N-70，10-14 不做繼承在 json 與執行時那層照舊）、長出來的不收回、狀態機每隻一層先不做，出處暫照推薦只寫原始碼（08） |
| [aos-pylib-1119](aos-pylib-1119/README.md) | 整套 Python 庫版面調查設計稿：三塊（寫定義、除錯、其他）＋29 支指令盤點、一天 21 步對照（必要的四樣）、入口 aos.py＋把手式 a = agent.attach(名)＋一條通則做成通用代理（aos-agent／aos-daemon-ctl 子指令自動有 Python 寫法）、薄殼硬規則（延伸只有 a.bp、a.look）；Argon 審後寫定義與 aos.gdb 都不搬、整包加工具改加在指令上、tools／mailbox 不預做、先修 install.py 只加不刪；使用者 11-19 選項框裁：入口 aos.py、把手式、建斷點 a.bp.add.before_tool("x")（字串式不留）、讀檔收進 a.look，隨手 python3 暫照推薦（07）；三刀開工等使用者說 |
| [aos-inherit-第一刀](aos-inherit-第一刀.md) | 繼承第一刀施工：ag.load＋TOOLS／HOOKS／ag.fsm 收底（墓碑、帶標記 hook 組、換格），只動 agent_spec*，json 整份不記上一層、執行期沒動；骨架找套件兩處小洞順手修；收緊兩組 hook 互撞改報錯；測試 42 過、假腦實跑過。未決：ag.from_folder 沒做。 |
