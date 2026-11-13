/* -ma:lz6 (since zpaq-std 2.10.0): lz6's seq engine, levels 1..13.
   (The codec's own name is "lz6seq": "lz6" is the name of the LZ5 v1.5 profile that
   -ma:lz6 wrote up to 2.9.0 and -ma:lz6hc writes now, and its blocks keep that name.)

   The stream is a container of self-contained seq blocks ("chunks") of at most 16 MiB
   of original data each, so that the ZPAQL decoder (ZPAQLZ6SEQ) needs a bounded memory:
       [n_chunks:4 LE]   then n_chunks times:   [csize:4 LE][seq block, csize bytes]
   An empty input is one chunk, the empty stored block.

   The encoder is told (LZ6_compress_seq_opt) to write only what ZPAQLZ6SEQ decodes:
   normal and stored blocks, x86 blocks, literal modes 0, 1, 5, 7 and 8.
   See zs_codec.h. */
#include "zs_plugin.h"
#include <string.h>
extern "C" {
#include "../lz6/lz6.h"
#include "../lz6/entropy/lz6seq.h"
}

static const size_t ZS_L6S_CHUNK = (size_t)16 << 20;        /* original bytes a chunk */
static const size_t ZS_L6S_CSIZE_MAX = (size_t)17 << 20;    /* ZPAQLZ6SEQ's limit on csize */
static const unsigned ZS_L6S_BLOCKS = LZ6SEQ_BLOCK_X86;
static const unsigned ZS_L6S_LITS = LZ6SEQ_LIT(1) | LZ6SEQ_LIT(5) | LZ6SEQ_LIT(7) | LZ6SEQ_LIT(8);

/* LZ6_seq_init builds lz6's tables and is not safe to run from two threads at once */
static void zs_l6s_init() {
	static const int once = (LZ6_seq_init(), 0);
	(void)once;
}
static size_t zs_l6s_chunks(size_t n) {
	return n == 0 ? 1 : (n + ZS_L6S_CHUNK - 1) / ZS_L6S_CHUNK;
}
static void zs_l6s_put32(unsigned char* p, size_t v) {
	p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}
static size_t zs_l6s_get32(const unsigned char* p) {
	return (size_t)p[0] | ((size_t)p[1] << 8) | ((size_t)p[2] << 16) | ((size_t)p[3] << 24);
}

static size_t zs_bound(size_t n, int) {
	if (n > 0x7E000000)
		return 0;
	/* a chunk: its size, and what lz6 asks for (LZ6_COMPRESSBOUND + 64 KiB) */
	return 4 + n + zs_l6s_chunks(n) * (4 + (ZS_L6S_CHUNK / 128) + 16 + 65536 + 64);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7E000000 || level < 1 || level > 13)
		return -1;
	zs_l6s_init();
	const char* s = (const char*)src;
	unsigned char* d = (unsigned char*)dst;
	const size_t nch = zs_l6s_chunks(n);
	size_t o = 4;
	if (cap < 4)
		return -1;
	zs_l6s_put32(d, nch);
	for (size_t i = 0; i < nch; ++i) {
		const size_t off = i * ZS_L6S_CHUNK;
		const size_t m = n - off < ZS_L6S_CHUNK ? n - off : ZS_L6S_CHUNK;
		if (cap - o < 4 + 5)
			return -1;
		size_t c = 0;
		if (m > 0)
			c = LZ6_compress_seq_opt(s + off, m, (char*)d + o + 4, cap - o - 4, level, ZS_L6S_BLOCKS, ZS_L6S_LITS);
		if (c == 0 || c > ZS_L6S_CSIZE_MAX) {
			/* lz6 found no room (or the chunk is empty): the stored block, [0x01][size:4][bytes] */
			if (cap - o - 4 < m + 5)
				return -1;
			d[o + 4] = 0x01;
			zs_l6s_put32(d + o + 5, m);
			if (m > 0)
				memcpy(d + o + 9, s + off, m);
			c = m + 5;
		}
		zs_l6s_put32(d + o, c);
		o += 4 + c;
	}
	return (long long)o;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	const unsigned char* s = (const unsigned char*)src;
	char* d = (char*)dst;
	if (n < 4)
		return -1;
	zs_l6s_init();
	const size_t nch = zs_l6s_get32(s);
	size_t i = 4, o = 0;
	for (size_t k = 0; k < nch; ++k) {
		if (n - i < 4)
			return -1;
		const size_t c = zs_l6s_get32(s + i);
		i += 4;
		if (c < 5 || c > ZS_L6S_CSIZE_MAX || c > n - i)
			return -1;
		/* the original size of the chunk is in its header: [flags][isize:4] */
		const size_t isize = zs_l6s_get32(s + i + 1);
		if (isize > ZS_L6S_CHUNK || isize > cap - o)
			return -1;
		if (isize > 0) {
			const size_t r = LZ6_decompress_seq((const char*)s + i, c, d + o, isize);
			if (r != isize)
				return -1;
		}
		i += c;
		o += isize;
	}
	return (long long)o;
}

ZS_DEFINE_CODEC(lz6seq, "lz6 v2.1.0 (seq)", 1, 13, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
