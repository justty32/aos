# agent＝一個世界 + 一個小狀態機（先勾輪廓，之後會改）。
# 基礎設施只有一件：wait-for——agent 等東西時登記「等到什麼算數、等到了做什麼、等多久放棄」，
# 之後每一格由時鐘替它檢查。誰來叫醒它？永遠是時鐘，不用到處放計時器。

(import ./world :as world)
(import ./llm :as llm)

(defn wait-for
  "登記等待：until 是 (fn [agent] → 等到的東西或 nil)，then 是 (fn [agent 東西])。
   timeout 格數到了就叫 else（沒給 else 就回 idle）。"
  [a until then &opt timeout else]
  (put a :waiting @{:until until :then then :timeout timeout :else else :since (a :now)})
  (put a :state :wait))

(defn- check-wait [a]
  (def w (a :waiting))
  (def got ((w :until) a))
  (cond
    got (do (put a :waiting nil) ((w :then) a got) :busy)
    (and (w :timeout) (>= (- (a :now) (w :since)) (w :timeout)))
    (do (put a :waiting nil)
        (if (w :else) ((w :else) a) (put a :state :idle))
        :busy)
    :wait))

(defn- kind-of [m] (let [b (m :body)] (when (dictionary? b) (b :kind))))   # 信可能只是一句字串
(defn- llm-result? [id] (fn [m] (and (= (kind-of m) :llm-result) (= ((m :body) :id) id))))

(defn- think [a]
  # 把待回的信變成 user 訊息，丟給 LLM 世界，然後等結果
  (def req (llm/ask (a :llm) a (a :history)))
  (wait-for a
    (fn [a] (first (world/take-mail a (llm-result? (req :id)))))
    (fn [a m]
      (def body (m :body))
      (if (body :error)
        (do (put a :last-error (body :error)) (put a :state :idle))   # 先簡單：出錯回 idle
        (do (put a :reply (body :reply)) (put a :state :act))))
    (a :llm-timeout)))

(defn- act [a]
  (def reply (a :reply))
  (array/push (a :history) {:role :assistant :content (reply :text)})
  (world/say a (reply :text))
  (when-let [to (world/at (a :asker))] (world/send a to (reply :text)))
  (put a :state :idle))

(defn tick
  "四態：idle（有信就開始想）→ think（問 LLM）→ wait（等）→ act（把回覆說出去）→ idle"
  [a]
  (case (a :state)
    :idle (let [mails (world/take-mail a |(not= (kind-of $) :llm-result))]
            (if (empty? mails)
              :idle
              (do
                (each m mails
                  (array/push (a :history) {:role :user :content (string (m :body))})
                  (put a :asker (m :from)))
                (put a :state :think)
                :busy)))
    :think (do (think a) :busy)
    :wait (check-wait a)
    :act (do (act a) :busy)
    :busy))

(defn make
  "建一個 agent。llmw 是它要問的 LLM 世界。可選 :system 人格、:llm-timeout 等幾格放棄（預設 30）。"
  [name llmw & kvs]
  (def a (world/make name :state :idle :llm llmw :history @[] :waiting nil
                     :llm-timeout 30 :func-tick tick ;kvs))
  (when-let [sys (a :system)]
    (array/insert (a :history) 0 {:role :system :content sys}))
  a)
