# astra-8 共同規則（每條子線任務書都附這段）

你是 aos 專案 proto7-2 第八輪全日回歸（astra-8）的一條審查子線。受測 repo＝本 worktree（`/home/lorkhan/repo/simple_tools/aos-wt/R2`，分支 loop13/R2，HEAD cd544440＝main）。日期 2026-10-09。今天 main 進了約 348 個 commit（`git log --oneline cbc67a3d^..HEAD`，`git diff cbc67a3d^ HEAD -- <路徑>` 看今天改了什麼）：loop7 核心四線、brain 多回合、跨信記憶、llmcall 真傳輸、kernel 包、mail 白話化、up 一鍵入口、統一錯誤路徑、metrics 吸收 usage、diag 吸收 llmdiag。

**沙箱是唯讀**：你不能寫任何檔、不能跑會寫檔的測試。你可以讀檔、grep、`git log/diff/show`、跑**不寫檔**的指令（例如 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/modules/up/aos7-up --help`）。不呼叫任何 LLM／網路。

**重點**（今天新進的東西）：
1. 彼此是否一致（名詞、退出碼、檔案格式、鎖、狀態詞、README／spec／--help／程式四方是否說同一件事）；
2. 錯誤路徑是否統一（`proto7-2/notes/blueprint-errors.md`、`proto7-2/tests/error_path.json`：人話一行 `name: ...`、退出碼 0／2／3 慣例、不漏 traceback）；
3. 副作用有沒有超出必要（--help／壞參數／status／唯讀指令是否寫檔、建夾、拿鎖；寫到自己領地外；留下暫存檔）；
4. 新手接口在 ELI5 之後是否仍複雜（概念數、指令數、要先知道的前提）。

**不重審**：kernel 包內部（已在 `proto7-2/notes/play/2026-10-09-kernel-astra.md` 審過），只看它和其他模組怎麼接。**已知限制不當新發現**：先 grep `proto7-2/notes/decisions-2026-10-09.md` 的「已知限制」「待你決定」行、`proto7-2/notes/problems.md`、上一輪 `proto7-2/notes/play/2026-10-09-astra-7-infra.md`、kernel-astra 報告；若實際後果比文件寫的嚴重，可記但標「已知限制的延伸」。

**分類**：A＝會壞（崩潰、traceback、資料遺失、重複效果、文件承諾的行為實際做不到、卡死）；B＝不一致（模組間／文件與程式間／錯誤格式或退出碼不一致、副作用超出文件）；C＝可簡化（重複實作、多餘概念或指令、新手要知道的東西可以少）。每條加嚴重度（高／中／低）。

**證據規則**：不收自我宣告。每條要有
- 檔:行（引用原句，`file:line`，越精確越好），文件契約條文出處與程式對應處兩邊都要；
- **可重現指令**：一段 bash，假設從 repo 根執行、只在 `T=$(mktemp -d /tmp/astra8-<線>-XXXX)` 裡建檔、最後 `rm -rf "$T"`，並寫出「預期（照契約）」與「你推斷的實際」輸出。隊長會在可寫環境實跑核對；跑不出來的條目會被刪，所以寫得能直接貼上跑。靜態可證的（例如兩份文件互相矛盾）可只給 grep 指令。
- 建議修法一行。

**輸出**（你的最後一則回覆＝全部結果，會被存檔）：Markdown，開頭一段 5 行內總結，接著每條：
```
### NEW-<線>-n〔A|B|C／模組，高|中|低〕一句話標題
- 契約：file:line 「原句」
- 程式：file:line 「原句」
- 重現：```bash ... ```
- 預期／推斷實際：...
- 修法：...
```
最後列「看過但沒問題」的項目清單（一行一項），與「沒看完」的範圍。寧缺勿濫：不確定的放「可疑未證」節，不編號。
