from __future__ import annotations

import base64
import importlib
import io
import warnings
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import confusion_matrix
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import MinMaxScaler

from backend.models import Interaction
from backend.services.nn_recommender import build_nn_training_dataframe

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=ConvergenceWarning)

matplotlib_module = importlib.import_module("matplotlib")
matplotlib_module.use("Agg")
plt = importlib.import_module("matplotlib.pyplot")


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _rounded_rating(value: float) -> int:
    return int(_clamp(round(float(value)), 1, 5))


def _encode_figure(fig) -> str:
    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


def _make_line_plot(title: str, x_values: list[int], train_values: list[float], val_values: list[float], train_label: str, val_label: str):
    fig, axis = plt.subplots(figsize=(8.2, 4.6))
    axis.plot(x_values, train_values, marker="o", linewidth=2.2, label=train_label)
    axis.plot(x_values, val_values, marker="o", linewidth=2.2, label=val_label)
    axis.set_title(title)
    axis.set_xlabel("Epoch")
    axis.set_ylabel(title.split("vs")[0].strip())
    axis.grid(True, alpha=0.18)
    axis.legend()
    return _encode_figure(fig)


def _make_confusion_matrix_plot(matrix: np.ndarray) -> str:
    fig, axis = plt.subplots(figsize=(6.5, 5.5))
    image = axis.imshow(matrix, cmap="YlOrRd")
    axis.set_title("Confusion Matrix")
    axis.set_xlabel("Predicted Rating")
    axis.set_ylabel("Actual Rating")
    axis.set_xticks(range(5))
    axis.set_yticks(range(5))
    axis.set_xticklabels([1, 2, 3, 4, 5])
    axis.set_yticklabels([1, 2, 3, 4, 5])

    for row_index in range(matrix.shape[0]):
        for col_index in range(matrix.shape[1]):
            axis.text(col_index, row_index, str(int(matrix[row_index, col_index])), ha="center", va="center", color="#111827", fontsize=9)

    fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    return _encode_figure(fig)


def _make_scatter_plot(actual: list[float], predicted: list[float]) -> str:
    fig, axis = plt.subplots(figsize=(7.0, 5.2))
    axis.scatter(actual, predicted, alpha=0.7, color="#38bdf8", edgecolor="#0f172a")
    axis.plot([1, 5], [1, 5], linestyle="--", linewidth=2.0, color="#f59e0b", label="Ideal")
    axis.set_xlim(1, 5)
    axis.set_ylim(1, 5)
    axis.set_title("Prediction vs Actual")
    axis.set_xlabel("Actual Rating")
    axis.set_ylabel("Predicted Rating")
    axis.grid(True, alpha=0.18)
    axis.legend()
    return _encode_figure(fig)


def build_nn_metrics(data_dir: Path) -> dict:
    interactions = Interaction.query.all()
    frame = build_nn_training_dataframe(None, data_dir, interactions)

    feature_frame = frame[["user_id", "movie_id", "watch_duration_norm", "skipped_scenes", "skipped_music", "interest_level"]].to_numpy(dtype=float)
    target = frame["rating"].to_numpy(dtype=float)
    target_scaler = MinMaxScaler(feature_range=(0.0, 1.0))
    target_scaled = target_scaler.fit_transform(target.reshape(-1, 1)).ravel()

    split_index = max(1, int(len(frame) * 0.8))
    x_train = feature_frame[:split_index]
    y_train = target_scaled[:split_index]
    x_val = feature_frame[split_index:]
    y_val = target_scaled[split_index:]

    if len(x_val) == 0:
        x_val = x_train
        y_val = y_train

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_val_scaled = scaler.transform(x_val)

    model = MLPRegressor(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        random_state=42,
        warm_start=True,
        max_iter=1,
        shuffle=True,
    )

    epochs = 8
    loss_history: list[float] = []
    mae_history: list[float] = []
    val_loss_history: list[float] = []
    val_mae_history: list[float] = []
    epoch_ids = list(range(1, epochs + 1))

    for _ in range(epochs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            model.fit(x_train_scaled, y_train)

        train_predictions_scaled = model.predict(x_train_scaled)
        val_predictions_scaled = model.predict(x_val_scaled)

        train_predictions = target_scaler.inverse_transform(train_predictions_scaled.reshape(-1, 1)).ravel()
        val_predictions = target_scaler.inverse_transform(val_predictions_scaled.reshape(-1, 1)).ravel()
        train_actual = target_scaler.inverse_transform(y_train.reshape(-1, 1)).ravel()
        val_actual = target_scaler.inverse_transform(y_val.reshape(-1, 1)).ravel()

        train_predictions = np.clip(train_predictions, 1.0, 5.0)
        val_predictions = np.clip(val_predictions, 1.0, 5.0)
        train_actual = np.clip(train_actual, 1.0, 5.0)
        val_actual = np.clip(val_actual, 1.0, 5.0)

        train_mse = float(np.mean((train_predictions - train_actual) ** 2))
        train_mae = float(np.mean(np.abs(train_predictions - train_actual)))
        val_mse = float(np.mean((val_predictions - val_actual) ** 2))
        val_mae = float(np.mean(np.abs(val_predictions - val_actual)))

        loss_history.append(round(train_mse, 4))
        mae_history.append(round(train_mae, 4))
        val_loss_history.append(round(val_mse, 4))
        val_mae_history.append(round(val_mae, 4))

    final_val_predictions_scaled = model.predict(x_val_scaled)
    final_val_predictions = target_scaler.inverse_transform(final_val_predictions_scaled.reshape(-1, 1)).ravel()
    final_val_predictions = np.clip(final_val_predictions, 1.0, 5.0)
    actual_round = [_rounded_rating(value) for value in target_scaler.inverse_transform(y_val.reshape(-1, 1)).ravel()]
    predicted_round = [_rounded_rating(value) for value in final_val_predictions]
    matrix = confusion_matrix(actual_round, predicted_round, labels=[1, 2, 3, 4, 5])

    metrics = {
        "epochs": epochs,
        "rows": int(len(frame)),
        "train_loss": loss_history,
        "train_mae": mae_history,
        "val_loss": val_loss_history,
        "val_mae": val_mae_history,
        "final_mae": round(val_mae_history[-1], 4),
        "final_loss": round(val_loss_history[-1], 4),
    }

    plots = {
        "loss_curve": _make_line_plot("Training Loss vs Epochs", epoch_ids, loss_history, val_loss_history, "Train Loss", "Validation Loss"),
        "mae_curve": _make_line_plot("MAE vs Epochs", epoch_ids, mae_history, val_mae_history, "Train MAE", "Validation MAE"),
        "confusion_matrix": _make_confusion_matrix_plot(matrix),
        "prediction_vs_actual": _make_scatter_plot([float(value) for value in actual_round], [float(value) for value in final_val_predictions]),
    }

    return {
        "metrics": metrics,
        "plots": plots,
        "confusion_matrix": matrix.tolist(),
        "prediction_samples": [
            {"actual": int(actual), "predicted": round(float(predicted), 4)}
            for actual, predicted in zip(actual_round, final_val_predictions)
        ],
    }
