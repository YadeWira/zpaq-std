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

# Default tools
RM      ?= rm -f
MKDIR   ?= mkdir -p
LN      ?= ln -sf
STRIP   ?= $(CROSS_COMPILE)strip

# Program details
PROG    := zpaq-std
ALTNAME := dir
SOURCE  := zpaq-std.cpp
LZ4SRC  := compressors/lz4/lz4.c compressors/lz4/lz4hc.c
LZ5SRC  := compressors/lz5/lz5.c compressors/lz5/lz5hc.c
ZSTDSRC := compressors/zstd/zstd.c
FL2SRC  := compressors/fl2/fl2_common.c compressors/fl2/fl2_compress.c compressors/fl2/fl2_decompress.c compressors/fl2/fl2_pool.c compressors/fl2/fl2_threading.c compressors/fl2/lzma2_dec.c compressors/fl2/lzma2_enc.c compressors/fl2/radix_bitpack.c compressors/fl2/radix_mf.c compressors/fl2/radix_struct.c compressors/fl2/range_enc.c compressors/fl2/dict_buffer.c compressors/fl2/util.c
LIZSRC  := compressors/lizard/lizard_compress.c compressors/lizard/lizard_decompress.c compressors/lizard/entropy/entropy_common.c compressors/lizard/entropy/debug.c compressors/lizard/entropy/fse_compress.c compressors/lizard/entropy/fse_decompress.c compressors/lizard/entropy/hist.c compressors/lizard/entropy/huf_compress.c compressors/lizard/entropy/huf_decompress.c
BZIP2SRC := compressors/bzip2/blocksort.c compressors/bzip2/bzlib.c compressors/bzip2/compress.c compressors/bzip2/crctable.c compressors/bzip2/decompress.c compressors/bzip2/huffman.c compressors/bzip2/randtable.c
BZIP3SRC := compressors/bzip3/libbz3.c
BROTLISRC := $(wildcard compressors/brotli/common/*.c compressors/brotli/enc/*.c compressors/brotli/dec/*.c)
SNAPPYSRC := compressors/snappy/snappy.cc compressors/snappy/snappy-c.cc compressors/snappy/snappy-sinksource.cc compressors/snappy/snappy-stubs-internal.cc
ZSTDINC := -Icompressors/zstd
FL2INC  := -Icompressors/fl2 -DNO_XXHASH
LZ5INC  := -Icompressors/lz5
LIZINC  := -Icompressors/lizard -Icompressors/lizard/entropy
BZIP2INC := -Icompressors/bzip2
BZIP3INC := -Icompressors/bzip3 -DVERSION='"1.5.3"' -Wno-unused-function
BROTLIINC := -Icompressors/brotli/include
SNAPPYINC := -Icompressors/snappy -Wno-sign-compare
ZPAQ_CFLAGS := $(CFLAGS) -O3 -pthread -Wall

# Download URLs
SOURCE_URL_NIGHTLY  := http://www.francocorbelli.it/zpaq-std.cpp
SOURCE_URL_DOWNLOAD := http://www.francocorbelli.it/zpaq-std/win64/zpaq-std.cpp
SOURCE_URL_GITHUB   := https://raw.githubusercontent.com/fcorbelli/zpaq-std/main/zpaq-std.cpp

# User-overridable flags (safe to pass from command line or packaging systems)
CXXFLAGS ?= -O3
CPPFLAGS ?=

# Project-required flags (always present; user flags are appended)
ZPAQ_CXXFLAGS := -Wall -pthread $(CXXFLAGS)
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

$(PROG): $(SOURCE) $(LZ4SRC) $(ZSTDSRC) $(FL2OBJ) $(LZ5OBJ) $(LIZOBJ) $(BZIP2OBJ) $(BZIP3OBJ) $(BROTLIOBJ) $(SNAPPYOBJ)
	$(CXX) $(ZPAQ_CPPFLAGS) $(ZPAQ_CXXFLAGS) $(ZSTDINC) $(LDFLAGS) $(SOURCE) $(LZ4SRC) $(ZSTDSRC) $(FL2OBJ) $(LZ5OBJ) $(LIZOBJ) $(BZIP2OBJ) $(BZIP3OBJ) $(BROTLIOBJ) $(SNAPPYOBJ) $(LDLIBS) -o $@

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
