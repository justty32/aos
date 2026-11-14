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
