# aos 函式庫。跑法：janet test/aos.janet
(import ../src/aos :as aos)

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

(defn dirname [path]
  (string/slice path 0 (last (string/find-all "/" path))))
(def cf (os/realpath (dyn :current-file)))
(def fx (string (dirname cf) "/fx"))
(def root (dirname (dirname (dirname cf))))
(def fake-server (string root "/proto4-5/test/_fake_openai.py"))
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

(defn read-line [stream]
  (def out @"")
  (var ch (:read stream 1))
  (while (and ch (not (= "\n" (string ch))))
    (buffer/push out ch)
    (set ch (:read stream 1)))
  (string out))

(defer (rm-tree tmp)
  (do
    (os/mkdir tmp)

    (check "aos/wait-for 回指定的宣告形狀"
           (= {:aos/wait-for "out.json"} (aos/wait-for "out.json")))

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

    (def fed (aos/call (string fx "/cat.sh") @{:stdin "hello\n" :capture true}))
    (check ":stdin 餵給普通檔並用 :capture 接回" (= "hello\n" (fed :out)))
    (def multi (aos/call (string fx "/multi.sh") @{:capture true}))
    (check ":capture 接到多行 stdout" (= "one\ntwo\nthree\n" (multi :out)))
    (check "沒給 :capture 時 :out 是 nil" (nil? ((aos/call (string fx "/multi.sh")) :out)))

    (def streams (string tmp "/streams"))
    (mkdir2 streams ".aos")
    (spit (string streams "/.aos/inst.json")
          "{\"argv\":[\"/bin/sh\",\"-c\",\"printf '{\\\"a\\\":1,\\\"b\\\":[1,2]}'; printf warning >&2\"],\"stdout\":\"out.txt\",\"stderr\":\"err.txt\"}\n")
    (def read-result
      (aos/call-dir streams
                    @{:capture true
                      :read (string streams "/out.txt")
                      :read-err (string streams "/err.txt")}))
    (check ":read 把 inst stdout 檔讀進 :out" (= "{\"a\":1,\"b\":[1,2]}" (read-result :out)))
    (check ":read 與 :capture 同時給時 :read 贏" (not (= "" (read-result :out))))
    (check ":read-err 把檔案讀進 :err" (= "warning" (read-result :err)))
    (def missing-read (aos/call-dir streams @{:read (string streams "/missing.txt")}))
    (check ":read 檔案不存在時 :out 是 nil" (nil? (missing-read :out)))

    (def decoded (aos/call (string fx "/json.sh") @{:capture true :json true}))
    (check ":json 解出陣列內的值" (= 2 (get-in decoded [:value "b" 1])))
    (def bad-json (aos/call (string fx "/bad-json.sh") @{:capture true :json true}))
    (check "壞 JSON 的 :value 是 nil" (nil? (bad-json :value)))
    (check "壞 JSON 會放 :json-error" (string? (bad-json :json-error)))
    (def empty-json (aos/call (string fx "/empty.sh") @{:capture true :json true}))
    (check "空輸出的 :value 是 nil" (nil? (empty-json :value)))
    (check "空輸出沒有 :json-error" (nil? (empty-json :json-error)))
    (check "aos/value 優先回解過的 :value" (= 1 (get (aos/value decoded) "a")))
    (check "aos/value 沒有 :value 就回 :out" (= "one\ntwo\nthree\n" (aos/value multi)))

    (def piped
      (aos/pipe @[(string fx "/pipe-echo.sh")
                  [(string fx "/pipe-upper.sh") @{}]
                  (string fx "/pipe-count.sh")]))
    (check "pipe 三段串接後的最後 stdout 正確" (= "2" (string/trim (piped :out))))
    (check "pipe 回傳三段 steps" (= 3 (length (piped :steps))))
    (check "pipe 的中間段吃到上一段 stdout"
           (= "ONE\nTWO\n" (get-in piped [:steps 1 :out])))
    (def pipe-json
      (aos/pipe @[(string fx "/pipe-echo.sh")
                  (string fx "/pipe-upper.sh")
                  (string fx "/pipe-count.sh")]
                @{:json true}))
    (check "pipe opts 的 :json 只解最後一段"
           (and (= 2 (pipe-json :value))
                (nil? (get-in pipe-json [:steps 0 :value]))
                (nil? (get-in pipe-json [:steps 1 :value]))))
    (check "pipe 遇到資料夾 inst 會 error"
           (throws? (fn [] (aos/pipe @[(string fx "/pipe-echo.sh") streams]))))

    (def server (os/spawn ["python3" fake-server] :p {:out :pipe :err :pipe}))
    (defer (protect (os/proc-kill server true :term))
      (do
        (def port (read-line (server :out)))
        (def endpoint (string tmp "/endpoint.json"))
        (spit endpoint
              (string "{\"name\":\"local\",\"kind\":\"openai\",\"base_url\":\"http://127.0.0.1:"
                      port "/v1\",\"model\":\"fake-model\",\"timeout_ms\":2000}\n"))
        (def llm-out (string tmp "/llm.json"))
        (def llm-ok
          (aos/llm endpoint
                   @{:messages [@{:role "user" :content "echo:hi"}]}
                   llm-out))
        (check "aos/llm 成功回 code 0，llm-text 取到文字"
               (and (= 0 (llm-ok :code)) (= "hi" (aos/llm-text llm-ok))))
        (def llm-fail
          (aos/llm endpoint
                   @{:messages [@{:role "user" :content "fail:500"}]}
                   llm-out))
        (check "aos/llm HTTP 失敗回 code 1、llm-text nil 且保留 kind"
               (and (= 1 (llm-fail :code))
                    (nil? (aos/llm-text llm-fail))
                    (= "http" (get-in llm-fail [:value "error" "kind"]))))
        (def saved-req
          ((get-in (require (string (dyn :syspath) "/spork/json.so"))
                   ['decode :value])
           (slurp (string llm-out ".req.json"))))
        (check "aos/llm 留下可對帳的 .req.json"
               (and (= :file (os/stat (string llm-out ".req.json") :mode))
                    (= "fail:500" (get-in saved-req ["messages" 0 "content"]))))))

    (printf "%d 條通過 ✓" n)))
