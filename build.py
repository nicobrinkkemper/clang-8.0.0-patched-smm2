#!/usr/bin/env python3
"""Build the pinned SMM2 compiler in an isolated, resumable work directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

LLVM_COMMIT = "d2298e74235598f15594fe2c99bbac870a507c59"
REVISION = "smm2-stack-order-1"
HERE = Path(__file__).resolve().parent
TOOLS = [
    "clang", "lld", "llc", "opt", "llvm-ar", "llvm-objdump", "llvm-nm",
    "llvm-objcopy", "llvm-readobj", "llvm-as", "llvm-dis", "llvm-mc",
]
ALIASES = {
    "clang++": "clang", "clang-8": "clang", "ld.lld": "lld",
    "llvm-ranlib": "llvm-ar", "llvm-readelf": "llvm-readobj",
    "llvm-strip": "llvm-objcopy",
}


def run(args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--source-repo", type=Path,
                        help="Optional local LLVM git repository; only pinned git objects are read")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--repackage", action="store_true", help="Preserve an earlier package and create another")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    for command in ("git", "cmake", "ninja", "patch", "clang", "clang++", "strip"):
        if not shutil.which(command):
            parser.error("Missing build dependency: " + command)
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    patches = sorted(HERE.glob("*.patch"))
    identity = {
        "revision": REVISION, "llvm_commit": LLVM_COMMIT,
        "patches": {p.name: digest(p) for p in patches},
    }
    source = work / "source"
    prepared = work / "source.json"
    if prepared.exists():
        previous = json.loads(prepared.read_text())
        previous.pop("recipe_sha256", None)
        if previous != identity:
            raise SystemExit("Recipe changed; choose a new --work-dir (existing work is preserved).")
    else:
        if source.exists():
            raise SystemExit("Unmarked source directory exists; choose a new --work-dir.")
        repo = args.source_repo
        if repo is None:
            repo = work / "upstream.git"
            if not repo.exists():
                run(["git", "init", "--bare", repo])
            run(["git", "-C", repo, "fetch", "--depth=1",
                 "https://github.com/llvm/llvm-project.git", LLVM_COMMIT])
        actual = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", LLVM_COMMIT + "^{commit}"], text=True).strip()
        if actual != LLVM_COMMIT:
            raise SystemExit("Pinned LLVM commit does not match.")
        archive = work / "source.tar"
        with archive.open("wb") as output:
            run(["git", "-C", repo, "archive", LLVM_COMMIT, "llvm", "clang", "lld"],
                stdout=output)
        source.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(source, filter="data")
        archive.unlink()
        for patch in patches:
            with patch.open("rb") as patch_input:
                run(["patch", "--batch", "--forward", "-p1"], cwd=source, stdin=patch_input)
        prepared.write_text(json.dumps(identity, indent=2) + "\n")
    build = work / "build"
    options = [
        "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++",
        "-DLLVM_TARGETS_TO_BUILD=AArch64", "-DLLVM_ENABLE_PROJECTS=clang;lld",
        "-DLLVM_ENABLE_ASSERTIONS=ON", "-DLLVM_INCLUDE_TESTS=OFF",
        "-DLLVM_INCLUDE_EXAMPLES=OFF", "-DLLVM_INCLUDE_BENCHMARKS=OFF",
        "-DLLVM_ENABLE_TERMINFO=OFF", "-DLLVM_ENABLE_LIBXML2=OFF",
        "-DLLVM_ENABLE_ZLIB=OFF", "-DCLANG_ANALYZER_ENABLE_Z3_SOLVER=OFF",
        "-DLLVM_PARALLEL_LINK_JOBS=1",
    ]
    run(["cmake", "-S", source / "llvm", "-B", build, *options])
    run(["ninja", "-C", build, "-j", args.jobs, *TOOLS])
    package = work / "package" / "clang-8.0.0-patched"
    if package.exists():
        if not args.repackage:
            raise SystemExit("Package already exists; pass --repackage to preserve it and package again.")
        package.rename(package.with_name(package.name + ".previous-" + str(time.time_ns())))
    (package / "bin").mkdir(parents=True)
    for tool in TOOLS:
        shutil.copy2(build / "bin" / tool, package / "bin" / tool)
        run(["strip", package / "bin" / tool])
    for alias, target in ALIASES.items():
        (package / "bin" / alias).symlink_to(target)
    shutil.copytree(build / "lib/clang/8.0.0/include",
                    package / "lib/clang/8.0.0/include")
    licenses = package / "share/licenses"
    licenses.mkdir(parents=True)
    for project in ("llvm", "clang", "lld"):
        shutil.copy2(source / project / "LICENSE.TXT", licenses / (project + ".txt"))
    smoke = work / "smoke.cpp"
    smoke.write_text("extern int f(int); int g(int x) { return f(x + 1); }\n")
    run([package / "bin/clang++", "-target", "aarch64-none-elf", "-O3",
         "-mllvm", "-disable-icmp-canonicalization",
         "-mllvm", "-disable-cmp-canonicalization", "-c", smoke,
         "-o", work / "smoke.o"])
    run([package / "bin/ld.lld", "-shared", work / "smoke.o", "-o", work / "smoke.so"])
    runtime = {}
    for tool in ("clang", "ld.lld"):
        run([package / "bin" / tool, "--version"])
        runtime[tool] = subprocess.check_output(
            ["ldd", str(package / "bin" / tool)], text=True)
        if "not found" in runtime[tool]:
            raise SystemExit("Unresolved runtime dependency in " + tool)
    identity.update({
        "recipe_sha256": digest(__file__),
        "cmake_options": options,
        "host": subprocess.check_output(["uname", "-srm"], text=True).strip(),
        "host_compiler": subprocess.check_output(["clang++", "--version"], text=True),
        "runtime_dependencies": runtime,
        "binaries": {tool: digest(package / "bin" / tool) for tool in TOOLS},
    })
    (package / "smm2-toolchain.json").write_text(json.dumps(identity, indent=2) + "\n")
    output = work / ("clang-8.0.0-patched-" + REVISION + "-linux-x86_64.tar.xz")
    run(["tar", "--sort=name", "--mtime=@1552639450", "--owner=0", "--group=0",
         "--numeric-owner", "-cJf", output, "-C", package.parent, package.name])
    output.with_suffix(output.suffix + ".sha256").write_text(digest(output) + "  " + output.name + "\n")
    print("Package:", output, flush=True)


if __name__ == "__main__":
    main()

