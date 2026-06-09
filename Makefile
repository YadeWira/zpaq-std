# Universal Makefile for zpaq-std
# Build 1.6 2026-03-20
# By YadeWira (MIT License)
# Tested (kind of) on Linux, macOS, FreeBSD, OpenBSD, NetBSD, Solaris, illumos,
# sparc64, ppc, mips, ARM, aarch64, Apple Silicon, RISC-V, etc.

# NOTE: This Makefile requires GNU make
# On FreeBSD/OpenBSD/NetBSD/DragonFly/Solaris use 'gmake' instead of 'make'
# On macOS this is fine (Apple ships GNU make)

# Usage:
#
# make                     Compile zpaq-std (auto-NOJIT on non-x86)
# make install             Install to /usr/local/bin (or PREFIX)
# make install-clean       Compile, install, then remove the local binary
# make static              Static build without SFTP (for NAS, containers, rescue)
# make nointel             Force build without JIT (even on Intel)
# make debug               Debug build (no optimization)
# make clean               Remove local binary
# make uninstall           Remove from system
# make check               Show build configuration
# make test                Run all automatic tests
#
# Options:
# make CROSS_COMPILE=aarch64-linux-gnu-   Cross-compile for another arch
#
# Download:
# make nightly             Nightly (risky)
# make download            Latest official release
# make downloads           Stable from GitHub

# OS / Architecture detection
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# Compiler: prefer clang++, fallback g++
CXX ?= clang++
ifeq ($(shell command -v $(CXX) >/dev/null 2>&1 || echo "no"),no)
  CXX = g++
endif

# On Solaris, clang++ is often absent; fall back to g++ then CC (Solaris Studio)
ifeq ($(UNAME_S),SunOS)
  ifeq ($(shell command -v $(CXX) >/dev/null 2>&1 || echo "no"),no)
    ifeq ($(shell command -v g++ >/dev/null 2>&1 || echo "no"),no)
      CXX = CC
    else
      CXX = g++
    endif
  endif
endif

# Cross-compilation support (e.g. make CROSS_COMPILE=aarch64-linux-gnu-)
CROSS_COMPILE ?=
CXX := $(CROSS_COMPILE)$(CXX)

# C compiler for the bundled C codec sources (fl2, lz5, lizard, bzip2/3,
# brotli, libdeflate, lzlib). MUST be cross-prefixed like CXX. Otherwise
# make's built-in default CC ('cc' = the host compiler) builds these C
# codecs as HOST objects (e.g. Linux ELF) which then get linked into the
# cross-target binary (e.g. a Windows PE); the machine code runs but the
# objects' relocations/sections are wrong for the target, so the codec
# functions return garbage at runtime and -ma silently falls back. The
# C++ codecs were unaffected because they use $(CXX), which IS prefixed.
ifeq ($(origin CC),default)
  CC := $(CROSS_COMPILE)gcc
else
  CC := $(CROSS_COMPILE)$(CC)
endif

# Default tools
RM      ?= rm -f
MKDIR   ?= mkdir -p
LN      ?= ln -sf
STRIP   ?= $(CROSS_COMPILE)strip

# Program details
PROG    := zpaq-std
ALTNAME := dir
SOURCE  := zpaq-std.cpp
# zpaqfranz embedded LZ4 directly in zpaq-std.cpp inside an #ifdef _WIN32
# block. On Windows cross-compile that inline copy is the canonical LZ4
# (it was designed to be compiled alongside the rest of zpaq-std.cpp).
# On Linux/macOS we use the bundled compressors/lz4/*.c instead. Detect
# the cross-compile and skip the bundled .c files to avoid duplicate
# symbol errors on MinGW.
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  LZ4SRC  :=
else
  LZ4SRC  := compressors/lz4/lz4.c compressors/lz4/lz4hc.c
