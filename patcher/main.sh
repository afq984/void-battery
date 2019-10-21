export1() {
	venv/bin/python scripts/exporter.py dat json --files=$1 out/extracted/$1.$2.json
}
set -eux
poepatcher/poepatcher \
	"PathOfExile.exe" \
	"PathOfExile_x64.exe" \
	"Metadata/StatDescriptions/stat_descriptions.txt" \
	"Data/BaseItemTypes.dat" \
	"Data/PassiveSkills.dat" \
	"Data/ActiveSkills.dat" \
	"Data/Traditional Chinese/BaseItemTypes.dat" \
	"Data/Traditional Chinese/PassiveSkills.dat" \
	"Data/Traditional Chinese/ActiveSkills.dat" \
	"Data/Traditional Chinese/Words.dat"

cp Content.ggpk.d/latest/Metadata/StatDescriptions/stat_descriptions.txt out/extracted/stat_descriptions.txt
datfiles=(BaseItemTypes ActiveSkills PassiveSkills)
venv/bin/python scripts/exporter.py config set language 'English'
for datfile in "${datfiles[@]}"
do
	export1 "$datfile" en
done
venv/bin/python scripts/exporter.py config set language 'Traditional Chinese'
for datfile in "${datfiles[@]}"
do
	export1 "$datfile" tc
done
venv/bin/python scripts/exporter.py dat json --files=Words.dat out/extracted/Words.tc.json

venv/bin/python scripts/datrelease.py
venv/bin/python scripts/statparse.py out/extracted/stat_descriptions.txt > out/release/stat_descriptions.json
python scripts/charversion.py Content.ggpk.d/latest | tee out/release/version.txt
