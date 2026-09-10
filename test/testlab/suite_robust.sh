#!/bin/bash
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
CORPUS=$W/corpus
OUT=$W/${RUN:-run1}; mkdir -p $OUT
CSV=$OUT/robust.csv; LOG=$OUT/robust.log
echo "grupo,prueba,rc,detalle,resultado" > "$CSV"
: > "$LOG"
ok(){ printf '  %-10s %-40s rc=%-4s %-26s %s\n' "$1" "$2" "$3" "$4" "$5"; echo "$1,\"$2\",$3,\"$4\",$5" >> "$CSV"; }
O=$OUT/rb_out.txt
T(){ : > $O; timeout 240 "$@" > $O 2>&1 </dev/null; return $?; }

d=$OUT/rb; rm -rf $d; mkdir -p $d
cp -r $CORPUS/text $d/src
$Z a "$d/base.zpaq" "$d/src" -m2 -summary >/dev/null 2>&1
SZ=$(stat -c%s $d/base.zpaq)
echo "  (archivo base: $SZ bytes)"; echo

########## I: corrupcion en distintos offsets ##########
for off in 100 500 2000 $((SZ/4)) $((SZ/2)) $((SZ*3/4)) $((SZ-300)) $((SZ-50)); do
  cp $d/base.zpaq $d/c.zpaq
  python3 -c "
d=bytearray(open('$d/c.zpaq','rb').read()); d[$off]^=0xFF; open('$d/c.zpaq','wb').write(d)"
  T $Z t "$d/c.zpaq"; r=$?
  v=$(grep -oE 'VERDICT[^(]*' $O | head -1 | tr -s ' ')
  det=$(grep -cE 'corrupted|error|ERROR' $O)
  ok corrupcion "byte $off invertido" "$r" "lineas_error=$det" "$([ $r -ne 0 ] && echo DETECTADO || echo NO-DETECTADO) | $v"
done

########## J: archivos degenerados ##########
: > $d/cero.zpaq
T $Z x "$d/cero.zpaq" -to "$d/o/" -force; ok degenerado "archivo de 0 bytes" $? "$(grep -oE '39128!.*|AES-encrypted' $O|head -1|cut -c1-24)" "$([ $? -ne 0 ] && echo RECHAZADO)"
head -c $((SZ/2)) $d/base.zpaq > $d/trunc.zpaq
T $Z x "$d/trunc.zpaq" -to "$d/o2/" -force; ok degenerado "truncado a la mitad" $? "$(grep -oiE 'not found|39128|error' $O|head -1)" "$([ $? -ne 0 ] && echo RECHAZADO)"
head -c 100 $d/base.zpaq > $d/tiny.zpaq
T $Z x "$d/tiny.zpaq" -to "$d/o3/" -force; ok degenerado "solo 100 bytes" $? "$(grep -oiE 'not found|39128|error|AES'  $O|head -1)" "$([ $? -ne 0 ] && echo RECHAZADO)"
printf 'esto no es un zpaq en absoluto, es texto plano\n' > $d/notzpaq.zpaq
T $Z x "$d/notzpaq.zpaq" -to "$d/o4/" -force; ok degenerado "no es un zpaq" $? "$(grep -oiE 'AES|39128|error'  $O|head -1)" "$([ $? -ne 0 ] && echo RECHAZADO)"
T $Z x "$d/no-existe.zpaq" -to "$d/o5/" -force; ok degenerado "archivo inexistente" $? "$(grep -oiE 'not found' $O|head -1)" "$([ $? -ne 0 ] && echo RECHAZADO)"

