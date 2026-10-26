// SPDX-License-Identifier: MIT OR Apache-2.0
/*
 * sanitize_fuzz.c: feed sift_tokenize random bytes under ASan and UBSan.
 *
 * Every call gets a heap buffer of exactly len bytes and a span array
 * of exactly cap entries, so a read or write one byte past either is
 * an ASan report. The result is checked against the contract of
 * sift_tok.h. Built and run by extra.sh; exit 0 means no violation.
 */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sift_tok.h"

#define ROUNDS	200000
#define MAX_LEN	64

/* xorshift64: a fixed seed makes every run the same. */
static uint64_t next_rand(uint64_t *state)
{
	uint64_t x = *state;

	x ^= x << 13;
	x ^= x >> 7;
	x ^= x << 17;
	return *state = x;
}

/* Bytes that matter: ASCII token chars, lead and continuation bytes. */
static const unsigned char alphabet[] = {
	'a', 'z', '0', '_', '+', '#', ' ', 0x00, 0x7f, 0x80, 0xbf, 0xc0,
	0xc2, 0xdf, 0xe0, 0xe3, 0xe4, 0xe9, 0xed, 0xef, 0xf0, 0xf4, 0xf5,
	0xff, 0xb8, 0xad, 0xa0,
};

static int check(const unsigned char *data, size_t len, size_t cap)
{
	struct sift_span *out = cap ? malloc(cap * sizeof(*out)) : NULL;
	size_t n = (size_t)-1;
	size_t i;
	int rc;

	rc = sift_tokenize((const char *)data, len, out, cap, &n);
	if (rc != 0 && rc != -ENOSPC) {
		fprintf(stderr, "bad rc %d\n", rc);
		return 1;
	}
	if ((rc == -ENOSPC) != (n > cap)) {
		fprintf(stderr, "rc %d with n %zu cap %zu\n", rc, n, cap);
		return 1;
	}
	for (i = 0; i < n && i < cap; i++) {
		if (out[i].start >= out[i].end || out[i].end > len ||
		    (i && out[i].start < out[i - 1].start)) {
			fprintf(stderr, "bad span %zu\n", i);
			return 1;
		}
	}
	free(out);
	return 0;
}

int main(void)
{
	uint64_t state = 0x9e3779b97f4a7c15ULL;
	long round;

	for (round = 0; round < ROUNDS; round++) {
		size_t len = next_rand(&state) % (MAX_LEN + 1);
		size_t cap = next_rand(&state) % (MAX_LEN + 1);
		unsigned char *data = len ? malloc(len) : NULL;
		size_t i;
		int bad;

		for (i = 0; i < len; i++)
			data[i] = alphabet[next_rand(&state) %
					   sizeof(alphabet)];
		bad = check(data, len, cap) || check(data, len, 0);
		(void)sift_count_cjk((const char *)data, len);
		free(data);
		if (bad)
			return 1;
	}
	printf("%d rounds, no violation\n", ROUNDS);
	return 0;
}
