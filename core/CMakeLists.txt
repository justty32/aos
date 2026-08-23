# 核心小專案：aos 的基本組成部分。很通用，執行檔的子命令與函式庫一定成對出現，
# 而且一定會被建置（沒有關掉它們的選項）。
#
# 判準：如果拿掉它 aos 就不再是 aos，放這裡；否則放 ../modules/。

set(AOS_SUBPROJECT_CATEGORY core)

add_subdirectory(inst)
