;;; kernel：管時鐘。一個世界一個鐘；鐘＝「每 interval 秒對那個世界求值一格」。
;;; 兩種走法：step-all（同步走一格，測試與手動用）、start（每個鐘一條 thread 自己走）。
;;; 跟 proto3 的差別只有一個：鐘存成 list（照登記順序），這樣同步走格的先後是確定的，
;;; observer 才看得到 agent 的 form 一格一格換。
(in-package :aos)

(defstruct clock path world interval (status :running) (ticks 0) thread)

(defvar *clocks* '() "登記中的鐘，照登記順序")
(defvar *started* nil "start 過了沒；過了以後新登記的鐘要自己開 thread")
(defvar *steps* 0 "同步模式走了幾格（interval 在同步模式＝每幾格動一次）")
(defvar *tick-lock* (sb-thread:make-mutex :name "tick")
  "非同步模式下一次只讓一個鐘求值（世界之間會互相寄信、改對方）")

(defun find-clock (path) (find path *clocks* :key #'clock-path :test #'equal))

(defun run-clock (c)
  (loop until (eq (clock-status c) :stopped)
        do (when (eq (clock-status c) :running)
             (sb-thread:with-mutex (*tick-lock*)
               (incf (clock-ticks c))
               (dotick (clock-world c))))
           (sleep (clock-interval c))))

(defun register (w &optional (interval 1))
  "替世界登記一個鐘。interval 秒走一格（預設 1）。同一個世界重複登記＝換掉舊鐘。"
  (let* ((path (w-get w :path))
         (old (find-clock path))
         (c (make-clock :path path :world w :interval interval)))
    (when old (setf *clocks* (remove old *clocks*)))
    (setf *clocks* (append *clocks* (list c)))
    (when *started*
      (setf (clock-thread c)
            (sb-thread:make-thread (lambda () (run-clock c)) :name path)))
    c))

(defun unregister (path)
  (let ((c (find-clock path)))
    (when c
      (setf (clock-status c) :stopped)
      (setf *clocks* (remove c *clocks*))
      (when (clock-thread c) (sb-thread:join-thread (clock-thread c) :default nil)))))

(defun pause (path) "鐘停著不走，但登記還在。" (setf (clock-status (find-clock path)) :paused))
(defun resume (path) "暫停的鐘再走。（CL 已有 continue，所以叫 resume）"
  (setf (clock-status (find-clock path)) :running))
(defun stop-all ()
  (dolist (c *clocks*) (setf (clock-status c) :stopped))   ; 先全部叫停，再一個一個等，等待才不會累加
  (dolist (c (copy-list *clocks*)) (unregister (clock-path c))))

(defun ls ()
  "列所有鐘：(path 狀態 走了幾格)。"
  (loop for c in *clocks* collect (list (clock-path c) (clock-status c) (clock-ticks c))))

(defun step-all ()
  "同步：每個在走的鐘各走一格（不睡；interval N 的鐘每 N 格才動）。回傳 ((path . :busy/…) …)。"
  (incf *steps*)
  (loop for c in (copy-list *clocks*)
        when (and (eq (clock-status c) :running) (zerop (mod *steps* (clock-interval c))))
          collect (progn (incf (clock-ticks c))
                         (cons (clock-path c) (dotick (clock-world c))))))

(defun run (&optional steps (interval 0))
  "同步走 steps 格，每格睡 interval 秒（steps 給 nil 就一直走）。"
  (loop for n from 0
        while (or (null steps) (< n steps))
        do (step-all)
           (when (> interval 0) (sleep interval))))

(defun start ()
  "非同步：每個鐘一條 thread，各照自己的 interval 走。"
  (setf *started* t)
  (dolist (c0 *clocks*)
    (unless (clock-thread c0)
      (let ((c c0))                    ; 每條 thread 要抓自己那一份，不能共用 loop 變數
        (setf (clock-thread c)
              (sb-thread:make-thread (lambda () (run-clock c)) :name (clock-path c)))))))
