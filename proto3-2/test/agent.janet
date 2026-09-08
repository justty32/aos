# agent 是 list、跑一步＝eval。跑法：jpm test 或 janet test/agent.janet
(import ../src/agent :as agent)

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

(defn echo [context] {:text (string "收到：" (get (last context) :content))})

# ── 形狀：agent 就是一個 list ──
(def a0 (agent/new @[] echo @{}))
(check "new 回傳的是一個 list（tuple）" (tuple? a0))
(check "form 的頭是 step" (= (first a0) 'step))
(check "一開始是 idle" (= (agent/status a0) :idle))
(check "content 帶著 context／engine／tools" (deep= (sorted (keys (agent/content a0))) @[:context :engine :tools]))

# ── 跑一步＝eval，回傳下一個 agent ──
(def a1 (agent/next a0))
(check "沒人說話，idle 還是 idle" (= (agent/status a1) :idle))
(check "沒事發生，下一個 form 跟原來等值（tuple 比內容）" (deep= a1 a0))
(check "但 content 那張表一路是同一張" (= (agent/content a1) (agent/content a0)))

# ── 一句話走完：idle → think → idle ──
(agent/hear a1 "你好")
(def a2 (agent/next a1))
(check "有沒回的話 → think" (= (agent/status a2) :think))
(def a3 (agent/next a2))
(check "think 問過 engine → 回 idle" (= (agent/status a3) :idle))
(def ctx ((agent/content a3) :context))
(check "回覆記進 context" (deep= (last ctx) {:role :assistant :content {:text "收到：你好"}}))
(check "context 累積：user、assistant 兩句" (= (length ctx) 2))

# ── 工具呼叫：think → act → think → idle ──
(var calls 0)
(defn scripted [context]
  (++ calls)
  (if (= calls 1) {:tool "add" :args [1 2]} {:text "答案 3"}))
(def tools @{"add" (fn [[x y]] (+ x y))})
(var b (agent/new @[] scripted tools))
(agent/hear b "1+2=?")
(set b (agent/next b))
(check "工具版：idle → think" (= (agent/status b) :think))
(set b (agent/next b))
(check "engine 回工具呼叫 → act" (= (agent/status b) :act))
(set b (agent/next b))
(check "act 跑完工具 → 回 think" (= (agent/status b) :think))
(check "工具結果記進 context" (deep= (last ((agent/content b) :context)) {:role :tool :content 3}))
(set b (agent/next b))
(check "第二次 think 回話 → idle" (= (agent/status b) :idle))
(check "engine 被叫了兩次" (= calls 2))
(check "context 四句：user／assistant(tool)／tool／assistant" 
       (deep= (map |($ :role) ((agent/content b) :context)) @[:user :assistant :tool :assistant]))

# ── 沒有的工具 ──
(var c (agent/new @[] (fn [_] {:tool "nope" :args nil}) @{}))
(agent/hear c "?")
(set c (agent/next c)) (set c (agent/next c)) (set c (agent/next c))
(check "叫不存在的工具：結果是一句錯誤、還是回 think" 
       (and (= (agent/status c) :think) (string? (get (last ((agent/content c) :context)) :content))))

(print "proto3-2 agent 測試通過 ✓（" n " 條）")
