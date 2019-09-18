set -eux
patcher/poepatcher
cp Content.ggpk.d/latest/Metadata/StatDescriptions/stat_descriptions.txt out/extracted/stat_descriptions.txt
venv/bin/python scripts/exporter.py config set language 'English'
venv/bin/python scripts/exporter.py dat json --files=BaseItemTypes.dat out/extracted/BaseItemTypes.en.json
venv/bin/python scripts/exporter.py dat json --files=ActiveSkills.dat out/extracted/ActiveSkills.en.json
venv/bin/python scripts/exporter.py config set language 'Traditional Chinese'
venv/bin/python scripts/exporter.py dat json --files=BaseItemTypes.dat out/extracted/BaseItemTypes.tc.json
venv/bin/python scripts/exporter.py dat json --files=ActiveSkills.dat out/extracted/ActiveSkills.tc.json
venv/bin/python scripts/exporter.py dat json --files=Words.dat out/extracted/Words.tc.json

venv/bin/python scripts/datrelease.py
venv/bin/python scripts/statparse.py out/extracted/stat_descriptions.txt > out/release/stat_descriptions.json
python scripts/charversion.py Content.ggpk.d/latest | tee out/release/version.txt
