import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)


LABEL_MAPPING = {
    "Normal": 0,
    "Attack": 1,
    "Fault": 2,
    "normal": 0,
    "attack": 1,
    "fault": 2,
    0: 0,
    1: 1,
    2: 2
}

LABEL_NAME_MAPPING = {
    0: "Normal",
    1: "Attack",
    2: "Fault"
}

TARGET_COLUMN = "label"

PREDICTION_COLUMNS = [
    "DT_prediction",
    "RF_prediction",
    "LR_prediction"
]

MODEL_PREDICTION_NAMES = {
    "Decision Tree": "DT_prediction",
    "Random Forest": "RF_prediction",
    "Logistic Regression": "LR_prediction",
    "Manual Hard Voting Ensemble": "ensemble_prediction"
}


def setup_paths(base_dir):
    base_dir = Path(base_dir).resolve()
    data_dir = base_dir / "data"
    processed_dir = data_dir / "processed"
    outputs_dir = base_dir / "outputs"

    processed_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "base_dir": base_dir,
        "processed_dir": processed_dir,
        "outputs_dir": outputs_dir,
        "df_test": processed_dir / "df_test_lengkap.csv",
        "test_predictions": processed_dir / "test_predictions.csv",
        "test_predictions_numeric": processed_dir / "test_predictions_numeric.csv",
        "ensemble_result": processed_dir / "test_predictions_with_ensemble.csv",
        "dashboard_result": processed_dir / "ensemble_result_for_friend.csv",
        "evaluation_metrics": outputs_dir / "performance_metrics_result.csv",
        "classification_report": outputs_dir / "ensemble_classification_report.txt",
        "confusion_matrix": outputs_dir / "ensemble_confusion_matrix.csv",
        "evaluation_data": outputs_dir / "evaluation_data_with_predictions.csv",
        "confusion_matrix_plot": outputs_dir / "ensemble_confusion_matrix.png",
        "metrics_plot": outputs_dir / "model_metrics_comparison.png"
    }

    return paths


def load_csv(path, dataset_name):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"{dataset_name} tidak ditemukan di: {path}")

    data = pd.read_csv(path)
    print(f"{dataset_name} berhasil dimuat.")
    print(f"Path: {path}")
    print(f"Shape: {data.shape}")

    return data


def validate_columns(data, required_columns, dataset_name):
    missing_columns = [
        column for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom berikut tidak tersedia pada {dataset_name}: {missing_columns}"
        )

    print(f"Semua kolom wajib pada {dataset_name} tersedia.")


def convert_predictions_to_numeric(test_predictions):
    required_columns = [TARGET_COLUMN] + PREDICTION_COLUMNS
    validate_columns(test_predictions, required_columns, "test_predictions")

    numeric_data = test_predictions.copy()

    for column in PREDICTION_COLUMNS:
        numeric_data[column] = numeric_data[column].map(LABEL_MAPPING)

    if numeric_data[PREDICTION_COLUMNS].isnull().sum().sum() > 0:
        missing_summary = numeric_data[PREDICTION_COLUMNS].isnull().sum()
        raise ValueError(
            f"Ada nilai prediksi yang gagal dikonversi ke numerik:\n{missing_summary}"
        )

    for column in required_columns:
        numeric_data[column] = numeric_data[column].astype(int)

    print("Kolom label dan prediksi berhasil dikonversi menjadi numerik.")

    return numeric_data


def majority_vote_row(row):
    votes = [
        row["DT_prediction"],
        row["RF_prediction"],
        row["LR_prediction"]
    ]

    return pd.Series(votes).mode()[0]


def apply_manual_hard_voting(prediction_data):
    required_columns = [TARGET_COLUMN] + PREDICTION_COLUMNS
    validate_columns(prediction_data, required_columns, "prediction_data")

    voting_data = prediction_data.copy()

    voting_data["ensemble_prediction"] = voting_data.apply(
        majority_vote_row,
        axis=1
    ).astype(int)

    print("Manual hard voting ensemble berhasil dibuat.")

    return voting_data


def create_dashboard_dataset(ensemble_data):
    dashboard_columns = [
        "timestamp",
        "device_id",
        "voltage",
        "latency",
        "label",
        "ensemble_prediction"
    ]

    validate_columns(ensemble_data, dashboard_columns, "ensemble_data")

    dashboard_data = ensemble_data[dashboard_columns].copy()

    dashboard_data = dashboard_data.rename(
        columns={
            "label": "status",
            "ensemble_prediction": "ensemble_pred"
        }
    )

    print("Dataset ringkas untuk dashboard berhasil dibuat.")

    return dashboard_data


