ifndef FONTCONFIG_FILE
$(error run inside nix develop)
endif

# The Qt tests and labs draw offscreen. The host may export another
# platform (wayland, xcb): force this one so no window ever opens.
export QT_QPA_PLATFORM := offscreen

CHAPTERS := $(notdir $(wildcard lab/ch*))

.PHONY: corpus chapters lint typecheck test cov ci clean $(CHAPTERS)

# Later chapters add ext targets and list them in ci.

corpus:
	@test -f corpus/COMMIT || ./scripts/fetch-corpus.sh

$(CHAPTERS): %: corpus
	python3 scripts/chapter.py $*

chapters: $(CHAPTERS)

lint:
	ruff format --check --line-length 79 .
	ruff check .

typecheck:
	mypy && pyright

test:
	python3 -m pytest

cov:
	python3 -m pytest --cov=sift --cov-report=term-missing

ci: lint typecheck test chapters

clean:
	rm -rf out .sift
