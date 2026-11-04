# aos.janet 用到的路徑：本檔位置、spork json 模組、aos-exec／aos-llm／aos-kernel 的解析結果。
# 只有 aos.janet 以 (import ./paths :prefix "") 取用；import 進去的名字自動是 private，
# 不會被 aos-step 綁成 aos/*。

(defn dirname [path]
  (def cuts (string/find-all "/" path))
  (cond
    (empty? cuts) "."
    (= 0 (last cuts)) "/"
    (string/slice path 0 (last cuts))))

(def source-file
  (or (os/realpath (dyn :current-file))
      (error "aos: 無法定位 src/aos.janet")))

(def json-module (string (dyn :syspath) "/spork/json.so"))

(def default-exec
  (string (dirname (dirname source-file)) "/../proto4-3/aos-exec"))

(def default-llm
  (string (dirname (dirname source-file)) "/../proto4-5/aos-llm"))

(def default-kernel (string (dirname (dirname source-file)) "/../proto4-3/aos-kernel"))

(def resolved-exec
  (let [raw (or (os/getenv "AOS_EXEC") default-exec)
        tried (protect (os/realpath raw))
        path (if (tried 0) (tried 1) nil)]
    (unless (and path (= :file (os/stat path :mode)))
      (error (string "aos: 找不到 aos-exec：" raw)))
    path))

(def resolved-llm
  (let [raw (or (os/getenv "AOS_LLM") default-llm)
        tried (protect (os/realpath raw))
        path (if (tried 0) (tried 1) nil)]
    (unless (and path (= :file (os/stat path :mode)))
      (error (string "aos: 找不到 aos-llm：" raw)))
    path))

(def resolved-kernel
  (let [raw (or (os/getenv "AOS_KERNEL") default-kernel)
        tried (protect (os/realpath raw))
        path (if (tried 0) (tried 1) nil)]
    (unless (and path (= :file (os/stat path :mode)))
      (error (string "aos: 找不到 aos-kernel：" raw)))
    path))
