# KISS 審稿：總則與共通層（NORMS 01／06／08、NORMS.md；lib aos_cli、aos_directives、aos_tree、directives.md、README.md；test_cli／test_directives／test_tree）

← [討論紀錄](../README.md)｜最高原則：KISS（10-15 深夜使用者定，C-52、C-53 在它底下）｜只寫稿，程式、規範、索引一字未改｜不重提 [inst-exec 第三版](../2026-10-15-inst-exec-v3.md) 已定的事（TARGET 拿掉、旗標與 `-` 收進 aos-exec、刪 aos_tree），只看它還能不能更簡。

每條：現況 → KISS 版；要動到；風險。全部直接給推薦。

## 一、規範條文

**1. `檔#/位置`（N-35）整條退出規範。**
現況：總則用一條 8 行講 `#` 怎麼切、資料夾怎麼找 inst.json、`AOS_DIRNAME`、id 的形狀；v3 的 aos-exec 還留著 TARGET 接 `#/位置`。
KISS：`#/位置` 只活在 `$ref` 裡（語法糖，寫在 aos_cli 檔頭）；aos-exec TARGET 只收檔或資料夾，不接 `#/位置`——要一份檔裡的一格就 `{"$ref": "x.json#/a"}`。id 只剩一句併進 N-30：「inst 寫的 `id`；沒寫＝aos-exec 代填檔的 abspath；從 stdin 來又沒寫＝null」。
要動：NORMS/01、06、NORMS.md；aos_directives（`split_target`、`target_id`、`locate`、`resolve(at=)` 全退）；aos_cli `load_target`；aos_inst；test_cli、test_directives、test_inst。
風險：10-15 早使用者親口「`檔#/位置` 可以列進」；但 demo 零處用 TARGET 接 `#/位置`，daemon children 在 v3 也改內嵌了，整條只剩測試在用。

**2. `AOS_DIRNAME`／`.aos/inst.json` 刪。**
現況：資料夾 TARGET 先找 `<資料夾>/$AOS_DIRNAME/inst.json`、再找 `<資料夾>/inst.json`，外加 `DirnameBad` 錯與一段驗名字的程式。
KISS：資料夾＝只找 `inst.json`。想把 aos 的東西藏起來就 `aos-exec .aos`，一字不多。
要動：aos_inst `dirname()`／`find()`、inst.md、test_inst；N-35（隨 1 一起消失）。
風險：10-15 收工後使用者「都AOS_DIRNAME」才定；demo、paint 全沒用到（paint README 自己寫「沒展示到」）。

**3. NORMS/06 整檔刪。**
現況：N-21～N-23（TARGET／`-`、鏡射旗標、旗標優先序）加一句指向 directives.md。
KISS：v3 已把旗標、`-`、`--` 全收進 aos-exec；三條就都只是一支語法糖的用法，寫在 aos_exec 檔頭就好。N-22 自己說「不是硬規則」。
要動：NORMS/06 刪、NORMS.md 主題表少一列；v3 影響清單的「N-21～N-24 改」變成「刪」。
風險：無。

**4. N-29 與 N-43 併成一條「錯誤出口」，五句。**
現況：N-43 一條 1.9 KB、一半是使用者原話與「10-15 晚使用者『都按照推薦』」；N-29 另一條講 stderr 形狀；兩條互指。
KISS：一條——退 0＝正常、非 0（aos 一律 1）＝有錯；錯＝stderr 一份 `{"error": {"code", "msg"}}`，沒有警告；正常退出不寫 stderr，反過來不成立；每層只說自己，下層的碼只當資料放 stdout／窗；例外兩種：透明轉交（閘門、seq／par／if）、述詞。「daemon 收訊號退 0」搬去 daemon 說明；原話留在 principles 稿（已經在）。
要動：NORMS/01、NORMS.md。
風險：無，原話已在 thinking。

**5. N-12 砍成三句。**
現況：1.4 KB，含「以函數來看」「inst.json 格式不變、作為橋樑」「aos-inst／loop／daemon 已照本條重做」「半份不算」的出處連結、「JSON 串流當省略 `[]` 的陣列」。
KISS：stdin＝參數、stdout／stderr＝結果、exit 碼＝輔助；三者都是 JSON 串流（一份接一份，每份可跨行）；讀的人只認完整的 JSON，半份當沒有。「跑完的判定」與 exit 檔那句搬 N-30（inst 自家事）。
要動：NORMS/01。
風險：「exit 檔出現也算跑完」是 10-14 深夜使用者改的，搬去 N-30 不刪。

**6. N-18 刪「標準實作」這一級。**
現況：實作分基礎／標準兩級；標準實作一行程式都沒有，卻生出兩條待定（fsm 標準實作記不記時間、daemon 標準實作輪替）和各說明頁滿篇「基礎實作」。
KISS：只有一種實作。N-18 剩一句，併進「錯誤出口」那條：「規範沒說的邊緣狀況預設不會發生，出了算呼叫者的」。
要動：NORMS/01、08 的兩條待定、lib 各說明頁的「基礎實作」字樣。
風險：10-14 使用者親定分級；KISS 下「第二級」就是預留的複雜度，真要加再加。

