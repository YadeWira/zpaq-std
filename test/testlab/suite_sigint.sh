#!/bin/bash
# ============================================================================
# suite_sigint.sh -- control-C (SIGINT) durante a y backup.
#
# POR QUE EXISTE: BUG-022/023 (heredados de zpaqfranz 65.4m). El manejador cerraba
# el archivo mientras el hilo escritor escribia (pre63), y cerraba OTRA VEZ un
# archivo que add ya habia cerrado: un control-C durante el MD5 de backup daba
# "double free" (1.0.2). glibc solo lo detecta a veces; la senal fija es que el
# manejador diga "Closing file handle" despues de "Creating MD5".
#
#   uso: suite_sigint.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
SRC=${SRC:-/mnt/IA_LAB/agentes/ZPAQ-STD/bugs/stress/src}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-sigint}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
malos=0; casos=0

# 1) control-C durante el MD5 de backup (el archivo ya esta cerrado)
for i in 1 2 3 4 5; do
  casos=$((casos+1)); rm -f bk*
  (cd $SRC && $Z backup "$OUT/bk.zpaq" deep -noeta </dev/null >/dev/null 2>&1)
  (cd $SRC && exec $Z backup "$OUT/bk.zpaq" bigr -noeta </dev/null >"$OUT/b.log" 2>&1) & P=$!
  for k in $(seq 4000); do grep -qa 'Creating MD5' b.log && break; kill -0 $P 2>/dev/null || break; sleep 0.005; done
  kill -INT $P 2>/dev/null; wait $P 2>/dev/null; rc=$?
  r=ok
  grep -qa 'Creating MD5' b.log || r="no-llego-al-MD5"
  sed -n '/Creating MD5/,$p' b.log | grep -qa 'Closing file handle' && r="CIERRA-DOS-VECES"
  [ $rc = 134 ] || grep -qa 'free()' b.log && r="$r ABORTO"
  ls bk*.pid >/dev/null 2>&1 && r="$r pid-olvidado"
  (cd $SRC && timeout 120 $Z backup "$OUT/bk.zpaq" deep -noeta </dev/null >/dev/null 2>&1) || r="$r backup-siguiente-falla"
  [ "$r" = ok ] || malos=$((malos+1))
  printf '  backup, control-C en el MD5 %s: %s\n' $i "$r"
done

# 2) control-C en medio de a: vuelve atras, exacto, y pasa t
$Z a base.zpaq $SRC/deep -noeta >/dev/null 2>&1
for i in 1 2 3 4 5 6; do
  casos=$((casos+1)); cp base.zpaq k.zpaq
  d=$(awk -v s=$((RANDOM+i)) 'BEGIN{srand(s); printf "%.2f", 0.3+rand()*2}')
  $Z a k.zpaq $SRC/bigr -m1 -t4 -noeta </dev/null >a.log 2>&1 & P=$!
  sleep $d; kill -INT $P 2>/dev/null; wait $P 2>/dev/null; rc=$?
  r=ok
  [ $rc = 134 ] || grep -qa 'free()' a.log && r="ABORTO"
  if grep -qa 'rolling back' a.log; then cmp -s base.zpaq k.zpaq || r="$r no-vuelve-exacto"; fi
  $Z t k.zpaq -noeta >/dev/null 2>&1 || r="$r t-falla"
  [ "$r" = ok ] || malos=$((malos+1))
  printf '  a, control-C a %ss: %s\n' $d "$r"
done
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_SIGINT
