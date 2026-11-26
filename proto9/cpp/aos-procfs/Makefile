# Builds aos-procfs: libaos-procfs.a (src/*.cpp), the demo aos-procfs-demo (demo/*.cpp) and the field table test (tests/fields_test.cpp) under build/.
#
# Usage:
#   make            build/libaos-procfs.a, build/bin/aos-procfs-demo and build/bin/fields-test
#   make test       build, then run build/bin/fields-test, tests/run.py, tests/ctl_wait.py and tests/mail.py
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
FT_OBJ   := $(BUILD)/obj/tests/fields_test.o
FT       := $(BUILD)/bin/fields-test

all: $(LIB) $(DEMO) $(FT)

$(BUILD)/obj/%.o: %.cpp
	@mkdir -p $(@D)
	$(CXX) $(XFLAGS) $(OPT) -c $< -o $@

$(LIB): $(LIB_OBJ)
	@mkdir -p $(@D)
	ar rcs $@ $^

$(DEMO): $(DEMO_OBJ) $(LIB)
	@mkdir -p $(@D)
	$(CXX) -pthread $(DEMO_OBJ) $(LIB) -o $@

$(FT): $(FT_OBJ) $(LIB)
	@mkdir -p $(@D)
	$(CXX) -pthread $(FT_OBJ) $(LIB) -o $@

test: all
	$(FT)
	python3 tests/run.py
	python3 tests/ctl_wait.py
	python3 tests/mail.py

clean:
	rm -rf $(BUILD)

.PHONY: all test clean

-include $(LIB_OBJ:.o=.d) $(DEMO_OBJ:.o=.d) $(FT_OBJ:.o=.d)
