"""Development entry point.

    python run.py                 # http://127.0.0.1:5000
    flask --app run run --debug   # equivalent via the Flask CLI
    gunicorn "run:app"            # production
"""

import os

from app import create_app, db
from app.models import (
    DriftReport,
    Experiment,
    PredictionLog,
    RetrainEvent,
    Run,
)

app = create_app()


@app.shell_context_processor
def _shell_context():
    return {
        "db": db,
        "Experiment": Experiment,
        "Run": Run,
        "PredictionLog": PredictionLog,
        "DriftReport": DriftReport,
        "RetrainEvent": RetrainEvent,
    }


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
