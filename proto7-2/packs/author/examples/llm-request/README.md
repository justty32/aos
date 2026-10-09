# 真 AI 一整圈

← [author](../../README.md)

先啟動 LiteLLM（預設 `http://localhost:4000/v1`），需要時設定 `AOS7_LITELLM_URL`／`AOS7_LITELLM_KEY`，再從 repo 根執行：

```sh
bash proto7-2/packs/author/examples/llm-request/run.sh MODEL [OUTDIR]
```

預設輸出 `./evidence-<MODEL>`（模型名中的特殊字元換成 `_`）；OUTDIR 必須為空。腳本不進測試套，隊長親自跑。提示無標準答案，不設 max_tokens／temperature，reserve 1000000。

暫存 root 有 `llm/`（人工 closed round 與 100000000 token grant、帳任務）和 `work/`（CSV 需求、作者與 step 工作）。依序 register → propose（記 wall time）→ publish → daemon 執行（每秒 status、最多 120 秒）→ answer → step close → author close。任一關失敗停止；EXIT／INT／TERM trap 收 daemon 與帳任務，保留暫存 root。

每個 CLI stdout／stderr 寫進 OUTDIR；另收 llmcall request／raw／receipt（存在才收）、作者 candidate／verdict（close 前收最後一版）、`jobs/<job>/out/report.json`。`summary.py` 從實際證據抽出 summary.json，最後印出；未執行的階段與不存在的 usage 留 null，失敗結果照原文保存。`llm_seconds` 是 propose 的 wall time（含帳與驗證），不是 provider 的純推理時間。這次實作未執行真模型腳本。
