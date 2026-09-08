;;; proto3-1 骨幹範例（CL 版）：世界／時鐘／agent 三層在記憶體裡跑起來，
;;; 每個世界每一格就是 eval 它自己那句 list。劇情跟 proto3 同一個。
;;; 跑法：sbcl --script src/main.lisp 8          同步走 8 格就停
;;;       sbcl --script src/main.lisp async 5    非同步：每個鐘一條 thread 各走各的，5 秒後收
(load (merge-pathnames "load.lisp" (directory-namestring *load-truename*)))
(in-package :aos)

(defun log-line (&rest xs)
  (format t "~3d ~a：~{~a~}~%" (now) (w-get *me* :path) xs))

;; 1. 一個只會報時的世界：它的 list 就是 (tell-time)
(defun tell-time () (log-line "現在 " (get-universal-time)))
(defvar *world-1* (make-world "world-1" '(tell-time)))

;; 2. LLM 世界（假引擎：把話原樣回去），它的 list 是 (llm-step)，自己一個鐘
(defvar *llm-1* (make-llm "llm" #'echo-engine))

;; 3. 一個 agent，問 llm-1；它的 list 從 (agent-idle) 開始，一格一格被改寫。
;;    底下一個借它鐘的小孩、一個自己有鐘的小孩——小孩就是巢狀的 list。
(defvar *agent-1* (make-agent "agent-1" *llm-1* :system "你是 agent-1"))
(with-world *agent-1* (kid "shared-kid" '(log-line "跟著爸爸走")))
(defvar *own-kid*
  (with-world *agent-1* (kid "own-kid" :own '(log-line "自己的鐘，兩秒一格"))))

;; 4. 使用者也是一個世界（沒有鐘，只是有個 path 可以收回信）
(defvar *user* (make-world "user" nil))

;; 5. 旁觀者：狀態＝agent 現在的 form 的第一個符號，一變就印一行。
;;    它自己的「上次看到什麼」也是靠 setvar 留在自己的環境裡。
(defun watch-agent (path)
  (let* ((a (world-at path))
         (s (and a (state-of a))))
    (unless (eq s (var 'seen))
      (log-line "agent-1 的 form：" (var 'seen) " → " s)
      (setvar 'seen s))
    :busy))

;; 登記順序＝同步模式的走格順序，observer 放第一個才看得到每一格開始時的狀態
(register (make-world "observer" '(watch-agent "agent-1")))
(register *world-1*)
(register *llm-1*)
(register *agent-1*)
(register *own-kid* 2)

(defun summary ()
  (format t "~%agent-1 現在的 form：~s~%" (w-get *agent-1* :form))
  (format t "agent-1 說了：~{~a~^ / ~}~%" (mapcar (lambda (m) (getf m :body)) (w-get *agent-1* :outbox)))
  (format t "user 收到：~{~a~^ / ~}~%" (mapcar (lambda (m) (getf m :body)) (w-get *user* :inbox)))
  (format t "格的會計：~s~%" (w-get *agent-1* :ticks))
  (format t "鐘：~s~%" (ls)))

(defun main (args)
  (with-world *user* (send "agent-1" "你好，agent-1"))
  (if (equal (first args) "async")
      (let ((secs (parse-integer (or (second args) "5"))))
        (start)
        (sleep 1.5)
        (sb-thread:with-mutex (*tick-lock*) (with-world *user* (send "agent-1" "第二句")))
        (sleep (- secs 1.5))
        (stop-all)
        (summary))
      (progn (run (parse-integer (or (first args) "8")) 0)
             (summary)))
  (finish-output))

(main (rest sb-ext:*posix-argv*))
