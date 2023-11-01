
CC  ?= gcc
CXX ?= g++

TARGET_MACHINE := $(shell $(CC) -dumpmachine)

ifneq (,$(findstring apple,$(TARGET_MACHINE)))
MACOS = true
else ifneq (,$(findstring mingw,$(TARGET_MACHINE)))
WINDOWS = true
else ifneq (,$(findstring wasm,$(TARGET_MACHINE)))
WASM = true
endif

ifeq ($(WINDOWS),true)
LIB_EXT = .dll
else
LIB_EXT = .so
endif

CFLAGS += -Wall -Wextra -std=c99 -fPIC
CXXFLAGS += -Wall -Wextra -Wshadow -std=gnu++0x -fPIC
ifeq ($(DEBUG),1)
CFLAGS += -g -O0 -DDEBUG
CXXFLAGS += -g -O0 -DDEBUG
else
CFLAGS += -O3 -DNDEBUG
CXXFLAGS += -O3 -DNDEBUG
ifeq ($(MACOS),true)
LDFLAGS += -Wl,-dead_strip,-dead_strip_dylibs,-x
else
LDFLAGS += -Wl,-O1,--no-undefined,--strip-all
endif
endif

ifeq ($(MODAPP),1)
CXXFLAGS += -DMODAPP
ifneq ($(MACOS)$(WINDOWS),true)
LDFLAGS += -Wl,-rpath,'$$ORIGIN/..'
endif
else ifeq ($(shell pkg-config --exists alsa && echo true), true)
CXXFLAGS += -DHAVE_ALSA
ALSA_CFLAGS = $(shell pkg-config --cflags alsa)
ALSA_LIBS   = $(shell pkg-config --libs alsa)
endif

ifeq ($(shell pkg-config --atleast-version=0.22.0 lilv-0 && echo true), true)
CXXFLAGS += -DHAVE_NEW_LILV
endif

JACK_CFLAGS = $(shell pkg-config --cflags jack)
ifeq ($(MACOS),true)
JACK_LIBS   = $(shell pkg-config --libs-only-L jack) -ljack
else ifeq ($(WINDOWS),true)
JACK_LIBS   = $(shell pkg-config --libs-only-L jack) -Wl,-Bdynamic -ljack64 -Wl,-Bstatic
else
JACK_LIBS   = $(shell pkg-config --libs jack)
endif

LILV_CFLAGS = $(shell pkg-config --cflags lilv-0) -Wno-parentheses
LILV_LIBS   = $(shell pkg-config --libs lilv-0)

all: build

build: libmod_utils$(LIB_EXT)

clean:
	rm -f *.dll *.dylib *.so *.o sha1/*.o

libmod_utils$(LIB_EXT): utils_jack.cpp.o utils_lilv.cpp.o sha1/sha1.c.o
	$(CXX) $^ $(LDFLAGS) $(ALSA_LIBS) $(JACK_LIBS) $(LILV_LIBS) -shared -o $@

sha1/sha1.c.o: sha1/sha1.c
	$(CC) $< $(CFLAGS) -c -o $@

utils_jack.cpp.o: utils_jack.cpp utils.h
	$(CXX) $< $(CXXFLAGS) $(ALSA_CFLAGS) $(JACK_CFLAGS) -c -o $@

utils_lilv.cpp.o: utils_lilv.cpp sha1/sha1.h utils.h
	$(CXX) $< $(CXXFLAGS) $(LILV_CFLAGS) -c -o $@

test.cpp.o: test.cpp utils.h
	$(CXX) $< $(CXXFLAGS) -c -o $@

test: utils_jack.cpp.o utils_lilv.cpp.o test.cpp.o sha1/sha1.c.o
	$(CXX) $^ $(LDFLAGS) $(ALSA_LIBS) $(JACK_LIBS) $(LILV_LIBS) -o $@

test-run: test
	valgrind --leak-check=full --show-leak-kinds=all --partial-loads-ok=yes ./test
