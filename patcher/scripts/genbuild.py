import os
import shlex

import ninja_syntax


stampfile = "out/extracted/ggpk.stamp"


def write_dat2json(writer, table_name, path, out):
    write_extract(
        writer,
        f"{out}.datc64",
        path,
    )
    writer.build(
        f"{out}.jsonl",
        "dat2jsonl",
        inputs=f"{out}.datc64",
        implicit=["bin/dat2jsonl", "schema.min.json"],
        variables={"table_name": table_name},
    )


def write_extract(writer, out, path):
    writer.build(
        out,
        "extract",
        implicit=["extract/build/extract", stampfile],
        variables={"path": shlex.quote(path)},
    )


with open("build.ninja", "w", encoding="utf8") as file:
    writer = ninja_syntax.Writer(file)

    writer.rule(
        "extract",
        [
            "extract/build/extract",
            "Content.ggpk.d/latest",
            "$path",
            "$out",
        ],
    )
    writer.rule(
        "dat2jsonl",
        "bin/dat2jsonl --dat=$in --table-name=$table_name --schema=schema.min.json > $out",
    )

    write_extract(
        writer,
        "out/extracted/stat_descriptions.txt",
        "metadata/statdescriptions/stat_descriptions.txt",
    )

    write_extract(
        writer,
        "out/extracted/tincture_stat_descriptions.txt",
        "metadata/statdescriptions/tincture_stat_descriptions.txt",
    )

    json_files = []
    for (table_name, datfile) in [
        ("BaseItemTypes", "baseitemtypes"),
        ("ActiveSkills", "activeskills"),
        ("PassiveSkills", "passiveskills"),
        ("SkillGems", "skillgems"),
        ("Words", "words"),
    ]:
        for l, lang in [
            ["en", ""],
            ["tc", "traditional chinese/"],
        ]:
            write_dat2json(
                writer,
                table_name,
                f"data/{lang}{datfile}.datc64",
                f"out/extracted/{table_name}.{l}",
            )
            json_files.append(f"out/extracted/{table_name}.{l}.jsonl")

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
        [
            "out/extracted/stat_descriptions.txt",
            "out/extracted/tincture_stat_descriptions.txt",
        ],
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

    # Game data must be fetched beforehand via `bazel run //patcher:fetch`.
    # Stamp on the bundle index so ninja re-extracts when game data changes.
    writer.rule("stamp", "touch $out")
    writer.build(
        "out/extracted/ggpk.stamp",
        "stamp",
        implicit=["Content.ggpk.d/latest/Bundles2/_.index.bin"],
    )
