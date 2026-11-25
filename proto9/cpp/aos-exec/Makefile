# Builds proto9 aos-exec: libaos-exec.a (src/**/*.cpp except main.cpp), the command build/bin/aos-exec, and the test helper build/bin/resolve-check.
#
# Usage:
#   make            build/libaos-exec.a and build/bin/aos-exec
#   make test       build, then run tests/run.py (all tests)
#   make clean      remove build/
#
# Self-contained: nothing under proto8/ is included or linked; nlohmann json comes from ../third_party.

BUILD    := build
CXX      ?= g++
OPT      ?= -O2
XFLAGS   := -std=c++20 -Wall -Wextra -MMD -MP -Iinclude -Isrc -I../third_party

LIB_SRC  := $(filter-out src/main.cpp,$(wildcard src/*.cpp src/*/*.cpp))
LIB_OBJ  := $(patsubst %.cpp,$(BUILD)/obj/%.o,$(LIB_SRC))
MAIN_OBJ := $(BUILD)/obj/src/main.o
CHK_OBJ  := $(BUILD)/obj/tests/resolve_check.o
LIB      := $(BUILD)/libaos-exec.a
BIN      := $(BUILD)/bin/aos-exec
CHK      := $(BUILD)/bin/resolve-check

all: $(LIB) $(BIN)

$(BUILD)/obj/%.o: %.cpp
	@mkdir -p $(@D)
	$(CXX) $(XFLAGS) $(OPT) -c $< -o $@

$(LIB): $(LIB_OBJ)
	@mkdir -p $(@D)
	ar rcs $@ $^

$(BIN): $(MAIN_OBJ) $(LIB)
	@mkdir -p $(@D)
	$(CXX) $(MAIN_OBJ) $(LIB) -o $@

$(CHK): $(CHK_OBJ) $(LIB)
	@mkdir -p $(@D)
	$(CXX) $(CHK_OBJ) $(LIB) -o $@

test: all $(CHK)
	python3 tests/run.py

clean:
	rm -rf $(BUILD)

.PHONY: all test clean

-include $(LIB_OBJ:.o=.d) $(MAIN_OBJ:.o=.d) $(CHK_OBJ:.o=.d)
