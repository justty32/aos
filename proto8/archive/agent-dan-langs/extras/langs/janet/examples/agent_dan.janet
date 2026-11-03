# agent_dan - 用 Janet 寫的 agent-dan：編出來跟手寫的 proto8/demo/agent-dan 同一個形狀
#
# 編：proto8/extras/langs/janet/bin/aos-janet agent_dan.janet 輸出資料夾
# agent 是一個普通的 Janet 函數（範本）：給它 system、工具、腦…，回一個資料夾。
# Python 的葉子（brain.py、act.py、math 工具）照抄手寫版，這裡只管形狀。

(def dan "../../../../demo/agent-dan/")

(defn agent
  "一隻標準 agent：idle → think → act → idle，loop 每次跑一格 fsm（P-07）。"
  [&named model system idle brain act tools max]
  (dir "_entry" ["aos-loop" "loop.json"]
       ".env" (dotenv "# .env - 模型名放這裡，不寫死在 brain.py" ["AOS_BRAIN_MODEL" model])
       "loop.json" (aos-loop "fsm.json" :max max)
       "fsm.json" (aos-fsm :entry (self-entry "aos-fsm")
                    (idle  idle                                                    -> think)
                    (think (inst ["python3" "brain.py"] :timeout_ms 120000) -> act)
                    (act   (inst ["python3" "act.py"] :timeout_ms 60000)    -> idle))
       "system.txt" system
       "brain.py" brain
       "act.py" act
       "tools.json" (obj "tools" (obj ;(mapcat (fn [i] [(tools i) (obj "path" (string "tools/" (tools i)))])   # 腦／act 吃的工具清單（aos-tools）
                                               (range 0 (length tools) 2))))
       "tools" (dir ;tools)))

(def program
  (agent
    :model "chatgpt-gpt-6-luna-low"
    :max 40
    :system (copy (string dan "system.txt"))
    :idle (dir "_entry"
               (sh "# idle：cur/ 或 new/ 有題目就結束碼 0（往下走），沒有就 10（請 loop 停）"
                   `for f in "$AOS_WS"/cur/* "$AOS_WS"/new/*; do [ -e "$f" ] && exit 0; done`
                   "exit 10"))
    :brain (copy (string dan "brain.py"))
    :act (copy (string dan "act.py"))
    :tools ["clock" (tool :description "查現在的 UTC 時間，回 ISO 8601 格式（例：2026-10-23T08:00:00Z）。"
                          :entry (sh `exec date -u +"%Y-%m-%dT%H:%M:%SZ"`))
            "math" (tool :description "算一個算術式子，回結果。只收數字、+ - * / // % **、括號與正負號。"
                         :parameters {:type "object"
                                      :properties {:expr {:type "string" :description "要算的式子，例：17*23"}}
                                      :required ["expr"]}
                         :entry (copy (string dan "tools/math/_entry")))]))
