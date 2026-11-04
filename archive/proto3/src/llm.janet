# LLM 是另一個世界：有自己的鐘、一條請求佇列。agent 把請求丟進來、繼續走自己的格；
# LLM 世界每格處理幾筆，做完把結果寄回請求者的 inbox（三態：pending → running → done/failed）。
# engine 是一個函式：messages → 回覆。回覆的形狀：{:text "…"} 或 {:tool "名字" :args {…}}。

(import ./world :as world)

(defn- tick [llmw]
  (var n 0)
  (def q (llmw :queue))
  (while (and (< n (llmw :max-per-tick)) (not (empty? q)))
    (def req (q 0))
    (array/remove q 0)
    (put req :status :running)
    (def [ok reply] (protect ((llmw :engine) (req :messages))))
    (put req :status (if ok :done :failed))
    (update (llmw :usage) (req :from) (fn [c] (inc (or c 0))))
    (when-let [asker (world/at (req :from))]
      (world/send llmw asker
        {:kind :llm-result :id (req :id)
         :reply (if ok reply nil)
         :error (if ok nil (string reply))}))
    (++ n))
  (if (> n 0) :busy :idle))

(defn make
  "建一個 LLM 世界。engine：messages → 回覆。max-per-tick：一格最多處理幾筆（預設 1）。"
  [name engine &opt max-per-tick]
  (world/make name :engine engine :queue @[] :usage @{}
              :max-per-tick (or max-per-tick 1) :seq 0 :func-tick tick))

(defn ask
  "from 向 llmw 送一筆請求，馬上回傳請求（不等）。結果之後會以信寄到 from 的 inbox。"
  [llmw from messages]
  (update llmw :seq inc)
  (def req @{:id (llmw :seq) :from (from :path) :messages (array/slice messages)
             :status :pending :at (llmw :now)})
  (array/push (llmw :queue) req)
  req)

# ── 幾個現成的 engine（測試與範例用）────────────────────────
(defn echo-engine
  "把最後一句 user 的話原樣回去。"
  [messages]
  (def last-user (last (filter |(= ($ :role) :user) messages)))
  {:text (string "收到：" (if last-user (last-user :content) ""))})

(defn script-engine
  "照劇本一筆一筆回；劇本用完就回最後一筆。劇本元素可以是回覆、或 :error（模擬模型出錯）。"
  [script]
  (var i 0)
  (fn [messages]
    (def step (get script (min i (dec (length script)))))
    (++ i)
    (if (= step :error) (error "模型出錯（劇本）") step)))
