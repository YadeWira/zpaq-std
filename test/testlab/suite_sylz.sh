#!/bin/bash
# ============================================================================
# suite_sylz.sh -- -ma:sylz (experimental, plugin only, ZPAQSYLZ).
#
# POR QUE EXISTE: sylz es el primer codec que va SOLO como plugin (Free Pascal):
# el binario completo tiene que cargarlo de codecs/, negarse sin el (00605), y los
# bloques tienen que extraerse sin plugin por su ZPAQL (zpaq 7.15 y zpaq-std sin
# codecs/), igual que con el plugin. Y un bloque danado no puede tardar minutos.
#
#   uso: PLUG=.../sylz.so suite_sylz.sh   (Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
PLUG=${PLUG:-/home/forum/git/zpaq-std/plugins/codecs/sylz.so}
SRC=${SRC:-/mnt/IA_LAB/agentes/ZPAQ-STD/bugs/stress/src}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-sylz}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/con/codecs" "$OUT/sin"; cd "$OUT"
cp "$Z" con/zpaq-std; cp "$PLUG" con/codecs/sylz.so; cp "$Z" sin/zpaq-std
malos=0; casos=0
ok() { casos=$((casos+1)); [ "$2" = ok ] || malos=$((malos+1)); printf '  %-46s %s\n' "$1" "$2"; }

sin/zpaq-std a n.zpaq $SRC/deep -ma:sylz </dev/null >n.log 2>&1; rc=$?
[ $rc = 2 ] && grep -qa '00605' n.log && r=ok || r="rc=$rc sin 00605"; ok "sin plugin, a se niega" "$r"
for l in 1 6 12; do
  rm -rf x; con/zpaq-std a s$l.zpaq $SRC/tree -ma:sylz:$l </dev/null >a.log 2>&1; ra=$?
  r=ok; [ $ra = 0 ] || r="a rc=$ra"
  grep -qa '00603' a.log || r="$r sin-aviso-experimental"
  con/zpaq-std t s$l.zpaq >/dev/null 2>&1 || r="$r t-falla"
  for zz in "con/zpaq-std x s$l.zpaq -to x" "sin/zpaq-std x s$l.zpaq -to y" "/usr/bin/zpaq x s$l.zpaq -to z"; do
    d=${zz##* }; rm -rf $d; $zz >/dev/null 2>&1
    diff -r $SRC/tree $d$SRC/tree >/dev/null 2>&1 || r="$r $d-distinto"
  done
  ok "-ma:sylz:$l a, t, x (plugin, ZPAQL, zpaq 7.15)" "$r"
done
# bloque danado: el ZPAQL no puede escribir mas que el original ni tardar
cp s6.zpaq d.zpaq; python3 - <<'PY'
import random
b=bytearray(open('d.zpaq','rb').read()); random.seed(5)
for _ in range(40): b[random.randrange(len(b)//4, len(b))]^=255
open('d.zpaq','wb').write(b)
PY
s=$(date +%s); rm -rf w; timeout 120 sin/zpaq-std x d.zpaq -to w </dev/null >/dev/null 2>&1; rc=$?; e=$(date +%s)
[ $rc != 124 ] && [ $((e-s)) -lt 60 ] && r=ok || r="rc=$rc $((e-s))s"; ok "archivo danado, ZPAQL sin plugin termina" "$r"
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_SYLZ
