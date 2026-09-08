;;; kernel：管時鐘。一個世界一個鐘；鐘＝「每 interval 秒對那個世界求值一格」。
;;; 兩種走法：step-all（同步走一格，測試與手動用）、start（每個鐘一條 thread 自己走）。
(in-package :aos)

(defstruct clock world interval (status :running) (ticks 0) thread)

(defvar *clocks* (make-hash-table :test 'equal) "path → 鐘")
(defvar *started* nil "start 過了沒；過了以後新登記的鐘要自己開 thread")
(defvar *steps* 0 "同步模式走了幾格（interval 在同步模式＝每幾格動一次）")
(defvar *tick-lock* (sb-thread:make-mutex :name "tick")
  "非同步模式下一次只讓一個鐘求值（世界之間會互相寄信、改對方）")

(defun run-clock (c)
  (loop until (eq (clock-status c) :stopped)
        do (when (eq (clock-status c) :running)
             (sb-thread:with-mutex (*tick-lock*)
               (incf (clock-ticks c))
               (dotick (clock-world c))))
           (sleep (clock-interval c))))

(defun register (w &optional (interval 1))
  "替世界登記一個鐘。interval 秒走一格（預設 1）。同一個世界重複登記＝換掉舊鐘。"
  (let ((c (make-clock :world w :interval interval)))
    (setf (gethash (w-get w :path) *clocks*) c)
    (when *started*
      (setf (clock-thread c)
            (sb-thread:make-thread (lambda () (run-clock c)) :name (w-get w :path))))
    c))

(defun unregister (path)
  (let ((c (gethash path *clocks*)))
    (when c (setf (clock-status c) :stopped))
    (remhash path *clocks*)
    (when (and c (clock-thread c)) (sb-thread:join-thread (clock-thread c) :default nil))))

(defun pause (path) "鐘停著不走，但登記還在。" (setf (clock-status (gethash path *clocks*)) :paused))
(defun resume (path) "暫停的鐘再走。（CL 已有 continue，所以叫 resume）" (setf (clock-status (gethash path *clocks*)) :running))
(defun stop-all () (dolist (p (loop for k being the hash-keys of *clocks* collect k)) (unregister p)))

(defun ls ()
  "列所有鐘：(path 狀態 走了幾格)。"
  (loop for p being the hash-keys of *clocks* using (hash-value c)
        collect (list p (clock-status c) (clock-ticks c))))

(defun step-all ()
  "同步：每個在走的鐘各走一格（不睡；interval N 的鐘每 N 格才動）。回傳 ((path . :busy/…) …)。"
  (incf *steps*)
  (loop for p being the hash-keys of *clocks* using (hash-value c)
        when (and (eq (clock-status c) :running) (zerop (mod *steps* (clock-interval c))))
          collect (progn (incf (clock-ticks c)) (cons p (dotick (clock-world c))))))

(defun run (&optional steps (interval 0))
  "同步走 steps 格，每格睡 interval 秒（steps 給 nil 就一直走）。"
  (loop for n from 0
        while (or (null steps) (< n steps))
        do (step-all)
           (when (> interval 0) (sleep interval))))

(defun start ()
  "非同步：每個鐘一條 thread，各照自己的 interval 走。"
  (setf *started* t)
  (loop for c0 being the hash-values of *clocks*
        unless (clock-thread c0)
          do (let ((c c0))            ; 每條 thread 要抓自己那一份，不能共用 loop 變數
               (setf (clock-thread c)
                     (sb-thread:make-thread (lambda () (run-clock c))
                                            :name (w-get (clock-world c) :path))))))
