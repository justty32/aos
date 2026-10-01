# daemon 記住狀態模組：暫停與已停跨重開

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜格式：[P-123](../protocol/daemon/state.md)

本篇只有 B-643，寫記住狀態模組**做什麼**。設定的寫法、狀態檔的格式，寫在格式篇 [P-123](../protocol/daemon/state.md)。

依據：[verdicts 11 篇末「2026-10-01 第十一批：daemon 模組」](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十一批daemon-模組)、[plan m3m 模組三](../../../plan/m3m-daemon-modules.md#模組三記住狀態modulesstate)；現行程式 [記住狀態](../../../src/py/README.md#重讀設定與記住狀態m3m)（`lib/aos_daemon_state.py`，有出入以程式為準）。

## B-643：記住狀態模組〔使用者 2026-10-01 第十一批〕

**把每一項「暫停」「已停」這兩個狀態記在一個檔裡，daemon 重開時讀回來。** 它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了 `modules.state` 才有。

### 設定就是狀態檔

- `modules.state` 在原始設定檔裡**必須寫成 `$ref`**，指向狀態檔（使用者原話：「"state":{"$ref":...}會比較好，因為有時候它會頻繁被改動。」）。相對檔名跟其他 `$ref` 一樣，以設定檔所在資料夾為準。
- 所以展開後 `modules.state` 的內容就是目前的狀態：哪幾項暫停、哪幾項已停。
- **狀態檔不在＝全部正常**，不算設定錯；第一次要寫時才建。
- 寫成別的樣子（不是 `$ref`、帶 `#` 位置）算設定錯，daemon 不開始跑（[P-123](../protocol/daemon/state.md)）。

### 什麼時候寫

- 某一項的暫停或已停**一變就當場寫整份**：`pause`、`resume`（[B-641](control.md)）、被 `stop_on_nonzero` 停掉（[B-640](core.md)），以及重讀設定拿掉了項（[B-642](reload.md)）。內容跟上次一樣就不寫。
- 先寫同資料夾的暫檔再改名蓋過去，寫到一半被殺也不會留下半個檔。
- 只記暫停與已停兩個狀態。**不記**待補的那次叫醒、上次什麼時候跑完、上次的結束碼（使用者 2026-10-01 同意 S1：第一版不記，所以重開後沒暫停、沒停的項照樣先跑一次）。

### 開起來時

- 還在 `insts` 裡的項，照檔恢復成暫停或已停，**這些項開起來不先跑那一次**；stdout 印跟平常同樣的行（`paused`、`stopped`），在任何 `exit=` 行之前。
- 檔裡有、`insts` 裡沒有的鍵：丟掉，下一次寫檔時就不見了。
- 恢復成暫停的：照 [B-641](control.md)，`resume` 後馬上跑；暫停中 `wake` 跑一次、跑完照樣暫停。恢復成已停的：`wake` 回 `stopped`，要 `resume` 才救得回。

### 已停也跨重開

被 `stop_on_nonzero` 停掉的項重開 daemon 也不會再跑（使用者 2026-10-01 同意 S2）：重開不會讓一個已經壞掉的項默默又開始跑。要救回：掛了控制模組就 `aos-ctl resume`；沒掛控制模組就刪掉狀態檔（或刪掉檔裡那一項）再重開。

### 跟其他模組

- **控制模組**：暫停只能經控制模組下；沒掛控制模組時，這個模組只記得住「被 `stop_on_nonzero` 停掉」。
- **重讀設定**：重讀以記憶體為準，不拿狀態檔覆蓋（[B-642](reload.md)）。
- **擋板檔**：tick 那層的擋板檔照舊是 tick 的事，跟這個不衝突。

依據：使用者 2026-10-01 第十一批：「S1～S3 都照建議」；設定改成 `{"$ref": …}`。

**驗收：**掛控制與狀態模組，`aos-ctl pause a`：狀態檔裡 `a` 是 `paused:true`；Ctrl-C 重開：`a` 沒有先跑、stdout 有 `inst=a paused`、`status` 是 `paused:true`；`resume` 後馬上跑、檔裡 `a` 不見了。`stop_on_nonzero` 停掉後檔裡有 `stopped:true`，重開後它不跑、有 `inst=… stopped`；只掛狀態模組時刪檔重開才再跑。檔裡有設定檔已經沒有的鍵：重開時忽略，下一次寫檔時不見。檔不在：全部照常先跑一次、沒有異常就不建檔。`modules.state` 不是 `$ref`：回 1。測試見 `proto6/src/py/tests/test_daemon_state.py`。
