# Prepare data

Use the tools in `../patcher` to populate game data

# Automated tests

```
pytest tests
```

Note that the tests are very limited

# Verifying against real characters

`tools/ladder_verify.py` exports real characters from the current TW challenge
league ladder and checks the result: no untranslated names or mods, and every
item, gem and passive the API reported present in the generated build.

```
python3 tools/ladder_verify.py             # verify 10 public characters
python3 tools/ladder_verify.py --offline   # re-check from the cache, no requests
```

Only accounts with a public profile answer; the rest are reported as skipped.

All the network access lives in `tools/poe_tw.py`, which obeys the
`X-Rate-Limit` headers pathofexile.tw advertises, keeps to a fraction of every
advertised rule, meters 4xx replies separately (GGG restricts clients that make
too many invalid requests), and caches responses so re-runs are free.  Budgets
are shared between processes through a lockfile under `$XDG_CACHE_HOME`, so
running two copies at once is safe.  It also works standalone:

```
python3 tools/poe_tw.py items --account 'afg984#0342' --character GPGPU
```

# Testing locally

Start the web server and visit http://localhost:5000

## Method 1: Use a virtual environment

```
virtualenv env
env/bin/pip install -r requirements.txt
env/bin/python local_web.py
```

## Method 2: Use docker

```
docker build . -t gcr.io/void-battery/v0
docker run -p 5000:5000 -e PORT=5000 gcr.io/void-vattery/v0:latest
```
