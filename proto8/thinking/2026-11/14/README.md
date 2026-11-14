# proto8 討論紀錄：2026-11-14

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [proc-mental-model](proc-mental-model/README.md) | proc 新心智模型發想（線程，使用者「不急、單獨派線幫我想想」）：opus 11 個＋fable 8 個（世界線束、樂譜與演奏、可換的軸、光錐、開放系統、展開的 fsm、九軸＝束的統計量、契約、最小作用量…），每個附一句話、小圖、好想處、盲點；純發想，沒定稿、沒出待裁題 |
| [aos-brainstorm](aos-brainstorm/README.md) | aos 頭腦風暴輪（線腦，使用者「太早規劃了…先發想」）：fable 120 條＋Argon 22 條＋opus 匯總，重點題「人是外部計算單元」（人 kernel 讓人更懶、原則回收、行為量好不好懂、沉默六種、代定＝分支預測）、粗化細化與 `_metainfo`／`_index`、公開宣告 vs 私有看法；6 個可丟棄小實驗未跑；取代 11-13 any-resource-os；舊 D1～D16 不裁、自然浮現；沒出待裁題 |
| [astra-kernel-1114](astra-kernel-1114.md) | astra 當 kernel 施工（線星）：暫存樹 `~/code/astra-1114` 階段 0 的 0.1～0.4 過，0.5 門鈴留著、表態、轉寄都通了；新坑 AK14（`agents_ctl stop` 停自己會自鎖到 timeout，`aos-agent ctl` 有 `--no-wait` 但工具沒帶出來）、AK15、AK16；全用假腦，沒改程式；交棒給 ok-astra |
| [misc-1114](misc-1114.md) | 線雜：eca_main 來信七項與線庚剩的（set-def 停拔掛回、睡醒提醒、改名寫法、`AOS_HOME` 那句、真 CLI 實跑）與 T45～T48；只到施工圖與暫存樹（sol 腦通過、工人掛上未派工），程式沒改，交棒 ok-misc；T46 判 bug 可修，T45／T47／T48 牽涉設計只列；真 codex 實跑卡在「不要走codex」待問 |
| [kernel-limits-1114](kernel-limits-1114.md) | kernel 限資源施工（線限）：段 2、段 3 非 C++ 部分寫成三份施工圖紙（B1 kernel 站 `limits`／`users`／`groups`、B2 `aos-share`、B3 `aos-asuser`＋aos-sandbox 認 `sub:N`），暫存樹 `~/code/limits-1114` 與接 LiteLLM 的 gpt 隊搭好；還沒派工、沒寫碼，交棒 ok-limits；實作級代定 D1～D9、坑 K-a～K-g |
| [kernel-framework-1114](kernel-framework-1114.md) | 通用 kernel 框架（線框，家機）：批 5 接線做到七成（暫存 `~/code/kf-1114/b5`，沒跑測試、沒進 main，三個設計題待正規流程）；gpt agent-fsm 施工隊暫存樹 `~/code/kf-1114/fsm` 步驟 1～6 驗過、乾跑未跑；批 10 圖紙寫好未派；codex 照「不要走codex」收掉；交棒 ok-kf |
| [quiet-1114](quiet-1114.md) | 清淨時段小工具（repo-aos 自己的免打擾）：`wf/tools/quiet.py`（開 30m／關 off／status）、`quiet_hook.py`（before_queue，清淨期間擋 new_mail、kernel_hold、放行 xiaosi 與其他訊息）、`quiet_tick.py`（到期後合併成一則 `[aos] quiet_over` 寄回）；暫存樹實測與 7 題單元測試過、kernel_gate 請求不因通知被擋而消失；已掛活樹 repo-aos（備份在 `~/.aos/saves/tree-swap/quiet-1114-083239/`），未開清淨 |
| [skyrim-agentctl](skyrim-agentctl/README.md) | skyrim agentctl／wf 借鑑調查（skyrim-agent 線，使用者「看看那邊有啥…可以借鑑與參考」「fable作爲kernel，底下帶astra,sol」）：**進行中、已交棒給 ok-skyrim**；sol 蒐集五份落檔（通訊信箱、資源鎖與守門、等使用者與教訓庫、團隊模型、BRIEF lint），還缺兩塊；借鑑清單未寫；隊形心得草稿在交棒（中途改成不走 codex、sol 走 LiteLLM 上的 agent-fsm）；沒出待裁題 |
