/*
Copyright (c) 2015-2016, Apple Inc. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1.  Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2.  Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer
    in the documentation and/or other materials provided with the distribution.

3.  Neither the name of the copyright holder(s) nor the names of any contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

#ifndef LZFSE_H
#define LZFSE_H

#include <stddef.h>
#include <stdint.h>

/* The LZFSE bitstream is little-endian. Fail at compile time instead of
   silently producing data that cannot be decoded. */
#if defined(__BYTE_ORDER__) && defined(__ORDER_BIG_ENDIAN__) && \
    (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)
#  error "lzfse-ex supports little-endian targets only"
#endif

/*! @abstract Version of this library. */
#define LZFSE_VERSION_MAJOR 1
#define LZFSE_VERSION_MINOR 0
#define LZFSE_VERSION_PATCH 4
#define LZFSE_VERSION_STRING "1.0.4"

/*! @abstract Version of this fork, for codec/codecinfo-style output. */
#define LZFSE_EX_VERSION_STRING LZFSE_VERSION_STRING

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_MSC_VER) && !defined(__clang__)
#  define __attribute__(X)
#  pragma warning(disable : 4068)
#endif

#if defined(LZFSE_DLL)
#  if defined(_WIN32) || defined(__CYGWIN__)
#    if defined(LZFSE_DLL_EXPORTS)
#      define LZFSE_API __declspec(dllexport)
#    else
#      define LZFSE_API __declspec(dllimport)
#    endif
#  endif
#endif

#if !defined(LZFSE_API)
#  if __GNUC__ >= 4
#    define LZFSE_API __attribute__((visibility("default")))
#  else
#    define LZFSE_API
#  endif
#endif

/*! @abstract Get the required scratch buffer size to compress using LZFSE.   */
LZFSE_API size_t lzfse_encode_scratch_size();

/*! @abstract Compress a buffer using LZFSE.
 *
 *  @param dst_buffer
 *  Pointer to the first byte of the destination buffer.
 *
 *  @param dst_size
 *  Size of the destination buffer in bytes.
 *
 *  @param src_buffer
 *  Pointer to the first byte of the source buffer.
 *
 *  @param src_size
 *  Size of the source buffer in bytes.
 *
 *  @param scratch_buffer
 *  If non-NULL, a pointer to scratch space for the routine to use as workspace;
 *  the routine may use up to lzfse_encode_scratch_size( ) bytes of workspace
 *  during its operation, and will not perform any internal allocations. If
 *  NULL, the routine may allocate its own memory to use during operation via
 *  a single call to malloc( ), and will release it by calling free( ) prior
 *  to returning. For most use, passing NULL is perfectly satisfactory, but if
 *  you require strict control over allocation, you will want to pass an
 *  explicit scratch buffer.
 *
 *  @return
 *  The number of bytes written to the destination buffer if the input is
 *  successfully compressed. If the input cannot be compressed to fit into
 *  the provided buffer, or an error occurs, zero is returned, and the
 *  contents of dst_buffer are unspecified.                                   */
LZFSE_API size_t lzfse_encode_buffer(uint8_t *__restrict dst_buffer,
                                     size_t dst_size,
                                     const uint8_t *__restrict src_buffer,
                                     size_t src_size,
                                     void *__restrict scratch_buffer);

/*! @abstract Get the required scratch buffer size to decompress using LZFSE. */
LZFSE_API size_t lzfse_decode_scratch_size();

/*! @abstract Decompress a buffer using LZFSE.
 *
 *  @param dst_buffer
 *  Pointer to the first byte of the destination buffer.
 *
 *  @param dst_size
 *  Size of the destination buffer in bytes.
 *
 *  @param src_buffer
 *  Pointer to the first byte of the source buffer.
 *
 *  @param src_size
 *  Size of the source buffer in bytes.
 *
 *  @param scratch_buffer
 *  If non-NULL, a pointer to scratch space for the routine to use as workspace;
 *  the routine may use up to lzfse_decode_scratch_size( ) bytes of workspace
 *  during its operation, and will not perform any internal allocations. If
 *  NULL, the routine may allocate its own memory to use during operation via
 *  a single call to malloc( ), and will release it by calling free( ) prior
 *  to returning. For most use, passing NULL is perfectly satisfactory, but if
 *  you require strict control over allocation, you will want to pass an
 *  explicit scratch buffer.
 *
 *  @return
 *  The number of bytes written to the destination buffer if the input is
 *  successfully decompressed. If there is not enough space in the destination
 *  buffer to hold the entire expanded output, only the first dst_size bytes
 *  will be written to the buffer and dst_size is returned. Note that this
 *  behavior differs from that of lzfse_encode_buffer.                        */
LZFSE_API size_t lzfse_decode_buffer(uint8_t *__restrict dst_buffer,
                                     size_t dst_size,
                                     const uint8_t *__restrict src_buffer,
                                     size_t src_size,
                                     void *__restrict scratch_buffer);

/*! @abstract Status codes returned by lzfse_decode_buffer_with_status( ). */
enum {
  /*! The input was fully decompressed. */
  LZFSE_DECODE_STATUS_OK = 0,
  /*! The destination buffer was too small; call again with a larger one. */
  LZFSE_DECODE_STATUS_DST_FULL = 1,
  /*! The input ended before the end-of-stream marker (truncated input). */
  LZFSE_DECODE_STATUS_SRC_EMPTY = 2,
  /*! The input is not a valid LZFSE stream. */
  LZFSE_DECODE_STATUS_ERROR = 3
};

/*! @abstract Decompress a buffer, reporting why decoding stopped.
 *
 *  This is a variant of lzfse_decode_buffer( ) that, unlike that function,
 *  always lets the caller distinguish a destination that was too small from
 *  corrupt or truncated input, and from a successful decode that happened to
 *  fill the destination exactly.
 *
 *  @param dst_buffer
 *  Pointer to the first byte of the destination buffer.
 *
 *  @param dst_size
 *  Size of the destination buffer in bytes.
 *
 *  @param src_buffer
 *  Pointer to the first byte of the source buffer.
 *
 *  @param src_size
 *  Size of the source buffer in bytes.
 *
 *  @param scratch_buffer
 *  As for lzfse_decode_buffer( ).
 *
 *  @param decoded_size
 *  If non-NULL, receives the number of bytes written to the destination
 *  buffer, also when the return value is LZFSE_DECODE_STATUS_DST_FULL.
 *
 *  @return
 *  LZFSE_DECODE_STATUS_OK on success, LZFSE_DECODE_STATUS_DST_FULL if the
 *  destination buffer was too small, LZFSE_DECODE_STATUS_SRC_EMPTY if the
 *  input is truncated, or LZFSE_DECODE_STATUS_ERROR if the input is invalid. */
LZFSE_API int lzfse_decode_buffer_with_status(
    uint8_t *__restrict dst_buffer, size_t dst_size,
    const uint8_t *__restrict src_buffer, size_t src_size,
    void *__restrict scratch_buffer, size_t *decoded_size);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* LZFSE_H */
