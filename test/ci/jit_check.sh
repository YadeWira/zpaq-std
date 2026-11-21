#!/bin/bash
# CI: the JIT against the interpreter (-nojit). -m1..-m5 make the same archive both ways,
# and each archive passes t both ways; the times are printed (one thread), which is where
# a real CPU tells what the JIT is worth. With a test build (-DZS_JITTEST) the test of
# ZPAQL::assemble runs too: programs made at random, interpreter against JIT.
#   test/ci/jit_check.sh <zpaq-std binary> [test]
set -u
Z=$1; TESTBUILD=${2:-}
W=ci-jit; rm -rf "$W"; mkdir -p "$W/data"
head -c 4000000 zpaq-std.cpp > "$W/data/a.txt"
head -c 2000000 "$Z" > "$W/data/b.bin"
cp CHANGELOG.md "$W/data/"
cd "$W" || exit 1
"$Z" version 2>&1 | grep -E '^JIT ' || true
# milliseconds: date where it has %N (GNU, Termux), perl where it does not (macOS), else seconds
ms() {
  local t; t=$(date +%s%3N 2>/dev/null)
  case "$t" in
    ''|*[!0-9]*) perl -MTime::HiRes=time -e 'printf "%d", time()*1000' 2>/dev/null || echo $(( $(date +%s)*1000 )) ;;
    *) echo "$t" ;;
  esac
}
bad=0
if [ -n "$TESTBUILD" ]; then
  for seed in 1 2 3; do
    ZS_JITTEST=$seed,20000 "$Z" 2>&1 | grep JITTEST || { echo "the test of the JIT did not run"; bad=$((bad+1)); }
  done > jittest.txt
  cat jittest.txt
  grep -q ' [1-9][0-9]* DIFFERENT' jittest.txt && bad=$((bad+1))
fi
F="-t1 -nolfast -timestamp 2026-01-01_00:00:00"
for m in 1 2 3 4 5; do
  line="-m$m:"
  for v in jit nojit; do
    s=""; [ $v = nojit ] && s="-nojit"
    rm -f $v$m.zpaq
    t0=$(ms); "$Z" a $v$m.zpaq data -m$m $F $s </dev/null >a_$v$m.log 2>&1 || { echo "-m$m $v: a fails"; tail -3 a_$v$m.log; bad=$((bad+1)); }
    line="$line a $v $(( $(ms)-t0 )) ms"
  done
  if cmp -s jit$m.zpaq nojit$m.zpaq; then line="$line, same archive"; else line="$line, DIFFERENT ARCHIVES"; bad=$((bad+1)); fi
  for v in jit nojit; do
    s=""; [ $v = nojit ] && s="-nojit"
    t0=$(ms); "$Z" t jit$m.zpaq -t1 $s </dev/null >t_$v$m.log 2>&1 || { echo "-m$m $v: t fails"; tail -3 t_$v$m.log; bad=$((bad+1)); }
    line="$line, t $v $(( $(ms)-t0 )) ms"
  done
  echo "$line"
done
echo "jit_check: $bad problem(s)"
[ $bad = 0 ]
