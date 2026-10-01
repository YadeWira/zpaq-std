/*
  zpaq-std's C wrapper around kanzi (github.com/flanglet/kanzi-cpp), for -ma:kanzi.
  Not part of kanzi. Levels 1 and 2 (decoded by ZPAQKANZI), 3 and 4 (ZPAQKANZI3),
  5 and 6 (ZPAQKANZI5B), 7 (ZPAQKANZI7) and 8 and 9 (ZPAQKANZI8), see
  compressors/zpaqkanzi/. The stream is kanzi's own, without its stream header
  (headerless): the level travels in zpaq-std's block header instead.
*/
#include <sstream>
#include <string>
#include <exception>
#include "io/CompressedOutputStream.hpp"
#include "io/CompressedInputStream.hpp"
#include "kanzi_zpaqstd.h"
using namespace kanzi;

/* kanzi's own levels (BlockCompressor::getTransformAndCodec) */
static const char* const KZ_TR[10] = { "NONE", "LZX", "DNA+LZ", "TEXT+UTF+PACK+MM+LZX",
    "TEXT+UTF+EXE+PACK+MM+ROLZ", "TEXT+UTF+BWT+RANK+ZRLT", "TEXT+UTF+BWT+SRT+ZRLT",
    "LZP+TEXT+UTF+BWT+LZP", "EXE+RLT+TEXT+UTF+DNA", "EXE+RLT+TEXT+UTF+DNA" };
static const char* const KZ_EN[10] = { "NONE", "NONE", "HUFFMAN", "HUFFMAN", "NONE", "ANS0", "FPAQ", "CM",
    "TPAQ", "TPAQX" };
static bool kz_level_ok(int level) { return (level >= 1) && (level <= 9); }
static const int KZ_BITSTREAM = 7;          /* kanzi 2.6.0, frozen in ZPAQKANZI */

static int kz_blocksize(size_t n)
{
    size_t bs = (n + 15) & ~size_t(15);
    if (bs < 1024) bs = 1024;
    if (bs > (size_t(1) << 30)) bs = size_t(1) << 30;
    return int(bs);
}

extern "C" size_t kanzi_zs_compress(const void* src, size_t n, void* dst, size_t dstcap, int level)
{
    if (!kz_level_ok(level) || (n == 0) || (n >= (size_t(1) << 30)))
        return 0;
    try {
        std::ostringstream os;
        {
            CompressedOutputStream co(os, 1, KZ_EN[level], KZ_TR[level], kz_blocksize(n), 0,
                uint64(n),
#ifdef CONCURRENCY_ENABLED
                nullptr,
#endif
                true);
            co.write(static_cast<const char*>(src), std::streamsize(n));
            co.close();
        }
        const std::string z = os.str();
        if (z.size() > dstcap)
            return 0;
        memcpy(dst, z.data(), z.size());
        return z.size();
    }
    catch (...) {
        return 0;
    }
}

extern "C" int kanzi_zs_decompress(const void* src, size_t srclen, void* dst, size_t n, int level)
{
    if (!kz_level_ok(level))
        return 1;
    try {
        std::istringstream is(std::string(static_cast<const char*>(src), srclen));
        CompressedInputStream ci(is, 1, KZ_EN[level], KZ_TR[level], kz_blocksize(n), 0, uint64(n),
#ifdef CONCURRENCY_ENABLED
            nullptr,
#endif
            true, KZ_BITSTREAM);
        ci.read(static_cast<char*>(dst), std::streamsize(n));
        const bool ok = size_t(ci.gcount()) == n;
        char extra;
        ci.read(&extra, 1);
        const bool fin = ci.gcount() == 0;
        ci.close();
        return (ok && fin) ? 0 : 1;
    }
    catch (...) {
        return 1;
    }
}

/* Length of the entropy-decoded data of the first block (kanzi's preTransformLength),
   read from the block header; 0 if the stream does not start with a block. zpaq-std
   uses it to size M for ZPAQKANZI3 and later decoders. */
extern "C" size_t kanzi_zs_first_pre(const void* src, size_t srclen)
{
    const unsigned char* p = static_cast<const unsigned char*>(src);
    size_t pos = 0;
    auto bits = [&](int n) -> unsigned long long {
        unsigned long long v = 0;
        for (int i = 0; i < n; i++, pos++) {
            if ((pos >> 3) >= srclen) return 0;
            v = (v << 1) | ((p[pos >> 3] >> (7 - (pos & 7))) & 1);
        }
        return v;
    };
    const int lr = 3 + int(bits(5));
    if ((lr > 40) || (bits(lr) == 0))
        return 0;
    const unsigned mode = unsigned(bits(8));
    const bool copy = (mode & 0x80) != 0;
    if ((copy && (mode & 0x10)) || (!copy && (mode & 0x10)))
        bits(8);
    const int dsz = 1 + int((mode >> 5) & 3);
    return size_t(bits(8 * dsz));
}
