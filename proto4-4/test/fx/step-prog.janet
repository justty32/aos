(def x 10)
(defn f [a] (* a x))
(spit (string here "/side.txt") (string (f 2)))
(aos/call-dir (string here "/child"))
