#!/bin/bash
# libzpaqstd for one target: linux64 linux86 win64 win32. Run from the root of the source.
# build_lib.sh <target> relink: only the library again (the objects of that target must be the ones there).
# The objects of the full build (every C/C++ codec linked), then the library from lib/libzpaqstd.cpp.
set -e
T=$1; O=lib/out/$T; mkdir -p $O
case $T in
  linux64) A=(PICFLAG=-fPIC); P=zpaq-std; L=libzpaqstd.so; X="-fPIC -fvisibility=hidden -Wl,--gc-sections -Wl,--exclude-libs,ALL";;
  linux86) A=(PICFLAG=-fPIC CXXFLAGS="-O3 -m32" CFLAGS="-O3 -m32"); P=zpaq-std; L=libzpaqstd.so; X="-fPIC -fvisibility=hidden -Wl,--gc-sections -Wl,--exclude-libs,ALL";;
  win64) A=(CROSS_COMPILE=x86_64-w64-mingw32-); P=zpaq-std; L=zpaqstd.dll; X="-static -static-libgcc -static-libstdc++ -Wl,--gc-sections";;
  win32) A=(CROSS_COMPILE=i686-w64-mingw32-); P=zpaq-std; L=zpaqstd.dll; X="-static -static-libgcc -static-libstdc++ -Wl,--gc-sections";;
  *) echo "target?"; exit 2;;
esac
if [ "$2" != relink ]; then
  make clean >/dev/null 2>&1
  make -j${JOBS:-16} "${A[@]}" build > $O/make.log 2>&1
fi
C=$(make -n -W zpaq-std.cpp "${A[@]}" build 2>/dev/null | grep -E " zpaq-std\.cpp .* -o $P\$" | head -1)
[ -n "$C" ] || { echo "no link line"; exit 1; }
C=$(echo "$C" | sed -E "s# zpaq-std\.cpp # lib/libzpaqstd.cpp #; s# -o $P\$# -o $O/$L#; s# win/[^ ]*\.o# #g; s# -mconsole # #")
C="${C/ / -shared -s -ffunction-sections -fdata-sections $X }"
echo "$C" > $O/link.cmd
bash $O/link.cmd > $O/link.log 2>&1
ls -la $O/$L
