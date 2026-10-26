// SPDX-License-Identifier: MIT OR Apache-2.0
/*
 * sift_tok.c: the tokenizer of Sift in C. See sift_tok.h.
 */
#include <errno.h>
#include <stdint.h>

#include "sift_tok.h"

/* Returned by utf8_decode() for bytes that do not start a character. */
#define BAD_CP		UINT32_MAX

/*
 * Every CJK character Sift knows is in the BMP, so it takes exactly
 * three bytes in UTF-8. Bigram spans rely on it.
 */
#define CJK_BYTES	3

static int is_latin(unsigned char c)
{
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || c == '_';
}

/* The ranges of CJK in src/sift/analysis/tokenize.py. */
static int is_cjk(uint32_t cp)
{
	return (cp >= 0x3400 && cp <= 0x4dbf) ||
	       (cp >= 0x4e00 && cp <= 0x9fff) ||
	       (cp >= 0xf900 && cp <= 0xfaff);
}

static int is_cont(unsigned char c)
{
	return (c & 0xc0) == 0x80;
}

/*
 * utf8_decode - read one character at s[0], with @rem bytes left
 *
 * Return its length and store its code point in *cp. For a byte that
 * does not start a well-formed character (stray continuation byte,
 * truncated, overlong or surrogate sequence, value above U+10FFFF) the
 * length is 1 and *cp is BAD_CP, so the caller moves on one byte and
 * never reads past the end.
 */
static size_t utf8_decode(const unsigned char *s, size_t rem, uint32_t *cp)
{
	uint32_t c = s[0];

	*cp = BAD_CP;
	if (c < 0x80) {
		*cp = c;
		return 1;
	}
	if (c >= 0xc2 && c <= 0xdf && rem >= 2 && is_cont(s[1])) {
		*cp = (c & 0x1f) << 6 | (s[1] & 0x3f);
		return 2;
	}
	if (c >= 0xe0 && c <= 0xef && rem >= 3 && is_cont(s[1]) &&
	    is_cont(s[2])) {
		c = (c & 0x0f) << 12 | (s[1] & 0x3f) << 6 | (s[2] & 0x3f);
		if (c < 0x800 || (c >= 0xd800 && c <= 0xdfff))
			return 1;
		*cp = c;
		return 3;
	}
	if (c >= 0xf0 && c <= 0xf4 && rem >= 4 && is_cont(s[1]) &&
	    is_cont(s[2]) && is_cont(s[3])) {
		c = (c & 0x07) << 18 | (s[1] & 0x3f) << 12 |
		    (s[2] & 0x3f) << 6 | (s[3] & 0x3f);
		if (c < 0x10000 || c > 0x10ffff)
			return 1;
		*cp = c;
		return 4;
	}
	return 1;
}

/*
 * cjk_run - the length in bytes of the CJK run at s[0], and its size
 *
 * Store the number of characters in *chars. The run is empty (return
 * 0) when s[0] is not CJK.
 */
static size_t cjk_run(const unsigned char *s, size_t rem, size_t *chars)
{
	size_t i = 0;
	uint32_t cp;
	size_t n;

	*chars = 0;
	while (i < rem) {
		n = utf8_decode(s + i, rem - i, &cp);
		if (!is_cjk(cp))
			break;
		i += n;
		(*chars)++;
	}
	return i;
}

/* Store a span if there is room; the count goes on either way. */
static void put_span(struct sift_span *out, size_t cap, size_t n,
		     size_t start, size_t end)
{
	if (n < cap) {
		out[n].start = start;
		out[n].end = end;
	}
}

int sift_tokenize(const char *utf8, size_t len, struct sift_span *out,
		  size_t cap, size_t *n_out)
{
	const unsigned char *s = (const unsigned char *)utf8;
	size_t i = 0;
	size_t n = 0;

	if (!n_out)
		return -EINVAL;
	*n_out = 0;
	if ((!utf8 && len) || (!out && cap))
		return -EINVAL;

	while (i < len) {
		size_t start = i;
		size_t chars;
		size_t k;
		uint32_t cp;

		if (is_latin(s[i])) {
			while (i < len && is_latin(s[i]))
				i++;
			if (i < len && s[i] == '+') {
				i++;
				if (i < len && s[i] == '+')
					i++;
			} else if (i < len && s[i] == '#') {
				i++;
			}
			put_span(out, cap, n++, start, i);
			continue;
		}

		i += cjk_run(s + i, len - i, &chars);
		if (chars == 1) {
			put_span(out, cap, n++, start, i);
		} else if (chars > 1) {
			for (k = 0; k + 1 < chars; k++)
				put_span(out, cap, n++,
					 start + k * CJK_BYTES,
					 start + (k + 2) * CJK_BYTES);
		} else {
			/* Not a token: step over one whole character. */
			i += utf8_decode(s + i, len - i, &cp);
		}
	}

	*n_out = n;
	return n > cap ? -ENOSPC : 0;
}

size_t sift_count_cjk(const char *utf8, size_t len)
{
	const unsigned char *s = (const unsigned char *)utf8;
	size_t i = 0;
	size_t count = 0;
	size_t chars;
	size_t used;
	uint32_t cp;

	if (!utf8)
		return 0;
	while (i < len) {
		used = cjk_run(s + i, len - i, &chars);
		if (chars) {
			count += chars;
			i += used;
		} else {
			i += utf8_decode(s + i, len - i, &cp);
		}
	}
	return count;
}
