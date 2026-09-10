#!/bin/bash
export ZPAQ_YTOOL=/home/forum/git/ytool/ytool
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
CORPUS=$W/corpus
OUT=$W/${RUN:-run1}; mkdir -p $OUT
CSV=$OUT/ytool.csv; LOG=$OUT/ytool.log
echo "prueba,caso,rc_add,arch,rc_x,resultado,nota" > "$CSV"
: > "$LOG"
ok(){ printf '  %-24s %-9s add=%-3s %11s x=%-3s %s\n' "$1" "$2" "$3" "$4" "$5" "$6"; echo "$1,$2,$3,$4,$5,$6,$7" >> "$CSV"; }
echo "  (ytool: $($ZPAQ_YTOOL 2>&1 </dev/null | head -1 | cut -c1-60))"
d=$OUT/yt; rm -rf $d; mkdir -p $d
# corpus con streams recomprimibles: gz, png, jpg, pdf y un tar que los contenga
mkdir -p $d/src
cp $CORPUS/precomp/data.gz $d/src/ 2>/dev/null
cp $CORPUS/img/* $d/src/ 2>/dev/null
C=/mnt/OSR_D3/fileFormatSamples/fileFormatSamples
find $C/document -type f -size -400k 2>/dev/null | sort | head -4 | xargs -I{} cp {} $d/src/ 2>/dev/null
tar cf $d/src/contenedor.tar -C $d/src . 2>/dev/null
echo "  (corpus ytool: $(ls $d/src|wc -l) archivos, $(du -sh $d/src|cut -f1))"
for f in "-m5 -ytool" "-m3 -ytool" "-ma:zstd -ytool" "-m5 -ytool -t 1" "-m5 -ytool -t 4" \
         "-m5 -ytool:zlib" "-m5 -ytool -key Secreta1" "-m5" ; do
  a=$d/y.zpaq; rm -f $a; rm -rf $d/out
  timeout 600 $Z a "$a" "$d/src" $f -summary >>"$LOG" 2>&1 </dev/null; rca=$?
  sz=$(stat -c%s $a 2>/dev/null || echo 0)
  rf=""; case "$f" in *-key*) rf="-key Secreta1";; esac
  timeout 600 $Z x "$a" -to "$d/out/" -force $rf -summary >>"$LOG" 2>&1 </dev/null; rcx=$?
  res=MATCH; diff -r "$d/src" "$d/out$d/src" >>"$LOG" 2>&1 || res=MISMATCH
  ok "$f" mixto "$rca" "$sz" "$rcx" "$res" ""
done
rm -rf $d
echo DONE_YTOOL
