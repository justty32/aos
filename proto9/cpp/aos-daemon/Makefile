# Builds aos-daemon (src/*.cpp) under build/; the aos-procfs library sources are compiled here too (into build/obj/procfs/), so ../aos-procfs is only read.
#
# Usage:
#   make            build/bin/aos-daemon
#   make test       build, then run tests/run.py
#   make clean      remove build/

BUILD    := build
CXX      ?= g++
OPT      ?= -O2
PROCFS   := ../aos-procfs
GEN      := $(BUILD)/gen
SYSTAB   := $(GEN)/syscalls_x86_64.inc
XFLAGS   := -std=c++20 -Wall -Wextra -MMD -MP -I$(PROCFS)/include -I../third_party -I$(GEN) -pthread

SRC      := $(wildcard src/*.cpp)
OBJ      := $(patsubst %.cpp,$(BUILD)/obj/%.o,$(SRC))
PF_SRC   := $(wildcard $(PROCFS)/src/*.cpp)
PF_OBJ   := $(patsubst $(PROCFS)/src/%.cpp,$(BUILD)/obj/procfs/%.o,$(PF_SRC))
BIN      := $(BUILD)/bin/aos-daemon

all: $(BIN)

$(BUILD)/obj/%.o: %.cpp
	@mkdir -p $(@D)
	$(CXX) $(XFLAGS) $(OPT) -c $< -o $@

$(BUILD)/obj/procfs/%.o: $(PROCFS)/src/%.cpp
	@mkdir -p $(@D)
	$(CXX) $(XFLAGS) $(OPT) -c $< -o $@

# x86_64 system call names for seccomp lists: generated from the asm/unistd_64.h the compiler finds (Arch: /usr/include/asm,
# Ubuntu: /usr/include/x86_64-linux-gnu/asm), so the table is as new as the headers; remade when that header changes.
$(SYSTAB):
	@mkdir -p $(@D)
	echo '#include <asm/unistd_64.h>' | $(CXX) -E -dM -MD -MP -MF $(GEN)/syscalls.d -MT $@ -x c++ - | \
	  sed -n 's/^#define __NR_\([A-Za-z0-9_]*\) \([0-9][0-9]*\)$$/{"\1", \2},/p' | sort -t, -k2 -n > $@.tmp
	@n=$$(wc -l < $@.tmp); if [ "$$n" -lt 300 ]; then \
	  echo "only $$n syscall names found in asm/unistd_64.h (install the Linux API headers: linux-api-headers, linux-libc-dev)" >&2; \
	  rm -f $@.tmp; exit 1; fi
	mv $@.tmp $@

$(BUILD)/obj/src/seccomp.o: $(SYSTAB)

$(BIN): $(OBJ) $(PF_OBJ)
	@mkdir -p $(@D)
	$(CXX) -pthread $(OBJ) $(PF_OBJ) -o $@

test: all
	python3 tests/run.py

clean:
	rm -rf $(BUILD)

.PHONY: all test clean

-include $(OBJ:.o=.d) $(PF_OBJ:.o=.d) $(GEN)/syscalls.d