**7. 條文身上的註記全刪：「（草稿）」「（10-14）」「原 h3」「D-3」「10-15 使用者『都按照推薦』」、使用者引文。**
現況：NORMS 九檔 33 個「草稿」、總則一檔 20 個日期標，每條末尾一段出處與引文，條文本身只佔三分之一。
KISS：條文只剩規則；誰定的、哪天定的、原話，去 thinking 與 git 找。NORMS.md 留一句「出處看 thinking」。
要動：NORMS/*.md。
風險：查「這條誰定」要多翻一步；thinking 本來就是為這個留的。

**8. NORMS/08 待定：已定的直接刪。**
現況：6.9 KB，一半是 ~~刪除線~~ 的已定項，底下還掛著當時的原文；「argv[0] 程式的規矩【擱置】」四小點；`grace_ms` 慣例也住在待定裡。
KISS：已定的刪（跟 user.md「被推翻的直接刪，不標刪除線」同一把尺），只留 5 條 open；「argv[0] 規矩」刪（結束碼已進 N-43，另三句是 daemon 自家事）；`grace_ms` 建議值搬 lib loop.md 一行。
要動：NORMS/08、lib loop.md。
風險：無。

**9. NORMS.md 砍「條號 → 檔」表與「各批出處」段。**
現況：8.7 KB：主題表、條號對照表、各批出處；條號表只為了「條文散在九檔找不到」而存在。
KISS：只留主題表（每列本來就寫了條號）；出處段搬 thinking 的月份索引。
要動：NORMS.md。
風險：無。

**10. NORMS 分檔併回一份。**
現況：NORMS.md ＋ 9 個分檔 ＋ 一個 62 bytes 的 README.md；分檔裡 02 只 958 B、09 1.2 KB、06（條 3 要刪）2.2 KB；每檔檔頭一行「概念在哪、規範在哪、實作在哪」互指。
KISS：照 4～9 裁完，規範全部約 12 KB，一份 NORMS.md 裝得下：主題當 `##` 標題、條號照舊不重編、NORMS/ 資料夾與它的 README 刪。
要動：NORMS/ 整個資料夾、所有指進去的連結（lib 說明、CONCEPTS、wf）。
風險：10-15 使用者定「按主題分」——主題還在（標題），只是不再一主題一檔。

**11. 條號體系：N- 留著，但只有一套。**
現況：N-01～N-44 按定下來的日期批次編、跳號、同主題散四處；稿裡又有 D-1～D-6、h1～h16、S1～S5、A～L 幾套臨時號，常被條文引用（「原 h3」「D-3」）。
KISS：規範裡只認 N- 號（當錨點，不重編）；稿內的臨時號不進條文（隨 7 一起刪）。
要動：NORMS/*.md。
風險：無。

**12. 錯誤代號通則一句（寫進條 4 那條）。**
現況：lib 約 50 個代號，`FieldType` 一個用 55 次，其餘大半各用一次、沒人靠它分支；指示詞一支就 7 個。
KISS：「代號只在有人要分支時才開；一支程式不超過五個；設定／引數不對一律 `ConfigBad`、輸入不對一律 `InputBad`，哪裡不對寫 `msg`」。
要動：NORMS/01 一句；各 lib 自己收（inst、loop 等不在本稿）。
風險：測試裡 assert 代號的要跟著改。

**13.（跨範圍，一句帶過）同一個錯兩種形。**
現況：stderr 是 `{"code", "msg"}` 物件，state 窗的 `last_error`／`last_warning` 是「代號: 白話」字串。
KISS：都用物件。
要動：N-29、aos_ctl_state、loop／daemon／kernel（窗是別人的範圍，這裡只標）。
風險：無。

## 二、程式、lib 說明、測試

**14. `$at` 刪。**
現況：`$ref` 的位置可以另寫成 `"$at": "/a/0"`；只有 test_directives 用過。
KISS：位置只有 `檔#/位置` 一種寫法。
要動：aos_directives、test_directives。
風險：無。

**15. `$ref` 的 `./`、`../`、空檔名（指回同一份）三種相對寫法刪。**
現況：位置可以從「這個指示詞所在的位置」往上爬，還要解釋「目前文件」「別的檔是那份檔的根」；demo 零處用，只有 test_loop／daemon／inst 三處拿它共用一段 shell 字串。
KISS：`$ref` 只收「檔#/從根算的位置」；同一份檔裡要共用就拆成小檔——指示詞本來就是拆檔用的（C-48 原話）。
要動：aos_directives `_at()`、`ref()`；三個測試改成寫一個小檔。
風險：無。

**16. `~0`／`~1` 轉義刪。**
現況：JSON pointer 的轉義，只在 aos_tree（要刪）與測試出現。
KISS：key 含 `/`、`~` 的指不到——跟「空字串 key 指不到」「檔名含 `#` 不支援」合成一句「怪名字不支援」。
要動：aos_directives、tests。
風險：無。

**17. 指示詞錯誤代號 7 → 1。**
現況：`DirectiveUnknown`、`DirectiveValueTypeMismatch`、`EnvironmentVariableMissing`、`ReferenceReadFailed`、`ReferenceJsonInvalid`、`ReferencePointerInvalid`、`ReferenceCycle`。
KISS：全是「這份 JSON 寫壞了」同一分支，一個 `DirectiveBad`，`msg` 說哪一格、為什麼。
要動：aos_directives、test_directives、test_inst／loop／daemon 裡 assert 代號的幾行。
風險：唯一靠代號分支的是 aos_tree（已定刪）。

**18. `DirectiveError` 與 `CliError` 併一個；aos_directives.py 併進 aos_cli.py。**
現況：兩檔、兩個一模一樣的例外類，aos_cli 到處 `except DirectiveError → raise CliError`。
KISS：一檔 `aos_cli.py`（估約 120 行）：`CliError`、`read_stream`、`emit`、`error`、`is_int`、`expand`、`resolve`；`split_target`／`target_id`／`locate`／`resolve(at=)` 隨條 1 退場；`parse_argv`／`config`／`load_target` 隨 v3 搬去 aos_exec。
要動：兩檔、所有 `from aos_directives import`、README 相依圖、test_cli ＋ test_directives 併成一檔。
風險：無。

**19. directives.md 刪。**
現況：2.9 KB，跟 aos_directives.py 檔頭逐句重複，還留一段「三支程式一個手感」（早就五支）和 N-35 的實作細節。
KISS：檔頭就是說明（C-54：結構與名字就是說明）；README 一行指到檔頭。
要動：lib/directives.md、lib/README.md。
風險：無。

**20. lib/README.md 兩張表併一張。**
現況：11 KB：「細節（各一份）」表、「程式」表（每格把檔頭重抄一遍）、相依圖、測試段列十二個測試檔各在測什麼、行程規矩段。
KISS：一張表，一檔一行（一句＋連到它的說明頁或檔頭）；相依圖刪（import 一看就有）；測試段只留「怎麼跑」「改 lib 就補一個測試」兩句；行程規矩搬 aos_proc 檔頭。
要動：lib/README.md、aos_proc.py 檔頭。
風險：無。

**21. 隨 aos_tree 一起刪 test_tree.py 的手寫 schema 驗證器。**
現況：test_tree.py 一半是 aos_tree 的測試（v3 已定刪），另一半是一個自製的 mini-jsonschema 拿來驗 `demo/kernels/general/judges/schema.json`。
KISS：整檔刪；schema.json 留著當資料（opinions 5～7 採納的方向），真要驗的那天裝 jsonschema。判官回話的形狀 aos_kernel_judge 執行期已經在驗。
要動：tests/test_tree.py。
風險：無。

**22. `expand(v, key="val")` 的 `key=` 參數刪。**
現況：原值那格已定一律叫 `val`（C-55），`key=` 是「以防萬一」留的。
KISS：`expand(v)` 只認 `val`。
要動：aos_cli、test_cli。
風險：無。

**23. aos_cli 檔頭的歷史刪。**
現況：檔頭寫「原本只看第一份、stderr 警告，10-15 使用者『都按照推薦。』改」「Q6」「D-1～D-3」。
KISS：只寫現在怎麼樣（同條 7，程式檔頭也照辦）。
要動：aos_cli.py 檔頭；v3 之後只剩三扇門那幾行。
風險：無。

## 最小核心（從零重寫，這一塊只留）

- **規範**：一份 NORMS.md，總則四條——(1) 給人讀的檔先寫 `.` 暫存再改名（N-05）；(2) stdin＝參數、stdout／stderr＝結果，都是 JSON 串流，半份不算（N-12）；(3) 錯誤出口：0／1、stderr 一份 `{"error": {"code", "msg"}}`、正常不寫 stderr、不傳下層的碼、例外＝透明轉交與述詞；(4) 規範沒說的邊緣狀況預設不會發生。
- **程式**：`aos_cli.py` 一檔——`CliError`、`read_stream`、`emit`、`error`、`is_int`、`expand`、`resolve`（`$ref` 只有 `檔#/位置`、`$env`、抓循環，一個錯誤代號）。
- **說明**：aos_cli 檔頭 ＋ lib/README 一張一檔一行的表。
- **測試**：`test_cli.py` 一檔。

## 不在範圍

概念層（C-48 JSON 族／私有 key／值的雙形、附錄 1、附錄 2、abbr.json）使用者說「概念倒是不用」，本稿不審。
