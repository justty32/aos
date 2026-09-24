← [本提案](README.md)｜[stage0 報告](stage0.md)

# 任務書：唯讀審查「cli-agents 階 0」

你是唯讀審查員。**不要改任何檔、不要跑 claude 或 codex 的任務（只准 `--help`／`--version`）、不要開 daemon、不要碰 LM Studio／ollama。** 你的最後一則訊息就是審查報告（會存成 review2-astra.md）。繁體中文、白話、≤ 6 KB。

## 要審的（都是這次新加或改的）

- `proto5/templates/cli-agents/`：README.md、kernel2.json、claude-job.json、claude-next.json、codex-review.json、codex-review-next.json
- `proto5/tutorials/07-cli-agents.md`
- `proto5/notes/2026-09-24-cli-agents/stage0.md`、`stage0-run.sh`
- 導航：`proto5/tutorials/README.md`、`proto5/README.md`、`proto5/notes/README.md`、`proto5/notes/2026-09-24-cli-agents/README.md` 加的那幾列

## 使用者已拍板（照這些審，不要建議推翻）

1. 普通 cpu 池＋單子範本，不寫新種 cpu；2. 牢外、用他自己的登入、保守旗標，**「跳過權限」類旗標一律不准出現**；3. 花錢的池放另一個 kernel 家，claude 1 顆、codex 2 顆；4. 接著聊每次從上一次**成功的**分岔；5. 不讀他自己的 `~/.claude` 記憶／CLAUDE.md 與 codex 設定（claude `--safe-mode`、codex 專用 `CODEX_HOME`）。codex 只有 `gpt-6-astra` 能用。

## 對照

- `proto5/spec/inst-posix/`（路徑相對 `cwd`、`envs` 的 `$opt: clear`、指示詞）、`proto5/spec/kernel/`（home.md、cli.md、cli-ops.md、daemon-link.md、syscall.md）、`proto5/spec/daemon/`（methods.md、shutdown.md、home.md）、`proto5/spec/cpu/`（messages.md 的 ack、stop.md）
- `proto5/tutorials/01～02`（口吻、`env.sh`、`$W`）
- `claude --help`、`codex --help`、`codex exec --help`、`codex exec fork --help`

## 審三件事

1. **照教程抄會不會失敗**：每一段指令在 01 開好的環境下能不能跑（變數、路徑、sed 換字、JSON 合不合法、`$env` 在 daemon 環境解不解得開、kill／ack 單的格式、`rm` 與回音的說法）。
2. **安全與花錢**：範本旗標有沒有漏洞或比說的寬（例如 acceptEdits 實際准什麼、`--disallowedTools` 變長參數會不會吃掉後面的東西、`$opt: clear` 會不會讓 claude／codex 起不來）；三個洞講得對不對、有沒有漏。
3. **報告說法對不對**：stage0.md 的五條驗證、坑、要拍的題目，跟範本／腳本／規範對得上嗎。

## 報告格式

- **必修**（錯的、照做會出事的）：編號，「哪個檔哪一段 → 問題 → 建議改成什麼」。
- **建議**：同上。
- **確認沒問題的**：簡短列幾條。
