;;; proto3-1 骨幹的 Common Lisp 版（SBCL）：世界是 list，跑一格＝eval 那個 list。
;;; 只用標準庫＋ sb-thread，不裝任何套件（這台是 SBCL 2.2.9）。
(defpackage :aos
  (:use :cl))
(in-package :aos)
