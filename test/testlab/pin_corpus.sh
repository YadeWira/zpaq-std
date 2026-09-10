#!/bin/bash
# Fija el corpus con un manifiesto de sha256.
#
# POR QUE: las suites (suite_cmds/robust/extra/ytool) REGENERAN su corpus base en
# cada corrida con `find | head`, que elige archivos distintos entre corridas.
# Eso ya invalido una comparacion de tamanos: dos binarios "distintos" que en
# realidad habian comprimido entradas distintas. El golden gate no puede depender
# de datos que se mueven, y difftest tampoco si se quiere comparar entre dias.
#
#   uso: pin_corpus.sh [verify]
#        sin argumento -> (re)genera corpus/MANIFEST.sha256
#        verify        -> compara el corpus actual contra el manifiesto
set -u
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
M=$W/corpus/MANIFEST.sha256

cd "$W" || exit 2

if [ "${1:-}" = "verify" ]; then
    [ -f "$M" ] || { echo "no hay manifiesto: corre pin_corpus.sh primero"; exit 2; }
    # el propio manifiesto no se autoincluye
    if find corpus -type f ! -name MANIFEST.sha256 -print0 \
         | sort -z | xargs -0 sha256sum | diff -q - "$M" >/dev/null; then
        echo "corpus OK: $(( $(wc -l < "$M") )) archivos coinciden con el manifiesto"
        exit 0
    fi
    echo "CORPUS CAMBIO respecto del manifiesto:"
    find corpus -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum \
      | diff "$M" - | head -20
    exit 1
fi

find corpus -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > "$M"
echo "manifiesto: $(wc -l < "$M") archivos, $(du -sh corpus | cut -f1)"
