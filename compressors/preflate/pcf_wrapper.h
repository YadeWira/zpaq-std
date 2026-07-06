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

/* ---- File-level PCF container (whole-file MVP; generalises to embedded streams) ----

   A PCF stream is: magic "zPCF", version, then a list of segments — each either a
   literal passthrough or a recompressed DEFLATE block (recon + unpacked). This lets
   us strip a gzip/zlib wrapper (stored as literals) around a DEFLATE payload and
   recompress only the payload, reconstructing the exact original. */

/* True if buf begins with the PCF magic. */
bool pcf_is_container(const unsigned char* buf, size_t len);

/* Try to turn an original file (gzip / zlib / raw-DEFLATE) into a PCF stream.
   Performs an internal byte-exact verify (decode(encode(x)) == x) and returns false
   if the file is not a recompressible stream OR the verify fails — in which case the
   caller stores the file verbatim (never any corruption risk). On success, pcf_out
   holds the PCF stream and *out is always larger-or-similar (the win is downstream). */
bool pcf_file_encode(const std::vector<unsigned char>& original,
                     std::vector<unsigned char>& pcf_out);

/* Reverse a PCF stream to the exact original bytes. False if not a valid PCF. */
bool pcf_file_decode(const std::vector<unsigned char>& pcf,
                     std::vector<unsigned char>& original_out);

/* Safe reverse for extraction: returns true (and sets original_out) ONLY if
   `stored` is an AUTHENTIC PCF stream — i.e. it decodes AND re-encoding the result
   reproduces `stored` byte-for-byte. This rejects a verbatim file that merely
   happens to begin with the PCF magic, so it is never wrongly "reversed". */
bool pcf_authentic_reverse(const std::vector<unsigned char>& stored,
                           std::vector<unsigned char>& original_out);

/* Tri-state variant of pcf_authentic_reverse, for callers that must distinguish
   "leave silently" from "warn loudly":
     0 = authentic PCF, original_out holds the reversed original;
     1 = not an authentic-looking PCF (no magic, or magic but does not decode --
         e.g. a verbatim user file coincidentally starting with "zPCF", or an
         unsupported segment kind on this build): leave the file, stay silent;
     2 = DECODES as a valid PCF but re-encoding does not reproduce the stored
         bytes: near-certainly a real PCF this build can no longer reproduce
         (codec version skew). The file is left untouched, but callers should
         WARN per-file -- silence here hides an unrestored file. */
int pcf_authentic_reverse2(const std::vector<unsigned char>& stored,
                           std::vector<unsigned char>& original_out);

/* In-binary self-test: round-trips an embedded raw-DEFLATE constant and verifies
   the re-encode is byte-identical. Returns true on success. Used to prove preflate
   links and works inside the real zpaq-std binary on each platform. */
bool pcf_autotest();

/* Cap preflate's internal worker-thread pool (globalTaskPool). Call once during
   single-threaded startup, before any -pc work. extra_threads = 0 makes preflate
   run inline (no internal pool threads). Used to keep total threads within the
   archiver's -t / x86 budget when -pc work is parallelised across files. */
void pcf_set_internal_threads(int extra_threads);

/* One-time, single-threaded init of packJPG (-sa JPEG path): intra-file thread count
   (0=auto, 1=off, >=3 = N threads within one JPEG) and a decompression-bomb output cap
   in MiB (0=none). Call once at add()/extract() startup before any -pc/-sa work. */
void pcf_packjpg_init(int intra_threads, int max_output_mb);

/* True if -sa PNG/APNG recompression (packPNG, WebP-lossless) can actually run
   right now: compiled in (64-bit builds only -- the vendored library has no
   32-bit form) AND the CPU has AVX2 (checked via CPUID+OSXSAVE+XGETBV; the
   vendored library is built for AVX2 and would SIGILL without it, so this is
   checked before every call, never assumed). Query this before routing a
   png/apng file so the caller can skip the attempt entirely when unsupported;
   pcf_file_encode()/pcf_file_decode() also re-check internally, so calling
   them without checking first is safe (just wasted work), never unsafe. */
bool pcf_packpng_supported(void);

/* Number of PCF_SEG_PACKPNG segments encountered by pcf_file_decode that could
   NOT be reversed because this build/CPU lacks packPNG support. Extraction
   checks this AFTER the reverse pass to print one accurate note only when such
   content actually exists (an incapable build extracting an archive with no
   packPNG content stays silent). Thread-safe (atomic). */
long pcf_packpng_skipped(void);

/* Cap packPNG's internal worker threads (0 = its default = hardware threads).
   Call single-threaded at setup, BEFORE the add()-side prefetch pool or the
   extraction reverse pool start: when those pools are the parallelism axis,
   each pool worker must run packPNG single-threaded (n=1) or the box is
   oversubscribed by orders of magnitude. Same policy as preflate's
   pcf_set_internal_threads and packJPG's pcf_packjpg_init. */
void pcf_packpng_set_threads(int n);

#endif /* PCF_WRAPPER_H */