endif
LZ5SRC  := compressors/lz5/lz5.c compressors/lz5/lz5hc.c
ZSTDSRC := compressors/zstd/zstd.c
# fl2 util.c uses POSIX (chown/lstat/__errno_location) not in MinGW.
# Skip it on Windows cross-compile. fast-lzma2 only needs lzma2_*.c
# and the range/dict_buffer helpers.
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  FL2SRC  := compressors/fl2/fl2_common.c compressors/fl2/fl2_compress.c compressors/fl2/fl2_decompress.c compressors/fl2/fl2_pool.c compressors/fl2/fl2_threading.c compressors/fl2/lzma2_dec.c compressors/fl2/lzma2_enc.c compressors/fl2/radix_bitpack.c compressors/fl2/radix_mf.c compressors/fl2/radix_struct.c compressors/fl2/range_enc.c compressors/fl2/dict_buffer.c
else
  FL2SRC  := compressors/fl2/fl2_common.c compressors/fl2/fl2_compress.c compressors/fl2/fl2_decompress.c compressors/fl2/fl2_pool.c compressors/fl2/fl2_threading.c compressors/fl2/lzma2_dec.c compressors/fl2/lzma2_enc.c compressors/fl2/radix_bitpack.c compressors/fl2/radix_mf.c compressors/fl2/radix_struct.c compressors/fl2/range_enc.c compressors/fl2/dict_buffer.c compressors/fl2/util.c
