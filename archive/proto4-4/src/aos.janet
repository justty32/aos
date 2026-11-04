# proto4-3 aos-exec 的 Janet 薄包裝。不自己解 inst.json。

(import ./paths :prefix "")

(defn exec-path [] resolved-exec)

(defn- integer? [x]
  (and (number? x) (= x (math/floor x))))

(defn- argv-for [target opts]
  (unless (string? target)
    (error "aos/call: target 必須是字串"))
  (when (and opts (not (table? opts)))
    (error "aos/call: opts 必須是 table"))
  (default opts @{})
  (eachp [key value] opts
    (case key
      :dir-target
        (unless (string? value)
          (error "aos/call: :dir-target 必須是字串"))
      :timeout-ms
        (unless (and (integer? value) (>= value 0))
          (error "aos/call: :timeout-ms 必須是非負整數"))
      :args
        (do
          (unless (or (array? value) (tuple? value))
            (error "aos/call: :args 必須是字串陣列"))
          (each arg value
            (unless (string? arg)
              (error "aos/call: :args 必須是字串陣列"))))
      :stdin
        (unless (or (string? value) (buffer? value))
          (error "aos/call: :stdin 必須是字串或 buffer"))
      :capture
        (unless (boolean? value)
          (error "aos/call: :capture 必須是 boolean"))
      :read
        (unless (string? value)
          (error "aos/call: :read 必須是字串"))
      :read-err
        (unless (string? value)
          (error "aos/call: :read-err 必須是字串"))
      :json
        (unless (boolean? value)
          (error "aos/call: :json 必須是 boolean"))
      (error (string "aos/call: 不認得的選項 " key))))
  (def argv @[resolved-exec target])
  (when-let [value (opts :dir-target)]
    (array/push argv "--dir-target")
    (array/push argv value))
  (when-let [value (opts :timeout-ms)]
    (array/push argv "--timeout-ms")
    (array/push argv (string value)))
  (when (has-key? opts :args)
    (when (or (string/has-suffix? ".json" target)
              (= :directory (os/stat target :mode)))
      (error "aos/call: :args 只能用在普通檔案目標；inst 目標的參數寫在 inst.json 的 argv 裡"))
    (array/push argv "--")
    (each arg (opts :args) (array/push argv arg)))
  argv)

(defn- pump-pipe [stream]
  (def out @"")
  (ev/spawn
    (var chunk (:read stream 4096))
    (while chunk
      (buffer/push out chunk)
      (set chunk (:read stream 4096)))
    (:close stream))
  out)

(defn- read-file [path]
  (if (= :file (os/stat path :mode)) (string (slurp path)) nil))

