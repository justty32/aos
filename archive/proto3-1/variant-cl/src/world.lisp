;;; 世界＝一個 list（form）＋一個資料夾（hash table）。跑一格＝在那個資料夾裡 eval 那個 list。
;;; 下一格要跑什麼？form 自己用 (next 新form) 寫回去——狀態機就是 form 改寫。
;;;
;;; CL 沒有一等環境可以餵給 eval，所以「在資料夾裡 eval」＝把資料夾綁到動態變數 *me*，
;;; form 裡用 (var 'x)／(setvar 'x v) 讀寫自己的狀態，其他原語（now／say／send／mail／kid／kill）
;;; 也都是普通函式、內部看 *me*。老實記下這個差別，不硬模擬 Janet 的 make-env。
(in-package :aos)

(defvar *all* (make-hash-table :test 'equal)
  "檔案系統：path → 世界。path 就是身分（父 path + \"/\" + 名字）。")
(defvar *me* nil "目前正在求值的那個世界。form 裡的原語全看它。")
(defvar *next-form* '%none "這格有沒有叫過 (next f)。'%none＝沒叫過。")

(defun w-get (w key &optional default) (gethash key w default))
(defun w-put (w key val) (setf (gethash key w) val))

(defmacro with-world (w &body body)
  "在 form 之外（測試、main、kernel）也想用那些原語時，先把世界綁上去。"
  `(let ((*me* ,w)) ,@body))

(defun make-world (name form &rest kvs)
  "建一個世界：name 是名字，form 是它每格要 eval 的 list，其餘 kvs 是 key value 直接塞進去。"
  (let ((w (make-hash-table :test 'eq)))
    (w-put w :name name)
    (w-put w :path name)
    (w-put w :form form)                                      ; 現在的 list
    (w-put w :kids (make-hash-table :test 'equal))
    (w-put w :inbox '())
    (w-put w :outbox '())
    (w-put w :ticks (list :busy 0 :wait 0 :idle 0 :frozen 0)) ; 格的會計：這格在幹嘛
    (w-put w :now 0)                                          ; 自己走了幾格
    (loop for (k v) on kvs by #'cddr do (w-put w k v))
    (setf (gethash name *all*) w)
    w))

(defun world-at (path) "用 path 找世界，找不到回 nil。" (gethash path *all*))

(defun state-of (w)
  "世界現在的『狀態』＝ form 的第一個符號（agent 的 idle／think／wait／act 就是這樣看的）。"
  (let ((f (w-get w :form))) (if (consp f) (first f) f)))

(defun count-tick (w kind) (incf (getf (gethash :ticks w) kind 0)))

(defun dotick (w)
  "對一個世界求值一格：eval 它的 form。回傳這格做了什麼：:busy／:wait／:idle／:frozen。
   form 回 :busy／:wait／:idle 就照記，其他一律算 busy；求值期間叫過 (next f) 就換 form。"
  (if (w-get w :frozen)
      (progn (count-tick w :frozen) :frozen)
      (let ((result :idle)
            ;; 先把小孩拍快照：這格才生出來的小孩，下一格開始才跟著走
            (kids (loop for k being the hash-values of (w-get w :kids) collect k)))
        (incf (gethash :now w))
        (when (w-get w :form)
          (let ((*me* w) (*next-form* '%none))
            (let ((r (eval (w-get w :form))))
              (setf result (if (member r '(:busy :wait :idle)) r :busy)))
            (unless (eq *next-form* '%none) (w-put w :form *next-form*))))
        (dolist (k kids) (when (eq (w-get k :clock) :shared) (dotick k)))
        (count-tick w result)
        result)))

;;; ── form 裡可以用的原語（全部看 *me*）─────────────────────
(defun me () "自己的環境（那個 hash table）。" *me*)
(defun now () "自己走了幾格。" (w-get *me* :now))

(defun var (name &optional default)
  "讀自己的狀態。這是 CL 版取代『form 裡 (def x …)』的做法。"
  (w-get *me* name default))
(defun setvar (name val) "寫自己的狀態，下一格還在。" (w-put *me* name val))

(defun next (form) "下一格改跑這個 form。沒叫就維持原樣（每格重跑同一句）。"
  (setf *next-form* form))

(defun say (body)
  "自己說一句話，記進 outbox。"
  (w-put *me* :outbox (append (w-get *me* :outbox) (list (list :at (now) :body body)))))

(defun send (to-path body)
  "寄一封信到 to-path 的 inbox。信＝(:from 寄件人 path :body 內容 :at 收件人當時的格)。"
  (let ((to (world-at to-path)))
    (when to
      (let ((m (list :from (w-get *me* :path) :body body :at (w-get to :now))))
        (w-put to :inbox (append (w-get to :inbox) (list m)))
        m))))

(defun mail (&optional pred)
  "把自己 inbox 的信拿走（拿走就算讀過）。給 pred 就只拿符合的那些。"
  (let ((inbox (w-get *me* :inbox)))
    (if (null pred)
        (progn (w-put *me* :inbox '()) inbox)
        (let ((got (remove-if-not pred inbox)))
          (w-put *me* :inbox (remove-if pred inbox))
          got))))

;;; ── 小孩：巢狀 list ────────────────────────────────────────
(defun kid (name &rest args)
  "子世界＝巢狀的 list。(kid \"n\" form) 第一次求值時建立（path＝父/名字、借父的鐘），
   之後每次父求值它就跟著求值一格；(kid \"n\" :own form) 只建立、不跟著走（要另外向 kernel 登記）。
   已經有了就直接回傳那個小孩（所以放在 form 裡每格叫也沒關係）。"
  (let* ((parent *me*)
         (own (eq (first args) :own))
         (form (if own (second args) (first args))))
    (or (gethash name (w-get parent :kids))
        (let ((k (make-world name form)))
          (when (eq (gethash name *all*) k) (remhash name *all*))  ; 別佔著頂層的名字
          (w-put k :path (format nil "~a/~a" (w-get parent :path) name))
          (w-put k :parent (w-get parent :path))
          (w-put k :clock (if own :own :shared))
          (setf (gethash name (w-get parent :kids)) k)
          (setf (gethash (w-get k :path) *all*) k)
          k))))

(defun prefix-p (prefix s)
  (and (>= (length s) (length prefix)) (string= prefix s :end2 (length prefix))))

(defun kill (path)
  "把那個世界從父的 :kids 與檔案系統拿掉（它的小孩也一起消失）。"
  (let ((w (world-at path)))
    (when w
      (let ((parent (world-at (w-get w :parent))))
        (when parent (remhash (w-get w :name) (w-get parent :kids))))
      (let ((gone '()))
        (loop for p being the hash-keys of *all*
              when (prefix-p (format nil "~a/" path) p) do (push p gone))
        (dolist (p gone) (remhash p *all*)))
      (remhash path *all*))))
