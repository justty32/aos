# agent 就是一個 list。(new …) 回傳一個 form：
#     (step :status :idle :content @{:context … :engine … :tools …})
# 「跑一步」＝求值這個 form，求值的結果就是下一個 agent（下一個 form）。
# 所以 (next agent) 只做一件事：eval。狀態機在 step 裡：看 :status 做一件事、回傳新 form。
#
# 補全時的取捨（可推翻）：
# - 偽碼裡 form 的頭和「跑一步」都叫 next，一個名字兩個意思會打架，form 的頭改叫 step。
# - :statue 是筆誤，改 :status。
# - :content 那張 table 一路帶在 form 裡、同一張（可變），所以 context 會累積。
#   但 eval 會把 form 裡的 table 當建構式、每次求值新建一張，所以要用 (quote …) 包住才是同一張。
# - engine 先是同步函式 (fn [context] → 回覆)，回覆是 {:text "…"} 或 {:tool "名" :args …}；
#   tools 是 table {"名" (fn [args] → 結果)}。之後接 LLM 世界再改成非同步等信。

(def- env (curenv))   # eval 要在本模組的環境裡跑，step 才找得到

(defn- form
  "把狀態和內容包回 agent 的形狀。"
  [status content]
  ~(step :status ,status :content (quote ,content)))

(defn- last-role [context] (get (last context) :role))

(defn- do-idle [c]
  # 有一句沒回的 user 話才開始想；否則繼續 idle
  (if (= (last-role (c :context)) :user) :think :idle))

(defn- do-think [c]
  # 問 engine，回覆記進 context；是工具呼叫就去 act，是話就講完回 idle
  (def reply ((c :engine) (c :context)))
  (array/push (c :context) {:role :assistant :content reply})
  (if (reply :tool) :act :idle))

(defn- do-act [c]
  # 跑上一句 assistant 指定的工具，結果記進 context，再回去想
  (def call (get (last (c :context)) :content))
  (def tool (get (c :tools) (call :tool)))
  (def result (if tool (tool (call :args)) (string "沒有這個工具：" (call :tool))))
  (array/push (c :context) {:role :tool :content result})
  :think)

(defn step
  "agent form 的頭：照 :status 做一步，回傳下一個 form。"
  [& kvs]
  (def {:status status :content c} (table ;kvs))
  (def status-next
    (case status
      :idle (do-idle c)
      :think (do-think c)
      :act (do-act c)
      :idle))
  (form status-next c))

(defn new
  "make a new agent：回傳一個 form，狀態 idle。
   context 是 messages 陣列（會被直接加東西）、engine 是函式、tools 是 table。"
  [context engine tools]
  (form :idle @{:context context :engine engine :tools tools}))

(defn next
  "run a step of agent：求值它，回傳下一個 agent。"
  [agent]
  (eval agent env))

(defn- unquote* [x] (if (and (tuple? x) (= (first x) 'quote)) (get x 1) x))
(defn status "agent 現在的狀態。" [agent] (get (table ;(drop 1 agent)) :status))
(defn content "agent 帶著的那張表（拆掉 quote）。" [agent] (unquote* (get (table ;(drop 1 agent)) :content)))

(defn hear
  "外面對 agent 說一句話：塞進 context（下一步 idle 看到就會開始想）。"
  [agent text]
  (array/push ((content agent) :context) {:role :user :content text})
  agent)
