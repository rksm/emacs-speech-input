.PHONY: test clean

EMACS ?= emacs
EMACS_MODULE_INCLUDE ?= $(shell $(EMACS) --batch -Q --eval "(princ (expand-file-name \"../include\" invocation-directory))")
CFLAGS += -I$(EMACS_MODULE_INCLUDE)

all: esi-core.so

test: tests/test-prep
	$(EMACS) --batch -Q -L . -L tests --eval "(require 'buttercup)" -f buttercup-run-discover tests
	tests/test-prep
	touch tests/test-prep.c

LIBS = -lsndfile -lfftw3 -lm -lcblas -lsoundio

TORCH_DIR = ./resources/libtorch
TORCH_FLAGS = -I $(TORCH_DIR)/include -L $(TORCH_DIR)/lib -L ./lib \
	'-Wl,-rpath,$$ORIGIN/$(TORCH_DIR)/lib' '-Wl,-rpath,$$ORIGIN/lib' \
	-ltorch -lc10 -lpthread

clean:
	rm -f esi-core.so esi-embed-core.so src/embed/esi-embed.o

tests/test-prep: tests/test-prep.c esi-core.so
	gcc $(CFLAGS) -lcmocka $(LIBS) -I ./src/ tests/test-prep.c -o $@

esi-core.so: $(wildcard src/*.c) $(wildcard src/*.h)
	gcc $(CFLAGS) $(LIBS) -fPIC -pthread -shared $(wildcard src/*.c) -o $@
