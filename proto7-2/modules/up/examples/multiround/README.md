同一封信做 8 回合：假 AI 每回合記下停在哪，第 5 回合報進度，第 8 回合回信。
從 repo 根跑：`bash proto7-2/modules/up/examples/multiround/run.sh`。
會看到 PROGRESS、DONE 和 STATE 的回合紀錄；結束會停心跳並刪掉暫存房子。
預設離線、不花錢；設 `MODEL=<LiteLLM 模型名>` 就改用真 AI 做 5 回合，需先準備好端點，會花用量。
