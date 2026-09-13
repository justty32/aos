# 任務書 2：proto4-5 llm-cpu 小修——model 別名放行（`strict_model`）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改 `proto4-5/` 底下的檔案**。**不要 git commit、不要 push。** 不要開其他 agent。不要打真網路（測試用既有的假 server）。先讀 `proto4-5/README.md`、`llm_cpu_worker.py`、`llm_cpu_home.py`、`test/test_worker.py`。

## 實測撞到的問題（Fable 2026-09-13 真打 DeepSeek）

請求指到 endpoint `deepseek`（設定 `model:"deepseek-chat"`），DeepSeek 回應的 `model` 是 `deepseek-flash`——`deepseek-chat` 是別名，回應寫真名。worker 判成 `model_mismatch`、`ok:false`，其實那發是成功的（usage 都有）。LM Studio 那條（`google/gemma-4-e4b`）回的名字一樣，沒事。

## 定案

- endpoint 多一個選填欄 `"strict_model"`，**預設 true**（LM Studio 需要嚴格：它會偷偷換模型）。`false` 時回應 model 跟設定不同**不算錯**：`ok:true`、結果的 `model` 照回應寫（真名），另外多一欄 `"model_requested"`（設定那個）。`strict_model:true` 時行為照舊，但錯誤訊息補一句「別名 endpoint 請在 endpoints.json 這筆加 "strict_model": false」。
- `init` 寫的三筆範例：deepseek 那筆加 `"strict_model": false`；local 不加（預設 true）。
- 結果檔一律都有 `model_requested`（成功失敗都有，方便對帳）。
- README：endpoint 設定那節加 `strict_model` 一行說明＋為什麼（DeepSeek 別名）；結果欄位表加 `model_requested`；`model_mismatch` 那列補「strict_model:false 可放行」。
- 測試（`test/test_worker.py`）加 3 條：假 server 回 `model:other` 時——strict 預設 → `model_mismatch`（既有那條照舊）；`strict_model:false` → `ok true`、`model` 是 other、`model_requested` 是設定值；成功結果有 `model_requested`。

## 驗證

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-5 && python3 -m unittest discover -s test 2>&1 | tail -2
```

## 回報（六行以內）

改了哪些檔、測試數與最後一行、自己決定的事。
