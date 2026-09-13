# 一次只跑一個 Janet 頂層 form，把環境存進 PROG 旁的 .aos-step/。

(defn- dirname [path]
  (def cuts (string/find-all "/" path))
  (if (= 0 (last cuts)) "/" (string/slice path 0 (last cuts))))

(def- source-file
  (or (os/realpath (dyn :current-file))
      (error "aos-step: 無法定位 src/step.janet")))
(def- aos-file (string (dirname source-file) "/aos.janet"))

(defn- path [state name] (string state "/" name))
(defn- exists? [p] (not (nil? (os/stat p :mode))))

(defn- rm-tree [p]
  (case (os/stat p :mode)
    :directory (do (each name (os/dir p)
                     (rm-tree (string p "/" name)))
                   (os/rmdir p))
    nil nil
    (os/rm p)))

(defn- atomic-spit [p contents]
  (def tmp (string p ".tmp." (os/getpid)))
  (spit tmp contents)
  (os/rename tmp p))

(defn- parse-forms [prog]
  (def parser (parser/new))
  (parser/consume parser (slurp prog))
  (parser/eof parser)
  (when-let [message (parser/error parser)]
    (error message))
  (def forms @[])
  (var wrapped (parser/produce parser true))
  (while wrapped
    (array/push forms (wrapped 0))
    (set wrapped (parser/produce parser true)))
  forms)

(defn- read-pc [state]
  (def p (path state "pc"))
  (if (not (exists? p))
    0
    (let [text (string/trim (slurp p))
          value (scan-number text)]
      (unless (and value (number? value) (= value (math/floor value)) (>= value 0))
        (error (string "pc 壞了：" text)))
      value)))

(defn- error-text [state]
  (def p (path state "error"))
  (if (exists? p) (string (slurp p)) nil))

(defn- trace-text [fib err]
  (def out @"")
  (with-dyns [*err* out]
    (debug/stacktrace fib err ""))
  (string/trim out))

(defn- write-error [state pc err trace]
  (os/mkdir state)
  (atomic-spit (path state "error")
               (string "form " pc "\n"
                       (describe err) "\n"
                       trace "\n")))

(defn- fail [state pc err &opt fib]
  (def trace (if fib (trace-text fib err) (describe err)))
  (write-error state pc err trace)
  (eprintf "aos-step: form %d 失敗：%s" pc (describe err))
  1)

(defn- bind-runtime [env here pc]
  # 絕對路徑用 require 載入，再把公開名字每次重綁進持久 env。
  (def module (require aos-file))
  (each name ['exec-path 'call 'call-dir 'call-json 'ok? 'value 'pipe]
    (eval ~(def ,(symbol (string "aos/" name)) (quote ,((module name) :value))) env))
  # env 裡的綁定有編譯器用的描述層，不能只用 put 塞裸值。
  (eval ~(def here ,here) env)
  (eval ~(def pc ,pc) env)
  env)

(defn- load-env [state]
  (def p (path state "env.img"))
  (if (exists? p) (load-image (slurp p)) (make-env)))

(defn- step [prog here state done-exit]
  (label finish
  (var pc 0)
  (def parsed (fiber/new (fn [] (parse-forms prog)) :e))
  (def forms (resume parsed))
  (when (= :error (fiber/status parsed))
    (return finish (fail state pc (fiber/last-value parsed) parsed)))
  (def got-pc (fiber/new (fn [] (read-pc state)) :e))
  (set pc (resume got-pc))
  (when (= :error (fiber/status got-pc))
    (return finish (fail state 0 (fiber/last-value got-pc) got-pc)))
  (when (>= pc (length forms))
    (os/mkdir state)
    (spit (path state "done") "")
    (return finish done-exit))
  (when (exists? (path state "done"))
    (os/rm (path state "done")))
  (def prepared (fiber/new
                  (fn []
                    (def env (bind-runtime (load-env state) here pc))
                    (def value (eval (forms pc) env))
                    # image 存不下也算這一步失敗，pc 和舊 image 都不動。
                    [value (make-image env)])
                  :e))
  (def result (resume prepared))
  (when (= :error (fiber/status prepared))
    (return finish (fail state pc (fiber/last-value prepared) prepared)))
  (def [value image] result)
  (os/mkdir state)
  (atomic-spit (path state "env.img") image)
  (atomic-spit (path state "pc") (string (inc pc) "\n"))
  (when (exists? (path state "error"))
    (os/rm (path state "error")))
  (if (= (inc pc) (length forms))
    (spit (path state "done") "")
    (when (exists? (path state "done")) (os/rm (path state "done"))))
  (printf "%q" value)
  0))

(defn- status [prog state]
  (var n 0)
  (var parse-error nil)
  (def parsed (fiber/new (fn [] (parse-forms prog)) :e))
  (def forms (resume parsed))
  (if (= :error (fiber/status parsed))
    (set parse-error (describe (fiber/last-value parsed)))
    (set n (length forms)))
  (var pc 0)
  (def read (protect (read-pc state)))
  (if (read 0) (set pc (read 1)) (set parse-error (describe (read 1))))
  (def err (or parse-error (error-text state)))
  # table/struct 不會保留 nil value，所以手寫最外層，確保 :error nil 也真的印出來。
  (printf "{:pc %d :n %d :done %s :error %s}"
          pc n
          (if (exists? (path state "done")) "true" "false")
          (if err (string/format "%q" err) "nil"))
  0)

(defn- usage []
  (eprint "用法：aos-step PROG.janet [--status|--reset] [--done-exit N]")
  2)

(defn main [& argv]
  (def args (drop 1 argv))
  (when (< (length args) 1)
    (os/exit (usage)))
  (def given (args 0))
  (var flag nil)
  (var done-exit 100)
  (var i 1)
  (while (< i (length args))
    (def arg (args i))
    (case arg
      "--status"
        (if flag
          (os/exit (usage))
          (set flag arg))
      "--reset"
        (if flag
          (os/exit (usage))
          (set flag arg))
      "--done-exit"
        (do
          (++ i)
          (when (>= i (length args))
            (os/exit (usage)))
          (def value (scan-number (args i)))
          (unless (and value (number? value) (= value (math/floor value))
                       (>= value 0) (<= value 255))
            (os/exit (usage)))
          (set done-exit value))
      (os/exit (usage)))
    (++ i))
  (def tried (protect (os/realpath given)))
  (def prog (if (tried 0) (tried 1) nil))
  (unless (and prog (= :file (os/stat prog :mode)))
    (eprintf "aos-step: 找不到程式：%s" given)
    (os/exit 2))
  (def here (dirname prog))
  (def state (string here "/.aos-step"))
  (def code
    (case flag
      "--reset" (do (rm-tree state) 0)
      "--status" (status prog state)
      (step prog here state done-exit)))
  (os/exit code))
