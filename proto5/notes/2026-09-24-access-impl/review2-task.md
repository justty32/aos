← [第二輪報告](round2.md)

# astra 唯讀審查任務書（第二輪，2026-09-24）

你是唯讀審查者。repo 在目前資料夾；**不要改任何檔**，只回報。用繁體中文、白話。

## 背景

proto5 的權限牆（`access.json`＋`aos-jail`＋bwrap）第一輪已審過（`proto5/notes/2026-09-24-access-impl/review-astra.md`）。
使用者對五題拍了板，這輪照裁決改了程式與規範。用 `git log --oneline main..HEAD` 與 `git diff main..HEAD` 看這輪改了什麼。

裁決：

1. **檔案工具（read／write／edit／ls／grep／find）的根改成整個 `/work`**：牢裡看得到 access.json 掛進來的全部；唯讀掛的只能讀，寫進唯讀掛點要被擋、錯誤訊息看得懂。bash 本來就是整個 /work，改完兩邊一致。
   做法：`aos-jail` 多設 `AOS_TOOL_FENCE=/work`、掛完後 `--remount-ro /`（牢的根含 /work 本身唯讀）；`tools/base/_common.py` 的範圍檢查改用 fence；寫入遇到 `EROFS` 回 `ReadOnly`。
2. 換起點或改表時不自動告訴模型：程式不動，文件補一句「記得 `aos-agent say`」。
3. `access set` 相對路徑照殼的目前資料夾算：程式不動，文件補提醒。
4. **有工具的家卻沒有 access.json 時拒跑**：送件時要關牢的工具（沒寫 `_jail: false`）一律不送（`NoAccess`），給模型一段看得懂的話（含要跑的那行指令），log 也印；`check` 從 warn 改成 bad；`aos-agent init` 改成直接寫一份預設 access.json（只掛 workspace）。
5. `tools rm` 不改。

## 請查

- 第 1 點：有沒有辦法讓 base 的檔案工具碰到 `/work` 以外（符號連結、`..`、`/proc/self/root`、`/opt/tool` 等）？`AOS_TOOL_FENCE` 能不能被工具自己或 `_meta.envs` 蓋掉而放大範圍（注意 `--setenv` 對 `AOS_*` 的過濾）？沒關牢（`_jail: false`、舊 base 工具包副本）時行為有沒有變？`--remount-ro /` 會不會弄壞既有的東西（/tmp、/dev、/proc、`/opt/tool`、可寫 mount）？`ReadOnly` 訊息的判斷對不對（例如可寫 mount 裡某個子資料夾剛好不能寫的情況）？
- 第 4 點：有沒有路徑能在沒有 access.json 時讓要關牢的工具仍被送出（例如 state 裡舊的 `batch.access`、崩潰重送、`_jail` 寫成非 bool、think 批）？`check` 的判斷跟送件的判斷一致嗎？init 寫的預設表會不會跟信任資料重疊（`AccessUnsafe`）？
- 規範（`proto5/spec/agent/access.md`、`proto5/spec/aos-agent/access.md`、`proto5/spec/aos-exec/aos-jail.md`、`proto5/spec/agent/tools-opt.md`、`proto5/spec/aos-agent/tools-manage.md`、`proto5/tools/README.md`）與教程 `proto5/tutorials/04b-access-and-tool-admin.md` 的句子跟程式一致嗎？
- 測試有沒有漏掉改到的行為；有沒有測試是「把新規則放水」才過的。

## 回報格式

分三段：**必修**（會造成安全漏洞、錯的行為、規範跟程式不一致）、**建議**、**不用改但值得記**。每條：一句話講問題、在哪個檔哪幾行、怎麼修。沒有就寫「無」。
