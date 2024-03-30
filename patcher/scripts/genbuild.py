import os
import shlex
import subprocess

import ninja_syntax


targets = [
    "PathOfExile.exe",

    "Bundles2/_.index.bin",
    "Bundles2/_Startup.bundle.bin",
    "Bundles2/Login_2.bundle.bin",
    "Bundles2/Preload.bundle.bin",

    "Bundles2/Folders/data/0/traditional chinese.dat64.bundle.bin",
    "Bundles2/Folders/data/1/traditional chinese.dat64.bundle.bin",
    "Bundles2/Folders/data/4/traditional chinese.dat64.bundle.bin",
    "Bundles2/Folders/data/F/traditional chinese.dat64.bundle.bin",
]

objects = [os.path.join("Content.ggpk.d", "latest", target) for target in targets]
stampfile = "out/extracted/ggpk.stamp"


def write_build(writer):
    write_download(writer)


def write_dat2json(writer, table_name, path, out):
    writer.build(
        f"{out}.dat64",
        "extract",
        implicit=["extract/build/extract", stampfile],
        variables={"path": shlex.quote(path)},
    )
    writer.build(
        f"{out}.jsonl",
        "dat2jsonl",
        inputs=f"{out}.dat64",
        implicit=["bin/dat2jsonl", "schema.min.json"],
        variables={"table_name": table_name},
    )


subprocess.check_call(['bin/poepatcher', *targets])


with open("build.ninja", "w", encoding="utf8") as file:
    writer = ninja_syntax.Writer(file)

    writer.rule("stamp", "touch $out")
    writer.build("out/extracted/ggpk.stamp", "stamp", implicit=objects)

    writer.rule(
        "extract",
        [
            "extract/build/extract",
            "Content.ggpk.d/latest",
            "$out",
            "$path",
        ],
    )
    writer.rule(
        "dat2jsonl",
        "bin/dat2jsonl --dat=$in --table-name=$table_name --schema=schema.min.json > $out",
    )

    writer.build(
        "out/extracted/stat_descriptions.txt",
        "extract",
        implicit=["extract/build/extract", stampfile],
        variables={"path": "Metadata/StatDescriptions/stat_descriptions.txt"},
    )

    json_files = []
    for datfile in [
        "BaseItemTypes",
        "ActiveSkills",
        "PassiveSkills",
        "SkillGems",
        "Words",
    ]:
        for l, lang in [
            ["en", ""],
            ["tc", "Traditional Chinese/"],
        ]:
            write_dat2json(
                writer,
                datfile,
                f"Data/{lang}{datfile}.dat64",
                f"out/extracted/{datfile}.{l}",
            )
            json_files.append(f"out/extracted/{datfile}.{l}.jsonl")

    writer.rule("datrelease", "venv/bin/python scripts/datrelease.py")
    writer.build(
        [
            os.path.join("out", "release", p)
            for p in ["bases.json", "passives.json", "words.json"]
        ],
        "datrelease",
        implicit=[
            "scripts/datrelease.py",
            *json_files,
        ],
    )

    writer.rule(
        "statparse",
        "venv/bin/python scripts/statparse.py $in > $out",
        pool="console",
    )
    writer.build(
        "out/release/stat_descriptions.json",
        "statparse",
        "out/extracted/stat_descriptions.txt",
        implicit="scripts/statparse.py",
    )

    writer.rule("charversion", "venv/bin/python scripts/charversion.py $in | tee $out")
    writer.build(
        "out/release/version.txt",
        "charversion",
        "Content.ggpk.d/latest/PathOfExile.exe",
        implicit="scripts/charversion.py",
    )

    writer.rule("fingerprint", "venv/bin/python scripts/fingerprint.py $in | tee $out")
    writer.build(
        "out/release/fingerprint.txt",
        "fingerprint",
        [
            "out/release/bases.json",
            "out/release/stat_descriptions.json",
            "out/release/words.json",
            "out/release/passives.json",
            "out/release/version.txt",
        ],
        implicit="scripts/fingerprint.py",
    )
