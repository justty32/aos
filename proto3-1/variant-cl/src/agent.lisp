;;; agent＝一個世界 + 一個小狀態機，而狀態機就是 form 改寫：
;;;   (agent-idle) → (agent-think) → (agent-wait …) → (agent-act) → (agent-idle)
;;; 沒有 :state 欄位，「現在什麼狀態」就看 form 的第一個符號（state-of）。
;;; 等東西的那一格特別有意思：等什麼／等到了叫誰／幾格放棄，全都當參數帶在 form 裡，
;;; 所以 (agent-wait '(:llm-result 3) 'agent-got-llm 30 2) 印出來就是它在等什麼。
;;; 誰來叫醒它？永遠是時鐘，不用到處放計時器。
(in-package :aos)

(defun kind-of (m) "信可能只是一句字串" (let ((b (getf m :body))) (when (consp b) (getf b :kind))))
(defun llm-result-p (id) (lambda (m) (and (eq (kind-of m) :llm-result) (eql (getf (getf m :body) :id) id))))

(defun wait-check (until)
  "until 是一段『等什麼』的描述（純資料，不是 closure，才放得進 form）。"
  (case (first until)
    (:llm-result (first (mail (llm-result-p (second until)))))
    (:mail (first (mail (lambda (m) (not (eq (kind-of m) :llm-result))))))
    (t nil)))

(defun wait-for (until then &optional timeout)
  "登記等待，效果＝(next '(agent-wait until then timeout 現在的格))。
   until：等什麼的描述；then：等到時要叫的函式名（會用 (funcall then 東西) 叫）；
   timeout：幾格還沒等到就放棄（回 idle）。"
  (next (list 'agent-wait (list 'quote until) (list 'quote then) timeout (now)))
  :busy)

(defun agent-wait (until then timeout since)
  (let ((got (wait-check until)))
    (cond
      (got (funcall then got) :busy)                       ; then 自己決定 next 成 act 還是 idle
      ((and timeout (>= (- (now) since) timeout))
       (next '(agent-idle)) :busy)
      (t :wait))))

(defun agent-idle ()
  "有非 llm-result 的信 → 記進 history、記 asker、換成 (agent-think)；沒信就 idle。"
  (let ((mails (mail (lambda (m) (not (eq (kind-of m) :llm-result))))))
    (if (null mails)
        :idle
        (progn
          (dolist (m mails)
            (setvar 'history (append (var 'history)
                                     (list (list :role :user :content (format nil "~a" (getf m :body))))))
            (setvar 'asker (getf m :from)))
          (next '(agent-think))
          :busy))))

(defun agent-got-llm (m)
  "等到 LLM 回信了：出錯就先簡單回 idle 並記 :last-error，否則收下回覆、換成 (agent-act)。"
  (let ((body (getf m :body)))
    (if (getf body :error)
        (progn (setvar 'last-error (getf body :error)) (next '(agent-idle)))
        (progn (setvar 'reply (getf body :reply)) (next '(agent-act))))))

(defun agent-think ()
  "把 history 丟給 LLM 世界，然後等結果。"
  (let ((req (ask (var 'llm) *me* (var 'history))))
    (wait-for (list :llm-result (getf req :id)) 'agent-got-llm (var 'llm-timeout))))

(defun agent-act ()
  "回覆進 history、say 出來、回信給 asker，然後回 (agent-idle)。"
  (let ((text (getf (var 'reply) :text)))
    (setvar 'history (append (var 'history) (list (list :role :assistant :content text))))
    (say text)
    (when (var 'asker) (send (var 'asker) text))
    (next '(agent-idle))
    :busy))

(defun make-agent (name llmw &rest kvs &key system (llm-timeout 30) &allow-other-keys)
  "建一個 agent，初始 form 是 (agent-idle)。llmw 是它要問的 LLM 世界。
   可選 :system 人格、:llm-timeout 等幾格放棄（預設 30）。"
  (let ((a (apply #'make-world name '(agent-idle)
                  'llm llmw 'history '() 'asker nil 'llm-timeout llm-timeout kvs)))
    (when system (w-put a 'history (list (list :role :system :content system))))
    a))
