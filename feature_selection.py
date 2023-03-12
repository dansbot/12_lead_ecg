from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, train_test_split

DIAGNOSI_MAP = {
    "SR": 0,
    "AFIB": 1,
    "STACH": 0,
    "SARRH": 2,
    "SBRAD": 0,
    "PACE": 3,
    "SVARR": 4,
    "BIGU": 5,
    "AFLT": 6,
    "SVTAC": 7,
    "PSVT": 8,
    "TRIGU": 9,
}

LABELS = {
    str(i): k
    for i, k in enumerate(
        [
            "Sinus Rhythm",
            "Atrial Fibrillation",
            "Sinus Arrhythmia",
            "Normal Functioning Artificial Pacemaker",
            "Supraventricular Arrhythmia",
            "Bigeminal Pattern (Unknown Origin, SV or Ventricular)",
            "Atrial Flutter",
            "Supraventricular Tachycardia",
            "Paroxysmal Supraventricular Tachycardia",
            "Trigeminal Pattern (Unknown Origin, SV or Ventricular)",
        ]
    )
}

CM_LABELS = [""] * (max(list(DIAGNOSI_MAP.values())) + 1)
for k, i in DIAGNOSI_MAP.items():
    CM_LABELS[i] = k
CM_LABELS[0] = "NSR"

DROP_COLUMNS = [
    "ritmi",
    "ecg_id",
    "patient_id",
    "nurse",
    "site",
    "device",
    "recording_date",
    "report",
    "scp_codes",
    "infarction_stadium1",
    "infarction_stadium2",
    "initial_autogenerated_report",
    "baseline_drift",
    "static_noise",
    "burst_noise",
    "electrodes_problems",
    "extra_beats",
    "filename_lr",
    "filename_hr",
    "validated_by",
    "second_opinion",
    "validated_by_human",
    "strat_fold",
]


def format_df(
    df: pd.DataFrame, drop_columns: Union[bool, List[str], None] = True
) -> pd.DataFrame:
    """Preprocesses the input DataFrame to prepare it for further analysis.

    This function drops unnecessary columns, fills missing age values based on height and weight,
    groups patients into age ranges, fills missing values in height and weight based on age and sex,
    and maps categorical variables to numerical values.

    :param df: The DataFrame to preprocess.
    :type df: pd.DataFrame
    :return: The preprocessed DataFrame.
    :rtype: pd.DataFrame
    """

    df = df.drop(columns=DROP_COLUMNS)

    df = fill_age_height_weight(df)

    # fill missing values for heart_axis with missing
    df["heart_axis"] = df["heart_axis"].fillna("Missing")

    # fill missing values for pacemaker with missing
    df["pacemaker"] = df["pacemaker"].fillna("Missing")

    # map heart_axis to numerical values
    df["heart_axis"] = (
        df["heart_axis"]
        .map({k: i for i, k in enumerate(df["heart_axis"].unique())})
        .values
    )
    # map pacemaker to numerical values, there is a pacemaker if "ja" is in the value
    df["pacemaker"] = (
        df["pacemaker"]
        .map({k: int("ja" in str(k)) for i, k in enumerate(df["pacemaker"].unique())})
        .values
    )
    # map diagnosi to numerical values, sr, sb, and st are all nsr
    df["diagnosi"] = df["diagnosi"].map(DIAGNOSI_MAP).values

    return df


def fill_age_height_weight(df: pd.DataFrame) -> pd.DataFrame:
    """
    This function fills missing age, height, and weight values in a given Pandas DataFrame using
    other available data in the same DataFrame.

    :param df: The Pandas DataFrame to be filled.
    :type df: pd.DataFrame

    :return: The Pandas DataFrame with missing age, height, and weight values filled.
    :rtype: pd.DataFrame

    :raises ValueError: If the input DataFrame does not contain the necessary columns.

    """
    # define function to fill missing age values based on height and weight
    def fill_age(row: pd.Series) -> pd.Series:
        """Fill missing age values in a Pandas DataFrame row based on height and weight.

        :param row: A Pandas DataFrame row containing height, weight, and age columns.
        :type row: pandas.Series
        :return: The input row with the age column filled in if it was missing.
        :rtype: pandas.Series
        """
        if np.isnan(row["age"]):
            age_subset = df[
                (df["height"] >= row["height"] - 2.5)
                & (df["height"] <= row["height"] + 2.5)
                & (df["weight"] >= row["weight"] - 2)
                & (df["weight"] <= row["weight"] + 2)
                & (~np.isnan(df["age"]))
            ]["age"]
            if len(age_subset) > 0:
                row["age"] = int(age_subset.median() + 0.5)
            else:
                row["age"] = int(df["age"].mean() + 0.5)
        return row

    # Check that the DataFrame contains the necessary columns
    required_columns = ["age", "height", "weight"]
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Input DataFrame is missing required columns: {missing_columns}"
        )

    # apply function to fill missing age values
    df = df.apply(fill_age, axis=1)

    # Define age range bins and custom labels
    h_age_bins = [-1, 4, 9, 19, np.inf]
    h_age_labels = ["0-4", "5-9", "10-19", "20+"]
    w_age_bins = [-1, 4, 9, 19, 29, 39, 49, 59, 69, 79, 89, np.inf]
    w_age_labels = [
        "0-4",
        "5-9",
        "10-19",
        "20-29",
        "30-39",
        "40-49",
        "50-59",
        "60-69",
        "70-79",
        "80-89",
        "90+",
    ]

    # Group by age range and sex, and fill missing values with the mean
    df["height"] = df.groupby(
        [pd.cut(df["age"], h_age_bins, labels=h_age_labels), "sex"]
    )["height"].transform(lambda x: x.fillna(round(x.mean(), 1)))
    df["weight"] = df.groupby(
        [pd.cut(df["age"], w_age_bins, labels=w_age_labels), "sex"]
    )["weight"].transform(lambda x: x.fillna(round(x.mean(), 1)))

    return df


