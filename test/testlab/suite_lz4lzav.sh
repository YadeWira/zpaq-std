#!/bin/bash
# ============================================================================
# suite_lz4lzav.sh -- -ma:lz4 (lz4hc, lz4f) y -ma:lzav, para sacarlos de experimental (2.0.1).
#
# Desde 2.0.0 son códecs propios de zpaq-std otra vez (zpaqfranz los sacó en 65.5d): sus
# decodificadores ZPAQL congelados (los de -m6/-m7 de 65.3-65.4) y el camino nativo. Lo que
# tiene que valer:
#  1. cada nivel, con bloques de 16 MB (-m1) y de 64 MB (-m3): x nativo, x en zpaq 7.15 (corre
#     el ZPAQL) y t devuelven lo mismo que la fuente;
#  2. los bloques de datos son byte a byte los de zpaq-std 1.10.0 (OLD110) y 2.0.1 lee los
#     archivos de 1.10.0;
#  3. un bloque dañado (bytes cambiados en sus datos) no cuelga ni rompe: ni zpaq-std (nativo)
#     ni zpaq 7.15 (ZPAQL); un error o una salida mala están bien, un cuelgue o una señal no.
#   uso: Z=<zpaq-std> [OLD110=<zpaq-std 1.10.0>] [DANOS=N] bash suite_lz4lzav.sh
# ============================================================================
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=${W:-/mnt/IA_LAB/agentes/ZPAQ-STD/testlab}; RUN=${RUN:-zf_lz4lzav}; DANOS=${DANOS:-60}
OUT=$W/$RUN; rm -rf "${OUT:?}"; mkdir -p "$OUT/src/sub"; cd "$OUT"
casos=0; malos=0
ok(){ casos=$((casos+1)); [ "$2" = ok ] || malos=$((malos+1)); printf '  %-60s %s\n' "$1" "$2"; }
# la fuente: texto, un ejecutable, un JPEG (ya comprimido), azar y ceros (~22 MB: más de un bloque de 16 MB)
cp /home/forum/git/zpaq-std/CHANGELOG.md /home/forum/git/zpaq-std/README.md src/
head -c 9000000 "$Z" > src/sub/prog.bin
cp "$(find /mnt/OSR_D3/fileFormatSamples/fileFormatSamples/image -iname '*.jpg' -size +1M -size -4M 2>/dev/null | sort | head -1)" src/sub/photo.jpg
python3 -I -c "
import random; r=random.Random(7)
open('src/sub/random.bin','wb').write(bytes(r.getrandbits(8) for _ in range(3000000)))
open('src/sub/zeros.bin','wb').write(bytes(4000000))
t=open('src/CHANGELOG.md','rb').read()
open('src/sub/repeat.txt','wb').write((t*4)[:6000000])"
TS="-timestamp 2026-01-01_00:00:00"
# 1. cada nivel
for m in lz4:1 lz4:4 lz4:5 lz4:9 lz4:12 lz4hc:1 lz4hc:12 lz4f:1 lz4f:9 lz4f:12 lzav:0 lzav:1 "lz4:9 -m3" "lz4f:1 -m3" "lzav:1 -m3" "lzav:0 -m3"; do
  n=$(echo "$m" | tr -dc 'a-z0-9'); rm -f l$n.zpaq; rm -rf x y
  $Z a l$n.zpaq src -ma:$m $TS -noeta >a$n.log 2>&1; ra=$?
  $Z x l$n.zpaq -to x >/dev/null 2>&1; rx=$?
  (mkdir y && cd y && timeout 600 zpaq x ../l$n.zpaq >/dev/null 2>&1); ry=$?
  $Z t l$n.zpaq >/dev/null 2>&1; rt=$?
  r=ok; [ $ra = 0 ] || r="a=$ra"; diff -r src x/src >/dev/null || r="$r x-mal"; diff -r src y/src >/dev/null || r="$r zpaq715-mal($ry)"; [ $rt = 0 ] || r="$r t=$rt"
  ok "-ma:$m: a, x nativo, x zpaq 7.15 (ZPAQL), t" "$r"
