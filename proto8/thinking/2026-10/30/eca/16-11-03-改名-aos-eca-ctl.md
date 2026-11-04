← [入口](README.md)｜涵蓋：11-03 改名：aos-eca-hub → aos-eca-ctl（使用者原文、頂層代定，可翻案）｜上一份 [15-實作時代定](15-實作時代定.md)｜下一份 [17-11-03-批次-status](17-11-03-批次-status.md)

## 11-03 改名：aos-eca-hub → aos-eca-ctl

使用者 11-03（逐字）：「aos-eca-hub應該改名為aos-eca-ctl」

### 決定（11-03，使用者）

指令 `aos-eca-hub` 改名 `aos-eca-ctl`（說明在 extras/eca_ctl）。

### 頂層代定（11-03，可翻案）

1. **跟著改的檔名**：執行檔 `extras/eca_hub/bin/aos-eca-hub` → `extras/eca_ctl/bin/aos-eca-ctl`、資料夾 `extras/eca_hub/` → `extras/eca_ctl/`、測試 `tests/test_eca_hub.py` → `tests/test_eca_ctl.py`（照 C-54「對外指令名＝資料夾名底線換連字號」）。
2. **不留舊名**：沒有 `aos-eca-hub` 別名或轉接殼，跟 11-02 `AOS_DAEMON` → `AOS_DAEMON_STACK` 同例（舊名退場）。
3. **內部名字不動**：`eca_reap`（daemon 上的子 loop 名）、小格的 `eca.json`、`reap/loop.json` 都不帶 hub，照舊；`reap/loop.json` 叫的程式跟著改成 `../bin/aos-eca-ctl`。說明、help、stderr 前綴（`aos-eca-ctl: 代號 原因`）跟新名。
4. **舊紀錄照舊名**：thinking、session_logs、digest 裡帶日期的紀錄不改字，只把連到 `extras/eca_hub/` 的連結改指新路徑（不然會斷）。活文件（README、CONVENTION P-43、code map、SESSION-LOG／HANDOFF 那幾行）改成新名或補「11-03 改名」。
5. **概念條文不改寫、只加註**：[C-54 R13](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md) 的例子 `aos-eca-hub` 與功能 `hub`、NORMS N-63 的歷次修改紀錄（10-30 夜「aos-hub 改做 aos-eca-hub」）是當時的條文與紀錄；C-54 照 11-01 aos-round 那次的先例加一句 11-03 加註，條文改不改由使用者定；N-63 只把連結改指新資料夾、旁邊註「11-03 改名」。
6. **試驗場不動**：`~/code/playground` 裡的拷貝（不在 git）沒改；裡面若有寫死 `aos-eca-hub` 或 `extras/eca_hub` 的，要用時自己換。

## 11-03 再改名：aos-eca-ctl → aos-eca

使用者 11-03（逐字）：「好像也不用aos-eca-ctl，改成aos-eca就好。」

### 決定（11-03，使用者）

指令 `aos-eca-ctl` 改名 `aos-eca`（說明在 extras/eca）。

### 頂層代定（11-03，可翻案；做法同上一節）

1. **跟著改的檔名**：`extras/eca_ctl/` → `extras/eca/`、`extras/eca/bin/aos-eca-ctl` → `extras/eca/bin/aos-eca`；測試 `tests/test_eca_ctl.py` → **`tests/test_eca_cmd.py`**（`tests/test_eca.py` 已經是 `demo/eca-claude` 範本的測試，撞名，所以另取）。
2. **不留舊名**：沒有 `aos-eca-ctl` 別名；help、stderr 前綴（`aos-eca: 代號 原因`）、`reap/loop.json` 叫的程式（`../bin/aos-eca`）跟新名；`eca_reap`、小格的 `eca.json` 不動。
3. **舊紀錄照舊名**：thinking、session_logs、digest 帶日期的紀錄不改字，只把連到 `extras/eca_ctl/` 的連結改指 `extras/eca/`；本檔檔名（`16-11-03-改名-aos-eca-ctl.md`）也不改，免得一堆連結跟著斷。活文件（README、CONVENTION P-43、code map、SESSION-LOG／HANDOFF）換新名；寫著「11-03 改名 aos-eca-ctl」的地方補「同日再改 aos-eca」。
4. **概念條文只加註**：C-54 R13 的 11-03 加註、NORMS N-63 那兩處同樣補「同日再改 aos-eca」，條文本身不改。
5. **名字跟 R13 的關係**：`aos-eca` 只有領域、沒有功能段（R13 寫 `aos-<領域>-<功能>`）；使用者親口定的名字，照用，R13 那條不跟著改，旁邊加註。
