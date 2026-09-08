;;; 世界＝一個 hash table（key 是 keyword）。「跑世界」＝對它求值：走一遍元素，
;;; :func-tick 就叫它、:kids 裡借父時鐘的小孩跟著走一格。
;;; 這就是「list 當資料夾、執行資料夾＝對 list 求值」。
(in-package :aos)

(defvar *all* (make-hash-table :test 'equal)
  "檔案系統：path → 世界。path 就是身分（父 path + \"/\" + 名字）。")

(defun w-get (w key &optional default) (gethash key w default))
(defun w-put (w key val) (setf (gethash key w) val))
(defmacro w-update (w key fn) `(setf (gethash ,key ,w) (funcall ,fn (gethash ,key ,w))))

(defun make-world (name &rest kvs)
  "建一個世界。name 是名字，其餘 kvs 是 :key value 直接塞進去（例如 :func-tick）。"
  (let ((w (make-hash-table :test 'eq)))
    (w-put w :name name)
    (w-put w :path name)
    (w-put w :kids (make-hash-table :test 'equal))
    (w-put w :inbox '())
    (w-put w :outbox '())
    (w-put w :ticks (list :busy 0 :wait 0 :idle 0 :frozen 0)) ; 格的會計：這格在幹嘛
    (w-put w :now 0)                                          ; 自己走了幾格
    (loop for (k v) on kvs by #'cddr do (w-put w k v))
    (setf (gethash (w-get w :path) *all*) w)
    w))

(defun world-at (path) "用 path 找世界，找不到回 nil。" (gethash path *all*))

(defun count-tick (w kind)
  (incf (getf (gethash :ticks w) kind 0)))

(defun dotick (w)
  "對一個世界求值一格。回傳這格做了什麼：:busy／:wait／:idle／:frozen。"
  (if (w-get w :frozen)
      (progn (count-tick w :frozen) :frozen)
      (let ((result :idle)
            (keys (loop for k being the hash-keys of w collect k))) ; 先拍快照：元素求值時可以改世界自己
        (incf (gethash :now w))
        (dolist (key keys)
          (case key
            (:func-tick
             (let ((r (funcall (w-get w :func-tick) w)))
               (setf result (if (member r '(:busy :wait :idle)) r :busy))))
            (:kids
             (loop for kid being the hash-values of (w-get w :kids)
                   when (eq (w-get kid :clock) :shared) do (dotick kid)))))
        (count-tick w result)
        result)))

;;; ── 信箱：任何世界都能收信、說話 ────────────────────────────
(defun send-mail (from to body)
  "from 寄一封信到 to 的 inbox。信＝(:from 寄件人 path :body 內容 :at 收件人當時的格)。"
  (let ((m (list :from (w-get from :path) :body body :at (w-get to :now))))
    (w-put to :inbox (append (w-get to :inbox) (list m)))
    m))

(defun take-mail (w &optional pred)
  "把 inbox 全部拿走（拿走就算讀過）。給 pred 就只拿符合的那些。"
  (let ((inbox (w-get w :inbox)))
    (if (null pred)
        (progn (w-put w :inbox '()) inbox)
        (let ((got (remove-if-not pred inbox)))
          (w-put w :inbox (remove-if pred inbox))
          got))))

(defun say (w body)
  "世界自己說一句話，記進 outbox。"
  (w-put w :outbox (append (w-get w :outbox) (list (list :at (w-get w :now) :body body)))))

;;; ── 小孩：資料夾裡的資料夾 ─────────────────────────────────
(defun spawn (parent name &rest kvs)
  "在 parent 底下生一個小孩。:clock :shared（預設，借父的鐘、父走一格它走一格）
   或 :own（自己一個鐘，要另外向 kernel 登記）。"
  (let ((kid (apply #'make-world name kvs)))
    (remhash name *all*)
    (w-put kid :path (format nil "~a/~a" (w-get parent :path) name))
    (w-put kid :parent (w-get parent :path))
    (unless (w-get kid :clock) (w-put kid :clock :shared))
    (setf (gethash name (w-get parent :kids)) kid)
    (setf (gethash (w-get kid :path) *all*) kid)
    kid))

(defun prefix-p (prefix s)
  (and (>= (length s) (length prefix)) (string= prefix s :end2 (length prefix))))

(defun kill (kid)
  "把小孩從父的 :kids 與檔案系統拿掉（它的小孩也一起消失）。"
  (let ((parent (world-at (w-get kid :parent)))
        (path (w-get kid :path)))
    (when parent (remhash (w-get kid :name) (w-get parent :kids)))
    (loop for p being the hash-keys of *all*
          when (prefix-p (format nil "~a/" path) p) collect p into gone
          finally (dolist (p gone) (remhash p *all*)))
    (remhash path *all*)))
