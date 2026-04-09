# Custom Clang 8.0.0 Compiler

To achieve 100% byte-matching on Nintendo Switch binaries, we use a custom-patched version of Clang 8.0.0. Nintendo's internal fork of Clang 8 included custom modifications to Loop Strength Reduction and disabled certain optimizations (like store merging and instruction canonicalization) that the vanilla Clang 8 release does not support disabling out of the box.

## Patches

1. `0001-add-disable-store-merging-flag.patch`
   Adds `-mllvm -disable-store-merging` to prevent DAGCombiner from merging adjacent zero stores into NEON instructions.
2. `0002-add-disable-icmp-canonicalization-flag.patch`
   Adds `-mllvm -disable-icmp-canonicalization` to prevent LLVM from aggressive ICMP reordering.
3. `0003-add-disable-cmp-canonicalization-flag.patch`
   Adds `-mllvm -disable-cmp-canonicalization` to prevent generic CMP reordering.

## Build Process

To build the patched compiler from source on an Ubuntu system:

```bash
# 1. Download LLVM 8.0.0 source
wget https://github.com/llvm/llvm-project/releases/download/llvmorg-8.0.0/llvm-8.0.0.src.tar.xz
wget https://github.com/llvm/llvm-project/releases/download/llvmorg-8.0.0/cfe-8.0.0.src.tar.xz

# 2. Extract and structure the source tree
tar xf llvm-8.0.0.src.tar.xz
tar xf cfe-8.0.0.src.tar.xz
mv cfe-8.0.0.src llvm-8.0.0.src/tools/clang

# 3. Apply custom patches
cd llvm-8.0.0.src
patch -p1 < ../tools/llvm-patches/0001-add-disable-store-merging-flag.patch
patch -p1 < ../tools/llvm-patches/0002-add-disable-icmp-canonicalization-flag.patch
patch -p1 < ../tools/llvm-patches/0003-add-disable-cmp-canonicalization-flag.patch

# 4. Build the compiler
mkdir build && cd build
cmake .. -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_TARGETS_TO_BUILD="AArch64" \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DCMAKE_INSTALL_PREFIX=../../tools/clang-8.0.0-patched
ninja install
```

Once installed, ensure `cmake/aarch64-none-elf.cmake` points to the `clang-8.0.0-patched` directory and includes the new `-mllvm` flags.
