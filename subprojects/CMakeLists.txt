# 所有小專案都住在這個目錄底下。每個小專案的結構與職責見
# ../docs/subprojects.md，樣板函式在 ../cmake/AosSubproject.cmake。
#
# 新增一個小專案：在這裡加一行 add_subdirectory()。根 CMakeLists.txt 不用動，
# app/ 也不用動（子命令表是從各小專案的登記結果產生的）。

add_subdirectory(inst)
