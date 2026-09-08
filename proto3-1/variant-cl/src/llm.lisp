;;; LLM 是另一個世界，它的 form 就是 (llm-step)：有自己的鐘、一條請求佇列。
;;; agent 把請求丟進來、繼續走自己的格；LLM 世界每格處理幾筆，做完把結果寄回請求者的 inbox
;;; （三態：pending → running → done/failed）。engine 是一個函式：messages → 回覆。
;;; 回覆的形狀：(:text "…") 或 (:tool "名字" :args (…))。
(in-package :aos)

(defun llm-step ()
  "LLM 世界每一格跑的那句 list。"
  (let ((llmw *me*) (n 0))
    (loop while (and (< n (w-get llmw :max-per-tick)) (w-get llmw :queue))
          do (let ((req (pop (gethash :queue llmw))))
               (setf (getf req :status) :running)
               (multiple-value-bind (reply err)
                   (handler-case (values (funcall (w-get llmw :engine) (getf req :messages)) nil)
                     (error (e) (values nil (format nil "~a" e))))
                 (setf (getf req :status) (if err :failed :done))
                 (incf (gethash (getf req :from) (w-get llmw :usage) 0))
                 (send (getf req :from)
                       (list :kind :llm-result :id (getf req :id) :reply reply :error err)))
               (incf n)))
    (if (> n 0) :busy :idle)))

(defun make-llm (name engine &optional (max-per-tick 1))
  "建一個 LLM 世界。engine：messages → 回覆。max-per-tick：一格最多處理幾筆（預設 1）。"
  (make-world name '(llm-step)
              :engine engine :queue '() :usage (make-hash-table :test 'equal)
              :max-per-tick max-per-tick :seq 0))

(defun ask (llmw from messages)
  "from 向 llmw 送一筆請求，馬上回傳請求（不等）。結果之後會以信寄到 from 的 inbox。
   請求是一個 plist，之後 :status 會被改（要看狀態就留著它）。"
  (let ((req (list :id (incf (gethash :seq llmw)) :from (w-get from :path)
                   :messages (copy-list messages) :status :pending :at (w-get llmw :now))))
    (w-put llmw :queue (append (w-get llmw :queue) (list req)))
    req))

;;; ── 幾個現成的 engine（測試與範例用）────────────────────────
(defun echo-engine (messages)
  "把最後一句 user 的話原樣回去。"
  (let ((last-user (car (last (remove-if-not (lambda (m) (eq (getf m :role) :user)) messages)))))
    (list :text (format nil "收到：~a" (if last-user (getf last-user :content) "")))))

(defun script-engine (script)
  "照劇本一筆一筆回；劇本用完就回最後一筆。劇本元素可以是回覆、或 :error（模擬模型出錯）。"
  (let ((i 0) (script (coerce script 'vector)))
    (lambda (messages)
      (declare (ignore messages))
      (let ((step (aref script (min i (1- (length script))))))
        (incf i)
        (if (eq step :error) (error "模型出錯（劇本）") step)))))
