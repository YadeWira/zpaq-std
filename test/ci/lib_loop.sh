#!/bin/bash
# libzpaqstd in CI: lib_loop.sh <linux64|linux86|win64|win32> [folder of the library] [hashes of linux64]
# Each case three times in one process (there and back, the same bytes each time); the archives' hashes
# are written to hashes.txt and, with a reference, compared with it. Windows: 40 runs that unload the
# library before the process ends (what a corrupted heap showed on, see libzpaqstd.cpp).
set -u
T=$1; D=${2:-lib/out/$T}; REF=${3:-}
head -c 3000000 zpaq-std.cpp > lib_in.bin
case $T in
  linux64) gcc -O1 lib/lib_loop.c -o $D/lib_loop -ldl; RUN="$D/lib_loop $D/libzpaqstd.so";;
  linux86) gcc -O1 -m32 lib/lib_loop.c -o $D/lib_loop -ldl; RUN="$D/lib_loop $D/libzpaqstd.so";;
  win64|win32) RUN="$D/lib_loop.exe $D/zpaqstd.dll";;
  *) echo "target?"; exit 2;;
esac
bad=0; : > hashes-lib.txt
export LIBD=-t4
for c in "-m00" "-m10" "-m22" "-m32" "-m10 -ma:zstd:3" "-m10 -ma:lzma:6" "-m10 -ma:flzma2:5" "-m10 -ma:bsc:3" "-m10 -ma:kanzi:2" "-m10 -ma:ppmd:6" "-m10 -ma:brotli:5" "-m10 -ma:zxc:3" "-m10 -ma:bz2:9" "-m10 -ma:lzh:2"; do
  out=$($RUN lib_in.bin 3 $c -t4 2>&1); rc=$?
  line=$(echo "$out" | grep '^rounds' | tr -d '\r')
  h=$(echo "$line" | sed -n 's/.*archive \([0-9a-f]*\).*/\1/p')
  echo "$c: rc=$rc $(echo "$line" | cut -d'|' -f1-3)"
  echo "$c $h" >> hashes-lib.txt
  if [ $rc != 0 ] || [ -z "$h" ] || ! echo "$line" | grep -q 'bad 0 '; then bad=$((bad+1)); echo "  FAILED: $out" | tail -5; fi
done
out=$($RUN lib_in.bin 100 -m10 -t4 2>&1); rc=$?; echo "100 calls: rc=$rc $(echo "$out" | grep '^rounds' | tr -d '\r')"
[ $rc != 0 ] && bad=$((bad+1))
case $T in win64|win32)
  n=0
  for i in $(seq 1 40); do LIBFREE=1 $RUN lib_in.bin 2 -m00 -t1 >/dev/null 2>&1 || n=$((n+1)); done
  echo "load, d, unload x40: $n bad"; [ $n != 0 ] && bad=$((bad+1));;
esac
cp hashes-lib.txt $D/hashes.txt
REFOK=1
if [ -n "$REF" ]; then
  if diff <(tr -d '\r' < "$REF") hashes-lib.txt >/dev/null; then echo "the archives of linux64: the same"; else echo "NOT the archives of linux64:"; diff <(tr -d '\r' < "$REF") hashes-lib.txt; bad=$((bad+1)); fi
fi
rm -f lib_in.bin lib_in.bin.zpaq.tmp lib_in.bin.out.tmp hashes-lib.txt
echo "failures: $bad"
[ $bad = 0 ]
