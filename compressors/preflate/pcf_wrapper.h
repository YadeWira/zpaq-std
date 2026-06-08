/* pcf_wrapper.h — thin, collision-free bridge between zpaq-std.cpp and the
   vendored preflate library.

   zpaq-std.cpp includes ONLY this header. It deliberately exposes nothing from
   preflate's headers (which declare global-namespace classes like InputStream /
   OutputStream / MemStream that could clash with the 100k-line main TU). The
   implementation in pcf_wrapper.cpp is the sole translation unit that sees
   preflate.

   All buffers are std::vector<unsigned char>. Functions never throw; they return
   false on failure (caller falls back to storing data verbatim). */
#ifndef PCF_WRAPPER_H
#define PCF_WRAPPER_H

#include <vector>
#include <cstddef>

/* Decode a raw DEFLATE stream into its uncompressed bytes plus a small
   "reconstruction diff" that lets pcf_deflate_reencode reproduce the exact
   original DEFLATE bitstream. Returns false if the stream is not preflate-able. */
bool pcf_deflate_decode(const unsigned char* deflate, size_t deflate_len,
                        std::vector<unsigned char>& unpacked,
                        std::vector<unsigned char>& recon);

/* Inverse of pcf_deflate_decode: rebuild the original DEFLATE bytes.
   Returns false on failure. */
bool pcf_deflate_reencode(const std::vector<unsigned char>& unpacked,
                          const std::vector<unsigned char>& recon,
                          std::vector<unsigned char>& deflate_out);

/* In-binary self-test: round-trips an embedded raw-DEFLATE constant and verifies
   the re-encode is byte-identical. Returns true on success. Used to prove preflate
   links and works inside the real zpaq-std binary on each platform. */
bool pcf_autotest();

#endif /* PCF_WRAPPER_H */
