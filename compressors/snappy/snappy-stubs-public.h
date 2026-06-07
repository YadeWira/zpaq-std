// Copyright 2011 Google Inc. All Rights Reserved.
//
// Various type stubs for the open-source version of Snappy.
// (manually generated for bundled build, replaces CMake's configure_file)

#ifndef THIRD_PARTY_SNAPPY_OPENSOURCE_SNAPPY_STUBS_PUBLIC_H_
#define THIRD_PARTY_SNAPPY_OPENSOURCE_SNAPPY_STUBS_PUBLIC_H_

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>

#ifdef _WIN32
/* On Windows (MinGW-w64 / MSVC) these POSIX headers are not available. */
#  define HAVE_SYS_UIO_H 0
#  define HAVE_UNISTD_H 0
#  define HAVE_SYS_MMAN_H 0
#  define HAVE_BYTESWAP_H 0
#  define NOMINMAX
#  include <windows.h>
   /* Stub iovec for snappy on Windows (not in <winsock2.h> directly) */
   struct iovec { void* iov_base; size_t iov_len; };
#else
#  define HAVE_SYS_UIO_H 1
#  define HAVE_UNISTD_H 1
#  define HAVE_SYS_MMAN_H 1
#  define HAVE_BYTESWAP_H 1
#endif

#if HAVE_SYS_UIO_H
#include <sys/uio.h>
#endif

#if HAVE_UNISTD_H
#include <unistd.h>
#endif

#if HAVE_SYS_MMAN_H
#include <sys/mman.h>
#endif

#if HAVE_BYTESWAP_H
#include <byteswap.h>
#endif

#endif  // THIRD_PARTY_SNAPPY_OPENSOURCE_SNAPPY_STUBS_PUBLIC_H_
