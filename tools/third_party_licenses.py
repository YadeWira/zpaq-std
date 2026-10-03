#!/usr/bin/env python3
# Builds THIRD-PARTY-LICENSES.txt: what the release binary of zpaq-std contains from
# other authors, and the full text of each licence. Run from the repository root:
#     python3 tools/third_party_licenses.py > THIRD-PARTY-LICENSES.txt
# The list follows the Makefile (what is compiled in) and the -ma table of README.md
# (versions). Each bundled library keeps its licence next to its code, in
# compressors/<dir>/LICENSE; the part inherited from zpaqfranz is the credits block at
# the top of zpaq-std.cpp, without the NOSFTP sections that the "open" build leaves out.
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (name, version, licence, authors, licence file(s), note)
BUNDLED = [
    ('zstd', '1.5.7', 'BSD-3-Clause (dual BSD / GPLv2: BSD chosen)', 'Meta Platforms, Inc. and affiliates',
     ['compressors/zstd/LICENSE'], ''),
    ('brotli', '1.2.0', 'MIT', 'Google Inc.', ['compressors/brotli/LICENSE'], ''),
    ('LZMA SDK', '26.03', 'Public domain', 'Igor Pavlov', ['compressors/lzmasdk/LICENSE'], ''),
    ('fast-lzma2', '1.0.1', 'BSD-3-Clause (dual BSD / GPLv2: BSD chosen)', 'Conor McCarthy',
     ['compressors/fl2/LICENSE'], 'Parts based on zstd, copyright Yann Collet.'),
    ('ultra-fast-lzma2', '1.6.0', 'BSD-3-Clause', 'Conor McCarthy (fast-lzma2), fork by YadeWira',
     ['compressors/uflzma2/LICENSE'], ''),
    ('lzlib', '1.16', 'BSD-2-Clause', 'Antonio Diaz Diaz', ['compressors/lzlib/LICENSE'], ''),
    ('bzip2 / libbzip2', '1.0.8', 'bzip2 licence (BSD-style)', 'Julian R Seward', ['compressors/bzip2/LICENSE'], ''),
    ('libdeflate', '1.26', 'MIT', 'Eric Biggers', ['compressors/libdeflate/LICENSE'], ''),
    ('Lizard', '2.1', 'BSD-2-Clause (library)', 'Yann Collet, Przemyslaw Skibinski', ['compressors/lizard/LICENSE'], ''),
    ('lz5-ex', 'commit 5541227', 'BSD-2-Clause', 'Yann Collet, Przemyslaw Skibinski (LZ5), YadeWira (lz5-ex)',
     ['compressors/lz5/LICENSE'], 'A fork of LZ5 1.5 with the same block format.'),
    ('lz6', 'see compressors/lz6/VERSION', 'BSD-2-Clause', 'Yann Collet (LZ4), YadeWira', ['compressors/lz6/LICENSE'], ''),
    ('Snappy', '1.2.1', 'BSD-3-Clause', 'Google Inc.', ['compressors/snappy/LICENSE'], ''),
    ('LZFSE', '-', 'BSD-3-Clause', 'Apple Inc.', ['compressors/lzfse/LICENSE'], ''),
    ('heatshrink', '0.4.1', 'ISC', 'Scott Vokes', ['compressors/hs/LICENSE'], ''),
    ('bzip3', '1.5.4', 'LGPL-3.0-or-later', 'Kamila Szewczyk',
     ['compressors/bzip3/LICENSE', 'compressors/bzip3/COPYING.GPL-3'],
     'bzip3 is linked statically. Its source, as built, is part of zpaq-std\'s source\n'
     'code (compressors/bzip3/ in https://github.com/YadeWira/zpaq-std), so a modified\n'
     'bzip3 can be built into zpaq-std from it. The LGPL is an addition to the GNU GPL,\n'
     'so the text of both follows. bzip3 includes libsais (Ilya Grebnov, Apache-2.0,\n'
     'text under libbsc below).'),
    ('libbsc', '3.3.12', 'Apache-2.0', 'Ilya Grebnov', ['compressors/bsc/LICENSE'],
     'Includes libsais (Ilya Grebnov), also Apache-2.0. No NOTICE file is distributed\n'
     'with either.'),
    ('LZHAM', '1.0', 'MIT', 'Richard Geldreich, Jr.', ['compressors/lzham/LICENSE'], ''),
    ('PPMd var.H (Ppmd7)', '7-Zip / LZMA SDK', 'Public domain', 'Dmitry Shkarin, Igor Pavlov',
     ['compressors/ppmd/LICENSE-PPMD.txt'], ''),
    ('kanzi', '2.6.0', 'Apache-2.0', 'Frederic Langlet', ['compressors/kanzi/LICENSE'],
     'No NOTICE file is distributed with kanzi. kanzi_zpaqstd.cpp/.h are zpaq-std\'s own.'),
    ('libdivsufsort', '2.0 (stripped)', 'MIT', 'Yuta Mori', ['libdivsufsort/LICENSE'], ''),
    ('ZPAQLZMA decoder', '-', 'see text', 'kaitz', ['compressors/zpaqlzma/LICENSE'],
     'The ZPAQL program that decodes -ma:lzma blocks in any zpaq.'),
]

def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8', errors='replace') as f:
        return f.read().rstrip('\n') + '\n'

def inherited():
    src = read('zpaq-std.cpp').split('\n')
    a = next(i for i, l in enumerate(src) if l.startswith('Credits and copyrights and licenses and links'))
    b = next(i for i in range(a + 1, len(src)) if '_____ _____  ______ ______ _______ _____' in src[i])
    # curl (entry 24) is only used by the full build's SFTP/HTTP code: not in the open build
    out, skip, drop = [], False, False
    for l in src[a:b]:
        if '///NOSFTPSTART' in l.replace(' ', ''): skip = True; continue
        if '///NOSFTPEND' in l.replace(' ', ''): skip = False; continue
        m = re.match(r'\s?\d+ \[', l)
        if m: drop = 'curl.se' in l
        if skip or drop or re.match(r'\s*///\s*LICENSE_(START|END)\.\d+', l): continue
        out.append(l.rstrip())
    while out and out[-1] == '': out.pop()
    return '\n'.join(out) + '\n'

def main():
    w = sys.stdout.write
    bar = '=' * 79 + '\n'
    w('THIRD-PARTY LICENSES of zpaq-std\n' + bar)
    w('zpaq-std itself is MIT (see LICENSE). Its release binaries also contain the\n'
      'software below, each under its own licence. Part 1 lists the compressors that\n'
      'zpaq-std bundles under compressors/ (and libdivsufsort); part 2 is what zpaq-std\n'
      'inherits from zpaqfranz, as zpaqfranz itself credits it. The full text of every\n'
      'licence follows its entry. Generated by tools/third_party_licenses.py.\n\n')
    w('PART 1 - BUNDLED COMPRESSORS\n' + bar)
    for n, v, lic, who, _, _ in BUNDLED:
        w(f'  {n:<20} {v:<28} {lic}\n')
    w('\n')
    for n, v, lic, who, files, note in BUNDLED:
        w(bar + f'{n} {v}\nLicence: {lic}\nCopyright: {who}\n')
        if note: w(note + '\n')
        w('\n')
        for f in files:
            if len(files) > 1: w(f'--- {os.path.basename(f)} ---\n')
            w(read(f) + '\n')
    w(bar + 'PART 2 - INHERITED FROM ZPAQFRANZ (embedded in zpaq-std.cpp)\n' + bar)
    w(inherited())

main()
