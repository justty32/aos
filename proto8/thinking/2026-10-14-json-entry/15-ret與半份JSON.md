# 2026-10-14 深夜收尾：ret／err 增長、半份 JSON、今晚交接

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[14-h拍板](14-h拍板.md)

## 42. 使用者拍板（經協調 agent 轉達，使用者兩題都說「隨你」）

1. **【拍板】ret／err 無限增長＝方案 B。** 基礎實作：daemon 起子 loop 時 stdout 接 `/dev/null`，結果一律從 state 窗讀；stderr 照舊 append 到 `work_dir/N/err.json`，只在出錯時長，`ret.json` 不再有。標準實作才做：stdout／stderr 選填路徑＋上限輪替、不帶 `load` 重起時清掉 table 沒列到的舊格子。落點：[NORMS 待定](../../NORMS/04-待定.md)該條結案、[lib daemon.md](../../lib/daemon.md)、`aos_daemon_table._spawn()`。
2. **【拍板】被殺時 stdout 最後一份只寫一半＝半份不算。** 讀的人只認完整、能解析的 JSON；解析不了就忽略；因此找不到結果＝沒有結果。落成 [N-12](../../NORMS/01-定了的-N01至N13.md) 附註。

## 43. 結論

- 現有程式本來就這樣做，不用改：tasks（`aos_tasks._code`）從最後一行往回找第一份帶整數 `code` 的物件，找不到報 `ResultUnreadable`；loop（`_Tail` 只記最後一行、`_json` 解析失敗回空）記 `code` null。補了一個測試（`test_half_json_ignored`）。

## 44. 今晚交接（明天從這裡開始）

**已完成**：七題回覆（[12](12-七題回覆.md)）；NORMS N-18～N-34；inst／loop／daemon 照 N-12 重做（基礎實作）；tasks 改讀子 aos-inst 的 stdout（N-34）；N-12 跑完判定改成「stdout 吐出結果＋行程結束，有 exit 檔則出現也算」；本份兩題；三份網頁已更新：

- 選擇題解說（58 題）：https://claude.ai/artifact/DKBifn39yRtYDGjwGEAzC5
- inst／loop／daemon 重做：https://claude.ai/artifact/HGkzKJKAsEAwhv1dQPQX8d
- aos-llm 與 fsm：https://claude.ai/artifact/K2aQ7KCad1u3dFTfDvArda

**尚未決定**：[NORMS 待定](../../NORMS/04-待定.md)剩下的——aos-fsm 寫成 N 條文、a～f 暫定預設（全部可改）、資料夾別亂弄的細則、argv[0] 程式的規矩、kernel 公告、時鐘格式、`檔#/位置` 要不要列規範、`_metainfo` 通用寫法。

**新發現的不一致**：58 題頁第三組 Q12 說 agent 心跳「可選」，但 [N-32](../../NORMS/06-實作細則-N29至N34.md) 規定每秒一次、不開 key。留給做 aos-fsm 時對齊。

**下一步候選**（等使用者開口挑）：aos-fsm 同步版 demo（think 格阻塞跑，基礎實作）；aos-fsm 寫成 N 條文；標準實作的 stdout／stderr 輪替與清舊格子。
