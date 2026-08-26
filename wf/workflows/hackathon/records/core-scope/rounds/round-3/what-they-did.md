# 第 3 輪紀錄 — 各人這輪改了什麼

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/what-they-did.md)

四位這一輪各自改了什麼、只攻哪幾個窗口、成果放到哪個路徑，逐人一段。

## 1. 各人這輪改了什麼

**Carmack persona。** 沒有再擴充整條 loop，只補評委指定的兩個 Effect 窗口：response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit。兩案都把同一條 resolve 連跑兩次，量第二次的 commit delta、provider ledger delta 與 final hash；另新增 `response_ready_done_missing`、`decision_ready_done_missing` 與 `adopt-ready-response`。上一輪只做到 unknown 的明示決策，這輪補的是已有完整 response 或已有 decision 後，重開只投影 done、不得再叫 provider。R2 的 `/tmp` 已消失，因此先以 R1 baseline 做 byte-for-byte continuity gate，再於 `/tmp/aos-core-scope-p1-r3/round3/` 重建最小 R3 原語。

**Armstrong persona。** 沒有重跑前兩輪的整條假模型 loop，改攻上一輪尚未解的 consumer acknowledgment。producer receipt 降為 visibility evidence；completion ack 改由 aggregate consumer 在 `claim → aggregate publish → delete delivery → ack commit` 中留下，且 `aos exec` 前必須先通過 ack gate。四刀分別砍在 target、claim、delete、ack 之後，每案重開兩次、再把 `aos exec` 叫兩次；另加一個不合作 consumer 直接刪 ready、但不寫 claim／ack 的反例。上一輪的 `adopt-consumed`、人工 `mv` 與重造半批 instruction 在這份原型裡消失。R2 的 `/tmp` 已消失，R3 重建於 `/tmp/aos-p2-round3.KcFA3d/`。

**Cantrill persona。** 沒有再改 Publish／Deliver 路線；這輪修正上一輪第一個數字的量詞，把同一份 source inventory 分成實作份數、靜態呼叫點、runtime transaction、人工 rename，題目答案固定取實作份數。另以 `ctypes` 直接呼叫現有 `libaos_inst` C ABI，逐案對照私有 validator 與 canonical parser，不再把私有 schema 當成等價。R2 的 `/tmp` 已消失；兩支 v2 腳本依上一輪內容復原後，SHA-256 與 manifest 相同，再於 `/tmp/p3-core-scope-round3/` 重跑三回合閉環。沒有 hash 的其他 R2 raw artifacts 沒有宣稱復原。

**Thompson persona。** 只測評委指定的 publish 成功但 receipt 未回，以及 consumer 已取走 target 但 ack 未寫。新增只回 `Already`、`Unknown`、`Conflict` 的窄 Deliver 分類器，並製造「publish 前被殺」與「已消費、ack 前被殺」兩段 producer 可見現場，再用完全相同的 Deliver 命令重試。第一版 consumer 用 `mv`，因 hard-link 的 `st_nlink` 洩漏歷史而整案作廢；固定版改成 copy＋unlink，確認兩邊 `links=1` 後重跑於 `/tmp/p4-round3-fixed/`。R2 的 `/tmp` 同樣已消失。
