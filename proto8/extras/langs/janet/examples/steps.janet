# steps - 三個組合子：seq 依序、par 同時、if 看條件；每個都編成一個資料夾（入口是短 shell 腳本）
#
# 編：proto8/extras/langs/janet/bin/aos-janet steps.janet 輸出資料夾；跑：aos-exec --ws 工作區 輸出資料夾

(defn say "印一行，接在工作區的 out.txt 後面" [s] (inst ["echo" s] :stdout (env "AOS_WS" "/out.txt") :stdout_append true))

(def program
  (aos-seq
    (say "一")
    (aos-par (say "二a") (say "二b"))
    (aos-if (inst ["test" "-e" (env "AOS_WS" "/flag")])
            (say "有 flag")
            (say "沒有 flag"))))
