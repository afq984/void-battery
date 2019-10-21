python -m venv venv
venv/bin/pip install git+https://github.com/OmegaK2/PyPoE#egg=PyPoE[cli] tqdm
venv/bin/pypoe_exporter config set ggpk_path install.sh  # just to suppress warnings
cd poepatcher
go build
cd ..
mkdir -p out/release
mkdir -p out/extracted