done
# 2. los bloques de 1.10.0
if [ -n "${OLD110:-}" ] && [ -x "$OLD110" ]; then
  for m in lz4:9 lz4f:1 lzav:1 lzav:0; do
    n=$(echo "$m" | tr -dc 'a-z0-9'); rm -f o$n.zpaq; rm -rf xo
    $OLD110 a o$n.zpaq src -ma:$m $TS -noeta >/dev/null 2>&1
    $Z x o$n.zpaq -to xo >/dev/null 2>&1
    r=ok; diff -r src xo/src >/dev/null || r="2.0-no-lee-1.10"
    s=$(python3 -I - l$n.zpaq o$n.zpaq <<'PY'
import sys,re
def bloques(f):
    d=open(f,'rb').read(); o=[m.start() for m in re.finditer(rb'7kSt',d)]
    return sorted(d[o[i]:(o[i+1] if i+1<len(o) else len(d))] for i in range(len(o)))
a=bloques(sys.argv[1]); b=bloques(sys.argv[2])
# los bloques de datos: los mas grandes (el indice y la lista de fragmentos cambian con 65.x)
ga=sorted(a,key=len)[-2:]; gb=sorted(b,key=len)[-2:]
print('iguales' if ga==gb else 'distintos')
PY
)
    [ "$s" = iguales ] || r="$r datos-distintos-de-1.10"
    ok "-ma:$m: los bloques de datos de 1.10.0, y 2.0 los lee" "$r"
  done
fi
# 3. daño: bytes cambiados en los datos del bloque mas grande (no en su programa ZPAQL: correr un
#    decodificador dañado es otro tema, que zpaq-std ya rechaza al reconocerlo dañado)
for m in lz4:9 lz4f:1 lzav:1 lzav:0; do
  n=$(echo "$m" | tr -dc 'a-z0-9'); rm -rf dsrc; mkdir -p dsrc; cp src/CHANGELOG.md src/sub/prog.bin dsrc/
  rm -f d$n.zpaq; $Z a d$n.zpaq dsrc -ma:$m $TS -noeta >/dev/null 2>&1
  cuelgues=0; senales=0; errores=0; buenos=0
  for k in $(seq 1 $DANOS); do
    python3 -I - d$n.zpaq dd.zpaq $k <<'PY'
import sys,re,random
d=bytearray(open(sys.argv[1],'rb').read()); r=random.Random(int(sys.argv[3]))
o=[m.start() for m in re.finditer(rb'7kSt',d)]+[len(d)]
i=max(range(len(o)-1),key=lambda j:o[j+1]-o[j]); a,b=o[i]+100000,o[i+1]-64  # tras el programa ZPAQL (el PCOMP va al principio): se dañan los datos, no el decodificador
for _ in range(r.choice([1,1,2,8])): d[r.randrange(a,b)]^=1<<r.randrange(8)
open(sys.argv[2],'wb').write(d)
PY
    for e in zs z715; do
      rm -rf dx; mkdir dx
      if [ $e = zs ]; then timeout 30 $Z x dd.zpaq -to dx -force >/dev/null 2>&1; rc=$?
      else (cd dx && timeout 120 zpaq x ../dd.zpaq >/dev/null 2>&1); rc=$?; fi
      if [ $rc = 124 ]; then cuelgues=$((cuelgues+1))
      elif [ $rc -ge 128 ]; then senales=$((senales+1))
      elif diff -r dsrc dx/dsrc >/dev/null 2>&1; then buenos=$((buenos+1))
      else errores=$((errores+1)); fi
    done
  done
  r=ok; [ $cuelgues = 0 ] && [ $senales = 0 ] || r="cuelgues=$cuelgues senales=$senales"
  ok "-ma:$m: $DANOS bloques dañados (nativo y ZPAQL): $errores error, $buenos bien" "$r"
done
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_LZ4LZAV
