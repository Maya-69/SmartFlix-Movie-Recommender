from pathlib import Path

from flask import Blueprint, jsonify

from backend.services.metrics_service import build_nn_metrics

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.get("/metrics/nn")
def metrics_nn():
    data_dir = Path(__file__).resolve().parents[1] / "data"
    try:
        payload = build_nn_metrics(data_dir)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(payload)
