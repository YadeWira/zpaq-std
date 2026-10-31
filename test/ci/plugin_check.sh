#!/bin/bash
# CI: the Free Pascal plugins (sylz with sylzec, and pja), built with make fpc-plugins,
# load in the full program, and sylz and sylzec compress and extract a fixed tree at
# several levels. The archives' SHA-256 go to plughashes-<platform>.txt, for
# same_bytes.sh. pja: its ten codecs (five and their z variants) must be listed by codecinfo.
#   test/ci/plugin_check.sh <zpaq-std binary> <codecs dir> <platform name>
# NOPJA=1 leaves pja out (macOS, until a PJA release exports Darwin's names).
set -u
Z=$1; C=$2; PLAT=$3
W=ci-plug; rm -rf "$W"; mkdir -p "$W/codecs" "$W/data/sub"
cp "$Z" "$W/zpaq-std"; cp "$C"/sylz.* "$W/codecs/"; [ -n "${NOPJA:-}" ] || cp "$C"/pja.* "$W/codecs/"
cp README.md CHANGELOG.md LICENSE "$W/data/"; cp compressors/bsc/PATCHES "$W/data/sub/"
head -c 300000 THIRD-PARTY-LICENSES.txt > "$W/data/sub/tpl.txt"
find "$W/data" -exec touch -d '2026-01-01T12:00:00Z' {} +
cd "$W" || exit 1
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -c1-64; }
bad=0; n=0; : > "../plughashes-$PLAT.txt"
info=$(./zpaq-std codecinfo 2>&1 | tr -d '\r')
for c in sylz sylzec; do
  echo "$info" | grep -E "^$c " | grep -v MISSING | grep -q "codecs/sylz" || { echo "FAIL $c not loaded from codecs/"; bad=$((bad+1)); }
done
[ -n "${NOPJA:-}" ] || for c in pja pjax pjall pjals pjalsx pjaz pjaxz pjallz pjalsz pjalsxz; do
  echo "$info" | grep -qE "^ +pja:$c +pja stream" || { echo "FAIL pja:$c not loaded"; bad=$((bad+1)); }
done
if [ $bad != 0 ]; then   # why: the exported names, and what dlopen says
  for f in codecs/sylz.* codecs/pja.*; do
    echo "== $f"; nm -g "$f" 2>/dev/null | grep -i zpaqstd
    python3 -c "
import ctypes, sys
try:
    l = ctypes.CDLL(sys.argv[1])
    for n in ('zpaqstd_codec_v1', 'zpaqstd_codecs_v1', 'zpaqstd_detect_v1'):
        print(n, hasattr(l, n))
except OSError as e:
    print('dlopen:', e)
" "$PWD/$f"
  done
fi
for m in sylz:0 sylz:1 sylz:5 sylz:10 sylzec:0 sylzec:1 sylzec:9; do
  n=$((n+1)); f=p$n.zpaq
  if ! ./zpaq-std a $f data -ma:$m -timestamp 2026-01-01_00:00:00 -nofast -noattributes -nomore >a.log 2>&1; then echo "FAIL a $m"; tail -3 a.log; bad=$((bad+1)); continue; fi
  rm -rf x; ./zpaq-std x $f -to x -nomore >/dev/null 2>&1
  diff -r data x/data >/dev/null 2>&1 || { echo "FAIL x $m"; bad=$((bad+1)); }
  echo "-ma:$m $(sha256 $f)" >> "../plughashes-$PLAT.txt"
done
# pja: a JPEG made here (a test pattern, through sips on macOS or ImageMagick), -sa
# compresses it with pja and gives it back identical. Skipped if there is no tool.
if [ -z "${NOPJA:-}" ]; then
  python3 - <<'PY'
import struct, math
w, h = 2048, 1536
def px(x, y):
    return (int(127+120*math.sin(x/23.0)), int(127+120*math.cos(y/17.0)), int(127+100*math.sin((x+y)/41.0)))
raw = b''.join(bytes(px(x, y)) for y in range(h) for x in range(w))
# minimal uncompressed RGB TIFF: what sips and ImageMagick both read
ent = [(256,3,1,w),(257,3,1,h),(258,3,3,0),(259,3,1,1),(262,3,1,2),(273,4,1,0),(277,3,1,3),(278,3,1,h),(279,4,1,len(raw))]
ifd_off = 8; n = len(ent); bps_off = ifd_off + 2 + 12*n + 4; data_off = bps_off + 6
out = bytearray(b'II*\x00' + struct.pack('<I', ifd_off) + struct.pack('<H', n))
for tag, typ, cnt, val in ent:
    if tag == 258: val = bps_off
    if tag == 273: val = data_off
    out += struct.pack('<HHI', tag, typ, cnt) + (struct.pack('<HH', val, 0) if typ == 3 and cnt == 1 else struct.pack('<I', val))
out += struct.pack('<I', 0) + struct.pack('<HHH', 8, 8, 8) + raw
open('pat.tif', 'wb').write(out)
PY
  mkdir -p jpg
  if command -v sips >/dev/null; then sips -s format jpeg pat.tif --out jpg/pat.jpg >/dev/null 2>&1
  elif command -v magick >/dev/null; then magick pat.tif -quality 90 jpg/pat.jpg
  elif command -v convert >/dev/null; then convert pat.tif -quality 90 jpg/pat.jpg; fi
  if [ -s jpg/pat.jpg ]; then
    ./zpaq-std a s.zpaq jpg -sat:pja:pjax+2:pja+2:pjall+2:pjals+2:pjalsx+2 -nomore >sa.log 2>&1
    # since 1.10.0 a file alone also goes as pjaz (the LZ77 variant) when that takes fewer bytes
    grep -qE "jpg/pat.jpg: pjaz?,.*plugin decode .* OK; (pjaz )?ZPAQL OK" sa.log || { echo "FAIL -sa: no pja block for the JPEG"; grep -i "pat.jpg" sa.log; bad=$((bad+1)); }
    rm -rf x; ./zpaq-std x s.zpaq -to x -nomore >/dev/null 2>&1
    cmp -s jpg/pat.jpg x/jpg/pat.jpg && echo "-sa with pja: $(wc -c < jpg/pat.jpg) bytes back identical" || { echo "FAIL -sa x"; bad=$((bad+1)); }
  else echo "no JPEG tool: -sa with pja not checked"; fi
fi
echo "$PLAT plugins: $n methods, $bad failures"
[ $bad = 0 ]
