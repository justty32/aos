# Builds aos-daemon (src/*.cpp) under build/, linked against ../aos-procfs/build/libaos-procfs.a (build that first).
#
# Usage:
#   make            build/bin/aos-daemon
#   make test       build, then run tests/run.py
#   make clean      remove build/

BUILD    := build
CXX      ?= g++
OPT      ?= -O2
PROCFS   := ../aos-procfs
XFLAGS   := -std=c++20 -Wall -Wextra -MMD -MP -I$(PROCFS)/include -pthread

SRC      := $(wildcard src/*.cpp)
OBJ      := $(patsubst %.cpp,$(BUILD)/obj/%.o,$(SRC))
LIB      := $(PROCFS)/build/libaos-procfs.a
BIN      := $(BUILD)/bin/aos-daemon

all: $(BIN)

$(BUILD)/obj/%.o: %.cpp
	@mkdir -p $(@D)
	$(CXX) $(XFLAGS) $(OPT) -c $< -o $@

# 只編這一夾；庫沒編好就說一聲，不替它編
$(LIB):
	@echo "missing $(LIB): run make -C $(PROCFS) first" >&2; exit 1

$(BIN): $(OBJ) $(LIB)
	@mkdir -p $(@D)
	$(CXX) -pthread $(OBJ) $(LIB) -o $@

test: all
	python3 tests/run.py

clean:
	rm -rf $(BUILD)

.PHONY: all test clean

-include $(OBJ:.o=.d)
