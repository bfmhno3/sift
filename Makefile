ifndef FONTCONFIG_FILE
$(error run inside nix develop)
endif

# The Qt tests and labs draw offscreen. The host may export another
# platform (wayland, xcb): force this one so no window ever opens.
export QT_QPA_PLATFORM := offscreen

CHAPTERS := $(notdir $(wildcard lab/ch*))

.PHONY: corpus chapters lint typecheck ext ext-rs test cov ci clean \
	$(CHAPTERS)

corpus:
	@test -f corpus/COMMIT || ./scripts/fetch-corpus.sh

$(CHAPTERS): %: corpus
	python3 scripts/chapter.py $*

# The ch24 labs load what make ext builds; the ch25 labs also load what
# make ext-rs builds.
ch24: ext
ch25: ext ext-rs

chapters: $(CHAPTERS)

lint:
	ruff format --check --line-length 79 .
	ruff check .
	cd rust/sift-rs && cargo fmt --check
	cd rust/sift-rs && cargo clippy --all-targets -- -D warnings

typecheck:
	mypy && pyright

# The C library, the C API module and the Cython module (see c/Makefile).
ext:
	$(MAKE) -C c

# The Rust tokenizer: maturin builds rust/sift-rs in release mode and
# puts sift/_rs*.so into src/ through the virtual environment.
ext-rs:
	cd rust/sift-rs && maturin develop --release

test:
	python3 -m pytest
	cd rust/sift-rs && cargo test

cov:
	python3 -m pytest --cov=sift --cov-report=term-missing

ci: lint typecheck ext ext-rs test chapters

clean:
	$(MAKE) -C c clean
	rm -rf src/sift/_rs*.so rust/sift-rs/target
	rm -rf out .sift
