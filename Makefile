.PHONY: compile python native demo clean

compile: python native

python:
	python -m compileall -q causalforge

native:
	g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only engine/causal_rank.cpp
