# proto3 骨幹範例：世界／時鐘／agent 三層在記憶體裡跑起來。
# 跑法：janet src/main.janet 8          同步走 8 格就停（測試用）
#       janet src/main.janet async 5    非同步：每個鐘一條 fiber 各走各的，5 秒後收

(import ./world :as world)
(import ./kernel :as kernel)
(import ./llm :as llm)
(import ./agent :as agent)

(defn- log [w & xs] (print (string/format "%3d" (w :now)) " " (w :path) "：" ;xs))

# 1. 一個只會報時的世界
(def world-1 (world/make "world-1" :func-tick (fn [w] (log w "現在 " (os/time)))))

# 2. LLM 世界（假引擎：把話原樣回去），自己一個鐘
(def llm-1 (llm/make "llm" llm/echo-engine))

# 3. 一個 agent，問 llm-1；它底下一個借它鐘的小孩、一個自己有鐘的小孩
(def agent-1 (agent/make "agent-1" llm-1 :system "你是 agent-1"))
(world/spawn agent-1 "shared-kid" :func-tick (fn [w] (log w "跟著爸爸走")))
(def own-kid (world/spawn agent-1 "own-kid" :clock :own
                          :func-tick (fn [w] (log w "自己的鐘，兩秒一格"))))

# 4. 使用者也是一個世界（沒有鐘，只是有個 path 可以收回信）
(def user (world/make "user"))

(kernel/register world-1)
(kernel/register llm-1)
(kernel/register agent-1)
(kernel/register own-kid 2)

(defn- watch [w]
  # 旁觀 agent：狀態一變就印一行
  (fn [_] (when (not= (w :state) (w :seen))
            (log w "狀態 " (w :seen) " → " (w :state))
            (put w :seen (w :state)))))
(def observer (world/make "observer" :func-tick (watch agent-1)))
(kernel/register observer)

(defn- summary []
  (print "\nagent-1 說了：" (string/join (map |(string ($ :body)) (agent-1 :outbox)) " / "))
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
