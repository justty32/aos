# Builds aos-procfs: libaos-procfs.a (src/*.cpp) and the demo aos-procfs-demo (demo/*.cpp) under build/.
#
# Usage:
#   make            build/libaos-procfs.a and build/bin/aos-procfs-demo
#   make test       build, then run tests/run.py and tests/mail.py
#   make clean      remove build/

BUILD    := build
CXX      ?= g++
OPT      ?= -O2
XFLAGS   := -std=c++20 -Wall -Wextra -MMD -MP -Iinclude -pthread

LIB_SRC  := $(wildcard src/*.cpp)
LIB_OBJ  := $(patsubst %.cpp,$(BUILD)/obj/%.o,$(LIB_SRC))
DEMO_OBJ := $(patsubst %.cpp,$(BUILD)/obj/%.o,$(wildcard demo/*.cpp))
LIB      := $(BUILD)/libaos-procfs.a
DEMO     := $(BUILD)/bin/aos-procfs-demo

all: $(LIB) $(DEMO)

$(BUILD)/obj/%.o: %.cpp
	@mkdir -p $(@D)
	$(CXX) $(XFLAGS) $(OPT) -c $< -o $@

$(LIB): $(LIB_OBJ)
	@mkdir -p $(@D)
	ar rcs $@ $^

$(DEMO): $(DEMO_OBJ) $(LIB)
	@mkdir -p $(@D)
	$(CXX) -pthread $(DEMO_OBJ) $(LIB) -o $@

test: all
	python3 tests/run.py
	python3 tests/mail.py

clean:
	rm -rf $(BUILD)

.PHONY: all test clean

-include $(LIB_OBJ:.o=.d) $(DEMO_OBJ:.o=.d)
