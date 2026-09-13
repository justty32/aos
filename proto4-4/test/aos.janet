# aos 函式庫。跑法：janet test/aos.janet
(import ../src/aos :as aos)

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

(defn dirname [path]
  (string/slice path 0 (last (string/find-all "/" path))))
(def cf (os/realpath (dyn :current-file)))
(def fx (string (dirname cf) "/fx"))
(def tmp (string "/tmp/aos-proto4-4-lib-" (os/getpid) "-" (math/floor (os/time))))

(defn rm-tree [p]
  (case (os/stat p :mode)
    :directory (do (each x (os/dir p) (rm-tree (string p "/" x))) (os/rmdir p))
    nil nil
    (os/rm p)))

(defn mkdir2 [a b]
  (os/mkdir a)
  (os/mkdir (string a "/" b)))

(defn throws? [f]
  (not ((protect (f)) 0)))

(defer (rm-tree tmp)
  (do
    (os/mkdir tmp)

    (def d1 (string tmp "/default"))
    (mkdir2 d1 ".aos")
    (spit (string d1 "/.aos/inst.json")
          "{\"argv\":[\"/bin/sh\",\"-c\",\"printf yes > made.txt\"]}\n")
    (def r1 (aos/call-dir d1))
    (check "call-dir 的 kind 是 child" (= "child" (r1 :kind)))
    (check "call-dir 成功回 0" (= 0 (r1 :code)))
    (check "call-dir 真的跑了 inst" (= "yes" (string (slurp (string d1 "/made.txt")))))
    (check "ok? 認得成功" (aos/ok? r1))

    (spit (string d1 "/.aos/other.json")
          "{\"argv\":[\"/bin/sh\",\"-c\",\"printf alt > alt.txt\"]}\n")
    (def r2 (aos/call-dir d1 @{:dir-target ".aos/other.json"}))
    (check ":dir-target 會改叫的 inst" (and (aos/ok? r2) (= "alt" (string (slurp (string d1 "/alt.txt"))))))

    (def direct (string tmp "/direct.json"))
    (spit direct "{\"argv\":[\"/bin/sh\",\"-c\",\"printf json > json.txt\"]}\n")
    (def r3 (aos/call-json direct))
    (check "call-json 直接吃 inst.json" (and (aos/ok? r3) (= "json" (string (slurp (string tmp "/json.txt"))))))

    (def r4 (aos/call (string fx "/exit3.sh")))
    (check "普通檔案的子程式碼原樣回來" (and (= 3 (r4 :code)) (= "child" (r4 :kind))))
    (check "ok? 不把子程式 3 當成成功" (not (aos/ok? r4)))

    (def r5 (aos/call-json (string tmp "/missing.json")))
    (check "不存在的 .json 是 aos 失敗" (and (= 125 (r5 :code)) (= "aos" (r5 :kind))))
    (check "aos 失敗的 stderr 有被接回" (string/has-prefix? "aos-exec: " (r5 :stderr)))

    (def r6 (aos/call (string tmp "/missing")))
    (check "不存在的普通路徑是 usage" (and (= 2 (r6 :code)) (= "usage" (r6 :kind))))

    (def r7 (aos/call (string fx "/sleep.sh") @{:timeout-ms 50}))
    (check "timeout 會砍掉子程式" (and (has-value? [143 137] (r7 :code)) (= "child" (r7 :kind))))
    (check "ok? 不把 timeout 當成成功" (not (aos/ok? r7)))

    (def plain (string tmp "/plain"))
    (spit plain "x")
    (check "call-dir 拒絕普通檔案" (throws? (fn [] (aos/call-dir plain))))
    (check "call-json 拒絕非 .json" (throws? (fn [] (aos/call-json plain))))

    (printf "%d 條通過 ✓" n)))
