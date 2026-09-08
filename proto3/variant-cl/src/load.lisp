;;; 把 src/ 底下的檔案照順序載入。main／test 用 (load "…/src/load.lisp") 即可。
(defvar *aos-src-dir*
  (directory-namestring (or *load-truename* *compile-file-truename*)))
(dolist (name '("package" "world" "kernel" "llm" "agent"))
  (load (merge-pathnames (format nil "~a.lisp" name) *aos-src-dir*)))
