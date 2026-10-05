# SMM2 Clang 8.0.0

This repository builds the versioned compiler used by
[smm2-decomp](https://github.com/nicobrinkkemper/smm2-decomp).
The game uses one common compiler configuration for every translation unit.

## Build

On Ubuntu 24.04 x86_64, install Git, CMake, Ninja, host Clang/Clang++, Python 3.12,
patch, GNU binutils and xz-utils. Then run:

    python3 build.py --work-dir /tmp/smm2-clang-build --jobs 4

The recipe fetches immutable LLVM 8.0.0 monorepo commit
d2298e74235598f15594fe2c99bbac870a507c59 and builds Release Clang/LLD for AArch64
with assertions enabled. Optional terminfo, XML, zlib and Z3 are disabled.
Existing source checkouts and compiler installations are untouched.

To read pinned Git objects from an existing local LLVM repository:

    python3 build.py --work-dir /tmp/smm2-clang-build \
        --source-repo /path/to/llvm-project --jobs 4

This exports the pinned commit, never its working tree. Resume interrupted
compilation with the same command. A different patch set needs a new work
directory; --repackage preserves a previous package before creating another.

The archive includes compiler/linker/inspection tools, resource headers,
licenses and smm2-toolchain.json. The manifest records upstream and patch hashes,
recipe hash, host, CMake settings, runtime libraries and binary fingerprints.
The archive's .sha256 file pins its exact contents. Runtime compatibility is
with Ubuntu 24.04 or compatible libraries; this recipe does not claim identical
compiler archive bytes across different host toolchains.

## Patches and provenance

Patches 0001–0003 retain the switches for optional store-merging and comparison
canonicalization changes. The game's normal build leaves store merging enabled.
Patches 0001–0002 are rebased onto actual LLVM 8.0.0; comparison assertions honor
the canonicalization switch. Patch 0004 retains the existing epilogue behavior
of the locally validated project compiler.

Patch 0005 backports only the same-stack-object offset ordering correction and
matching AArch64 assertion from
[LLVM commit 97ca7c2](https://github.com/llvm/llvm-project/commit/97ca7c2cc9083ebde681b0e11f7a8ccae1966d64)
([D71334](https://reviews.llvm.org/D71334)).
It sorts offsets within one stack object in increasing address order while
preserving ordering across separate stack objects and register-based accesses.
The upstream commit's separate fixed-stack-object scaling changes are excluded.
Patch 0006 adds standard headers required by modern host compilers.

These patches record a validated decompilation toolchain; they do not identify
Nintendo's exact internal compiler revision.

## Release validation

Before publishing, rebuild all game translation units with identical source,
flags and link order using both compiler versions. Compare named matching-label
failures and the set of WIP functions that match, regenerating Viking's derived
CSV independently each time. Run the affected behavior tests against the new
image.

The isolated ordering backport preserved all existing matches across 1,227
translation units at smm2-decomp develop aaa7fc6f: the same 178 baseline failures,
all 21 already matching WIP functions, plus a new exact 268-byte player bounce
match. All 1,877 bounce, friction-request and speed-dispatch bridge tests passed.
The release package must independently repeat that validation before use.


The final comparison was repeated on develop b70faf0 with **1,260 translation
units**. The clean package and normal installed compiler preserve all **25**
existing WIP matches and the same **178** baseline failures, adding only the
268-byte bounce match. The targeted official checks report OK for bounce and
the 48-byte StateMachine constructor. The 1,877 request bridge cases and 11
compiler installation/upgrade tests pass.
