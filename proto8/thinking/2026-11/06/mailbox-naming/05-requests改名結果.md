裁定 4（使用者 11-06 選項框「現在統一 requests/」）與裁定 1～3 的實作結果：改了哪些、照 R14 哪些不改、驗收。
← [入口](README.md)｜上一份 [04-規則草稿](04-規則草稿.md)｜下一份 —

## 改了什麼

- **llm kernel 的收件箱**：`$AOS_STACK/mailbox/` → `$AOS_STACK/requests/`；`aos-llm ask` 的共用回信信箱跟著是 `<stack>/requests/reply/`。程式：aos-llm-kernel `serve/config.cpp`（`Cfg::mailbox` 欄改名 `requests`）、`serve.hpp`、`main.cpp` 的 help；aos-llm `send/send.cpp`、`send.hpp`、`common.hpp`、`main.cpp` 的 help。`AOS_LLM_KERNEL` 的意思不變（＝llm kernel 的 stack）。
- **寄信端與設定**：aos-sandbox `examples/agent.json` 綁 `{"$env": "AOS_LLM_KERNEL", "$path": "/requests"}`、`root/setup.sh` 說明、`bin/aos-sandbox` 註解。
- **文件**：aos-llm-kernel README、docs/01、04；aos-llm README、docs/01；kernel/docs/01；templates/docs/02；aos-sandbox README；aos-post docs/01 的路徑例子。
- **知識庫**（腦看）：brain、world 改 `requests/`；README 的 letter 改說「a folder with a letter.json」；me/README、status 把 agent 的 queue 叫 inbox 的改成 queue。
- **用語**：`py/aos_ws.py`、`cmd/aos-agent/README.md` 的「有順序的信箱」改「當 queue 用的信箱」；判官 `_entry` 的變數 `inbox` 改 `requests`（行為、輸出不變）。
- **queue.json 檔頭**（裁定 2）：llm kernel `queue.hpp` 註解與 docs/01 各一句「排法＝優先序」；判官的未實作，[os-impl 05](../os-impl/05-寄信者自設逾時.md) 窗那列加註。
- **條文**（原句全留、只加註）：C-54 加 [R14](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法/03-R14.md)（入口表與前言加註、02 的下一份指過去）；N-16、N-42、N-63、P-23 加「11-06 改名」註；NORMS 附錄3 舊名對照加一列；名詞表板子比喻加 11-06 註。

## 照 R14 不改的（機制名）

- 錯誤代號 `MailboxMissing`、`MailboxBad`：講「任何一個信箱不在／寫不了」，不是這一個箱的名字（R14 第 1 點）。aos-llm `regret` 時 `requests/` 不在照舊報 `MailboxMissing`。
- aos-post、`aos::post::Mailbox`、llm-kernel 自己的 `struct Mailbox`、`mb_` 等識別字；錯誤訊息裡的「mailbox」一字（例 `mailbox <路徑> is locked by another kernel`，路徑本身已是 `…/requests`）。
- aos-sandbox 的 `--mailbox` 旗標：收任何一個信箱的路徑。
- `procs_ctl_mailbox`、`mailbox_warning`、`daemon_reply/`、`--reply-to BOX`。
- thinking 與日誌照當時的名字（讀時照舊名對照換）。

不留舊名、不認舊資料夾、不寫遷移（使用者 11-05「一律當成沒有舊版」）：舊 stack 裡殘留的 `mailbox/` 沒人讀，要清就手刪。

## 驗收

- 改法：codex `gpt-6.1-sol` 帶 `/goal` 在 `/tmp/lteam/work` 複本改，隊長審 diff（退回它為守 2 KB 刪掉的知識庫句子與兩句錯誤訊息改字），套進主 clone。
- 建置：複本與主 clone 全量建置過，warning 跟改前一樣（aos-json check.cpp 既有兩條）；`install.sh` 退 0、`find ~/.local/bin -xtype l` 空；code map 0 stale。
- 假腦試驗場最短路＋C++ help／錯誤行 119 例（T 隊 cases.sh 複本，試驗場複本、kernel stack 只留 def/）：改前改後只差 3 例，全是 help 文字裡的路徑（`aos-llm-kernel --help`／`-h` 的「from $AOS_STACK/requests/」、`aos-llm regret --help` 的 `requests/new/`）；kernel 起來建的是 `requests/`。另跑一次 `aos-llm ask`（fake 包）退 0、回 FAKE ANSWER，`requests/reply/` 有建。
- 試驗場 `~/code/playground`：先備份 `~/code/playground.bak-1106L`，lib、知識庫照 main 整份換，env.sh 與 README 的 `mailbox/` 改 `requests/`（README 開頭歷史加一句）。
