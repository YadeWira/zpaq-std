/* -ma:bsc: libbsc's one-shot API, as zpaq-std called it: level 1..9 picks the
   sort transform ST3, ST4 or ST5, with the default coder and no LZP. See
   zs_codec.h. */
#include "zs_plugin.h"
extern "C" {
#include "../bsc/libbsc.h"
}

/* bsc_init() builds the QLFC coder's static model (a global table): once, and
   without a race between threads (a local static is initialised once, safely,
   since C++11). */
static void zs_bsc_init() {
	static const int done = (bsc_init(0), 1);
	(void)done;
}
static size_t zs_bound(size_t n, int) {
	return n + 1024;	/* bsc_compress needs n + LIBBSC_HEADER_SIZE */
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7FFFFFFF || cap < n + LIBBSC_HEADER_SIZE)
		return -1;
	zs_bsc_init();
	int sorter = LIBBSC_BLOCKSORTER_ST3 + (level - 1) / 3;
	if (sorter > LIBBSC_BLOCKSORTER_ST5)
		sorter = LIBBSC_BLOCKSORTER_ST5;
	const int r = bsc_compress((const unsigned char*)src, (unsigned char*)dst, (int)n, 0, 0,
	                           sorter, LIBBSC_DEFAULT_CODER, 0);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	zs_bsc_init();
	const int r = bsc_decompress((const unsigned char*)src, (int)n, (unsigned char*)dst, (int)cap, 0);
	return r < 0 ? -1 : (long long)cap;
}

ZS_DEFINE_CODEC(bsc, "libbsc 3.4.0", 1, 9, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