def train_test_split_by_category(df: pd.DataFrame, category: str):
    """
    Split a pandas DataFrame into train and test sets by category.

    :param df: The input pandas DataFrame.
    :type df: pd.DataFrame
    :param category: The column name of the target variable.
    :type category: str
    :return: A tuple of two tuples, each containing a pandas DataFrame of features and a pandas Series of labels.
             The first tuple contains the train set, and the second tuple contains the test set.
    :rtype: tuple
    """
    # separate the target variable from the rest of the features
    X = df.drop(category, axis=1)
    y = df[category]

    # split the data into train and test sets
    test_size = 0.2
    test_indices = []
    for label in y.unique():
        label_indices = y[y == label].index.tolist()
        label_test_indices = train_test_split(
            label_indices, test_size=test_size, random_state=42
        )[1]
        test_indices.extend(label_test_indices)
    X_train = X.drop(test_indices)
    X_test = X.loc[test_indices]
    y_train = y.drop(test_indices)
    y_test = y.loc[test_indices]
    return (X_train, y_train), (X_test, y_test)


def train(
    X_train: pd.DataFrame, y_train: pd.DataFrame, param_grid: Optional[Dict] = None
) -> RandomForestClassifier:
    """
    Trains a random forest classifier using the given training data with optimized hyperparameters
    and class weights based on the number of occurrences of each class in y_train.

    :param X_train: A pandas DataFrame containing the feature data for training.
    :type X_train: pd.DataFrame
    :param y_train: A pandas DataFrame containing the target labels for training.
    :type y_train: pd.DataFrame
    :return: A trained random forest classifier.
    :rtype: RandomForestClassifier
    """
    # count the number of occurrences of each class in y_train
    class_counts = np.bincount(y_train)
    # compute the inverse frequency of each class as the class_weight
    class_weight = {
        i: sum(class_counts) / class_counts[i] for i in range(len(class_counts))
    }

    if param_grid is not None:
        if param_grid.get("class_weight"):
            param_grid["class_weight"].append(class_weight)

        # Create a random forest classifier object
        rf = RandomForestClassifier()

        # Create a GridSearchCV object
        grid_search = GridSearchCV(
            estimator=rf, param_grid=param_grid, cv=5, scoring="accuracy"
        )

        # Fit the GridSearchCV object to the training data
        print(
            f"Finding best training parameters with a cross validation k-fold = 5, and scoring = accuracy"
        )
        grid_search.fit(X_train, y_train)
        print(f"Best parameters: {grid_search.best_params_}")
        print(f"Best score: {grid_search.best_score_}")

        # Train a random forest classifier with the best parameters
        print("Training on full dataset with best parameters.")
        rf = RandomForestClassifier(**grid_search.best_params_, random_state=42)
        rf.fit(X_train, y_train)
    else:
        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)

    return rf


def predict(rf: RandomForestClassifier, X: pd.DataFrame) -> np.ndarray:
    """
    Predict the target variable using a trained random forest classifier.

    :param rf: A trained random forest classifier.
    :type rf: RandomForestClassifier
    :param X: The input features used to make the predictions.
    :type X: pd.DataFrame
    :return: The predicted target variable.
    :rtype: np.ndarray
    """
    # make predictions on the inputs
    return rf.predict(X)


def test(rf: RandomForestClassifier, X_test: pd.DataFrame, y_test: pd.DataFrame):
    """Predicts on test data using a random forest classifier and reports on the predictions.

    :param rf: A trained random forest classifier.
    :type rf: RandomForestClassifier
    :param X_test: The test features.
    :type X_test: pd.DataFrame
    :param y_test: The test target variable.
    :type y_test: pd.DataFrame
    """
    # predict on test data
    y_pred = predict(rf, X_test)
    # report on predictions
    return create_reports(y_test, y_pred)


