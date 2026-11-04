# 封存：2026-10-02 之前的 spec（舊設計）

2026-10-02 第二十七批，使用者：「舊的設計 spec 可以開 agent 去做整理封存。舊的連結也封存。現在我們的 settled 要成為唯一事實，佔據 spec。」

這裡是 `proto6/spec/` 在當天之前、**不屬於 settled（整理區）**的所有舊篇，內容原樣、只用 `git mv` 搬過來，相對結構照舊（`agent/`、`base/`、`cli/`、`conformance/`、`scheduling/`、`readme/`、`protocol/` 的舊協議篇、`contracts.md`、`terms.md`、`cli.md`、`conformance.md`、`check_ids.py`；原 `spec/README.md` 叫 [spec-README.md](spec-README.md)）。舊 schema 與範例在 `protocol/schemas/`、`protocol/examples/`（agent、kernel、llm、work、msg、ops、res 與 outbox 那一批）。

- **不是現行規格**：很多說法已過時（node／kernel／agent、LLM 排程、檔案收件與 `.aos/outbox/`、舊 daemon IPC、CLI、驗收場景…）。現行以 [proto6/spec](../../../spec/README.md)（原 settled）為準，行為正本是程式（`proto6/src/py`）加測試加 schema。
- 這裡的連結不維護，壞了不修；lint 不下鑽 `archive/`。
- 還有用的幾條（時間單位 C-01、版本與陌生欄位 C-07、inst、協議通則）已用新寫法收進新 spec：[conventions](../../../spec/conventions.md)、[inst](../../../spec/inst.md)、[protocol/README](../../../spec/protocol/README.md)、[terms](../../../spec/terms.md)。其餘（含 B-404 滿碟與 `aos-clean`）現行程式沒有，只留在這裡。
