# combine - seq／par／if 三個組合子：各編成一個資料夾，入口是一支短短的 shell 腳本
#
# 每一步可以是：字串（aos-exec 的目標，照寫）、[目標 參數…]、單子（放進 steps.json，目標寫 steps.json#/<步名>）、
# 檔案節點（(dir …) 等，長成子資料夾 <步名>/）。每一步給一個自己的小格 $AOS_STACK/<步名>（P-17）。

(import ./aos)

(def- step-fn
  "腳本裡的 step：開小格、在那格跑 aos-exec。"
  `step() { name=$1; shift; mkdir -p "$AOS_STACK/$name" && AOS_STACK="$AOS_STACK/$name" aos-exec -- "$@"; }`)

(defn- quote-word [w]
  (if (peg/match '(* (some (set "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./#:=+,@%-")) -1) w)
    w
    (string "'" (string/replace-all "'" `'\''` w) "'")))

(defn- place
  "把一步放好，回腳本裡那一行的 step 呼叫；檔案節點與單子記進 items／steps。"
  [name x items steps]
  (def words
    (cond
      (bytes? x) [x]
      (and (indexed? x) (all bytes? x) (not (empty? x))) x
      (aos/node? x) (do (array/push items name x) [name])
      (or (struct? x) (table? x)) (do (array/push steps name x) [(string "steps.json#/" name)])
      (aos/fail "StepBad" (string "這一步不是目標、單子或檔案節點：" (describe x)))))
  (string "step " name " " (string/join (map quote-word words) " ")))

(defn- build [doc names xs body-fn]
  (def items @[])
  (def steps @[])
  (def calls (map |(place $0 $1 items steps) names xs))
  (aos/dir "_entry" (aos/sh (string "# " doc) step-fn ;(body-fn calls))
           ;(if (empty? steps) [] ["steps.json" (aos/obj ;steps)])
           ;items))

(defn aos-seq
  "依序跑；哪一步非 0 就以它的碼結束。"
  [& xs]
  (build "aos-seq：依序跑，哪一步非 0 就以它的碼結束" (map |(string "s" (+ $ 1)) (range (length xs))) xs
         (fn [calls] (map |(string $ " || exit") calls))))

(defn aos-par
  "同時跑、全部等完；有任何一步非 0 就以最後一個非 0 的碼結束。"
  [& xs]
  (def names (map |(string "p" (+ $ 1)) (range (length xs))))
  (build "aos-par：同時跑、全部等完，有一步非 0 就以（最後一個）非 0 的碼結束" names xs
         (fn [calls]
           [;(map |(string $0 " & pid_" $1 "=$!") calls names)
            "rc=0"
            ;(map |(string "wait $pid_" $ " || rc=$?") names)
            "exit $rc"])))

(defn aos-if
  "先跑 cond；0 跑 then，非 0 跑 else（沒給 else＝結束碼 0）。"
  [cond-x then-x &opt else-x]
  (def names (if (nil? else-x) ["cond" "then"] ["cond" "then" "else"]))
  (def xs (if (nil? else-x) [cond-x then-x] [cond-x then-x else-x]))
  (build "aos-if：cond 結束碼 0 跑 then，否則跑 else" names xs
         (fn [[c t e]]
           [(string "if " c "; then " t (if e (string "; else " e) "") "; fi")])))
