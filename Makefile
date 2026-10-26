ifndef FONTCONFIG_FILE
$(error run inside nix develop)
endif

# The Qt tests and labs draw offscreen. The host may export another
# platform (wayland, xcb): force this one so no window ever opens.
export QT_QPA_PLATFORM := offscreen

CHAPTERS := $(notdir $(wildcard lab/ch*))

.PHONY: corpus chapters lint typecheck ext test cov ci clean $(CHAPTERS)

corpus:
	@test -f corpus/COMMIT || ./scripts/fetch-corpus.sh

$(CHAPTERS): %: corpus
	python3 scripts/chapter.py $*

# The ch24 labs load what make ext builds.
ch24: ext

chapters: $(CHAPTERS)

lint:
	ruff format --check --line-length 79 .
	ruff check .

typecheck:
	mypy && pyright

# The C library, the C API module and the Cython module (see c/Makefile).
ext:
	$(MAKE) -C c

test:
	python3 -m pytest

cov:
	python3 -m pytest --cov=sift --cov-report=term-missing

ci: lint typecheck ext test chapters

clean:
	$(MAKE) -C c clean
	rm -rf out .sift
