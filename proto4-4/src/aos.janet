# proto4-3 aos-exec 的 Janet 薄包裝。不自己解 inst.json。

(defn- dirname [path]
  (def cuts (string/find-all "/" path))
  (cond
    (empty? cuts) "."
    (= 0 (last cuts)) "/"
    (string/slice path 0 (last cuts))))

(def- source-file
  (or (os/realpath (dyn :current-file))
      (error "aos: 無法定位 src/aos.janet")))

(def- default-exec
  (string (dirname (dirname source-file)) "/../proto4-3/aos-exec"))

(def- resolved-exec
  (let [raw (or (os/getenv "AOS_EXEC") default-exec)
        tried (protect (os/realpath raw))
        path (if (tried 0) (tried 1) nil)]
    (unless (and path (= :file (os/stat path :mode)))
      (error (string "aos: 找不到 aos-exec：" raw)))
    path))

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
      (error (string "aos/call: 不認得的選項 " key))))
  (def argv @[resolved-exec target])
  (when-let [value (opts :dir-target)]
    (array/push argv "--dir-target")
    (array/push argv value))
  (when-let [value (opts :timeout-ms)]
    (array/push argv "--timeout-ms")
    (array/push argv (string value)))
  argv)

(defn- read-pipe [stream]
  (def out @"")
  (var chunk (:read stream 4096))
  (while chunk
    (buffer/push out chunk)
    (set chunk (:read stream 4096)))
  (:close stream)
  (string out))

(defn- aos-line? [stderr]
  (var found false)
  (each line (string/split "\n" stderr)
    (when (string/has-prefix? "aos-exec: " line)
      (set found true)))
  found)

(defn call
  "把 target 原封不動交給 aos-exec，回 {:code :kind :stderr}。"
  [target &opt opts]
  (def proc (os/spawn (argv-for target opts) :p {:err :pipe}))
  # 先排空 pipe 再 wait，避免 aos-exec 的 stderr 撐滿後雙方互等。
  (def stderr (read-pipe (proc :err)))
  (def code (os/proc-wait proc))
  (def marked? (aos-line? stderr))
  @{:code code
    :kind (cond
            (and (= code 125) marked?) "aos"
            (and (= code 2) marked?) "usage"
            "child")
    :stderr stderr})

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
