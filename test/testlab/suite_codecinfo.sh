#!/bin/bash
# ============================================================================
# suite_codecinfo.sh -- codecinfo y codecinfoex.
#
# POR QUE EXISTE: la tabla de codecinfo (ZS_INFO en zpaq-std.cpp) repite los
# niveles y defaults que aplica el parser de -ma y que dice el README; si uno
# cambia y el otro no, codecinfo miente sin que nada falle. Lo que mide:
# (1) codecinfo lista los 28 switches -ma; (2) niveles y default de cada uno
# coinciden con la tabla del README; (3) codecinfoex <codec> funciona con cada
# uno y da su decodificador; (4) los plugins externos de codecs/ aparecen
# marcados, con su ficha (ZS_DATA_INFO) y el SHA-256 real del archivo; uno roto
# se informa sin romper nada; (5) codecinfo <codec> da su ficha; (6) un
# nombre desconocido da 00736 y rc 2.
#
#   uso: suite_codecinfo.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
R=${R:-/home/forum/git/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-codecinfo}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/codecs"; cd "$OUT"
cc -O2 -shared -fPIC -I"$R/compressors/plug" "$R/tools/plugin_example/zs_example.c" -o codecs/example.so || { echo "no compila el ejemplo"; exit 1; }
echo basura > codecs/roto.so
cp "$Z" ./zpaq-std
malos=0; casos=0
ok() { casos=$((casos+1)); [ "$2" = ok ] || malos=$((malos+1)); printf '  %-52s %s\n' "$1" "$2"; }
./zpaq-std codecinfo > ci.txt 2>&1; rc=$?
n=$(grep -cE '^[a-z0-9]+ +(stable|experimental) ' ci.txt)
[ $rc = 0 ] && [ "$n" = 28 ] && r=ok || r="rc=$rc filas=$n"; ok "codecinfo: 28 switches -ma" "$r"
r=$(python3 -I - "$R/README.md" ci.txt <<'EOF'
import re,sys
readme=open(sys.argv[1],encoding='utf-8').read()
doc={}
for line in readme.splitlines():
    if not line.startswith('| `-ma:'): continue
    cols=[c.strip() for c in line.strip('|').split('|')]
    names=re.findall(r'`(?:-ma:)?([a-z0-9]+)(?::N)?`',cols[0])
    lv=cols[2].split()[0].replace('–','-'); d=cols[3]
    for nm in names: doc[nm]=(lv,d)
bad=[]
seen=0
for line in open(sys.argv[2]):
    m=re.match(r'^([a-z0-9]+) +(stable|experimental) +(\d+-\d+) +(\d+) ',line)
    if not m: continue
    seen+=1
    nm,lv,d=m.group(1),m.group(3),m.group(4)
    if nm not in doc: bad.append(nm+':no-esta-en-README')
    elif doc[nm]!=(lv,d): bad.append('%s:codecinfo=%s/%s README=%s/%s'%(nm,lv,d,doc[nm][0],doc[nm][1]))
print('ok' if not bad and seen==28 else ' '.join(bad) or 'filas=%d'%seen)
EOF
)
ok "niveles y default iguales a la tabla del README" "$r"
r=ok
for c in $(grep -oE '^[a-z0-9]+ +(stable|experimental) ' ci.txt | awk '{print $1}'); do
  ./zpaq-std codecinfoex $c > ex_$c.txt 2>&1 || r="$r $c:rc"
  grep -q "^-ma:$c\$" ex_$c.txt && grep -q '  decoder ' ex_$c.txt || r="$r $c:ficha"
done; ok "codecinfoex de cada codec" "$r"
r=ok
grep -q 'example:rle .*ZPAQL yes, for -mae/-mat, -sae/-sat' ci.txt || r="rle"
grep -q 'example:rlenz .*ZPAQL no, for -mat, -sat' ci.txt || r="$r rlenz"
grep -q 'roto.so: not a usable codec' ci.txt || r="$r roto"
grep -q 'EXTERNAL, NOT part of zpaq-std' ci.txt || r="$r sin-marca"
ok "codecinfo: externos marcados, el roto informado" "$r"
./zpaq-std codecinfoex example:rle > ex_ext.txt 2>&1
r=ok; h=$(sha256sum codecs/example.so | cut -d' ' -f1)
grep -q "plugin hash  SHA-256 $h" ex_ext.txt || r="hash"
grep -q 'repository   https://github.com/YadeWira/zpaq-std' ex_ext.txt || r="$r ficha"
grep -q 'NOT an official' ex_ext.txt || r="$r sin-aviso"
ok "codecinfoex example:rle: ficha y SHA-256 real" "$r"
./zpaq-std codecinfo zstd > ci_zstd.txt 2>&1; rc=$?
r=ok; [ $rc = 0 ] || r="rc=$rc"; grep -q '^-ma:zstd$' ci_zstd.txt && grep -q '  decoder      ZPAQZSTD' ci_zstd.txt || r="$r sin-ficha"
./zpaq-std codecinfo example:rle | grep -q 'NOT an official' || r="$r externo"
ok "codecinfo <codec> da su ficha (como codecinfoex)" "$r"
./zpaq-std codecinfoex nada > ex_nada.txt 2>&1; rc=$?
[ $rc = 2 ] && grep -q 00736 ex_nada.txt && r=ok || r="rc=$rc"; ok "nombre desconocido: 00736" "$r"
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_CODECINFO
