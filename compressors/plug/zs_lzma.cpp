/* -ma:lzma: the LZMA SDK's LzmaCompress/LzmaUncompress, as zpaq-std called them.
   See zs_codec.h. The stream is the one ZPAQLZMA reads: 5 bytes of properties
   (lc=3 lp=0 pb=2 and the dictionary), 4 bytes that zpaq-std fills with the
   original size (written as 0 here), and raw LZMA without an end marker. The
   dictionary is the smallest power of 2 >= the block, 64 KB at least, as
   zpaq-std sizes the decoder's memory from it. */
#include "zs_plugin.h"
#include "../lzmasdk/LzmaLib.h"
#include "../lzmasdk/7zVersion.h"
#include <string.h>

static int zs_dict_log(size_t n) {
	int k = 16;
	while (k < 30 && ((size_t)1 << k) < n) k++;
	return k;
}
static size_t zs_bound(size_t n, int) {
	return n + n / 3 + (1 << 16) + 9;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (cap < 9)
		return -1;
	unsigned char* d = (unsigned char*)dst;
	size_t destLen = cap - 9, propsSize = LZMA_PROPS_SIZE;
	const int r = LzmaCompress(d + 9, &destLen, (const unsigned char*)src, n, d, &propsSize,
	                           level, (unsigned)1 << zs_dict_log(n), 3, 0, 2, -1, 1);
	if (r != SZ_OK || propsSize != LZMA_PROPS_SIZE)
		return -1;
	memset(d + 5, 0, 4);
	return (long long)destLen + 9;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n < 10)
		return -1;
	const unsigned char* s = (const unsigned char*)src;
	size_t dlen = cap, slen = n - 9;
	const int r = LzmaUncompress((unsigned char*)dst, &dlen, s + 9, &slen, s, LZMA_PROPS_SIZE);
	if (r != SZ_OK && r != SZ_ERROR_INPUT_EOF)
		return -1;
	return (long long)dlen;
}

ZS_DEFINE_CODEC(lzma, "LZMA SDK " MY_VERSION, 0, 9, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
