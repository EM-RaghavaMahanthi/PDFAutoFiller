from flask import Flask
from flask_cors import CORS
from src.flaskapis.pipeline_routes import pipeline_bp
from src.utils.stream_status import stream_status

app = Flask(__name__)

# 🔥 This enables CORS for all domains and methods
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

app.register_blueprint(pipeline_bp)

@app.route("/stream/<job_id>")
def stream(job_id):
    return stream_status(job_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
