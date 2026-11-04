# 資料夾模擬 lisp：(runf (./xxx a b)) ＝ 切到 ./xxx、把 ./xxx/.aos/inst 當 Janet 程式跑、回最後一個值。
# .aos/inst 這段相對路徑可以設定：dynamic binding :inst-path（setdyn 全域改、with-dyns 改一段）。

(def default-inst "沒設定時的 inst 相對路徑" ".aos/inst")

(defn inst-path
  "現在生效的 inst 相對路徑（先看 dynamic :inst-path，沒有就用預設）。"
  [] (or (dyn :inst-path) default-inst))

(var- exports nil)   # inst 環境裡要看得到的名字，檔案尾端才填（runf 定義在後面）

(defn expand
  "路徑開頭的 ~ 換成家目錄（Janet 不會自己做這件事）。"
  [dir]
  (cond
    (= dir "~") (os/getenv "HOME")
    (string/has-prefix? "~/" dir) (string (os/getenv "HOME") (string/slice dir 1))
    dir))

(defn run-dir
  "跑一個資料夾：讀 <dir>/<inst-path>，工作目錄切到 dir，整份當 Janet 程式求值，回最後一個值。
   inst 裡看得到 args（參數 tuple）、here（資料夾絕對路徑）、runf／run-dir。
   資料夾或 inst 不存在就 error；inst 自己 error 也會往外丟，工作目錄一定切回來。"
  [dir0 & args]
  (def dir (expand dir0))
  (def file (string dir "/" (inst-path)))
  (unless (= (os/stat dir :mode) :directory) (error (string "不是資料夾：" dir)))
  (unless (os/stat file :mode) (error (string "找不到 " file)))
  (def src (slurp file))
  (def env (make-env root-env))
  (eachp [k v] exports (put env k v))          # v 是整個綁定表（runf 是巨集，要連 :macro 一起帶）
  (put env 'args @{:value args})
  (put env 'here @{:value (os/realpath dir)})
  (put env :inst-path (inst-path))          # 子孫沿用同一個設定
  (put env :source file)
  (def old (os/cwd))
  (os/cd dir)
  (defer (os/cd old)
    (eval-string src env)))

(defmacro runf
  "(runf (./xxx a b)) → 跑資料夾 ./xxx，a b 當參數。路徑也可以是字串：(runf \"./xxx\" a b)。
   這是巨集，所以 (./xxx a b) 不用加引號；加了 '(./xxx a b) 也行，當成同一回事。"
  [form0 & rest]
  # 使用者若寫 '(./xxx …)，拿到的是 (quote (./xxx …))，剝掉那層
  (def form (if (and (tuple? form0) (= (first form0) 'quote)) (get form0 1) form0))
  (def head (get form 0))
  (cond
    # (~/xxx …)：Janet 把 ~ 讀成準引號，頭變成 (quasiquote /xxx)，拼回 "~/xxx"
    (and (tuple? form) (tuple? head) (= (first head) 'quasiquote) (symbol? (get head 1)))
    ~(,run-dir ,(string "~" (get head 1)) ,;(slice form 1))
    (and (tuple? form) (symbol? head))
    ~(,run-dir ,(string head) ,;(slice form 1))
    ~(,run-dir ,form ,;rest)))

(set exports {'runf (dyn 'runf) 'run-dir (dyn 'run-dir) 'inst-path (dyn 'inst-path) 'expand (dyn 'expand)})
