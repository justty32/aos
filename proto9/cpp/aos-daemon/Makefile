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
XFLAGS   := -std=c++20 -Wall -Wextra -MMD -MP -I$(PROCFS)/include -I../third_party -pthread

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

$(BIN): $(OBJ) $(PF_OBJ)
	@mkdir -p $(@D)
	$(CXX) -pthread $(OBJ) $(PF_OBJ) -o $@

test: all
	python3 tests/run.py

clean:
	rm -rf $(BUILD)

.PHONY: all test clean

-include $(OBJ:.o=.d) $(PF_OBJ:.o=.d)
