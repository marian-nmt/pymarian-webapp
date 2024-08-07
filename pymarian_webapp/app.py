#!/usr/bin/env python
"""
Serves Marian model using Flask HTTP server
"""
import argparse
import getpass
import os
import platform
import socket
import sys
import time
from pathlib import Path
from typing import List, Optional

import flask
import pymarian
import yaml
from flask import Blueprint, Flask, request, send_from_directory
from flask_socketio import SocketIO, emit, send
from pymarian.defaults import Defaults as D

from . import __version__, log
from .constants import BASE_ARGS, DEF_FLICKER_SIZE
from .translator_service import TranslatorService

DEF_MODEL_ID = 'NA'
FLOAT_POINTS = 4
exp = None
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
bp = Blueprint('app', __name__, template_folder='templates', static_folder='static')
socketio = SocketIO(app)


sys_info = {
    'pymarian': pymarian.__version__,
    'Python Version': sys.version,
    'Platform': platform.platform(),
    'Platform Version': platform.version(),
    'Processor': platform.processor(),
    'GPU': '[unavailable]',  # TODO: get GPU name
    'Hostname': socket.gethostname(),
    'Username': getpass.getuser(),
    'Root Directory': str(Path(__file__).parent.absolute()),
    'Base Args': BASE_ARGS,
}


def render_template(*args, **kwargs):
    return flask.render_template(*args, environ=os.environ, **kwargs)


def jsonify(obj):

    if obj is None or isinstance(obj, (int, bool, str)):
        return obj
    elif isinstance(obj, float):
        return round(obj, FLOAT_POINTS)
    elif isinstance(obj, dict):
        return {key: jsonify(val) for key, val in obj.items()}
    elif isinstance(obj, list):
        return [jsonify(it) for it in obj]
    # elif isinstance(ob, np.ndarray):
    #    return _jsonify(ob.tolist())
    else:
        log.warning(f"Type {type(obj)} maybe not be json serializable")
        return obj


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(bp.root_path, 'static', 'favicon'), 'favicon.ico')


def attach_routes(**kwargs):
    transl_service = TranslatorService(kwargs.get('mt_models', None), eager_load=kwargs.get('eager', False))
    sys_info['mt_models'] = transl_service.known_models

    @bp.route('/')
    def home():
        return render_template(
            'home.html', translator=transl_service, known_models=list(transl_service.known_models.keys()), model_data=transl_service.known_models
        )

    @bp.route("/translate", methods=["POST", "GET"])
    def translate():
        st = time.time()
        if request.method not in ("POST", "GET"):
            return "GET and POST are supported", 400
        if request.method == 'GET':
            args = request.args
        if request.method == 'POST':
            if request.headers.get('Content-Type') == 'application/json':
                args = request.json
            else:
                args = request.form

        if hasattr(args, 'getlist'):
            sources = args.getlist("source")
        else:
            sources = args.get("source")
            if isinstance(sources, str):
                sources = [sources]

        if not sources:
            return "Please submit 'source' parameter", 400

        model_name = args.get("model_name")
        translations = transl_service.translate(model_name, sources)

        res = dict(
            sources=sources, translations=translations, time_taken=round(time.time() - st, 3), time_units='s'
        )

        return flask.jsonify(jsonify(res))

    ####### Live MT ########
    @bp.route("/live", methods=["GET"])
    def live_translate():
        return render_template(
            'livemt.html', translator=transl_service, known_models=list(transl_service.known_models.keys())
        )

    @socketio.on('connect')
    def on_connect(auth):
        log.debug('Client connected')

    @socketio.on('disconnect')
    def ont_disconnect():
        log.debug('Client disconnected')

    @socketio.on('translate')
    def on_translate(data):
        st = time.time()
        model_name = data.get("model_name")
        source = data.get("source", "").strip()
        target_segments_in = data.get("target_segments", [])
        flicker_size = data.get("flicker_size", DEF_FLICKER_SIZE)
        assert (
            isinstance(flicker_size, int) and flicker_size >= 0
        ), f"flicker_size should be an integer. Given: {flicker_size} a {type(flicker_size)}"
        if not source:
            return dict(status=400, error="Please submit 'source' parameter")
        if target_segments_in and not isinstance(target_segments_in, list):
            return dict(status=400, error="target_segments should be a list or empty.")

        if model_name not in transl_service.known_models:
            return dict(status=400, error=f"Model '{model_name}' not found")

        source_segs, target_segs_out = transl_service.live_translate(
            model_name, source=source, target_segments=target_segments_in, flicker_size=flicker_size
        )

        res = dict(
            status=200,
            source_segments=source_segs,
            target_segments=target_segs_out,
            time_taken=round(time.time() - st, 3),
            time_units='s',
        )
        return res

    @bp.route('/about')
    def about():
        return render_template('about.html', sys_info=sys_info)


def parse_args():
    parser = argparse.ArgumentParser(
        prog="pymarian-webapp",
        description="Deploy Marian model to a RESTful server",
        epilog=f'Loaded from {__file__}',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Run Flask server in debug mode")
    parser.add_argument("-p", "--port", type=int, help="port to run server on", default=6060)
    parser.add_argument("-ho", "--host", help="Host address to bind.", default='0.0.0.0')
    parser.add_argument("-b", "--base", help="Base prefix path for all the URLs. E.g., /v1")
    parser.add_argument(
        "-c", "--config", type=argparse.FileType('r'), default=None, help="Config file with MT models"
    )
    parser.add_argument("-e", "--eager", action="store_true", help="Eagerly load models")
    args = parser.parse_args()

    config_stream = args.config
    args.mt_models = {}
    if config_stream:
        try:
            config = yaml.safe_load(config_stream)
            args.mt_models = config.get("translators", {})
            args.custom_website_info = config.get("website", {})
        except yaml.YAMLError as exc:
            print(f"Error parsing the config file: {exc}")

    return vars(args)


# uwsgi can take CLI args too
# uwsgi --http 127.0.0.1:5000 --module nllb_serve.app:app # --pyargv "--foo=bar"
cli_args = parse_args()
attach_routes(**cli_args)
app.register_blueprint(bp, url_prefix=cli_args.get('base'))
if cli_args.pop('debug'):
    app.debug = True

# register an index page if needed; and link to home
if cli_args.get('base'):

    @app.route('/')
    def index():
        return render_template('index.html', demo_url=cli_args.get('base'))


def main():
    sys_yaml = yaml.dump(sys_info, default_flow_style=False)
    log.info(f"System Info:\n{sys_yaml}")
    # app.run(port=cli_args["port"], host=cli_args["host"], threaded=False, processes=8)
    # app.run(port=cli_args["port"], host=cli_args["host"], threaded=True)
    """
    FIXME: threaded=True  :: is slow for MTAPI. it doesnt really parallelize requests
           threaded=False, processes=8  :: parallelize requests, but... cached_models doesnt work.
                                so we endup reloading model for each request
    """
    socketio.run(app, port=cli_args["port"], host=cli_args["host"], debug=app.debug)


if __name__ == "__main__":
    main()
