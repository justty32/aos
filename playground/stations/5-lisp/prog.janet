# 五個 form，一次跑一個。環境會存成 image，所以 def 過的東西下一格還在。
(def K "__K__")
(defn ask [q name]
  (aos/llm-submit K @{:messages [@{:role "user" :content q}]} name))
(def result (ask "說一個一句話的冷笑話。" "play-lisp-1"))
(aos/wait-for result)
(spit (string here "/answer.json") (slurp result))
