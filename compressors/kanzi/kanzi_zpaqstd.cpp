/*
  zpaq-std's C wrapper around kanzi (github.com/flanglet/kanzi-cpp), for -ma:kanzi.
  Not part of kanzi. Levels 1 and 2 only: the ones ZPAQKANZI decodes (see
  compressors/zpaqkanzi/). The stream is kanzi's own, without its stream header
  (headerless): the level travels in zpaq-std's block header instead.
*/
#include <sstream>
#include <string>
#include <exception>
#include "io/CompressedOutputStream.hpp"
#include "io/CompressedInputStream.hpp"
#include "kanzi_zpaqstd.h"
using namespace kanzi;

static const char* const KZ_TR[3] = { "NONE", "LZX", "DNA+LZ" };
static const char* const KZ_EN[3] = { "NONE", "NONE", "HUFFMAN" };
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
    if ((level < 1) || (level > 2) || (n == 0) || (n >= (size_t(1) << 30)))
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
    if ((level < 1) || (level > 2))
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
