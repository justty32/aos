# agent＝一個世界 + 一個小狀態機（先勾輪廓，之後會改）。
# 這一版狀態機不是 case，是 **form 改寫**：它的 form 從 (agent-idle) 被改寫成 (agent-think)、
# 再改寫成 (agent-wait 等到什麼 等到了做什麼 幾格放棄 從第幾格開始)、(agent-act)，然後回 (agent-idle)。
# 「現在是什麼狀態」＝現在的 form 第一個符號，不必另外存 :state。
# 等待的三件事直接帶在那個 list 裡——誰來叫醒它？永遠是時鐘。

(import ./world :as world)
(import ./llm :as llm)

(defn wait-for
  "登記等待：把 (agent-wait until then timeout since else) 寫成下一格的 form。
   until 是 (fn [a] → 等到的東西或 nil)，then 是 (fn [a 東西])，timeout 格數到了就叫 else
   （沒給 else 就回 (agent-idle)）。"
  [a until then &opt timeout else]
  (world/set-next a ~(agent-wait ,until ,then ,timeout ,(a :now) ,else)))

(defn- do-wait [a until then timeout since else]
  (def got (until a))
  (cond
    got (do (then a got) :busy)                       # then 自己決定 next 成 act 還是 idle
    (and timeout (>= (- (a :now) since) timeout))
    (do (if else (else a) (world/set-next a '(agent-idle))) :busy)
    :wait))

(defn- kind-of [m] (let [b (m :body)] (when (dictionary? b) (b :kind))))   # 信可能只是一句字串
(defn- llm-result? [id] (fn [m] (and (= (kind-of m) :llm-result) (= ((m :body) :id) id))))

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
  (wait-for a
    (fn [a] (first (world/take-mail a (llm-result? (req :id)))))
    (fn [a m]
      (def body (m :body))
      (if (body :error)
        (do (put a :last-error (body :error)) (world/set-next a '(agent-idle)))  # 先簡單：出錯回 idle
        (do (put a :reply (body :reply)) (world/set-next a '(agent-act)))))
    (a :llm-timeout))
  :busy)

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
  # 四個狀態＝四個綁在自己環境裡的原語，form 改寫就是在這四個之間跳
  (put a 'agent-idle  @{:value (fn [] (do-idle a))})
  (put a 'agent-think @{:value (fn [] (do-think a))})
  (put a 'agent-act   @{:value (fn [] (do-act a))})
  (put a 'agent-wait  @{:value (fn [u t to since else] (do-wait a u t to since else))})
  (when-let [sys (a :system)]
    (array/insert (a :history) 0 {:role :system :content sys}))
  a)