def align_actual_label(df_test, ensemble_data):
    required_df_test_columns = [
        "timestamp",
        "device_id",
        TARGET_COLUMN
    ]

    required_ensemble_columns = [
        "timestamp",
        "device_id",
        "DT_prediction",
        "RF_prediction",
        "LR_prediction",
        "ensemble_prediction"
    ]

    validate_columns(df_test, required_df_test_columns, "df_test")
    validate_columns(ensemble_data, required_ensemble_columns, "ensemble_data")

    if len(df_test) != len(ensemble_data):
        raise ValueError(
            "Jumlah baris df_test dan ensemble_data berbeda. "
            "Gunakan merge berdasarkan timestamp dan device_id jika urutan data tidak sama."
        )

    same_timestamp = (
        df_test["timestamp"].values == ensemble_data["timestamp"].values
    ).all()

    same_device_id = (
        df_test["device_id"].values == ensemble_data["device_id"].values
    ).all()

    if not same_timestamp or not same_device_id:
        raise ValueError(
            "Urutan timestamp atau device_id tidak sama. "
            "Perlu merge berdasarkan key sebelum evaluasi."
        )

    evaluation_data = ensemble_data.copy()
    evaluation_data["actual_label"] = df_test[TARGET_COLUMN].values

    columns_to_convert = [
        "actual_label",
        "DT_prediction",
        "RF_prediction",
        "LR_prediction",
        "ensemble_prediction"
    ]

    for column in columns_to_convert:
        evaluation_data[column] = evaluation_data[column].astype(int)

    print("Data evaluasi berhasil dibuat.")

    return evaluation_data


def evaluate_models(evaluation_data):
    y_true = evaluation_data["actual_label"]

    evaluation_results = []

    for model_name, prediction_column in MODEL_PREDICTION_NAMES.items():
        y_pred = evaluation_data[prediction_column]

        evaluation_results.append(
            {
                "model": model_name,
                "accuracy": accuracy_score(y_true, y_pred),
                "precision": precision_score(
                    y_true,
                    y_pred,
                    average="weighted",
                    zero_division=0
                ),
                "recall": recall_score(
                    y_true,
                    y_pred,
                    average="weighted",
                    zero_division=0
                ),
                "f1_score": f1_score(
                    y_true,
                    y_pred,
                    average="weighted",
                    zero_division=0
                )
            }
        )

    evaluation_results_df = pd.DataFrame(evaluation_results)

    print("Evaluasi semua model berhasil dihitung.")

    return evaluation_results_df


def create_ensemble_report(evaluation_data):
    target_names = [
        LABEL_NAME_MAPPING[0],
        LABEL_NAME_MAPPING[1],
        LABEL_NAME_MAPPING[2]
    ]

    report = classification_report(
        evaluation_data["actual_label"],
        evaluation_data["ensemble_prediction"],
        labels=[0, 1, 2],
        target_names=target_names,
        zero_division=0
    )

    cm = confusion_matrix(
        evaluation_data["actual_label"],
        evaluation_data["ensemble_prediction"],
        labels=[0, 1, 2]
    )

    cm_df = pd.DataFrame(
        cm,
        index=[f"Actual {name}" for name in target_names],
        columns=[f"Predicted {name}" for name in target_names]
    )

    print("Classification report dan confusion matrix ensemble berhasil dibuat.")

    return report, cm, cm_df, target_names


def save_confusion_matrix_plot(cm, target_names, output_path):
    plt.figure(figsize=(6, 5))
    plt.imshow(cm, interpolation="nearest")
    plt.title("Confusion Matrix - Manual Hard Voting Ensemble")
    plt.colorbar()

    tick_marks = np.arange(len(target_names))

    plt.xticks(tick_marks, target_names)
    plt.yticks(tick_marks, target_names)

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(
                j,
                i,
                cm[i, j],
                ha="center",
                va="center"
            )

    plt.xlabel("Predicted Label")
    plt.ylabel("Actual Label")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Plot confusion matrix berhasil disimpan ke: {output_path}")


