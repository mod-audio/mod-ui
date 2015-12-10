
CXX ?= g++

CXXFLAGS += -Wall -Wextra -Wshadow -std=gnu++0x -fPIC -O3
LDFLAGS += -Wl,-O1 -Wl,--no-undefined -Wl,--strip-all

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

test.cpp.o: test.cpp utils.h
	$(CXX) $< $(CXXFLAGS) -c -o $@

test: utils_jack.cpp.o utils_lilv.cpp.o test.cpp.o
	$(CXX) $^ $(LDFLAGS) $(shell pkg-config --libs jack lilv-0) -o $@

test-run: test
	valgrind --leak-check=full --show-leak-kinds=all --partial-loads-ok=yes ./test
