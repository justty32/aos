# proto8 討論紀錄：2026-11-19

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [公司WSL-環境-1119](公司WSL-環境-1119.md) | 公司 WSL 的 aos 程式裝到 repo 這層（install.py 退 0、28 支、暫存樹假腦過）；LiteLLM 查清兩台版本（家機 1.87.5、公司昨天裝的 1.109.1 還在但登入沒走完），沒起，版本待使用者拍板 |
| [aos-compile-庚](aos-compile-庚/README.md) | 庚的設計稿：一支 `agent.py` 宣告 SYSTEM／TOOLS／LLM／FSM 生出定義夾的 json；使用者答完六題，定調「好比C語言和.o之間的關係」——重生直接蓋、產出後的 json 照常能改、不記帳；第一刀只加 lib、骨架、測試，範圍說明已寫好；跟除錯線的接點與「插進 json 的東西重生就沒了」記著，沒改程式 |
| [litellm-1.109.1-實測](litellm-1.109.1-實測.md) | 公司 WSL 的 ~/litellm-proxy（1.109.1）起起來留著跑；三個 ChatGPT 模型非串流與串流都 200 回 ok、aos 整條線用 luna 回真字；登入是抄 codex 的同一份 token（續期時一邊會被登出）；附進 repo 的盤點，推薦併進 llm_proxy 當子夾，待使用者裁 |
| [subuid-1119](subuid-1119.md) | aos-daemon 認 `limits.user: "sub:N"`：免 root 把 proc 換成 subuid（linux-as-hw 乙案、kernel-limits-plan 段 3 最小一刀，commit 368719e7a）；公司 WSL 缺 newuidmap，真換身分等使用者 `sudo apt install uidmap` 後補驗；待拍板 Q1：家目錄 750 怎麼讓 subuid 穿過去（推薦 `setfacl -m g:160000:x ~`） |
| [aos-gdb-1119](aos-gdb-1119/README.md) | aos 的 gdb 在哪：板子到應用程式 aos 每格都有、除錯零件多沒成品；實測會等的 before_tool hook 就是斷點、跑著時加工具與插 fsm 格不用停；六案（推薦乙：斷點是檔、Python 薄殼）與七題待使用者答（第一題斷點先顧哪一層）；插進 json 的東西重生即消失列為邊緣，沒改程式 |
