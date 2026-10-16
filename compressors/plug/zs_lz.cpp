/* -ma:lz: lzlib, through the one-shot wrappers zpaq-std had for its stream API.
   See zs_codec.h. compress() returns a whole lzip member ("LZIP", version,
   dictionary, LZMA, 20-byte trailer); zpaq-std keeps only the LZMA inside and
   stores it as an -ma:lzma block, which the lzma plugin decodes. decompress()
   reads a whole lzip member back; zpaq-std itself does not need it. */
#include "zs_plugin.h"
#include <stdint.h>
#include "../lzlib/lzlib.h"

// lzlib (lzip) one-shot compress/decompress wrappers.
// lzlib has only a stream API; we wrap it in a single call that fills
// the output buffer and returns the compressed size.
static int lzlib_compress_wrapper(const unsigned char* in, size_t in_size,
                                  unsigned char* out, size_t out_size, size_t* out_used, int level)
{
    static const size_t DICT[]   = {65535, 1u<<20, 1572864, 2u<<20, 3u<<20, 4u<<20, 8u<<20, 16u<<20, 24u<<20, 32u<<20};
    static const int    MATCH[]  = {16, 5, 6, 8, 12, 20, 36, 68, 132, 273};
    if (level < 0) level = 6;
    if (level > 9) level = 9;
    LZ_Encoder* enc = LZ_compress_open(DICT[level], MATCH[level], 0x1000000000000ULL);
    if (!enc || LZ_compress_errno(enc) != LZ_ok) { LZ_compress_close(enc); return -1; }
    size_t inpos = 0, outpos = 0;
    int ret, error = 0;
    while (1) {
        ret = LZ_compress_write(enc, in + inpos, (int)(in_size - inpos));
        if (ret < 0) { error = 1; break; }
        inpos += ret;
        if (inpos >= in_size) LZ_compress_finish(enc);
        ret = LZ_compress_read(enc, out + outpos, (int)(out_size - outpos));
        if (ret < 0) { error = 1; break; }
        outpos += ret;
        if (LZ_compress_finished(enc) == 1) break;
        if (outpos >= out_size) { error = 1; break; }
    }
    LZ_compress_close(enc);
    if (error) return -1;
    *out_used = outpos;
    return 0;
}

static int lzlib_decompress_wrapper(const unsigned char* in, size_t in_size,
                                    unsigned char* out, size_t out_size, size_t* out_used)
{
    LZ_Decoder* dec = LZ_decompress_open();
    if (!dec) return -1;
    size_t inpos = 0, outpos = 0;
    int ret, error = 0;
    while (1) {
        /* Feed input incrementally. lzlib's input buffer is bounded
         * (~64 KB), so for compressed streams larger than that a single
         * LZ_decompress_write accepts only part of the data. Only signal
         * end-of-input once everything has actually been written —
         * calling LZ_decompress_finish() early (as a previous version did
         * every iteration) corrupts the stream for multi-buffer inputs,
         * which is why larger blocks failed to round-trip. */
        if (inpos < in_size) {
            ret = LZ_decompress_write(dec, in + inpos, (int)(in_size - inpos));
            if (ret < 0) { error = 1; break; }
            inpos += ret;
            if (inpos >= in_size) LZ_decompress_finish(dec);
        }
        ret = LZ_decompress_read(dec, out + outpos, (int)(out_size - outpos));
        if (ret < 0) { error = 1; break; }
        outpos += ret;
        if (LZ_decompress_finished(dec) == 1) break;
        if (outpos >= out_size) { error = 1; break; }
    }
    LZ_decompress_close(dec);
    if (error) return -1;
    *out_used = outpos;
    return 0;
}

static size_t zs_bound(size_t n, int) {
	return n + n / 8 + 1024;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	size_t used = 0;
	if (lzlib_compress_wrapper((const unsigned char*)src, n, (unsigned char*)dst, cap, &used, level) != 0)
		return -1;
	return (long long)used;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap) {
	size_t used = 0;
	if (lzlib_decompress_wrapper((const unsigned char*)src, n, (unsigned char*)dst, cap, &used) != 0)
		return -1;
	return (long long)used;
}

static_assert(LZ_API_VERSION == 1016, "update the version string below");
ZS_DEFINE_CODEC(lz, "lzlib 1.16", 0, 9, zs_bound, zs_compress, zs_decompress, nullptr)
