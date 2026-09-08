(import ./clock :as clock)

(def new
  "make new kernel"
  @{})

(def register
  "register a proc to kernel"
  [kernel proc &opt name interval]
  (put proc))
 

 

 
