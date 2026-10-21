#!/usr/bin/env bash
# Fetch the blog posts at a pinned commit into corpus/posts.
set -euo pipefail

COMMIT=2c3f11a4fefafdfd6baa58bd3e09db679227cbcc
REPO=https://github.com/bfmhno3/bfmhno3.github.io
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"
git init -q
if git fetch -q --depth 1 "$REPO" "$COMMIT" 2>/dev/null; then
	REF=FETCH_HEAD
else
	git clone -q --filter=blob:none --no-checkout "$REPO" clone
	git -C clone checkout -q "$COMMIT"
	cd clone
	REF=HEAD
fi

rm -rf "$ROOT/corpus"
mkdir -p "$ROOT/corpus/posts"
git archive "$REF" src/content/posts |
	tar -x --strip-components=3 -C "$ROOT/corpus/posts"
echo "$COMMIT" >"$ROOT/corpus/COMMIT"

count=$(find "$ROOT/corpus/posts" -name '*.md' | wc -l)
if [ "$count" -ne 123 ]; then
	echo "fetch-corpus: expected 123 posts, got $count" >&2
	exit 1
fi
echo "corpus: $count posts at $COMMIT"
