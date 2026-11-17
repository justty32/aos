# Builds every aos C/C++ project (11 libraries, 9 executables) with plain make; replaces the old CMake files.
#
# Usage (normally called by ../install.py):
#   make -j8                         objects and libraries under build/, executables under build/bin
#   make -j8 BINDIR=/x/bin LIBDIR=/x/lib
#   make STATIC= CXXFLAGS="-O1 -g -fsanitize=address"   (sanitizer builds cannot be fully static)
#   make aos-exec                    one executable (and what it needs)
#   make clean                       remove build/ (BINDIR/LIBDIR outside build/ are left alone)
#
# Each project aos-X: every src/**/*.cpp except src/main.cpp -> libaos-X.a; src/main.cpp + libs -> aos-X.
# aos-inst is C: libaos-inst.a and libaos-inst.so (default hidden visibility, only AOS_API symbols exported).
# nlohmann json is the single header third_party/nlohmann/json.hpp (no vcpkg, no find_package).
# Changing CXXFLAGS does not rebuild by itself: run make clean first.

BUILD  ?= build
BINDIR ?= $(BUILD)/bin
LIBDIR ?= $(BUILD)/lib
OBJ    := $(BUILD)/obj

ifeq ($(origin CC),default)
CC := gcc
endif
ifeq ($(origin CXX),default)
CXX := g++
endif
OPT      ?= -O3 -DNDEBUG
CXXFLAGS ?= $(OPT)
CFLAGS   ?= $(OPT)
ifneq ($(findstring -fsanitize,$(CXXFLAGS)),)
STATIC ?=
else
STATIC ?= -static-pie
endif

XFLAGS := -std=c++20 -fPIC -Wall -Wextra -MMD -MP -isystem third_party
IFLAGS := -std=c11 -fPIC -fvisibility=hidden -Wall -Wextra -Werror -MMD -MP

# link order: a library comes before the libraries it uses
DEPS_util      :=
DEPS_directive := util
DEPS_exec      := directive util inst
DEPS_json      := directive util
DEPS_lock      := util
DEPS_post      := lock util
DEPS_loop      := exec directive util inst
DEPS_fsm       := loop exec directive util inst
DEPS_daemon    := loop post lock exec directive util inst
DEPS_llm       := post lock util

LIBS := util directive exec json lock post loop fsm daemon llm
BINS := directive exec json lock post loop fsm daemon llm

all: $(addprefix $(BINDIR)/aos-,$(BINS)) $(LIBDIR)/libaos-inst.so $(LIBDIR)/libaos-util.a

# ---- aos-inst (C) ----
inst_src := $(shell find aos-inst/src -name '*.c' ! -path 'aos-inst/src/main.c')
inst_obj := $(patsubst %.c,$(OBJ)/%.o,$(inst_src))
$(OBJ)/aos-inst/%.o: aos-inst/%.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(IFLAGS) -Iaos-inst/include -c $< -o $@
$(LIBDIR)/libaos-inst.a: $(inst_obj)
	@mkdir -p $(@D); rm -f $@
	ar rcs $@ $^
$(LIBDIR)/libaos-inst.so: $(inst_obj)
	@mkdir -p $(@D)
	$(CC) -shared -o $@ $^
ALL_OBJ := $(inst_obj)

# ---- C++ projects ----
define cxx_project
$(1)_src := $$(shell find aos-$(1)/src -name '*.cpp' ! -path 'aos-$(1)/src/main.cpp')
$(1)_obj := $$(patsubst %.cpp,$$(OBJ)/%.o,$$($(1)_src))
$(1)_inc := -Iaos-$(1)/src $$(foreach d,$(1) $$(DEPS_$(1)),$$(if $$(wildcard aos-$$(d)/include),-Iaos-$$(d)/include))
$$(OBJ)/aos-$(1)/%.o: aos-$(1)/%.cpp
	@mkdir -p $$(@D)
	$$(CXX) $$(CXXFLAGS) $$(XFLAGS) $$($(1)_inc) -c $$< -o $$@
$$(LIBDIR)/libaos-$(1).a: $$($(1)_obj)
	@mkdir -p $$(@D); rm -f $$@
	ar rcs $$@ $$^
ALL_OBJ += $$($(1)_obj)
endef
$(foreach p,$(LIBS),$(eval $(call cxx_project,$(p))))

define cxx_bin
$$(BINDIR)/aos-$(1): $$(OBJ)/aos-$(1)/src/main.o $$(foreach d,$(1) $$(DEPS_$(1)),$$(LIBDIR)/libaos-$$(d).a)
	@mkdir -p $$(@D)
	$$(CXX) $$(CXXFLAGS) $$(STATIC) -pthread -o $$@ $$^
aos-$(1): $$(BINDIR)/aos-$(1)
.PHONY: aos-$(1)
ALL_OBJ += $$(OBJ)/aos-$(1)/src/main.o
endef
$(foreach p,$(BINS),$(eval $(call cxx_bin,$(p))))

clean:
	rm -rf $(BUILD)

.PHONY: all clean
-include $(ALL_OBJ:.o=.d)