endif
LIZSRC  := compressors/lizard/lizard_compress.c compressors/lizard/lizard_decompress.c compressors/lizard/entropy/entropy_common.c compressors/lizard/entropy/debug.c compressors/lizard/entropy/fse_compress.c compressors/lizard/entropy/fse_decompress.c compressors/lizard/entropy/hist.c compressors/lizard/entropy/huf_compress.c compressors/lizard/entropy/huf_decompress.c
BZIP2SRC := compressors/bzip2/blocksort.c compressors/bzip2/bzlib.c compressors/bzip2/compress.c compressors/bzip2/crctable.c compressors/bzip2/decompress.c compressors/bzip2/huffman.c compressors/bzip2/randtable.c
BZIP3SRC := compressors/bzip3/libbz3.c
BROTLISRC := $(wildcard compressors/brotli/common/*.c compressors/brotli/enc/*.c compressors/brotli/dec/*.c)
SNAPPYSRC := compressors/snappy/snappy.cc compressors/snappy/snappy-c.cc compressors/snappy/snappy-sinksource.cc compressors/snappy/snappy-stubs-internal.cc
LIBDEFLATE_CORE_SRC := $(wildcard compressors/libdeflate/lib/*.c)
LIBDEFLATE_X86_SRC  := $(wildcard compressors/libdeflate/lib/x86/*.c)
LIBDEFLATE_ARM_SRC  := $(wildcard compressors/libdeflate/lib/arm/*.c)
LZLIBSRC := compressors/lzlib/lzlib.c
PPMDSRC  := compressors/ppmd/Ppmd7.c compressors/ppmd/Ppmd7Enc.c compressors/ppmd/Ppmd7Dec.c compressors/ppmd/ppmd_wrapper.c
LZAVSRC  := compressors/lzav/lzav.h
HSSRC    := compressors/hs/heatshrink_encoder.c compressors/hs/heatshrink_decoder.c compressors/hs/hs_wrapper.c
LZFSESRC := compressors/lzfse/lzfse_decode.c compressors/lzfse/lzfse_decode_base.c compressors/lzfse/lzfse_encode.c compressors/lzfse/lzfse_encode_base.c compressors/lzfse/lzfse_fse.c compressors/lzfse/lzvn_decode_base.c compressors/lzfse/lzvn_encode_base.c
ZOPFLISRC :=
BSCSRC   := compressors/bsc/bwt/libsais/libsais.c compressors/bsc/libbsc/libbsc.cpp compressors/bsc/lzp/lzp.cpp compressors/bsc/coder/coder.cpp compressors/bsc/coder/qlfc/qlfc.cpp compressors/bsc/coder/qlfc/qlfc_model.cpp compressors/bsc/bwt/bwt.cpp compressors/bsc/st/st.cpp compressors/bsc/adler32/adler32.cpp compressors/bsc/platform/platform.cpp compressors/bsc/filters/preprocessing.cpp compressors/bsc/filters/detectors.cpp
# lzham threading: pthreads on Unix, Win32 on Windows cross-compile
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  LZHAM_THREADING := compressors/lzham/lzham_win32_threading.cpp
else
  LZHAM_THREADING := compressors/lzham/lzham_pthreads_threading.cpp
endif
LZHAMSRC := compressors/lzham/lzham_lib.cpp compressors/lzham/lzham_lzbase.cpp compressors/lzham/lzham_lzcomp.cpp compressors/lzham/lzham_lzcomp_internal.cpp compressors/lzham/lzham_lzcomp_state.cpp compressors/lzham/lzham_match_accel.cpp $(LZHAM_THREADING) compressors/lzham/lzham_assert.cpp compressors/lzham/lzham_checksum.cpp compressors/lzham/lzham_huffman_codes.cpp compressors/lzham/lzham_lzdecomp.cpp compressors/lzham/lzham_lzdecompbase.cpp compressors/lzham/lzham_mem.cpp compressors/lzham/lzham_polar_codes.cpp compressors/lzham/lzham_prefix_coding.cpp compressors/lzham/lzham_symbol_codec.cpp compressors/lzham/lzham_vector.cpp compressors/lzham/lzham_platform.cpp compressors/lzham/lzham_timer.cpp
# preflate (Apache-2.0): C++ stream-recompression library for -pc. selftest.cpp is
# standalone (has its own main) and must NOT be linked into the binary.
PREFLATE_ROOT_SRC := $(filter-out compressors/preflate/selftest.cpp,$(wildcard compressors/preflate/*.cpp))
PREFLATE_SUP_SRC  := $(wildcard compressors/preflate/support/*.cpp)

ZSTDINC := -Icompressors/zstd
FL2INC  := -Icompressors/fl2 -DNO_XXHASH -DNDEBUG -U_FORTIFY_SOURCE
LZ5INC  := -Icompressors/lz5
LIZINC  := -Icompressors/lizard -Icompressors/lizard/entropy
BZIP2INC := -Icompressors/bzip2
# bzip2 uses glibc fortify symbols (__fprintf_chk/__assert_fail) not
# in MinGW. Disable fortify per-file in the bzip2 sources.
# BZ_NO_STDIO compiles out bzip2's FILE* API and all stderr/stdout/stdin
# references (only used by debug/error paths and the bzopen/bzread family,
# which zpaq-std does not use — it only calls BZ2_bzBuffToBuff{Compress,
# Decompress}). Without it, bzlib.c references plain stderr/stdout/stdin
# symbols that msvcrt does not export, breaking the link. The application
# must then supply bz_internal_error() (provided in zpaq-std.cpp).
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  BZIP2INC += -U_FORTIFY_SOURCE -DBZ_NO_STDIO
endif
BZIP3INC := -Icompressors/bzip3 -DVERSION='"1.5.3"' -Wno-unused-function
BROTLIINC := -Icompressors/brotli/include -Icompressors/brotli/common
SNAPPYINC := -Icompressors/snappy -Wno-sign-compare
LIBDEFLATEINC := -Icompressors/libdeflate -Icompressors/libdeflate/lib -Icompressors/libdeflate/lib/x86 -Icompressors/libdeflate/lib/arm
LZLIBINC := -Icompressors/lzlib
PPMDINC  := -Icompressors/ppmd
LZAVINC  := -Icompressors/lzav
HSINC    := -Icompressors/hs
LZFSEINC := -Icompressors/lzfse -DNDEBUG -U_FORTIFY_SOURCE
ZOPFLIINC :=
BSCINC    := -Icompressors/bsc/libbsc -Icompressors/bsc/lzp -Icompressors/bsc/coder -Icompressors/bsc/coder/qlfc -Icompressors/bsc/bwt -Icompressors/bsc/bwt/libsais -Icompressors/bsc/st -Icompressors/bsc/adler32 -Icompressors/bsc/platform -Icompressors/bsc/filters
LZHAMINC  := -Icompressors/lzham
PREFLATEINC := -Icompressors/preflate -Icompressors/preflate/support
ZPAQ_CFLAGS := $(CFLAGS) -O3 -pthread -Wall -D_GLIBCXX_USE_CXX11_ABI=0

# Download URLs
SOURCE_URL_NIGHTLY  := http://www.francocorbelli.it/zpaq-std.cpp
SOURCE_URL_DOWNLOAD := http://www.francocorbelli.it/zpaq-std/win64/zpaq-std.cpp
SOURCE_URL_GITHUB   := https://raw.githubusercontent.com/fcorbelli/zpaq-std/main/zpaq-std.cpp

# User-overridable flags (safe to pass from command line or packaging systems)
CXXFLAGS ?= -O3
CPPFLAGS ?=

# Project-required flags (always present; user flags are appended)
ZPAQ_CXXFLAGS := -Wall -pthread $(CXXFLAGS) -D_GLIBCXX_USE_CXX11_ABI=0
# -mconsole tells the MinGW CRT to use main() instead of WinMain()
# as the entry point. Required for console (CLI) applications.
# -static* statically links the MinGW runtime (libgcc, libstdc++,
# libwinpthread) so the .exe does not depend on libgcc_s_seh-1.dll,
# libstdc++-6.dll or libwinpthread-1.dll being present alongside it.
# Without this the binary fails to load on a clean Windows box / wine
# with "bad EXE format" (missing DLL imports).
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  ZPAQ_CXXFLAGS += -mconsole -static -static-libgcc -static-libstdc++
endif
ZPAQ_CPPFLAGS := $(CPPFLAGS)

# Intel-specific flags (added only on x86)
INTEL_FLAGS := -DHWSHA2

# Libraries
LDLIBS ?= -lm



# Install directories
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin

# OS-specific adjustments
ifeq ($(UNAME_S),SunOS)
  ZPAQ_CPPFLAGS += -DSOLARIS
endif

# Windows-specific link flags: urlmon for URLDownloadToFileW (used by
# zpaqfranz's auto-update path), ws2_32 for sockets, bcrypt for SHA,
# msvcrt for stdio. We deliberately link ONLY msvcrt (the legacy C
# runtime present on every Windows since XP) and NOT ucrt. Mixing
# -lucrt -lmsvcrt pulls in the api-ms-win-crt-*.dll UCRT stubs, which
# are not guaranteed on Windows 7 and conflict with msvcrt's stdio.
# The system libs come EARLY in the link order so user objects can
# resolve their symbols; place them between LDFLAGS and the objects
# via ZPAQ_WIN_LIBS.
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  # Use -Wl,--start-group/--end-group to handle circular deps between
  # msvcrt/advapi32 (registry calls in the C runtime).
  ZPAQ_WIN_LIBS := -Wl,--start-group -lmsvcrt -ladvapi32 -lkernel32 -luser32 -lshell32 -Wl,--end-group -lurlmon -lws2_32 -lbcrypt -lwininet -lcomctl32 -lgdi32
  # RT_MANIFEST resource: enables Common-Controls v6 (themed/visual-styled progress
  # bar) for the -innosetup GUI window. Built with windres for the Windows target.
  WINRES := win/manifest_res.o
else
  ZPAQ_WIN_LIBS :=
  WINRES :=
endif

# Post-link step. On MinGW the linker emits a non-allocatable `.comment`
# section (GCC version string) with a bogus virtual address far beyond
# SizeOfImage. The Windows loader (and wine) reject the image with
# "bad EXE format". Strip it out so the .exe actually loads. Stripping
# also drops debug symbols, shrinking the binary. No-op on other targets.
# Note: MinGW gcc auto-appends .exe, so the produced file is $(PROG).exe
# even though the make target is $(PROG).
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  ZPAQ_POSTLINK := $(STRIP) --remove-section=.comment $(PROG).exe
else
  ZPAQ_POSTLINK := true
endif

# On Windows, fl2_threading.c references UTIL_countPhysicalCores
# (from util.c which we exclude on Windows). Provide a stub.
ifneq (,$(findstring mingw,$(CROSS_COMPILE)))
  ZPAQ_CPPFLAGS += -DUTIL_countPhysicalCores_DEFINED_AS_STUB
endif

# Architecture-specific adjustments
# Using findstring to cover all variants (ppc64, ppc64le, sparc64, sparcv9, mips64el, etc)
ifeq ($(findstring ppc,$(UNAME_M)),ppc)
  ZPAQ_CPPFLAGS += -DANCIENT -DBIG
else ifeq ($(findstring sparc,$(UNAME_M)),sparc)
  ZPAQ_CPPFLAGS += -DALIGNMALLOC
else ifeq ($(findstring mips,$(UNAME_M)),mips)
  ZPAQ_CPPFLAGS += -DBIG
endif

# Auto-NOJIT: enable JIT + HWSHA2 only on x86/amd64.
# Everything else (ARM, aarch64, Apple Silicon, RISC-V, ppc, sparc, mips, ...)
# gets -DNOJIT automatically. Just "make" anywhere and it works.
# BTW newer zpaq-std "automagically" enable JIT. This is for older releases
ifneq ($(filter x86_64 amd64 i386 i686 i86pc,$(UNAME_M)),)
  ZPAQ_CPPFLAGS += $(INTEL_FLAGS)
else
  ZPAQ_CPPFLAGS += -DNOJIT
endif

# Phony targets
.PHONY: all build install uninstall clean check help debug \
        nointel install-nointel install-clean static \
        nightly download downloads \
        _do_download \
        test test-nointel

# Default target
all: build

# Build
build: $(PROG)

FL2OBJ := $(FL2SRC:.c=.o)
LZ5OBJ := $(LZ5SRC:.c=.o)
LIZOBJ := $(LIZSRC:.c=.o)
BZIP2OBJ := $(BZIP2SRC:.c=.o)
BZIP3OBJ := $(BZIP3SRC:.c=.o)
BROTLI_COMMON_OBJ := $(patsubst compressors/brotli/common/%.c,compressors/brotli/common/%.o,$(wildcard compressors/brotli/common/*.c))
BROTLI_ENC_OBJ := $(patsubst compressors/brotli/enc/%.c,compressors/brotli/enc/%.o,$(wildcard compressors/brotli/enc/*.c))
BROTLI_DEC_OBJ := $(patsubst compressors/brotli/dec/%.c,compressors/brotli/dec/%.o,$(wildcard compressors/brotli/dec/*.c))
BROTLIOBJ := $(BROTLI_COMMON_OBJ) $(BROTLI_ENC_OBJ) $(BROTLI_DEC_OBJ)
SNAPPYOBJ := $(SNAPPYSRC:.cc=.o)
LIBDEFLATE_CORE_OBJ := $(LIBDEFLATE_CORE_SRC:.c=.o)
LIBDEFLATE_X86_OBJ  := $(LIBDEFLATE_X86_SRC:.c=.o)
LIBDEFLATE_ARM_OBJ  := $(LIBDEFLATE_ARM_SRC:.c=.o)
LIBDEFLATEOBJ := $(LIBDEFLATE_CORE_OBJ) $(LIBDEFLATE_X86_OBJ) $(LIBDEFLATE_ARM_OBJ)
LZLIBOBJ := $(LZLIBSRC:.c=.o)
PPMDOBJ  := $(PPMDSRC:.c=.o)
HSOBJ    := $(HSSRC:.c=.o)
LZFSEOBJ := $(LZFSESRC:.c=.o)
ZOPFLIOBJ := $(ZOPFLISRC:.c=.o)
BSCOBJ   := $(BSCSRC:.cpp=.o)
LZHAMOBJ := $(LZHAMSRC:.cpp=.o)
PREFLATE_ROOT_OBJ := $(PREFLATE_ROOT_SRC:.cpp=.o)
PREFLATE_SUP_OBJ  := $(PREFLATE_SUP_SRC:.cpp=.o)
PREFLATEOBJ := $(PREFLATE_ROOT_OBJ) $(PREFLATE_SUP_OBJ)

$(PROG): $(SOURCE) $(LZ4SRC) $(ZSTDSRC) $(FL2OBJ) $(LZ5OBJ) $(LIZOBJ) $(BZIP2OBJ) $(BZIP3OBJ) $(BROTLIOBJ) $(SNAPPYOBJ) $(LIBDEFLATEOBJ) $(LZLIBOBJ) $(HSOBJ) $(LZFSEOBJ) $(BSCOBJ) $(LZHAMOBJ) $(PREFLATEOBJ) $(PPMDOBJ) $(WINRES) $(LZAVSRC)
	$(CXX) $(ZPAQ_CPPFLAGS) $(ZPAQ_CXXFLAGS) $(ZSTDINC) $(LZAVINC) $(HSINC) $(LZFSEINC) $(BSCINC) $(LZHAMINC) $(BROTLIINC) $(PREFLATEINC) $(PPMDINC) $(LDFLAGS) $(SOURCE) $(LZ4SRC) $(ZSTDSRC) $(FL2OBJ) $(LZ5OBJ) $(LIZOBJ) $(BZIP2OBJ) $(BZIP3OBJ) $(BROTLIOBJ) $(SNAPPYOBJ) $(LIBDEFLATEOBJ) $(LZLIBOBJ) $(HSOBJ) $(LZFSEOBJ) $(BSCOBJ) $(LZHAMOBJ) $(PREFLATEOBJ) $(PPMDOBJ) $(WINRES) $(ZPAQ_WIN_LIBS) $(LDLIBS) -o $@
	$(ZPAQ_POSTLINK)

# RT_MANIFEST resource (Windows/MinGW only) for visual-styled common controls.
# Manifest resource object (named without a ".rc.o" double-extension to avoid a
# spurious GNU make circular-dependency warning). Arch-specific: the build script
# removes win/*.o between cross-compiles.
win/manifest_res.o: win/zpaq-std.rc win/zpaq-std.manifest
	$(CROSS_COMPILE)windres -I win win/zpaq-std.rc -o $@

compressors/fl2/%.o: compressors/fl2/%.c
	$(CC) $(ZPAQ_CFLAGS) $(FL2INC) -c $< -o $@

compressors/lz5/%.o: compressors/lz5/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LZ5INC) -c $< -o $@

compressors/lizard/%.o: compressors/lizard/%.c compressors/lizard/entropy/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LIZINC) -c $< -o $@

# Static pattern rules (specific files only, to avoid generic %.o:%.c match)
$(BZIP2OBJ): compressors/bzip2/%.o: compressors/bzip2/%.c
	$(CC) $(ZPAQ_CFLAGS) $(BZIP2INC) -c $< -o $@

$(BZIP3OBJ): compressors/bzip3/%.o: compressors/bzip3/%.c
	$(CC) $(ZPAQ_CFLAGS) $(BZIP3INC) -c $< -o $@

$(BROTLI_COMMON_OBJ): compressors/brotli/common/%.o: compressors/brotli/common/%.c
	$(CC) $(ZPAQ_CFLAGS) $(BROTLIINC) -c $< -o $@

$(BROTLI_ENC_OBJ): compressors/brotli/enc/%.o: compressors/brotli/enc/%.c
	$(CC) $(ZPAQ_CFLAGS) $(BROTLIINC) -c $< -o $@

$(BROTLI_DEC_OBJ): compressors/brotli/dec/%.o: compressors/brotli/dec/%.c
	$(CC) $(ZPAQ_CFLAGS) $(BROTLIINC) -c $< -o $@

# Snappy is C++; uses g++ directly
$(SNAPPYOBJ): compressors/snappy/%.o: compressors/snappy/%.cc
	$(CXX) $(ZPAQ_CXXFLAGS) $(SNAPPYINC) -c $< -o $@

# libdeflate: pure C, multi-subdir (like brotli). Use disjoint vars to avoid warnings.
$(LIBDEFLATE_CORE_OBJ): compressors/libdeflate/lib/%.o: compressors/libdeflate/lib/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LIBDEFLATEINC) -c $< -o $@

$(LIBDEFLATE_X86_OBJ): compressors/libdeflate/lib/x86/%.o: compressors/libdeflate/lib/x86/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LIBDEFLATEINC) -c $< -o $@

$(LIBDEFLATE_ARM_OBJ): compressors/libdeflate/lib/arm/%.o: compressors/libdeflate/lib/arm/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LIBDEFLATEINC) -c $< -o $@

# preflate: C++ (g++), root + support/ subdirs. -DZ_SOLO -DNO_GZIP matches upstream.
$(PREFLATE_ROOT_OBJ): compressors/preflate/%.o: compressors/preflate/%.cpp
	$(CXX) $(ZPAQ_CXXFLAGS) $(PREFLATEINC) -DZ_SOLO -DNO_GZIP -c $< -o $@

$(PREFLATE_SUP_OBJ): compressors/preflate/support/%.o: compressors/preflate/support/%.cpp
	$(CXX) $(ZPAQ_CXXFLAGS) $(PREFLATEINC) -DZ_SOLO -DNO_GZIP -c $< -o $@

# lzlib: single .c that #includes all other lzlib .c files (designed as one TU)
$(LZLIBOBJ): compressors/lzlib/%.o: compressors/lzlib/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LZLIBINC) -c $< -o $@

# ppmd (PPMd var.H, public domain): Ppmd7 model + range enc/dec + one-shot wrapper
$(PPMDOBJ): compressors/ppmd/%.o: compressors/ppmd/%.c
	$(CC) $(ZPAQ_CFLAGS) $(PPMDINC) -c $< -o $@

# heatshrink: encoder, decoder and one-shot wrapper
$(HSOBJ): compressors/hs/%.o: compressors/hs/%.c
	$(CC) $(ZPAQ_CFLAGS) $(HSINC) -c $< -o $@

# LZFSE: encoder, decoder, base, FSE, LZVN tables
$(LZFSEOBJ): compressors/lzfse/%.o: compressors/lzfse/%.c
	$(CC) $(ZPAQ_CFLAGS) $(LZFSEINC) -c $< -o $@

# bsc (libbsc): block sorting lossless compression. C++ library, all .cpp files.
$(BSCOBJ): compressors/bsc/%.o: compressors/bsc/%.cpp
	$(CXX) $(ZPAQ_CXXFLAGS) $(BSCINC) -c $< -o $@

# LZHAM (richgel999): LZMA-class codec. C++ library, all .cpp files.
$(LZHAMOBJ): compressors/lzham/%.o: compressors/lzham/%.cpp
	$(CXX) $(ZPAQ_CXXFLAGS) $(LZHAMINC) -c $< -o $@

# 32-bit build (i386/i686 Linux). Uses g++-multilib's 32-bit libstdc++ +
# zlib via the _GLIBCXX_USE_CXX11_ABI=0 override (added to ZPAQ_CXXFLAGS)
# to link against the older 32-bit C++ runtime. JIT (x86) still works.
m32: clean
	CXXFLAGS="-m32" CFLAGS="-m32" make build
	@echo "32-bit build completed (i386/i686)"

# Debug
debug: ZPAQ_CXXFLAGS = -g -O0 -Wall -Wextra -pthread
debug: $(PROG)
	@echo "Debug build completed"

# Force NOJIT even on Intel
nointel: ZPAQ_CPPFLAGS := $(filter-out $(INTEL_FLAGS),$(ZPAQ_CPPFLAGS)) -DNOJIT
nointel: clean build
	@echo "Built without JIT (forced)"

# Static build
static: LDFLAGS += -static
static: clean build
	@echo "Static build completed (no SFTP)"

# Install (cp + chmod for maximum portability, including old Solaris)
install: build
	$(MKDIR) $(DESTDIR)$(BINDIR)
	-$(RM) $(DESTDIR)$(BINDIR)/$(PROG) 2>/dev/null
	cp $(PROG) $(DESTDIR)$(BINDIR)/$(PROG)
	chmod 0755 $(DESTDIR)$(BINDIR)/$(PROG)
	-$(STRIP) $(DESTDIR)$(BINDIR)/$(PROG) 2>/dev/null || true
	@if [ ! -e $(DESTDIR)$(BINDIR)/$(ALTNAME) ] && [ ! -L $(DESTDIR)$(BINDIR)/$(ALTNAME) ]; then \
		echo "Creating symbolic link $(DESTDIR)$(BINDIR)/$(ALTNAME)"; \
		$(LN) $(PROG) $(DESTDIR)$(BINDIR)/$(ALTNAME); \
	else \
		echo "$(ALTNAME) already exists, skipping"; \
	fi

install-clean: install clean
	@echo "Installed and local binary cleaned"

install-nointel: ZPAQ_CPPFLAGS := $(filter-out $(INTEL_FLAGS),$(ZPAQ_CPPFLAGS)) -DNOJIT
install-nointel: clean build install
	@echo "Installed without JIT (forced)"

uninstall:
	$(RM) $(DESTDIR)$(BINDIR)/$(PROG)
	@if [ -L $(DESTDIR)$(BINDIR)/$(ALTNAME) ]; then \
		echo "Removing symbolic link $(DESTDIR)$(BINDIR)/$(ALTNAME)"; \
		$(RM) $(DESTDIR)$(BINDIR)/$(ALTNAME); \
	else \
		echo "$(ALTNAME) not found, skipping"; \
	fi

# Download helper
_do_download:
	@echo "------------------------------------------------------------"
	@echo "Source : $(SOURCE)"
	@echo "URL    : $(FETCH_URL)"
	@echo "------------------------------------------------------------"
	@$(RM) $(PROG) $(SOURCE)
	@if command -v wget >/dev/null 2>&1; then \
		echo "Downloader : wget"; \
		wget --no-check-certificate -L --progress=bar:force:noscroll "$(FETCH_URL)" -O "$(SOURCE)" 2>/dev/null \
		|| wget --no-check-certificate -L -q "$(FETCH_URL)" -O "$(SOURCE)"; \
		_RC=$$?; \
		if [ $$_RC -ne 0 ] || [ ! -s "$(SOURCE)" ]; then \
			echo "Error: wget failed or empty file."; \
			$(RM) "$(SOURCE)"; exit 1; \
		fi; \
		echo "Download OK (wget)."; \
	elif command -v curl >/dev/null 2>&1; then \
		echo "Downloader : curl"; \
		curl -k -L --fail --progress-bar "$(FETCH_URL)" -o "$(SOURCE)" 2>/dev/null \
		|| curl -k -L --fail -s "$(FETCH_URL)" -o "$(SOURCE)"; \
		_RC=$$?; \
		if [ $$_RC -ne 0 ] || [ ! -s "$(SOURCE)" ]; then \
			echo "Error: curl failed or empty file."; \
			$(RM) "$(SOURCE)"; exit 1; \
		fi; \
		echo "Download OK (curl)."; \
	elif command -v fetch >/dev/null 2>&1; then \
		echo "Downloader : fetch (BSD)"; \
		fetch -o "$(SOURCE)" "$(FETCH_URL)"; \
		_RC=$$?; \
		if [ $$_RC -ne 0 ] || [ ! -s "$(SOURCE)" ]; then \
			echo "Error: fetch failed or empty file."; \
			$(RM) "$(SOURCE)"; exit 1; \
		fi; \
		echo "Download OK (fetch)."; \
	else \
		echo "Error: no download tool (wget/curl/fetch)."; \
		exit 1; \
	fi

# Download targets: pass FETCH_URL as a make variable to the sub-make
nightly:
	$(MAKE) --no-print-directory _do_download FETCH_URL="$(SOURCE_URL_NIGHTLY)"

download:
	$(MAKE) --no-print-directory _do_download FETCH_URL="$(SOURCE_URL_DOWNLOAD)"

downloads:
	$(MAKE) --no-print-directory _do_download FETCH_URL="$(SOURCE_URL_GITHUB)"

# Test
test: build
	@if [ -x "./$(PROG)" ]; then ./$(PROG) autotest -all; else echo "Run 'make' first"; exit 1; fi

test-nointel: nointel
	@if [ -x "./$(PROG)" ]; then ./$(PROG) autotest -all; else echo "Run 'make nointel' first"; exit 1; fi

clean:
	$(RM) $(PROG)

# Check (with JIT and SFTP status)
check:
	@echo "OS           : $(UNAME_S)"
	@echo "Architecture : $(UNAME_M)"
	@echo "Compiler     : $(CXX)"
	@$(CXX) --version 2>&1 | head -n 5 || $(CXX) -v 2>&1 | head -n 5 || echo "(version not available)"
	@echo "ZPAQ_CPPFLAGS: $(ZPAQ_CPPFLAGS)"
	@echo "ZPAQ_CXXFLAGS: $(ZPAQ_CXXFLAGS)"
	@echo "LDLIBS       : $(LDLIBS)"
	@echo "JIT enabled  : $(if $(findstring -DNOJIT,$(ZPAQ_CPPFLAGS)),no (non-x86 or forced),yes (x86))"

	@echo "BINDIR       : $(BINDIR)"
	@echo ""
	@echo "Download URLs:"
	@echo "  nightly    : $(SOURCE_URL_NIGHTLY)"
	@echo "  download   : $(SOURCE_URL_DOWNLOAD)"
	@echo "  downloads  : $(SOURCE_URL_GITHUB)"

# Help
help:
	@echo ""
	@echo "zpaq-std -- Universal Makefile (Build 1.6)"
	@echo ""
	@echo "Build:"
	@echo "  make                   Compile zpaq-std (JIT auto on x86 only)"
	@echo "  make static            Static build (NAS, containers, rescue)"
	@echo "  make nointel           Force without JIT (even on Intel)"
	@echo "  make debug             Debug build (no optimization)"
	@echo ""
	@echo "Options:"

	@echo "  CROSS_COMPILE=prefix-  Cross-compile (e.g. aarch64-linux-gnu-)"
	@echo ""
	@echo "Install / Uninstall:"
	@echo "  make install           Install in $(BINDIR)"
	@echo "  make install-clean     Compile + install + clean local"
	@echo "  make install-nointel   Install without JIT"
	@echo "  make uninstall         Remove zpaq-std (and 'dir' symlink) from system"
	@echo ""
	@echo "Download source (three choices, pick one):"
	@echo "  make nightly           Nightly (latest, risky!)"
	@echo "  make download          Latest official release from my site"
	@echo "  make downloads         Stable from GitHub with https"
	@echo ""
	@echo "Test:"
	@echo "  make test              Full tests"
	@echo "  make test-nointel      Tests on no-JIT build"
	@echo ""
	@echo "Utility:"
	@echo "  make check             Show configuration (JIT status)"
	@echo "  make clean             Delete local binary"
	@echo "  make help              This message"
	@echo ""
	@echo "Note for BSD/Solaris: use 'gmake' instead of 'make'"
