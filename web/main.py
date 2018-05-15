# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import hashlib
import logging
import json
import zlib

import google.appengine.api.modules.modules
from google.appengine.api import app_identity
import cloudstorage as gcs
from flask import Flask, render_template, request, abort
from pobgen import export
from nebuloch.names import CannotTranslateName
from nebuloch.mods import CannotTranslateMod


app = Flask(__name__)


def write_exception_data(data):
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
    filename = '/%s/%s.tracking' % (bucket_name, tracking)
    gcs_file = gcs.open(filename, 'w', content_type='binary/octet-stream')
    gcs_file.write(d)
    gcs_file.close()
    logging.exception('Logged exception to {}'.format(filename))
    return tracking


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        data = ''
    else:
        r_form_data = request.form['data']
        try:
            j = json.loads(r_form_data)
        except ValueError:
            # This should really be JSONDecodeError, but we are stuck in python 2.7
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
            error = '錯誤：無法翻譯此名稱：' + unicode(e)
            tracking = write_exception_data(j)
        except CannotTranslateMod as e:
            error = '錯誤：無法翻譯此詞綴：' + unicode(e)
            tracking = write_exception_data(j)
        except Exception:
            error = '伺服器錯誤'
            tracking = write_exception_data(j)
        else:
            success = True
        if not success:
            data = '{}\n追蹤代碼：{}'.format(error, tracking)
    return render_template(
        'index.html',
        accountName=request.args.get('accountName', ''),
        character=request.args.get('character', ''),
        data=data,
        version=google.appengine.api.modules.modules.get_current_version_name()
    )
