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
