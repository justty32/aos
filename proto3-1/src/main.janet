# proto3-1 骨幹範例：跟 proto3 同一個劇情，但每個世界跑的是一段 list，狀態機靠 form 改寫。
# 跑法：janet src/main.janet 8          同步走 8 格就停
#       janet src/main.janet async 5    非同步：每個鐘一條 fiber 各走各的，5 秒後收

(import ./world :as world)
(import ./kernel :as kernel)
(import ./llm :as llm)
(import ./agent :as agent)

# 1. 一個只會報時的世界——它的「程式」就是這一句 list，每格 eval 一次
(def world-1 (world/make "world-1"
  '(do (print "  " (now) " world-1：現在 " (os/time)) :busy)))

# 2. LLM 世界（假引擎：把話原樣回去），form 是 (llm-step)，自己一個鐘
(def llm-1 (llm/make "llm" llm/echo-engine))

# 3. 一個 agent，問 llm-1。底下兩個小孩用 kid 原語現生：
#    因為世界就是環境，直接在 agent-1 的環境裡 eval 一句就好。
(def agent-1 (agent/make "agent-1" llm-1 :system "你是 agent-1"))
(eval '(do (kid "shared-kid" '(print "  " (now) " agent-1/shared-kid：跟著爸爸走"))
           (kid "own-kid" :own '(print "  " (now) " agent-1/own-kid：自己的鐘，兩格一動")))
      agent-1)
(def own-kid (world/at "agent-1/own-kid"))

# 4. 使用者也是一個世界（沒有鐘，只是有個 path 可以收回信）
(def user (world/make "user" nil))

# 5. 旁觀者：每格看一眼 agent-1 現在的 form 是哪一句，變了就印、並記進自己的環境
(def observer (world/make "observer"
  '(do (def s (first (watched :form)))
       (when (not= s (get me :last))
         (print "  " (now) " observer：agent-1 的 form → " s)
         (put me :last s)
         (array/push (me :chain) s))
       :busy)
  :chain @["agent-idle"]))                     # 先記下開場的 form，免得第一格就被 agent 搶先跑掉
(put observer 'watched @{:value agent-1})
(put observer :last 'agent-idle)

(kernel/register world-1)
(kernel/register llm-1)
(kernel/register agent-1)
(kernel/register own-kid 2)
(kernel/register observer)

(defn- summary []
  (print "\nagent-1 的 form 走過：" (string/join (map string (observer :chain)) " → "))
  (print "agent-1 說了：" (string/join (map |(string ($ :body)) (agent-1 :outbox)) " / "))
  (print "user 收到：" (string/join (map |(string ($ :body)) (user :inbox)) " / "))
  (print "格的會計：" (string/format "%q" (agent-1 :ticks)))
  (print "鐘：" (string/format "%q" (kernel/ls))))

(defn main [& args]
  (world/send user agent-1 "你好，agent-1")
  (if (= (get args 1) "async")
    (do (kernel/start)
        (ev/sleep 1.5)
        (world/send user agent-1 "第二句")
        (ev/sleep (- (scan-number (or (get args 2) "5")) 1.5))
        (kernel/stop-all)
        (summary))
    (do (kernel/run (scan-number (or (get args 1) "8")) 0)
        (summary))))
