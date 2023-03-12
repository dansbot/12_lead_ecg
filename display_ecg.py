from typing import Dict, Optional

import numpy as np
import plotly.graph_objs as go
import yaml
from plotly.subplots import make_subplots

# Define column names
LEADS = ["I", "II", "III", "aVF", "aVR", "aVL", "V1", "V2", "V3", "V4", "V5", "V6"]


def load_ecg(fn: str) -> np.ndarray:
    """
    Load a 2D numpy array from a CSV file with 12-lead ecg data.

    :param fn: File path of the CSV file.
    :type fn: str
    :return: 2D numpy array representing the ecg data in the CSV file.
    :rtype: np.ndarray
    """
    with open(fn, "rb") as fp:
        ecg = np.loadtxt(fp, delimiter=",", skiprows=1)
    return ecg


def load_metadata(fn: str) -> Dict:
    """Load metadata from a YAML file and return it as a dictionary.

    :param fn: The file path of the YAML file to be loaded.
    :type fn: str
    :return: A dictionary containing the loaded metadata.
    :rtype: dict
    """
    with open(fn, "r") as fp:
        metadata = yaml.safe_load(fp)
    return metadata


def make_figure(ecg: np.ndarray, metadata: Dict) -> go.Figure:
    """
    Make a Plotly figure of the ECG data.

    :param ecg: 2D numpy array representing the ecg data.
    :type ecg: np.ndarray
    :param metadata: Metadata associated with the ecg data.
    :type metadata: Dict
    :return: Plotly figure object containing the ECG plot.
    :rtype: go.Figure
    """
    fig = make_subplots(rows=6, cols=2, shared_xaxes=True, subplot_titles=LEADS)
    row, col = 1, 1
    for idx, lead in enumerate(LEADS):
        time_in_seconds = (
            np.arange(ecg.shape[0]) / 500.0
        )  # convert sample number to time in seconds
        fig.add_trace(
            go.Scatter(x=time_in_seconds, y=ecg[:, idx], name=lead),
            row=row,
            col=col,
        )
        col += 1
        if col > 2:
            col = 1
            row += 1

    age = metadata["age"] or "unknown"
    sex = metadata["sex"] or "unknown"
    height = f"{metadata['height']}cm" if metadata["height"] is not None else "unknown"
    weight = f"{metadata['weight']}kg" if metadata["weight"] is not None else "unknown"

    fig.update_layout(
        title=(
            f"{metadata['patient_id']}, "
            f"{metadata['diagnosi']}, "
            f"age: {age}, sex: {sex}, "
            f"height: {height}, weight: {weight}"
        ),
    )

    fig.update_xaxes(title_text="Time (s)", row=6, col=1)
    fig.update_xaxes(title_text="Time (s)", row=6, col=2)

    return fig


def show_figure(
    ecg: Optional[np.ndarray] = None,
    metadata: Optional[Dict] = None,
    fig: Optional[go.Figure] = None,
) -> None:
    """
    Show a Plotly figure of the ECG data.

    If `fig` is not provided, create a new figure with the `ecg` and `data` parameters.

    :param ecg: 2D numpy array representing the ecg data.
    :type ecg: np.ndarray
    :param metadata: Metadata associated with the ecg data.
    :type metadata: Dict
    :param fig: Plotly figure object containing the ECG plot.
    :type fig: go.Figure
    """
    if fig is None:
        assert isinstance(ecg, np.ndarray), "Must provide ECG if fig is None."
        assert metadata, "Must provide metadata if fig is None."
        fig = make_figure(ecg, metadata)
    fig.show()


if __name__ == "__main__":
    ecg_fn = "records/ecg/patient_1.csv"
    meta_fn = "records/meta/patient_1.yaml"

    ecg = load_ecg(ecg_fn)
    metadata = load_metadata(meta_fn)

    show_figure(ecg, metadata)
