# 審查腳本共用的環境。原版把 AOS／LAB 寫死成審查隊當時的 worktree 路徑，
# 別人重跑得先改檔；現在兩個都可以用環境變數覆寫，預設指向主 repo 的 build。
#
#   AOS  受測的 aos 執行檔（預設：主 repo 的 build/bin/aos）
#   LAB  實驗場地（預設：/tmp/aos-review-lab-$USER；會被各腳本自行清空重建）
#
# 用法：AOS=/path/to/aos LAB=/path/to/lab bash t3.sh
AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}"
LAB="${LAB:-/tmp/aos-review-lab-${USER:-u}}"
export AOS LAB
mkdir -p "$LAB" 2>/dev/null
mkworld() { rm -rf "$1"; mkdir -p "$1"; "$AOS" init "$1" >/dev/null 2>&1 || echo INIT_FAIL; }