(defn- decode-json [text]
  # 不把 spork 的 cfunction 綁進模組環境，讓 aos-step 可以 make-image。
  ((get-in (require json-module) ['decode :value]) text))

(defn- encode-json [value]
  (string ((get-in (require json-module) ['encode :value]) value)))

(defn- absolute-path [given]
  (def raw (if (string/has-prefix? "/" given) given (string (os/cwd) "/" given)))
  (def parts @[])
  (each part (string/split "/" raw)
    (cond (or (= "" part) (= "." part)) nil
          (= ".." part) (array/pop parts)
          (array/push parts part)))
  (string "/" (string/join parts "/")))

(defn- aos-line? [stderr]
  (var found false)
  (each line (string/split "\n" stderr)
    (when (string/has-prefix? "aos-exec: " line)
      (set found true)))
  found)

(defn call
  "把 target 原封不動交給 aos-exec，可選擇接住三條流。"
  [target &opt opts]
  (def argv (argv-for target opts))
  (default opts @{})
  (def spawn-opts @{:err :pipe})
  (when (opts :stdin) (put spawn-opts :in :pipe))
  (when (opts :capture) (put spawn-opts :out :pipe))
  (def proc (os/spawn argv :p spawn-opts))
  # stdout/stderr 同時排空，避免任一邊撐滿 pipe 後雙方互等。
  (def stderr-buffer (pump-pipe (proc :err)))
  (def stdout-buffer (if (opts :capture) (pump-pipe (proc :out)) nil))
  (when-let [input (opts :stdin)]
    (:write (proc :in) input)
    (:close (proc :in)))
  (def code (os/proc-wait proc))
  (def stderr (string stderr-buffer))
  (def marked? (aos-line? stderr))
  (def result
    @{:code code
      :kind (cond
              (and (= code 125) marked?) "aos"
              (and (= code 2) marked?) "usage"
              "child")
      :stderr stderr})
  (when (opts :capture)
    (put result :out (string stdout-buffer)))
  (when-let [path (opts :read)]
    (put result :out (read-file path)))
  (when-let [path (opts :read-err)]
    (put result :err (read-file path)))
  (when (opts :json)
    (def out (result :out))
    (unless (or (nil? out) (= 0 (length out)))
      (def decoded (protect (decode-json out)))
      (if (decoded 0)
        (put result :value (decoded 1))
        (put result :json-error (describe (decoded 1))))))
  result)

(defn call-dir [dir &opt opts]
  (unless (= :directory (os/stat dir :mode))
    (error (string "aos/call-dir: 不是資料夾：" dir)))
  (call dir opts))

(defn call-json [path &opt opts]
  (unless (and (string? path) (string/has-suffix? ".json" path))
    (error (string "aos/call-json: 不是 .json 路徑：" path)))
  (call path opts))

(defn ok? [result]
  (and (= "child" (result :kind)) (= 0 (result :code))))

(defn value [result]
  (if (has-key? result :value) (result :value) (result :out)))

(defn llm
  "同步呼叫一次 aos-llm，把請求與結果留在 out.req.json／out。"
  [endpoint req out &opt opts]
  (unless (string? endpoint)
    (error "aos/llm: endpoint 必須是字串"))
  (unless (or (table? req) (struct? req))
    (error "aos/llm: req 必須是 table 或 struct"))
  (unless (string? out)
    (error "aos/llm: out 必須是字串"))
  (when (and opts (not (table? opts)))
    (error "aos/llm: opts 必須是 table"))
  (default opts @{})
  (eachp [key value] opts
    (unless (= key :timeout-ms)
      (error (string "aos/llm: 不認得的選項 " key)))
    (unless (and (integer? value) (>= value 0))
      (error "aos/llm: :timeout-ms 必須是非負整數")))
  (def endpoint-path (absolute-path endpoint))
  (def out-path (absolute-path out))
  (def reqfile (string out-path ".req.json"))
  (spit reqfile (string (encode-json req) "\n"))
  (def call-opts @{:args @["call" endpoint-path reqfile out-path] :read out-path :json true})
  (when-let [timeout (opts :timeout-ms)]
    (put call-opts :timeout-ms timeout))
  (def result (call resolved-llm call-opts))
  # aos/call 為了辨認 kind 會接住 stderr；LLM 這條同步介面要讓它仍出現在
  # aos-step 的 stderr，同時保留在結果 table 供程式查看。
  (when (> (length (result :stderr)) 0)
    (eprint (string/trimr (result :stderr))))
  result)

(defn llm-text [result]
  (def value (result :value))
  (if (and (dictionary? value) (get value "ok"))
    (get value "text")
    nil))

(defn wait-for [path]
  (unless (string? path) (error "aos/wait-for: path 必須是字串"))
  {:aos/wait-for path})

(defn llm-submit [K req name]
  (unless (string? K) (error "aos/llm-submit: K 必須是字串"))
  (unless (or (table? req) (struct? req))
    (error "aos/llm-submit: req 必須是 table 或 struct"))
  (unless (and (string? name) (> (length name) 0))
    (error "aos/llm-submit: name 必須是非空字串"))
  (def kernel-home (absolute-path K))
  (def reqfile (string (os/cwd) "/" name ".req.json"))
  (spit reqfile (string (encode-json req) "\n"))
  (def result
    (call resolved-kernel
          @{:args @["llm" kernel-home reqfile "--name" name] :capture true}))
  (unless (ok? result)
    (def stderr (string/trim (result :stderr)))
    (def detail (if (> (length stderr) 0) stderr (string/trim (result :out))))
    (error (string "aos/llm-submit: aos-kernel 回 " (result :code) "：" detail)))
  (string kernel-home "/llm/results/" name ".json"))

(defn- copy-opts [opts]
  (def copied @{})
  (when opts (eachp [key val] opts (put copied key val)))
  copied)

(defn- plain-executable? [target]
  (and (string? target)
       (not (string/has-suffix? ".json" target))
       (= :file (os/stat target :mode))
       (not (nil? (string/find "x" (os/stat target :permissions))))))

(defn pipe
  "依序執行普通可執行檔，把前一段的 stdout 當下一段 stdin。"
  [targets &opt opts]
  (unless (array? targets)
    (error "aos/pipe: targets 必須是陣列"))
  (when (empty? targets)
    (error "aos/pipe: targets 不能是空陣列"))
  (when (and opts (not (table? opts)))
    (error "aos/pipe: opts 必須是 table"))
  (def steps @[])
  (var previous nil)
  (for i 0 (length targets)
    (def spec (targets i))
    (def target (if (string? spec) spec (get spec 0)))
    (def local-opts (if (string? spec) nil (get spec 1)))
    (unless (or (string? spec)
                (and (indexed? spec) (= 2 (length spec))
                     (string? target) (table? local-opts)))
      (error "aos/pipe: 每段必須是 target 字串或 [target opts]"))
    (unless (plain-executable? target)
      (error (string "aos/pipe: 只支援普通可執行檔；資料夾或 .json inst 目標的三條流由 inst.json 控制：" target)))
    (def call-opts (copy-opts opts))
    (when local-opts
      (eachp [key val] local-opts (put call-opts key val)))
    (put call-opts :capture true)
    (when (> i 0) (put call-opts :stdin previous))
    # pipe 最外層的 :json 只解最後一段。
    (when (< i (dec (length targets))) (put call-opts :json false))
    (def result (call target call-opts))
    (array/push steps result)
    (set previous (result :out)))
  # 複製最後一段再加 :steps，避免結果裡產生指回自己的 cycle。
  (def final-result (copy-opts (last steps)))
  (put final-result :steps steps)
  final-result)
