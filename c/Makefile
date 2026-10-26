# Native artifacts of Sift:
#   build/libsifttok.so     the C tokenizer, for ctypes and cffi
#   ../src/sift/ext/_capi*.so   the hand-written C API module
#   ../src/sift/ext/_cytok*.so  the Cython tokenizer
# Run inside nix develop (make ext at the top level calls this one).

CC ?= gcc
PYTHON ?= python3
CYTHON ?= cython
WARN := -Wall -Wextra
CFLAGS ?= -O2
EXT_DIR := ../src/sift/ext
SUFFIX := $(shell $(PYTHON) -c \
	'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
PY_INCLUDES := $(shell python3-config --includes)

CAPI := $(EXT_DIR)/_capi$(SUFFIX)
CYTOK := $(EXT_DIR)/_cytok$(SUFFIX)

.PHONY: all clean
all: build/libsifttok.so $(CAPI) $(CYTOK)

build:
	mkdir -p $@

build/libsifttok.so: sift_tok.c sift_tok.h | build
	$(CC) $(CFLAGS) -fPIC -shared $(WARN) -o $@ sift_tok.c

$(CAPI): sift_capi.c
	$(CC) $(CFLAGS) -fPIC -shared $(WARN) $(PY_INCLUDES) -o $@ sift_capi.c

$(EXT_DIR)/_cytok.c: $(EXT_DIR)/_cytok.pyx
	$(CYTHON) -3 $<

$(CYTOK): $(EXT_DIR)/_cytok.c
	$(CC) $(CFLAGS) -fPIC -shared $(WARN) $(PY_INCLUDES) -o $@ $<

clean:
	rm -rf build $(EXT_DIR)/_capi*.so $(EXT_DIR)/_cytok*.so \
		$(EXT_DIR)/_cytok.c
