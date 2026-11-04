# 任務書：daemon 與 kernel 能不能合成一支程式、能不能脫離 JSON 檔案體系（唯讀調查）

← [README](README.md)

你是唯讀調查員。**不改任何檔、不跑 daemon／kernel、不碰模型、不碰 LM Studio。** 用繁體中文、白話、少術語回答。
你的最後回覆就是報告（≤ 8 KB），不要寫檔。

## 使用者的題目（原話）
「去調查一些可能性：1. daemon 和 kernel 的功能能否合在一起弄成一個程式，乃至於脫離現在的大量依託於 json 等檔案的體系？優缺點？」

## 先讀
- `AGENTS.md`
- `proto5/README.md`、`proto5/spec/README.md`，以及 `proto5/spec/` 下的 `kernel/`、`daemon/`、`cpu/`、`agent/`、`aos-agent/`（尤其各 README 的「已拍板的前提」：cpu 範式一個家一個主人、info／state／requests／responses 四樣、pipe 只管生死、JSON-RPC 2.0、原子投遞）
- `proto5/notes/2026-09-23-rearch/README.md`（為什麼會長成現在這樣）
- `proto5/notes/2026-09-24-daemon-crash/README.md`、`proto5/notes/2026-09-24-kernel-crash/README.md`（檔案體系下的崩潰窗口怎麼處理）
- `proto5-2/README.md`、`proto5-2/spec/`（池式、宣告式、上千上萬顆 cpu 的方向；`scale.md` 的三個規模問題：kernel 帳本整份讀寫、aos-agent 每格偷看整份帳本、一顆 cpu 一支 Python）
- `wf/WAIT_USER.md` 的 C 段（使用者說規模先不動）
- `proto5/notes/play/2026-09-24-r5-opus.md`、`2026-09-24-r5-astra.md`（使用者端手感）
- 實作可翻 `proto5/lib/`（aos_daemon.py、aos_kernel*.py、aos_exec_cpu.py、aos_agent*.py）

## 要你交的
1. 一段白話拆解：「合一」和「脫離檔案」是不是兩件可分開的事。
2. **至少四種方案**，例如（可自己再加）：
   - A 全合一：daemon＋kernel 一支長駐程式，狀態在記憶體＋sqlite／journal，cpu／agent 走 socket／HTTP／stdin-stdout。
   - B 合一但保留檔案當介面：一支長駐程式，但 requests／responses／state 仍是檔案（內部可快取、可 inotify）。
   - C 分開但共用一個資料庫（例如 sqlite），檔案只留給人看。
   - D 維持現狀＋修規模（拆帳本、通知檔、一支行程管多顆 cpu…）。

   每種都講：優點、缺點、崩潰恢復怎麼做、上千顆撐不撐得住、使用者手感（`aos-agent say／listen／talk`、`aos-kernel ls`、每天重開機）變多少、跟「已拍板的前提」衝突哪幾條、proto5 大概保留幾成。
3. **你會選哪個、為什麼**；分幾步走、第一步是什麼。
4. **最大的風險**（一到三條）。
5. 你讀文件時覺得「這個說法其實不對／沒被注意到」的地方（可選，最多五條，附檔名）。
