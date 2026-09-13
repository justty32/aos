(do (spit (string here "/log.txt") "one\n" :a) :one)
(do (spit (string here "/log.txt") "two\n" :a) :two)
(do (spit (string here "/log.txt") "three\n" :a)
    # inst.stdout 每格會先截斷；最後一格補兩行，讓 fixture 的 out.txt 可驗三行。
    (print ":one")
    (print ":two")
    :three)