########## K: password / cifrado ##########
$Z a "$d/k.zpaq" "$d/src" -m1 -key Correcta1 -summary >/dev/null 2>&1
T $Z t "$d/k.zpaq" -key Correcta1;  ok cifrado "password correcta" $? "" "$([ $? -eq 0 ] && echo OK)"
T $Z t "$d/k.zpaq" -key Incorrecta; ok cifrado "password incorrecta" $? "$(grep -oiE 'password incorrect' $O|head -1)" "$([ $? -ne 0 ] && echo RECHAZADO)"
T $Z t "$d/k.zpaq";                 ok cifrado "sin password, stdin cerrado" $? "$(grep -oE '42026!.*' $O|head -1|cut -c1-30)" "$([ $? -eq 2 ] && echo RC2-OK)"
printf 'Correcta1\n' > $d/pw.txt
timeout 60 $Z t "$d/k.zpaq" < $d/pw.txt > $O 2>&1; ok cifrado "password por stdin (con newline)" $? "" "$([ $? -eq 0 ] && echo OK)"
printf 'Correcta1' > $d/pw2.txt
timeout 60 $Z t "$d/k.zpaq" < $d/pw2.txt > $O 2>&1; ok cifrado "password por stdin (SIN newline)" $? "" "$([ $? -eq 0 ] && echo OK)"
FRANZKEY=Correcta1 timeout 60 $Z t "$d/k.zpaq" > $O 2>&1 </dev/null; ok cifrado "password por env FRANZKEY" $? "" "$([ $? -eq 0 ] && echo OK)"

########## L: espacio insuficiente y -space ##########
dd if=/dev/zero of=$d/disco.img bs=1M count=60 status=none
sudo /usr/sbin/mkfs.ext4 -F -q $d/disco.img 2>/dev/null
mkdir -p $d/mnt && sudo mount -o loop $d/disco.img $d/mnt 2>/dev/null && sudo chown $(id -u):$(id -g) $d/mnt
if mountpoint -q $d/mnt; then
  libre=$(df --output=avail -B1 $d/mnt | tail -1)
  $Z a "$d/big.zpaq" "$CORPUS/dupes" "$CORPUS/edge" -m1 -summary >/dev/null 2>&1
  need=$(timeout 60 $Z l "$d/big.zpaq" 2>/dev/null </dev/null | grep -oE '[0-9.]+ bytes' | head -1)
  T $Z x "$d/big.zpaq" -to "$d/mnt/out/" -force; r=$?
  n=$(find $d/mnt/out -type f 2>/dev/null | wc -l)
  ok espacio "destino con $((libre/1048576)) MB para ~21 MB" "$r" "archivos=$n $(grep -oE '00935!' $O|head -1)" "$([ $r -ne 0 ] && [ $n -eq 0 ] && echo RECHAZADO-BIEN || echo REVISAR)"
  sudo rm -rf $d/mnt/out 2>/dev/null
  T $Z x "$d/big.zpaq" -to "$d/mnt/out2/" -force -space; r=$?
  ok espacio "el mismo con -space (fuerza)" "$r" "$(grep -oE '00082!.*' $O|head -1|cut -c1-30)" "$([ $r -ne 0 ] && echo FALLO-ESPERADO)"
  sudo umount $d/mnt 2>/dev/null
else
  ok espacio "no pude montar el disco de prueba" - "sudo/mkfs no disponible" OMITIDO
fi

########## M: pipes (-stdin / -stdout) ##########
tar cf - -C $CORPUS text 2>/dev/null | timeout 120 $Z a "$d/pipe.zpaq" -stdin -m1 -summary > $O 2>&1; r=$?
ok pipes "-stdin (tar por pipe)" "$r" "arch=$(stat -c%s $d/pipe.zpaq 2>/dev/null||echo 0)" "$([ $r -eq 0 ] && echo OK)"
if [ -f $d/pipe.zpaq ]; then
  timeout 120 $Z x "$d/pipe.zpaq" -stdout > $d/salida.tar 2>/dev/null </dev/null; r=$?
  ok pipes "-stdout (recuperar por pipe)" "$r" "tar=$(stat -c%s $d/salida.tar 2>/dev/null||echo 0) bytes" "$([ -s $d/salida.tar ] && echo OK || echo VACIO)"
  tar tf $d/salida.tar >/dev/null 2>&1 && ok pipes "el tar recuperado es valido" 0 "$(tar tf $d/salida.tar 2>/dev/null|wc -l) entradas" OK || ok pipes "el tar recuperado es valido" 1 "" TAR-INVALIDO
fi
sudo rm -rf $d 2>/dev/null; rm -rf $d 2>/dev/null
echo DONE_ROBUST
