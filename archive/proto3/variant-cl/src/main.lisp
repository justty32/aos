;;; proto3 骨幹範例（CL 版）：世界／時鐘／agent 三層在記憶體裡跑起來。
;;; 跑法：sbcl --script src/main.lisp 8          同步走 8 格就停
;;;       sbcl --script src/main.lisp async 5    非同步：每個鐘一條 thread 各走各的，5 秒後收
(load (merge-pathnames "load.lisp" (directory-namestring *load-truename*)))
(in-package :aos)

(defun log-line (w &rest xs)
  (format t "~3d ~a：~{~a~}~%" (w-get w :now) (w-get w :path) xs))

;; 1. 一個只會報時的世界
(defvar *world-1* (make-world "world-1" :func-tick (lambda (w) (log-line w "現在 " (get-universal-time)))))

;; 2. LLM 世界（假引擎：把話原樣回去），自己一個鐘
(defvar *llm-1* (make-llm "llm" #'echo-engine))

;; 3. 一個 agent，問 llm-1；它底下一個借它鐘的小孩、一個自己有鐘的小孩
(defvar *agent-1* (make-agent "agent-1" *llm-1* :system "你是 agent-1"))
(spawn *agent-1* "shared-kid" :func-tick (lambda (w) (log-line w "跟著爸爸走")))
(defvar *own-kid* (spawn *agent-1* "own-kid" :clock :own
                         :func-tick (lambda (w) (log-line w "自己的鐘，兩秒一格"))))

;; 4. 使用者也是一個世界（沒有鐘，只是有個 path 可以收回信）
(defvar *user* (make-world "user"))

(register *world-1*)
(register *llm-1*)
(register *agent-1*)
(register *own-kid* 2)

(defun watch (w)
  "旁觀 agent：狀態一變就印一行"
  (lambda (o) (declare (ignore o))
    (unless (eq (w-get w :state) (w-get w :seen))
      (log-line w "狀態 " (w-get w :seen) " → " (w-get w :state))
      (w-put w :seen (w-get w :state)))))
(register (make-world "observer" :func-tick (watch *agent-1*)))

(defun summary ()
  (format t "~%agent-1 說了：~{~a~^ / ~}~%" (mapcar (lambda (m) (getf m :body)) (w-get *agent-1* :outbox)))
  (format t "user 收到：~{~a~^ / ~}~%" (mapcar (lambda (m) (getf m :body)) (w-get *user* :inbox)))
  (format t "格的會計：~s~%" (w-get *agent-1* :ticks))
  (format t "鐘：~s~%" (ls)))

(defun main (args)
  (send-mail *user* *agent-1* "你好，agent-1")
  (if (equal (first args) "async")
      (let ((secs (parse-integer (or (second args) "5"))))
        (start)
        (sleep 1.5)
        (send-mail *user* *agent-1* "第二句")
        (sleep (- secs 1.5))
        (stop-all)
        (summary))
      (progn (run (parse-integer (or (first args) "8")) 0)
             (summary)))
  (finish-output))

(main (rest sb-ext:*posix-argv*))
