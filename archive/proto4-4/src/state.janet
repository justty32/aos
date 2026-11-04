# .aos-step/ 狀態檔的路徑、讀寫與等待狀態。

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

(defn- read-src [state]
  (def p (path state "src"))
  (if (exists? p) (parse (slurp p)) nil))

(defn- read-state [state]
  (def p (path state "state"))
  (if (exists? p)
    (let [value (parse (slurp p))]
      (unless (table? value) (error "state 壞了：必須是 table")) value)
    @{}))

(defn- write-state [state value]
  (atomic-spit (path state "state") (string/format "%q\n" value)))

(defn- now [] (string (os/strftime "%Y-%m-%dT%H:%M:%S" (os/time) false) "+00:00"))

(defn- absolute-path [given here]
  (unless (string? given) (error "aos/wait-for: path 必須是字串"))
  (def raw (if (string/has-prefix? "/" given) given (string here "/" given)))
  (def parts @[])
  (each part (string/split "/" raw)
    (cond (or (= "" part) (= "." part)) nil
          (= ".." part) (array/pop parts)
          (array/push parts part)))
  (string "/" (string/join parts "/")))

(defn- trim-history [history]
  (while (> (length history) 50) (array/remove history 0)) history)

(defn- waiting-line [waiting]
  (unless (and (dictionary? waiting)
               (string? (waiting :for)) (string/has-prefix? "/" (waiting :for))
               (string? (waiting :since))
               (number? (waiting :after_pc)) (>= (waiting :after_pc) 0)
               (number? (waiting :checks)) (>= (waiting :checks) 0))
    (error "state 壞了：waiting 欄位不合法"))
  (string "在等 " (waiting :for) "（已看 " (waiting :checks) " 次，從 " (waiting :since) " 起）"))

(defn- check-waiting [state saved]
  (if-let [waiting (saved :waiting)]
    (do
      (waiting-line waiting)
      (if (not (exists? (waiting :for)))
        (do (put waiting :checks (inc (waiting :checks)))
            (put saved :waiting waiting) (write-state state saved)
            (eprintf "在等 %s（第 %d 次）" (waiting :for) (waiting :checks))
            true)
        (do
          (var history (or (saved :history) @[]))
          (unless (array? history) (set history @[]))
          (array/push history @{:pc (waiting :after_pc) :step "(wait)" :exit 0
                                :waited_checks (waiting :checks) :at (now) :ms 0})
          (put saved :history (trim-history history))
          (put saved :waiting nil)
          (write-state state saved)
          false)))
    false))

(defn- source-changed? [state pc current]
  (def old (read-src state))
  (and (> pc 0) old (not (= old current))))

(defn- write-src [state src]
  (atomic-spit (path state "src") (string/format "%q\n" src)))

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

(defn- write-error [state pc err trace]
  (os/mkdir state)
  (atomic-spit (path state "error")
               (string "form " pc "\n"
                       (describe err) "\n"
                       trace "\n")))

(defn- load-env [state]
  (def p (path state "env.img"))
  (if (exists? p) (load-image (slurp p)) (make-env)))

# 保留上面搬來的 private 函式原文；step 只經這張 API 表取用。
(def api
  {:path path
   :exists? exists?
   :rm-tree rm-tree
   :atomic-spit atomic-spit
   :read-src read-src
   :read-state read-state
   :write-state write-state
   :now now
   :absolute-path absolute-path
   :trim-history trim-history
   :waiting-line waiting-line
   :check-waiting check-waiting
   :source-changed? source-changed?
   :write-src write-src
   :read-pc read-pc
   :error-text error-text
   :write-error write-error
   :load-env load-env})
