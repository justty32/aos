# 真的把 aos-step 放上 proto4-3/aos-run：一格一個 form。

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

(defn dirname [path]
  (string/slice path 0 (last (string/find-all "/" path))))
(def cf (os/realpath (dyn :current-file)))
(def test-dir (dirname cf))
(def root (dirname test-dir))
(def repo (dirname root))
(def fx (string test-dir "/fx"))
(def step (os/realpath (string root "/aos-step")))
(def cpu (os/realpath (string repo "/proto4-3/aos-run")))
(def tmp (string "/tmp/aos-proto4-4-cpu-" (os/getpid) "-" (math/floor (os/time))))

(defn rm-tree [p]
  (case (os/stat p :mode)
    :directory (do (each x (os/dir p) (rm-tree (string p "/" x))) (os/rmdir p))
    nil nil
    (os/rm p)))

(defn lines [text]
  (if (= "" (string/trim text)) 0 (length (string/split "\n" (string/trim text)))))

(defer (rm-tree tmp)
  (do
    (os/mkdir tmp)
    (def prog (string tmp "/prog.janet"))
    (spit prog (slurp (string fx "/cpu-prog.janet")))
    (def inst (string tmp "/inst.json"))
    (spit inst
          (string/format
            "{\"argv\":[%q,\"prog.janet\"],\"cwd\":%q,\"stdout\":\"out.txt\",\"stderr\":\"err.txt\"}\n"
            step tmp))
    (def runner-log (file/open (string tmp "/aos-run.err") :w))
    (def code (os/execute [cpu inst "--interval-ms" "100" "--max-runs" "3"]
                          :p {:err runner-log}))
    (file/close runner-log)
    (check "aos-run 跑滿三格正常停" (= 0 code))
    (check "三格後 pc 是 3 且 done 存在"
           (and (= "3\n" (string (slurp (string tmp "/.aos-step/pc"))))
                (= :file (os/stat (string tmp "/.aos-step/done") :mode))))
    (check "三個 form 各寫了 log 一行" (= 3 (lines (slurp (string tmp "/log.txt")))))
    (check "out.txt 有三行" (= 3 (lines (slurp (string tmp "/out.txt")))))
    (printf "%d 條通過 ✓" n)))
