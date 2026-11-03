← [入口](../2026-10-30-eca.md)｜涵蓋：11-03 改名：aos-eca-hub → aos-eca-ctl（使用者原文、頂層代定，可翻案）｜上一份 [15-實作時代定](15-實作時代定.md)｜下一份 [17-11-03-批次-status](17-11-03-批次-status.md)

## 11-03 改名：aos-eca-hub → aos-eca-ctl

使用者 11-03（逐字）：「aos-eca-hub應該改名為aos-eca-ctl」

### 決定（11-03，使用者）

指令 `aos-eca-hub` 改名 `aos-eca-ctl`（說明在 [extras/eca_ctl](../../extras/eca_ctl/README.md)）。

### 頂層代定（11-03，可翻案）

1. **跟著改的檔名**：執行檔 `extras/eca_hub/bin/aos-eca-hub` → `extras/eca_ctl/bin/aos-eca-ctl`、資料夾 `extras/eca_hub/` → `extras/eca_ctl/`、測試 `tests/test_eca_hub.py` → `tests/test_eca_ctl.py`（照 C-54「對外指令名＝資料夾名底線換連字號」）。
2. **不留舊名**：沒有 `aos-eca-hub` 別名或轉接殼，跟 11-02 `AOS_DAEMON` → `AOS_DAEMON_STACK` 同例（舊名退場）。
3. **內部名字不動**：`eca_reap`（daemon 上的子 loop 名）、小格的 `eca.json`、`reap/loop.json` 都不帶 hub，照舊；`reap/loop.json` 叫的程式跟著改成 `../bin/aos-eca-ctl`。說明、help、stderr 前綴（`aos-eca-ctl: 代號 原因`）跟新名。
4. **舊紀錄照舊名**：thinking、session_logs、digest 裡帶日期的紀錄不改字，只把連到 `extras/eca_hub/` 的連結改指新路徑（不然會斷）。活文件（README、CONVENTION P-43、code map、SESSION-LOG／HANDOFF 那幾行）改成新名或補「11-03 改名」。
5. **概念條文不改寫、只加註**：[C-54 R13](../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md) 的例子 `aos-eca-hub` 與功能 `hub`、NORMS N-63 的歷次修改紀錄（10-30 夜「aos-hub 改做 aos-eca-hub」）是當時的條文與紀錄；C-54 照 11-01 aos-round 那次的先例加一句 11-03 加註，條文改不改由使用者定；N-63 只把連結改指新資料夾、旁邊註「11-03 改名」。
6. **試驗場不動**：`~/code/playground` 裡的拷貝（不在 git）沒改；裡面若有寫死 `aos-eca-hub` 或 `extras/eca_hub` 的，要用時自己換。
