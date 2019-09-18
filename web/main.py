from __future__ import unicode_literals
import hashlib
import logging
import json
import zlib
import os

import cachetools.func
from flask import Flask, render_template, request, abort, redirect
from pobgen import export
from nebuloch.names import CannotTranslateName
from nebuloch.mods import CannotTranslateMod
import nebuloch
import prices


app = Flask(__name__)


def noop(function):
    def _noop(data):
        logging.exception('Data example not stored')
    return _noop


@noop
def write_exception_data(data):
    # This function is to be updated to python3 APIs.
    import google.appengine.api.modules.modules
    from google.appengine.api import app_identity
    import cloudstorage as gcs
    bucket_name = app_identity.get_default_gcs_bucket_name()
    j = json.dumps(data, separators=',:', ensure_ascii=False, sort_keys=True)
    jb = j.encode('utf-8')
    d = zlib.compress(jb)
    m = hashlib.sha1(jb)
    version = google.appengine.api.modules.modules.get_current_version_name()
    if version is None:
        version = '<NONE>'
    m.update(version)
    tracking = m.hexdigest()
    filename = '/%s/error-dumps/%s.tracking' % (bucket_name, tracking)
    gcs_file = gcs.open(filename, 'w', content_type='binary/octet-stream')
    gcs_file.write(d)
    gcs_file.close()
    logging.exception('Logged exception to {}'.format(filename))
    return tracking


def get_application_version():
    return os.environ.get('GAE_VERSION', '<unknown-version>')


PAGES = [
    ('/pob/', 'POB'),
    ('/ninja/LeagueSC/', '查價')
]


@app.route('/')
def index():
    return render_template(
        'index.html',
        pages=PAGES,
        version=get_application_version(),
    )


@app.route('/ninja/LeagueSC/')
def red():
    return redirect('/ninja/LeagueSC/Currency/')


@cachetools.func.ttl_cache()
def get_price_info(league):
    import cloudstorage as gcs
    bucket_name = 'void-battery.appspot.com'
    filename = '/%s/prices/%s.json' % (bucket_name, league)
    file = gcs.open(filename)
    data = json.load(file)
    file.close()
    return prices.getPriceGroups(data)


@app.route('/ninja/LeagueSC/<group>/')
def ninja(group):
    # XXX
    return render_template(
        'ninja.html',
        pages=PAGES,
        current_group=group,
        version=get_application_version(),
        groups=[('Currency', '通貨')],
        generatedAt='無資料',
        is_user_stash=False,
    )
    priceGroups, exaltedPrice, generatedAt = get_price_info('BetrayalSC')
    try:
        info = priceGroups[group]
    except KeyError:
        abort(404)
    return render_template(
        'ninja.html',
        pages=PAGES,
        current_group=group,
        groups=prices.Groups,
        version=get_application_version(),
        items=info,
        exaltedPrice=exaltedPrice,
        generatedAt=generatedAt,
        is_user_stash=False,
    )


@app.route('/pob/', methods=['GET', 'POST'])
def pob():
    if request.method == 'GET':
        data = ''
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
        success = False
        try:
            data = export(items, tree)
        except CannotTranslateName as e:
            error = '錯誤：無法翻譯此名稱：' + str(e)
            tracking = write_exception_data(j)
        except CannotTranslateMod as e:
            error = '錯誤：無法翻譯此詞綴：' + str(e)
            tracking = write_exception_data(j)
        except Exception:
            error = '伺服器錯誤'
            tracking = write_exception_data(j)
        else:
            success = True
        if not success:
            data = '{}'.format(error)
            tracking = tracking  # trick pyflakes
            # XXX: restore this when write_exception_data is upgraded to python3
            # data = '{}\n追蹤代碼：{}'.format(error, tracking)
    return render_template(
        'pob.html',
        pages=PAGES,
        accountName=request.args.get('accountName', ''),
        character=request.args.get('character', ''),
        data=data,
        version=get_application_version(),
        compat=nebuloch.version
    )
