;;; agent＝一個世界 + 一個小狀態機（先勾輪廓，之後會改）。
;;; 基礎設施只有一件：wait-for——agent 等東西時登記「等到什麼算數、等到了做什麼、等多久放棄」，
;;; 之後每一格由時鐘替它檢查。誰來叫醒它？永遠是時鐘，不用到處放計時器。
(in-package :aos)

(defun wait-for (a until then &optional timeout else)
  "登記等待：until 是 (lambda (agent) → 等到的東西或 nil)，then 是 (lambda (agent 東西))。
   timeout 格數到了就叫 else（沒給 else 就回 idle）。"
  (w-put a :waiting (list :until until :then then :timeout timeout :else else :since (w-get a :now)))
  (w-put a :state :wait))

(defun check-wait (a)
  (let* ((w (w-get a :waiting))
         (got (funcall (getf w :until) a)))
    (cond
      (got (w-put a :waiting nil) (funcall (getf w :then) a got) :busy)
      ((and (getf w :timeout) (>= (- (w-get a :now) (getf w :since)) (getf w :timeout)))
       (w-put a :waiting nil)
       (if (getf w :else) (funcall (getf w :else) a) (w-put a :state :idle))
       :busy)
      (t :wait))))

(defun kind-of (m) "信可能只是一句字串" (let ((b (getf m :body))) (when (consp b) (getf b :kind))))
(defun llm-result-p (id) (lambda (m) (and (eq (kind-of m) :llm-result) (eql (getf (getf m :body) :id) id))))

(defun think (a)
  ;; 把待回的信變成 user 訊息，丟給 LLM 世界，然後等結果
  (let ((req (ask (w-get a :llm) a (w-get a :history))))
    (wait-for a
              (lambda (a) (first (take-mail a (llm-result-p (getf req :id)))))
              (lambda (a m)
                (let ((body (getf m :body)))
                  (if (getf body :error)
                      (progn (w-put a :last-error (getf body :error)) (w-put a :state :idle)) ; 先簡單：出錯回 idle
                      (progn (w-put a :reply (getf body :reply)) (w-put a :state :act)))))
              (w-get a :llm-timeout))))

(defun act (a)
  (let ((text (getf (w-get a :reply) :text)))
    (w-put a :history (append (w-get a :history) (list (list :role :assistant :content text))))
    (say a text)
    (let ((to (world-at (w-get a :asker)))) (when to (send-mail a to text)))
    (w-put a :state :idle)))

(defun agent-tick (a)
  "四態：idle（有信就開始想）→ think（問 LLM）→ wait（等）→ act（把回覆說出去）→ idle"
  (case (w-get a :state)
    (:idle (let ((mails (take-mail a (lambda (m) (not (eq (kind-of m) :llm-result))))))
             (if (null mails)
                 :idle
                 (progn
                   (dolist (m mails)
                     (w-put a :history (append (w-get a :history)
                                               (list (list :role :user :content (format nil "~a" (getf m :body))))))
                     (w-put a :asker (getf m :from)))
                   (w-put a :state :think)
                   :busy))))
    (:think (think a) :busy)
    (:wait (check-wait a))
    (:act (act a) :busy)
    (t :busy)))

(defun make-agent (name llmw &rest kvs &key system (llm-timeout 30) &allow-other-keys)
  "建一個 agent。llmw 是它要問的 LLM 世界。可選 :system 人格、:llm-timeout 等幾格放棄（預設 30）。"
  (let ((a (apply #'make-world name :state :idle :llm llmw :history '() :waiting nil
                  :llm-timeout llm-timeout :func-tick #'agent-tick kvs)))
    (when system (w-put a :history (list (list :role :system :content system))))
    a))
