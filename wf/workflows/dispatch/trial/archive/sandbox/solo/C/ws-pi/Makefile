all: mini test

mini: src/main.cpp src/parse.cpp
	g++ -std=c++17 -o mini src/main.cpp src/parse.cpp

test: tests/test_parse.cpp src/parse.cpp
	g++ -std=c++17 -o test_parse tests/test_parse.cpp src/parse.cpp && ./test_parse

clean:
	rm -f mini test_parse
