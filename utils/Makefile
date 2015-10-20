
CXX ?= g++

CXXFLAGS += -Wall -Wextra -std=gnu++0x -fPIC -O0 -g -DDEBUG
LDFLAGS += -Wl,--no-undefined

all: build

build: libmod_utils.so

clean:
	rm -f *.so *.o

libmod_utils.so: utils_jack.cpp.o utils_lilv.cpp.o
	$(CXX) $^ $(LDFLAGS) -shared $(shell pkg-config --libs jack lilv-0) -o $@

utils_jack.cpp.o: utils_jack.cpp utils.h
	$(CXX) $< $(CXXFLAGS) $(shell pkg-config --cflags jack) -c -o $@

utils_lilv.cpp.o: utils_lilv.cpp utils.h
	$(CXX) $< $(CXXFLAGS) $(shell pkg-config --cflags lilv-0) -c -o $@
