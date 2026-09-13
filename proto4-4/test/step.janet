# 逐步執行器。每一步都另開 aos-step 行程。

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

(defn dirname [path]
  (string/slice path 0 (last (string/find-all "/" path))))
(def cf (os/realpath (dyn :current-file)))
(def test-dir (dirname cf))
(def root (dirname test-dir))
(def fx (string test-dir "/fx"))
(def runner (os/realpath (string root "/aos-step")))
(def tmp (string "/tmp/aos-proto4-4-step-" (os/getpid) "-" (math/floor (os/time))))

(defn rm-tree [p]
  (case (os/stat p :mode)
    :directory (do (each x (os/dir p) (rm-tree (string p "/" x))) (os/rmdir p))
    nil nil
    (os/rm p)))

(defn run [& args]
  (def out-name (string tmp "/capture-out"))
  (def err-name (string tmp "/capture-err"))
  (def out (file/open out-name :w))
  (def err (file/open err-name :w))
  (def code (os/execute (array/concat @[runner] args) :p {:out out :err err}))
  (file/close out)
  (file/close err)
  @{:code code :out (string (slurp out-name)) :err (string (slurp err-name))})

(defn stat [prog]
  (parse ((run prog "--status") :out)))

(defer (rm-tree tmp)
  (do
    (os/mkdir tmp)
    (def prog (string tmp "/prog.janet"))
    (spit prog (slurp (string fx "/step-prog.janet")))
    (def child (string tmp "/child"))
    (os/mkdir child)
    (os/mkdir (string child "/.aos"))
    (spit (string child "/.aos/inst.json")
          "{\"argv\":[\"/bin/sh\",\"-c\",\"printf ran > child-ran.txt; printf '{\\\"answer\\\":42}'\"],\"stdout\":\"out.txt\"}\n")

    (def s0 (stat prog))
    (check "初始 status 是 pc 0 / n 6 且沒改過" (and (= 0 (s0 :pc)) (= 6 (s0 :n))
                                                        (not (s0 :done)) (not (s0 :changed))))
    (def r1 (run prog))
    (check "第一步成功且 stdout 一行" (and (= 0 (r1 :code)) (= 1 (length (string/split "\n" (string/trim (r1 :out)))))))
    (check "第一步後 pc 是 1" (= 1 ((stat prog) :pc)))
    (def r2 (run prog))
    (check "第二步後 pc 是 2" (and (= 0 (r2 :code)) (= 2 ((stat prog) :pc))))
    (def r3 (run prog))
    (check "x 與 f 跨行程存活" (and (= 0 (r3 :code)) (= "20" (string (slurp (string tmp "/side.txt"))))))
    (def lib-dir (string tmp "/lib"))
    (os/mkdir lib-dir)
    (def lib-prog (string lib-dir "/prog.janet"))
    (spit lib-prog "(print (type aos/llm) \" \" (type aos/llm-text) \" \" (type aos/pipe) \" \" (type aos/wait-for) \" \" (type aos/llm-submit))\n")
    (def lib-run (run lib-prog))
    (check "函式庫每個公開名字都綁進 form（含新加的 aos/llm）"
           (and (= 0 (lib-run :code))
                (not (nil? (string/find "function function function function function" (lib-run :out))))))
    (check "第三步 status 是 pc 3" (= 3 ((stat prog) :pc)))
    (def r4 (run prog))
    (check "第四步叫了 child 資料夾" (and (= 0 (r4 :code)) (= "ran" (string (slurp (string child "/child-ran.txt"))))))
    (def s4 (stat prog))
    (check "第四步後還沒 done" (and (= 4 (s4 :pc)) (= 6 (s4 :n)) (not (s4 :done))))
    (def r5 (run prog))
    (check "第五步把 call 結果 table 存進 image" (and (= 0 (r5 :code)) (= 5 ((stat prog) :pc))))
    (def r6 (run prog))
    (check "第六步跨行程取到 JSON value" (and (= 0 (r6 :code)) (= "42" (string (slurp (string tmp "/child-value.txt"))))))
    (def s6 (stat prog))
    (check "六步完成後 status 是 done" (and (= 6 (s6 :pc)) (= 6 (s6 :n)) (s6 :done) (nil? (s6 :error))))
    (def r7 (run prog))
    (check "完成後再叫回 100 且 stdout 空" (and (= 100 (r7 :code)) (= "" (r7 :out))))
    (check "done 檔存在" (= :file (os/stat (string tmp "/.aos-step/done") :mode)))
    (def old-done-exit (run prog "--done-exit" "7"))
    (check "--done-exit 已拿掉" (= 2 (old-done-exit :code)))
    (check "--done-exit 提示改由 kernel 設定"
           (not (nil? (string/find "這個號碼由 kernel 的 config.json 說了算"
                                  (old-done-exit :err)))))

    (def changed-dir (string tmp "/changed"))
    (os/mkdir changed-dir)
    (def changed-prog (string changed-dir "/prog.janet"))
    (spit changed-prog "(def a 1)\n(spit (string here \"/ran.txt\") (string a))\n")
    (check "改程式前跑過一格" (= 0 ((run changed-prog) :code)))
    (def unchanged (run changed-prog))
    (check "程式沒改就沒警告"
           (nil? (string/find "prog.janet 改過了" (unchanged :err))))
    (spit changed-prog "(def inserted 9)\n(def a 1)\n(spit (string here \"/ran.txt\") (string a))\n")
    (check "程式改過時 status 有 changed true" ((stat changed-prog) :changed))
    (def shifted (run changed-prog))
    (check "前面插 form 會警告但 pc 照走"
           (and (= 0 (shifted :code))
                (not (nil? (string/find "上次 2 個 form、現在 3 個" (shifted :err))))
                (= 3 ((stat changed-prog) :n))
                (= 3 ((stat changed-prog) :pc))))
    (check "reset 後 changed false"
           (and (= 0 ((run changed-prog "--reset") :code))
                (not ((stat changed-prog) :changed))))

    (def bad-dir (string tmp "/bad"))
    (os/mkdir bad-dir)
    (def bad (string bad-dir "/bad.janet"))
    (spit bad "(def y 1)\n(error \"boom\")\n")
    (check "錯誤程式第一步成功" (= 0 ((run bad) :code)))
    (def boom (run bad))
    (check "第二個 form 失敗回 1" (= 1 (boom :code)))
    (check "失敗訊息說明 form 編號、只印第一行並指向全文"
           (and (not (nil? (string/find "第 1 個 form（0 起算）失敗" (boom :err))))
                (not (nil? (string/find "全文：.aos-step/error 或 --status" (boom :err))))
                (= 1 (length (string/split "\n" (string/trim (boom :err)))))))
    (check "失敗後 pc 不動" (= "1\n" (string (slurp (string bad-dir "/.aos-step/pc")))))
    (check "error 檔有 boom" (not (nil? (string/find "boom" (string (slurp (string bad-dir "/.aos-step/error")))))))
    (spit bad "(def y 1)\n(+ y 1)\n")
    (check "修好後重試同一個 form 成功" (= 0 ((run bad) :code)))
    (check "重試成功後 pc 2 且 error 消失"
           (and (= "2\n" (string (slurp (string bad-dir "/.aos-step/pc"))))
                (nil? (os/stat (string bad-dir "/.aos-step/error") :mode))))

    (def wait-dir (string tmp "/wait"))
    (os/mkdir wait-dir)
    (def wait-prog (string wait-dir "/wait.janet"))
    (spit wait-prog
          "(aos/wait-for \"out.json\")\n(spit (string here \"/next.txt\") \"ran\")\n")
    (check "wait-for 宣告那格成功且 pc 前進"
           (and (= 0 ((run wait-prog) :code)) (= 1 ((stat wait-prog) :pc))))
    (def waiting0 ((stat wait-prog) :waiting))
    (check "waiting 存絕對路徑且 checks 從 0 開始"
           (and (= (string wait-dir "/out.json") (waiting0 :for))
                (= 0 (waiting0 :checks))))
    (def waiting-run (run wait-prog))
    (check "檔不在時再叫回 101、checks 加一且下一格沒跑"
           (and (= 101 (waiting-run :code))
                (= 1 (get-in (stat wait-prog) [:waiting :checks]))
                (nil? (os/stat (string wait-dir "/next.txt") :mode))))
    (check "等待碼的 stderr 會說第幾次"
           (not (nil? (string/find (string "在等 " wait-dir "/out.json（第 1 次）")
                                   (waiting-run :err)))))
    (check "status stderr 有給人看的在等"
           (not (nil? (string/find (string "在等 " wait-dir "/out.json")
                                   ((run wait-prog "--status") :err)))))
    (spit (string wait-dir "/out.json") "{}")
    (check "檔出現後同一次呼叫會接著跑下一格"
           (and (= 0 ((run wait-prog) :code))
                (= "ran" (string (slurp (string wait-dir "/next.txt"))))))
    (def waited-state (stat wait-prog))
    (check "等完會清 waiting 並留一筆 wait history"
           (and (nil? (waited-state :waiting))
                (some |(= "(wait)" ($ :step)) (waited-state :history))))

    (def last-dir (string tmp "/last-wait"))
    (os/mkdir last-dir)
    (def last-prog (string last-dir "/last.janet"))
    (spit last-prog "(aos/wait-for \"last.out\")\n")
    (check "最後一格宣告等待時還不是 done"
           (and (= 0 ((run last-prog) :code)) (not ((stat last-prog) :done))))
    (check "最後一格等待中再叫回 101" (= 101 ((run last-prog) :code)))
    (spit (string last-dir "/last.out") "")
    (check "最後一格的檔出現後下一叫才回 100"
           (and (= 100 ((run last-prog) :code)) ((stat last-prog) :done)))

    (def reset-wait (string tmp "/reset-wait.janet"))
    (spit reset-wait "(aos/wait-for \"never\")\n")
    (run reset-wait)
    (check "reset 連 waiting 一起清掉"
           (and (= 0 ((run reset-wait "--reset") :code))
                (nil? ((stat reset-wait) :waiting))))

    (def reset-error-dir (string tmp "/reset-error"))
    (os/mkdir reset-error-dir)
    (def reset-error-prog (string reset-error-dir "/prog.janet"))
    (spit reset-error-prog "(error \"old boom\")\n")
    (check "reset 前有 error 檔" (= 1 ((run reset-error-prog) :code)))
    (check "reset 連 error 一起清、status 乾淨"
           (and (= 0 ((run reset-error-prog "--reset") :code))
                (nil? (os/stat (string reset-error-dir "/.aos-step/error") :mode))
                (nil? ((stat reset-error-prog) :error))))

    (def parse-dir (string tmp "/parse"))
    (os/mkdir parse-dir)
    (def broken (string parse-dir "/broken.janet"))
    (spit broken "(def z 1\n")
    (check "parse 失敗回 1" (= 1 ((run broken) :code)))
    (check "parse 失敗不建 pc" (nil? (os/stat (string parse-dir "/.aos-step/pc") :mode)))

    (check "reset 成功" (= 0 ((run prog "--reset") :code)))
    (def reset-status (stat prog))
    (check "reset 後 status 回 pc 0" (and (= 0 (reset-status :pc)) (not (reset-status :done))))
    (check "沒給檔案是用法錯" (= 2 ((run) :code)))
    (check "檔案不存在是用法錯" (= 2 ((run (string tmp "/nope.janet")) :code)))
    (check "不認得的旗標是用法錯" (= 2 ((run prog "--wat") :code)))

    (printf "%d 條通過 ✓" n)))
