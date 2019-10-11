python -m venv venv
venv/bin/pip install git+https://github.com/OmegaK2/PyPoE#egg=PyPoE[cli] tqdm
venv/bin/pypoe_exporter config set ggpk_path install.sh  # just to suppress warnings
go build -o patcher/poepatcher patcher/patcher.go
