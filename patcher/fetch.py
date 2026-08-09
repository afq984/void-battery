"""Populate Content.ggpk.d/ with game data needed by the patcher pipeline.

This is the non-hermetic fetch step: it downloads game files from the
patch server and resolves bundle paths via the extract binary.

Intended to be run via: bazel run //patcher:fetch
"""

import os
import subprocess
import sys

# Files to extract (must match genbuild.py)
EXTRACT_DEPS = [
    "data/activeskills.datc64",
    "data/baseitemtypes.datc64",
    "data/passiveskills.datc64",
    "data/skillgems.datc64",
    "data/words.datc64",
    "data/traditional chinese/activeskills.datc64",
    "data/traditional chinese/baseitemtypes.datc64",
    "data/traditional chinese/passiveskills.datc64",
    "data/traditional chinese/skillgems.datc64",
    "data/traditional chinese/words.datc64",
    "metadata/statdescriptions/stat_descriptions.txt",
    "metadata/statdescriptions/tincture_stat_descriptions.txt",
    "metadata/statdescriptions/graft_stat_descriptions.txt",
]


def main():
    extract = os.path.abspath(sys.argv[1])
    poepatcher = os.path.abspath(sys.argv[2])

    patcher_dir = os.path.join(os.environ["BUILD_WORKSPACE_DIRECTORY"], "patcher")
    os.chdir(patcher_dir)

    # Seed targets: game binary + bundle index
    targets = {
        "PathOfExile.exe",
        "Bundles2/_.index.bin",
    }
    subprocess.check_call([poepatcher, *targets])

    # Discover which bundles contain the files we need
    for dep in EXTRACT_DEPS:
        result = subprocess.run(
            [extract, "Content.ggpk.d/latest", dep],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            result.check_returncode()
        bundle_path = f"Bundles2/{result.stdout.strip()}.bundle.bin"
        print(f"{dep} => {bundle_path}", file=sys.stderr)
        targets.add(bundle_path)

    # Fetch all discovered bundles
    subprocess.check_call([poepatcher, *targets])

    # Write Bazel files so --override_repository can point here
    latest = os.path.join(patcher_dir, "Content.ggpk.d", "latest")
    with open(os.path.join(latest, "MODULE.bazel"), "w") as f:
        f.write('module(name = "gamedata", version = "0")\n')
    with open(os.path.join(latest, "BUILD.bazel"), "w") as f:
        f.write(
            'filegroup(name = "all", srcs = glob(["**"], exclude = ["BUILD.bazel", "MODULE.bazel"]), visibility = ["//visibility:public"])\n'
            'exports_files(glob(["**"], exclude = ["BUILD.bazel", "MODULE.bazel"]), visibility = ["//visibility:public"])\n'
        )


if __name__ == "__main__":
    main()
