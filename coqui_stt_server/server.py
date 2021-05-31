"""Server hosting the STT UI"""
import json
import logging
import os
import socket
import threading
import time
from typing import Optional, Tuple

from flask import Flask, Response, Blueprint, redirect, render_template, request, url_for
from flask_cors import CORS
from flask_socketio import SocketIO

from .modelmanager import ModelManager

app = Flask(__name__)
CORS(app, origins=["https://reub.in", "https://coqui.ai"])
app.config['FILEDIR'] = 'static/_files/'
socketio = SocketIO(app, cors_allowed_origins=["https://reub.in", "https://coqui.ai"])

_server_initialized = threading.Event()


def is_debug() -> bool:
    return "COQUI_STT_SERVER_DEBUG" in os.environ


def get_server_hostport() -> Tuple[str, int]:
    _server_initialized.wait()
    assert (
        "SERVER_HOST" in app.config
    ), "server not initialized (should never happen due to wait above)"
    assert (
        "SERVER_PORT" in app.config
    ), "server not initialized (should never happen due to wait above)"
    return (app.config["SERVER_HOST"], app.config["SERVER_PORT"])


@app.route("/")
def index():
    host, port = get_server_hostport()
    return render_template(
        "index.html",
        model_zoo_url=f"https://reub.in/test_model_callback.html?callback_url=http://{host}:{port}/install_model",
        installed_models=list(app.config["MODEL_MANAGER"].list_models()),
    )


@app.route("/install_model", methods=["POST"])
def install_model():
    model_card = json.loads(request.form["model_card"])
    print(f"Install model got data: {json.dumps(model_card)}")
    install_id = app.config["MODEL_MANAGER"].download_model(model_card)
    return redirect(url_for("model_install_page", install_id=install_id))


@app.route("/install_model/<string:install_id>")
def model_install_page(install_id):
    print(app.config["MODEL_MANAGER"].install_tasks)
    task = app.config["MODEL_MANAGER"].get_install_task_state(install_id)
    return render_template(
        "model_install.html",
        install_id=install_id,
        model_name=task.model_card.name,
        start_progress=task.total_progress,
    )


@app.route("/install_model/<string:install_id>/progress")
def get_progress_for_install(install_id):
    if not app.config["MODEL_MANAGER"].has_install_task_state(install_id):
        return ("Not found", 404)

    def generate():
        progress = (
            app.config["MODEL_MANAGER"]
            .get_install_task_state(install_id)
            .total_progress
        )
        while progress < 100:
            yield f"data:{progress}\n\n"
            time.sleep(1)
            progress = (
                app.config["MODEL_MANAGER"]
                .get_install_task_state(install_id)
                .total_progress
            )
        yield "data:100\n\n"

    return Response(generate(), mimetype="text/event-stream")


#@app.route("/transcribe/<string:model_name>")
@app.route("/transcribe")
def transcription_client_page():
#    # get model info from ModelManager
#    task = app.config["MODEL_MANAGER"].get_install_task_state(install_id),
#    # TODO: start WS transcription server in
#    # a background Thread or Process with selected model
    return render_template("transcribe.html")
#                           model_name=task.model_card.name,
#                           ws_transcription_server_info="foobar")


### from Miguel grinbergs socketio audio example
##
#

bp = Blueprint('audio', __name__, static_folder='static',
               template_folder='templates')

@socketio.on('start-recording', namespace='/audio')
def start_recording(options):
    """Start recording audio from the client."""
    id = uuid.uuid4().hex  # server-side filename
    session['wavename'] = id + '.wav'
    wf = wave.open(current_app.config['FILEDIR'] + session['wavename'], 'wb')
    wf.setnchannels(options.get('numChannels', 1))
    wf.setsampwidth(options.get('bps', 16) // 8)
    wf.setframerate(options.get('fps', 44100))
    session['wavefile'] = wf


@socketio.on('write-audio', namespace='/audio')
def write_audio(data):
    """Write a chunk of audio from the client."""
    session['wavefile'].writeframes(data)


@socketio.on('end-recording', namespace='/audio')
def end_recording():
    """Stop recording audio from the client."""
    emit('add-wavefile', url_for('static',filename='_files/' + session['wavename']))
    session['wavefile'].close()
    del session['wavefile']
    del session['wavename']

#
##
### from Miguel grinbergs socketio audio example

def start_app(host: str = "127.0.0.1", port: Optional[int] = None):
    if not is_debug():
        werkzeug_log = logging.getLogger("werkzeug")
        werkzeug_log.setLevel(logging.ERROR)

    port=5555
    # Get available but known port if no explicit port was specified
    if not port:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("localhost", 0))
        port = sock.getsockname()[1]
        sock.close()

    app.config["MODEL_MANAGER"] = ModelManager()
    app.config["SERVER_HOST"] = host
    app.config["SERVER_PORT"] = port
    _server_initialized.set()

    app.run(
        host=host,
        port=port,
        debug=is_debug(),
        use_reloader=False,  # Disable reloader to avoid problems when running the server from a thread
    )