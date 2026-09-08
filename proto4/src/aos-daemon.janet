# aos-daemon 命令列：跟常駐的 kernel（見 src/daemon.janet）講話。
#
#   janet src/aos-daemon.janet start|run|stop|ls        [--home DIR] [--interval N]
#   janet src/aos-daemon.janet register <dir> [name] [interval]  [--home DIR] [--no-wait]
#   janet src/aos-daemon.janet unregister|pause|resume <name>    [--home DIR] [--no-wait]
#   janet src/aos-daemon.janet eval '<janet 表達式>'      [--home DIR]
#
# home（daemon 的家）怎麼決定，照這個順序：
#   1. 命令列 --home DIR
#   2. 環境變數 AOS_DAEMON_DIR
#   3. 都沒有 → 印一句、退 2
# **home 只走 --home，不吃位置參數**——因為 register 的位置參數已經有 dir／name／interval 三個，
# 再多一個 home 很容易搞混（proto2 是吃位置參數的，這裡改掉）。
#
#   start   背景開一個 daemon，等它第一格跑完才回
#   run     前景跑（Ctrl-C 結束），除錯用
#   stop    請它跑完這格收工；不理就 kill
#   ls      讀 state.jdn 印現在的樣子（daemon 沒在跑也看得到）
#   其他    包成一個 Janet 表達式丟進 requests/，等 done/ 的結果印出來（--no-wait 就不等）
#
# register 的 dir 這裡就用 os/realpath 轉成絕對路徑再送——daemon 的 cwd 跟你不一樣。

(import ./daemon)

(defn- usage []
  (eprint "用法：")
  (eprint "  janet src/aos-daemon.janet start|run|stop|ls       [--home DIR] [--interval N]")
  (eprint "  janet src/aos-daemon.janet register <dir> [name] [interval] [--home DIR] [--no-wait]")
  (eprint "  janet src/aos-daemon.janet unregister|pause|resume <name>   [--home DIR] [--no-wait]")
  (eprint "  janet src/aos-daemon.janet eval '<janet 表達式>'    [--home DIR]")
  (eprint "home：--home DIR > 環境變數 AOS_DAEMON_DIR > 沒有就退 2"))

(defn- q
  "把一個值寫成 Janet 字面（字串會加引號跳脫），拼請求表達式用。"
  [v] (string/format "%j" v))

(defn- show-result
  "把 done 檔讀回來的 {:ok :result} 印成人看的樣子。"
  [r]
  (when r
    (if (r :ok)
      (do (print "ok") (pp (r :result)))
      (print "失敗：" (r :result)))))

(defn main [& argv]
  (def args (drop 1 argv))
  (when (empty? args) (usage) (os/exit 2))

  # 先把旗標挑掉，剩下的才是位置參數
  (def pos @[])
  (var home nil)
  (var interval nil)
  (var wait true)
  (var i 0)
  (while (< i (length args))
    (def a (args i))
    (cond
      (= a "--home")     (do (++ i) (set home (args i)))
      (= a "--interval") (do (++ i) (set interval (scan-number (args i))))
      (= a "--no-wait")  (set wait false)
      (or (= a "-h") (= a "--help")) (do (usage) (os/exit 0))
      (array/push pos a))
    (++ i))

  (unless home (set home (os/getenv "AOS_DAEMON_DIR")))
  (unless home
    (eprint "不知道 daemon 的家在哪：給 --home DIR 或設環境變數 AOS_DAEMON_DIR")
    (os/exit 2))

  (def cmd (get pos 0))
  (def rest (drop 1 pos))

  (cond
    (= cmd "start") (os/exit (if (daemon/start home (or interval 1)) 0 1))
    (= cmd "run")   (daemon/serve home (or interval 1))
    (= cmd "stop")  (os/exit (if (daemon/stop home) 0 1))
    (= cmd "ls")    (daemon/ls home)

    (= cmd "register")
    (do
      (when (empty? rest) (eprint "register 要給資料夾") (os/exit 2))
      (def dir (get rest 0))
      (unless (= (os/stat dir :mode) :directory)
        (eprint "不是資料夾：" dir) (os/exit 2))
      (def abs (os/realpath dir))          # 一律絕對路徑，daemon 的 cwd 跟這裡不一樣
      (def name (get rest 1))
      (def iv (if-let [s (get rest 2)] (scan-number s) nil))
      (show-result
        (daemon/request home
                        (string "(register " (q abs)
                                (if (or name iv) (string " " (if name (q name) "nil")) "")
                                (if iv (string " " iv) "")
                                ")")
                        wait)))

    (find |(= $ cmd) ["unregister" "pause" "resume"])
    (do
      (when (empty? rest) (eprint cmd " 要給名字") (os/exit 2))
      (show-result (daemon/request home (string "(" cmd " " (q (get rest 0)) ")") wait)))

    (= cmd "eval")
    (do
      (when (empty? rest) (eprint "eval 要給一個 Janet 表達式") (os/exit 2))
      (show-result (daemon/request home (get rest 0) wait)))

    (do (eprint "不認得的指令：" cmd) (usage) (os/exit 2))))
