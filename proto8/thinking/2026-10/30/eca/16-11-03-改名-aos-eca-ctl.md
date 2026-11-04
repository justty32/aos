← [入口](README.md)｜涵蓋：11-03 改名：aos-eca-hub → aos-eca-ctl（使用者原文、頂層代定，可翻案）｜上一份：[14-11-02-晚使用者想法](14-11-02-晚使用者想法.md)｜下一份：[17-11-03-批次-status](17-11-03-批次-status.md)

## 11-03 改名：aos-eca-hub → aos-eca-ctl

使用者 11-03（逐字）：「aos-eca-hub應該改名為aos-eca-ctl」

### 決定（11-03，使用者）

指令 `aos-eca-hub` 改名 `aos-eca-ctl`。同日再改 `aos-eca`（下一節），代定都寫在下一節。

## 11-03 再改名：aos-eca-ctl → aos-eca

使用者 11-03（逐字）：「好像也不用aos-eca-ctl，改成aos-eca就好。」

### 決定（11-03，使用者）

指令 `aos-eca-ctl` 改名 `aos-eca`（說明在 extras/eca）。

### 頂層代定（11-03，可翻案）

1. **跟著改的檔名**：資料夾 `extras/eca/`、執行檔 `extras/eca/bin/aos-eca`（C-54「對外指令名＝資料夾名底線換連字號」）。
2. **不留舊名**：沒有 `aos-eca-hub`、`aos-eca-ctl` 別名或轉接殼（同 11-02 `AOS_DAEMON` → `AOS_DAEMON_STACK`）；help、stderr 前綴（`aos-eca: 代號 原因`）跟新名；小格的 `eca.json` 不動。
3. **舊紀錄照舊名**：thinking、session_logs、digest 帶日期的紀錄不改字，只把連到舊資料夾的連結改指 `extras/eca/`；本檔檔名（`16-11-03-改名-aos-eca-ctl.md`）也不改，免得連結斷。活文件（README、CONVENTION P-43、code map、SESSION-LOG／HANDOFF）換新名。
4. **概念條文只加註**：[C-54 R13](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md) 的例子 `aos-eca-hub` 與 NORMS N-63 的歷次修改紀錄是當時的條文，各加一句 11-03 加註（改名 aos-eca-ctl、同日再改 aos-eca），條文改不改由使用者定。
5. **名字跟 R13 的關係**：`aos-eca` 只有領域、沒有功能段；使用者親口定的名字，照用，R13 不跟著改，旁邊加註。
6. **試驗場不動**：`~/code/playground` 裡的拷貝（不在 git）寫死舊名的，要用時自己換。
