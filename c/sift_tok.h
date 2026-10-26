/* SPDX-License-Identifier: MIT OR Apache-2.0 */
/*
 * sift_tok.h: the tokenizer of Sift in C.
 *
 * The rules are the ones of MixedTokenizer without its NFKC and
 * casefold step, which the caller applies first: a Latin token is a run
 * of [0-9a-z_] with an optional "+", "++" or "#" after it; a run of
 * CJK characters gives overlapping bigrams, or one unigram when the run
 * has a single character.
 */
#ifndef SIFT_TOK_H
#define SIFT_TOK_H

#include <stddef.h>

/* The half-open byte range [start, end) of one token in the input. */
struct sift_span {
	size_t start;
	size_t end;
};

/*
 * sift_tokenize - split UTF-8 text into token spans
 * @utf8:  the text; need not be NUL-terminated or valid UTF-8
 * @len:   the number of bytes at @utf8
 * @out:   room for @cap spans; may be NULL when @cap is 0
 * @cap:   the number of spans that fit in @out
 * @n_out: set to the number of spans the text has
 *
 * At most @cap spans are written, in input order. *@n_out is always
 * the full count, so a caller that gets -ENOSPC allocates *@n_out
 * spans and calls again. Bytes that are not valid UTF-8 are skipped
 * and never end up inside a token.
 *
 * Return 0 on success, -ENOSPC if @cap was too small, -EINVAL for a
 * NULL @n_out, a NULL @utf8 with @len > 0, or a NULL @out with @cap > 0.
 */
int sift_tokenize(const char *utf8, size_t len, struct sift_span *out,
		  size_t cap, size_t *n_out);

/*
 * sift_count_cjk - count the CJK characters of UTF-8 text
 *
 * The same character classes as sift_tokenize. Invalid bytes are
 * skipped. A NULL @utf8 counts as empty.
 */
size_t sift_count_cjk(const char *utf8, size_t len);

#endif /* SIFT_TOK_H */
