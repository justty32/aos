# count - 一個 loop＋fsm 小例子，葉子用 Janet 寫：tick 把 $AOS_STACK/n.txt 加一，到 3 就退 10 請 loop 停；tock 印一行
#
# 編：proto8/langs/janet/bin/aos-janet count.janet 輸出資料夾；跑：aos-exec --ws 工作區 輸出資料夾

(def program
  (dir "_entry" ["aos-loop" "loop.json"]
       "loop.json" (aos-loop "fsm.json" :max 10)
       "fsm.json" (aos-fsm :entry (self-entry "aos-fsm")
                    (tick (dir "_entry"
                               (janet-main [_]
                                 (def f (string (os/getenv "AOS_STACK") "/n.txt"))
                                 (def n (+ 1 (if (os/stat f) (scan-number (string/trim (slurp f))) 0)))
                                 (when (> n 3) (os/exit 10))
                                 (spit f (string n "\n"))))
                          -> tock)
                    (tock (inst ["echo" "tock"] :stdout (env "AOS_WS" "/out.txt") :stdout_append true) -> tick))))