def create_reports(y: pd.DataFrame, y_pred: np.ndarray) -> Tuple[Dict, np.ndarray]:
    """Generate a classification report and confusion matrix for a given set of true and predicted labels.

    :param y: A pandas DataFrame containing the true labels.
    :type y: pd.DataFrame
    :param y_pred: A numpy array containing the predicted labels.
    :type y_pred: np.ndarray
    :return: A dictionary containing the classification report and a numpy array containing the confusion matrix.
    :rtype: Tuple[Dict, np.ndarray]
    """
    # calculate classification report
    report = classification_report(y, y_pred, output_dict=True)
    # replace categories with human-readable labels
    for k in list(report.keys()):
        if k in LABELS:
            report[LABELS[k]] = report.pop(k)
    # calculate a confusion matrix
    cm = confusion_matrix(y, y_pred)
    return report, cm


def create_report_table(report: Dict) -> go.Figure:
    """
    Creates a plotly table from a classification report.

    :param report: A dictionary containing the classification report as produced by sklearn.metrics.classification_report.
    :type report: dict
    :return: A plotly table containing the classification report.
    :rtype: plotly.graph_objs.Figure

    Example usage:
    ```
    from sklearn.metrics import classification_report
    import plotly.graph_objs as go

    report = classification_report(y_true, y_pred, output_dict=True)
    table = create_report_table(report)
    table.show()
    ```
    """
    accuracy = report.pop("accuracy")
    macro_avg = report.pop("macro avg")
    weighted_avg = report.pop("weighted avg")
    columns = ["", "precision (%)", "recall (%)", "f1-score (%)", "support"]
    rows = []
    for k, v in report.items():
        row = [k] + [vv if vv > 1 else round(vv * 100, 2) for vv in v.values()]
        rows.append(row)
    rows.append(
        ["macro avg"] + [v if v > 1 else round(v * 100, 2) for v in macro_avg.values()]
    )
    rows.append(
        ["weighted avg"]
        + [v if v > 1 else round(v * 100, 2) for v in weighted_avg.values()]
    )
    rows.append(["", "", "", "accuracy", f"{round(accuracy * 100, 2)}%"])

    # Define the table
    table = go.Figure(
        data=[
            go.Table(header=dict(values=columns), cells=dict(values=list(zip(*rows))))
        ]
    )
    return table


def create_confusion_matrix(cm: np.ndarray) -> go.Figure:
    """
    Create a Plotly figure of the confusion matrix.

    :param cm: A confusion matrix represented as a NumPy array.
    :type cm: np.ndarray
    :return: A Plotly figure of the confusion matrix.
    :rtype: go.Figure
    """
    # Reverse the order of the y-axis labels and the rows of the confusion matrix
    cm_labels_reversed = CM_LABELS[::-1]
    cm_reversed = cm[::-1]

    # Create the trace for the confusion matrix heatmap
    trace = go.Heatmap(
        z=cm_reversed, x=CM_LABELS, y=cm_labels_reversed, colorscale="Blues"
    )

    # Create the layout
    layout = go.Layout(
        title="Confusion Matrix",
        xaxis=dict(title="Predicted Label"),
        yaxis=dict(title="True Label"),
    )

    # Create the figure
    fig = go.Figure(data=[trace], layout=layout)

    return fig


def select_features(
    rf: RandomForestClassifier, X: pd.DataFrame
) -> List[Tuple[str, float]]:
    """Return a list of tuples with the importance score for each feature, sorted by score (highest first).

    :param rf: A trained RandomForestClassifier model.
    :type rf: RandomForestClassifier
    :param X: The input data.
    :type X: pd.DataFrame
    :return: A list of tuples, where each tuple contains a feature name and its importance score.
    :rtype: List[Tuple[str, float]]
    """
    importances = rf.feature_importances_
    ordered = []
    for feature, importance in zip(X.columns, importances):
        ordered.append((feature, importance))
    ordered.sort(key=lambda x: x[1], reverse=True)
    return ordered


if __name__ == "__main__":
    from pprint import pprint

    csv_fn = "coorteeqsrafva_en.csv"
    # read in csv
    df = pd.read_csv(csv_fn, sep=";")
    df = format_df(df)

    (X_train, y_train), (X_test, y_test) = train_test_split_by_category(df, "diagnosi")

    param_grid = {
        "n_estimators": [50, 100, 200],
        "max_depth": [20, 30, None],
        "min_samples_split": [2, 5],
        "class_weight": ["balanced"],
    }

    rf = train(X_train, y_train)
    report, cm = test(rf, X_test, y_test)

    fig1 = create_report_table(report)
    fig2 = create_confusion_matrix(cm)

    fig1.show()

    fig2.show()
    features = select_features(rf, X_train)
    pprint(features)
