# 擴充小專案：可選的功能。用 -DAOS_BUILD_MODULES=OFF 可以整批不建。
#
# 判準：拿掉它 aos 仍然成立，放這裡；是 aos 的基本組成部分才放 ../core/。

set(AOS_SUBPROJECT_CATEGORY module)

# 目前還沒有擴充小專案。新增時在這裡加一行 add_subdirectory(<name>)。
