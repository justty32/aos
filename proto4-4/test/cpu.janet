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
(def daemon-bin (os/realpath (string repo "/proto4-3/aos-daemon")))
(def ctl (os/realpath (string repo "/proto4-3/aos-daemon-ctl")))
(def kernel-init (os/realpath (string repo "/proto4-3/aos-kernel-init")))
(def kernel (os/realpath (string repo "/proto4-3/aos-kernel")))
(def tmp (string "/tmp/aos-proto4-4-cpu-" (os/getpid) "-" (math/floor (os/time))))
(def json-module (string (dyn :syspath) "/spork/json.so"))

(defn rm-tree [p]
  (case (os/stat p :mode)
    :directory (do (each x (os/dir p) (rm-tree (string p "/" x))) (os/rmdir p))
    nil nil
    (os/rm p)))

(defn lines [text]
  (if (= "" (string/trim text)) 0 (length (string/split "\n" (string/trim text)))))

(defn decode-json [text]
  ((get-in (require json-module) ['decode :value]) text))

(defn stop-daemon [proc cleanup-log]
  (def stopped (protect (os/execute [ctl "stop"] :p {:out cleanup-log :err cleanup-log})))
  (if (and (stopped 0) (= 0 (stopped 1)))
    (protect (os/proc-wait proc))
    (protect (os/proc-kill proc true :term))))

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

    (def dhome (string tmp "/daemon-home"))
    (def k (string tmp "/K"))
    (def p (string tmp "/P"))
    (os/mkdir p)
    (spit (string p "/prog.janet") (slurp (string fx "/cpu-prog.janet")))
    (os/setenv "AOS_DAEMON_HOME" dhome)
    (def daemon-log (file/open (string tmp "/daemon.log") :w))
    (def daemon (os/spawn [daemon-bin] :p {:out daemon-log :err daemon-log}))
    (def cleanup-log (file/open (string tmp "/cleanup.log") :w))
    (defer (do (stop-daemon daemon cleanup-log)
               (file/close cleanup-log)
               (file/close daemon-log))
      (do
        (def cmd-out (file/open (string tmp "/kernel-cmd.out") :w))
        (def cmd-err (file/open (string tmp "/kernel-cmd.err") :w))
        (def started (os/clock :monotonic))
        (var waited 0)
        (while (and (nil? (os/stat (string dhome "/daemon.pid") :mode)) (< waited 60))
          (os/sleep 0.05)
          (++ waited))
        (check "測試 daemon 起來" (= :file (os/stat (string dhome "/daemon.pid") :mode)))
        (def init-code
          (os/execute [kernel-init k "--ncpu" "1" "--interval-ms" "200"
                                     "--quantum" "50"]
                      :p {:out cmd-out :err cmd-err}))
        (check "kernel init 成功" (= 0 init-code))
        (spit (string k "/procs/1.json")
              (string/format
                "{\"argv\":[%q,\"prog.janet\"],\"cwd\":%q,\"stdout\":\"out.txt\",\"stderr\":\"err.txt\"}\n"
                step p))
        (def add-code
          (os/execute [ctl "add" (string k "/inst.json") "--interval-ms" "200"]
                      :p {:out cmd-out :err cmd-err}))
        (check "kernel cpu 加進 daemon" (= 0 add-code))
        (def done (string k "/procs/done/1.json"))
        (var polls 0)
        (while (and (nil? (os/stat done :mode)) (< polls 300))
          (os/sleep 0.05)
          (++ polls))
        (def elapsed (- (os/clock :monotonic) started))
        (check "kernel 在 15 秒內收走完成行程" (= :file (os/stat done :mode)))
        (check "kernel 路徑的 aos-step 留下 done"
               (= :file (os/stat (string p "/.aos-step/done") :mode)))
        (def log-lines (lines (slurp (string p "/log.txt"))))
        (check "做完後再叫沒有重跑 form" (= 3 log-lines))
        (def idle (decode-json (slurp (string k "/cpus/0.json"))))
        (check "做完後 cpu 換回 idle"
               (and (= "." (idle "cwd"))
                    (= 1 (length (idle "argv")))
                    (= "true" ((idle "argv") 0))))
        (file/close cmd-out)
        (file/close cmd-err)
        (def old-cwd (os/cwd))
        (def ls-out-name (string tmp "/kernel-ls.out"))
        (def ls-out (file/open ls-out-name :w))
        (def ls-err (file/open (string tmp "/kernel-ls.err") :w))
        (var ls-code nil)
        (defer (os/cd old-cwd)
          (do (os/cd k)
              (set ls-code (os/execute [kernel "ls"] :p {:out ls-out :err ls-err}))))
        (file/close ls-out)
        (file/close ls-err)
        (def ls-text (string (slurp ls-out-name)))
        (check "kernel ls 列出 done: 1"
               (and (= 0 ls-code) (not (nil? (string/find "done: 1" ls-text)))))
        (var done-line "")
        (each line (string/split "\n" ls-text)
          (when (= 0 (string/find "done:" line)) (set done-line line)))
        (printf "kernel 整合：%.3f 秒，log.txt %d 行，%s" elapsed log-lines done-line)))
    (printf "%d 條通過 ✓" n)))
