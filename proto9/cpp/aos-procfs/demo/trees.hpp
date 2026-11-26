// trees.hpp：aos-procfs-demo 測試用的 trees/——ctl 的 tree NAME（加一整棵 trees/NAME/）與 rmtree PATH（拿掉任何路徑連同底下）。
#pragma once

#include "aos/procfs.hpp"

// 擺出 trees/、在 ctl 註冊 tree 與 rmtree（要在 mount 之前叫；之後隨時加、拿）
void demo_trees_setup(aos::procfs::Fs& fs, aos::procfs::Ctl& ctl);
