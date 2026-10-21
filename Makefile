ifndef FONTCONFIG_FILE
$(error run inside nix develop)
endif

CHAPTERS := $(notdir $(wildcard lab/ch*))

.PHONY: corpus chapters lint ci clean $(CHAPTERS)

# Later chapters add test, typecheck and ext targets and list them in ci.

corpus:
	@test -f corpus/COMMIT || ./scripts/fetch-corpus.sh

$(CHAPTERS): %: corpus
	python3 scripts/chapter.py $*

chapters: $(CHAPTERS)

lint:
	ruff format --check --line-length 79 .
	ruff check .

ci: lint chapters

clean:
	rm -rf out .sift
