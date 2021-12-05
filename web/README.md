# Prepare data

Use the tools in `../patcher` to populate game data

# Automated tests

```
pytest tests
```

Note that the tests are very limited

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
