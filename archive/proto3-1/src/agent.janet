# agent＝一個世界 + 一個小狀態機（先勾輪廓，之後會改）。
# 這一版狀態機不是 case，是 **form 改寫**：它的 form 從 (agent-idle) 被改寫成 (agent-think)、
# 再改寫成 (agent-wait until then timeout since)、(agent-act)，然後回 (agent-idle)。
# 「現在是什麼狀態」＝現在的 form 第一個符號，不必另外存 :state。
# 等待的那格特別有意思：until 是純資料（不是 closure，才放得進 form、印得出來、比得了）——
# 等什麼／等到了叫誰／幾格放棄，全都當參數帶在 form 裡，跟 variant-cl 的 agent-wait 是同一套做法。
# 誰來叫醒它？永遠是時鐘，不用到處放計時器。

(import ./world :as world)
(import ./llm :as llm)

(defn- kind-of [m] (let [b (m :body)] (when (dictionary? b) (b :kind))))   # 信可能只是一句字串
(defn- llm-result? [id] (fn [m] (and (= (kind-of m) :llm-result) (= ((m :body) :id) id))))

(defn wait-check
  "until 是一段『等什麼』的純資料描述（不是 closure，才放得進 form）：
   [:llm-result id] 等那筆 LLM 回信、[:mail] 等任何非 llm-result 的信；等不到／看不懂就回 nil。"
  [a until]
  (case (first until)
    :llm-result (first (world/take-mail a (llm-result? (get until 1))))
    :mail (first (world/take-mail a |(not= (kind-of $) :llm-result)))
    nil))

(defn wait-for
  "登記等待：把 (agent-wait until then timeout since) 寫成下一格的 form。
   until 是純資料的等待描述（交給 wait-check 判讀）；then 是綁在 agent 環境裡的原語符號
   （例如 'agent-got-llm）——這格存的就是那個符號本身，下一格 eval 這個 form 時，
   Janet 本來就會把裸符號解析成它綁定的原語函式，等到時就直接叫它，等於 CL 版的 funcall。
   timeout 格數到了還沒等到，一律回 (agent-idle)（沒有 else，跟 CL 版一致）。"
  [a until then &opt timeout]
  # until 要用 tuple/brackets 包一次：一般 [:kw …] 字面值求值完是 parens 型 tuple，
  # 塞進 form 裡再被 eval 一次會被誤當成呼叫（(:llm-result 3) 變成呼叫 :llm-result）；
  # brackets 型 tuple 才會被當成純資料字面值求值，不會被當函式呼叫。
  (world/set-next a ~(agent-wait ,(tuple/brackets ;until) ,then ,timeout ,(a :now))))

(defn- do-wait [a until then timeout since]
  (def got (wait-check a until))
  (cond
    got (do (then got) :busy)                          # then 自己決定 next 成 act 還是 idle
    (and timeout (>= (- (a :now) since) timeout))
    (do (world/set-next a '(agent-idle)) :busy)
    :wait))

(defn- do-idle [a]
  # 有非 llm-result 的信 → 記進 history、記下寄件人，改寫成 (agent-think)
  (def mails (world/take-mail a |(not= (kind-of $) :llm-result)))
  (if (empty? mails)
    :idle
    (do
      (each m mails
        (array/push (a :history) {:role :user :content (string (m :body))})
        (put a :asker (m :from)))
      (world/set-next a '(agent-think))
      :busy)))

(defn- do-think [a]
  # 把 history 丟給 LLM 世界（不等），然後改寫成「等那封回信」的 form
  (def req (llm/ask (a :llm) a (a :history)))
  (wait-for a [:llm-result (req :id)] 'agent-got-llm (a :llm-timeout))
  :busy)

(defn- do-got-llm [a m]
  "等到 LLM 回信了：出錯就先簡單回 idle 並記 :last-error，否則收下回覆、換成 (agent-act)。"
  (def body (m :body))
  (if (body :error)
    (do (put a :last-error (body :error)) (world/set-next a '(agent-idle)))
    (do (put a :reply (body :reply)) (world/set-next a '(agent-act)))))

(defn- do-act [a]
  (def reply (a :reply))
  (array/push (a :history) {:role :assistant :content (reply :text)})
  (world/say a (reply :text))
  (when-let [to (world/at (a :asker))] (world/send a to (reply :text)))
  (world/set-next a '(agent-idle))
  :busy)

(defn state
  "現在是什麼狀態？＝現在的 form 的第一個符號。"
  [a] (let [f (a :form)] (if (indexed? f) (first f) f)))

(defn make
  "建一個 agent，初始 form 是 (agent-idle)。llmw 是它要問的 LLM 世界。
   可選 :system 人格、:llm-timeout 等幾格放棄（預設 30）。"
  [name llmw & kvs]
  (def a (world/make name '(agent-idle) :llm llmw :history @[] :llm-timeout 30 ;kvs))
  # 五個狀態／事件＝五個綁在自己環境裡的原語，form 改寫就是在這幾個之間跳
  (put a 'agent-idle    @{:value (fn [] (do-idle a))})
  (put a 'agent-think   @{:value (fn [] (do-think a))})
  (put a 'agent-act     @{:value (fn [] (do-act a))})
  (put a 'agent-wait    @{:value (fn [u t to since] (do-wait a u t to since))})
  (put a 'agent-got-llm @{:value (fn [m] (do-got-llm a m))})
  (when-let [sys (a :system)]
    (array/insert (a :history) 0 {:role :system :content sys}))
  a)
