import hashlib
import logging
import json
import zlib
import os

from flask import Flask, render_template, request, abort
from pobgen import POBGenerator
import nebuloch


app = Flask(__name__)


_application_version = None
git_sha1 = None


def set_versions():
    global _application_version, git_sha1
    _application_version = os.environ.get('VOID_BATTERY_UPDATED', '<unknown>')
    git_sha1 = os.environ.get('VOID_BATTERY_VERSION', '<unknown>')


set_versions()


def get_application_version():
    return _application_version


@app.route('/version')
def version():
    return git_sha1


@app.route('/version.json')
def version_json():
    return {
        'application': get_application_version(),
        'commit': git_sha1,
        'compatible': nebuloch.version,
    }


PAGES = [
    ('/pob/', 'POB'),
]


@app.route('/')
def index():
    return render_template(
        'index.html',
        pages=PAGES,
        version=get_application_version(),
    )


@app.route('/pob/fingerprint')
def pob_fingerprint():
    return nebuloch.fingerprint


@app.route('/pob/', methods=['GET', 'POST'])
def pob():
    if request.method == 'GET':
        data = ''
        tr_errors = None
    else:
        r_form_data = request.form['data']
        try:
            j = json.loads(r_form_data)
        except json.JSONDecodeError:
            abort(400)
        try:
            items = j['items']
            tree = j['passive-skills']
        except KeyError:
            abort(400)
        generator = POBGenerator()
        try:
            data = generator.export(items, tree)
            tr_errors = generator.errors
        except Exception as e:
            data = f'伺服器錯誤\n{e.__class__.__name__}: {e}'
            tr_errors = None
            logging.exception('Unexpected exception')
    return render_template(
        'pob.html',
        pages=PAGES,
        accountName=request.args.get('accountName', ''),
        character=request.args.get('character', ''),
        data=data,
        tr_errors=tr_errors,
        version=get_application_version(),
        compat=nebuloch.version
    )