def save_metrics_plot(evaluation_results_df, output_path):
    metrics = [
        "accuracy",
        "precision",
        "recall",
        "f1_score"
    ]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    axes = axes.flatten()

    for index, metric in enumerate(metrics):
        axes[index].bar(
            evaluation_results_df["model"],
            evaluation_results_df[metric]
        )

        axes[index].set_title(f"Perbandingan {metric}")
        axes[index].set_xlabel("Model")
        axes[index].set_ylabel(metric)
        axes[index].set_ylim(0, 1.05)
        axes[index].tick_params(axis="x", rotation=20)

        for model_index, value in enumerate(evaluation_results_df[metric]):
            axes[index].text(
                model_index,
                value,
                f"{value:.3f}",
                ha="center",
                va="bottom"
            )

    plt.suptitle(
        "Perbandingan Performance Metrics Model Individual dan Ensemble",
        fontsize=14
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Plot perbandingan metrik berhasil disimpan ke: {output_path}")


def save_outputs(
    paths,
    numeric_predictions,
    ensemble_data,
    dashboard_data,
    evaluation_data,
    evaluation_results_df,
    ensemble_report,
    ensemble_cm_df,
    ensemble_cm,
    target_names
):
    numeric_predictions.to_csv(
        paths["test_predictions_numeric"],
        index=False
    )

    ensemble_data.to_csv(
        paths["ensemble_result"],
        index=False
    )

    dashboard_data.to_csv(
        paths["dashboard_result"],
        index=False
    )

    evaluation_results_df.to_csv(
        paths["evaluation_metrics"],
        index=False
    )

    evaluation_data.to_csv(
        paths["evaluation_data"],
        index=False
    )

    ensemble_cm_df.to_csv(
        paths["confusion_matrix"],
        index=True
    )

    with open(paths["classification_report"], "w", encoding="utf-8") as file:
        file.write("MANUAL HARD VOTING ENSEMBLE CLASSIFICATION REPORT\n")
        file.write("=" * 70)
        file.write("\n\n")
        file.write(ensemble_report)

    save_confusion_matrix_plot(
        ensemble_cm,
        target_names,
        paths["confusion_matrix_plot"]
    )

    save_metrics_plot(
        evaluation_results_df,
        paths["metrics_plot"]
    )

    print("Semua output berhasil disimpan.")


def print_best_model(evaluation_results_df):
    best_model = evaluation_results_df.sort_values(
        by="f1_score",
        ascending=False
    ).iloc[0]

    print("\nModel terbaik berdasarkan F1-score:")
    print(f"Model     : {best_model['model']}")
    print(f"Accuracy  : {best_model['accuracy']}")
    print(f"Precision : {best_model['precision']}")
    print(f"Recall    : {best_model['recall']}")
    print(f"F1-score  : {best_model['f1_score']}")


def run_pipeline(base_dir):
    paths = setup_paths(base_dir)

    df_test = load_csv(
        paths["df_test"],
        "df_test_lengkap.csv"
    )

    test_predictions = load_csv(
        paths["test_predictions"],
        "test_predictions.csv"
    )

    numeric_predictions = convert_predictions_to_numeric(
        test_predictions
    )

    ensemble_data = apply_manual_hard_voting(
        numeric_predictions
    )

    dashboard_data = create_dashboard_dataset(
        ensemble_data
    )

    evaluation_data = align_actual_label(
        df_test,
        ensemble_data
    )

    evaluation_results_df = evaluate_models(
        evaluation_data
    )

    ensemble_report, ensemble_cm, ensemble_cm_df, target_names = create_ensemble_report(
        evaluation_data
    )

    save_outputs(
        paths,
        numeric_predictions,
        ensemble_data,
        dashboard_data,
        evaluation_data,
        evaluation_results_df,
        ensemble_report,
        ensemble_cm_df,
        ensemble_cm,
        target_names
    )

    print("\nHasil evaluasi:")
    print(evaluation_results_df)

    print("\nClassification Report - Manual Hard Voting Ensemble")
    print("=" * 70)
    print(ensemble_report)

    print("\nConfusion Matrix Ensemble:")
    print(ensemble_cm_df)

    print_best_model(evaluation_results_df)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Pipeline prediksi ensemble manual hard voting."
    )

    parser.add_argument(
        "--base-dir",
        type=str,
        default="..",
        help="Path root project yang berisi folder data/processed dan outputs."
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    run_pipeline(args.base_dir)
