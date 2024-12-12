import plotly.graph_objects as go
import pandas as pd


def is_stressed(data, sensor):
    if sensor == "aba-water":
        return data < -2.65
    elif sensor == "aba-ozone":
        return data < -0.66
    elif sensor == "ros-ozone":
        return data > 19.8
    else:
        return None


def find_negative_drop(derivatives):
    long_window = 10
    short_window = 3
    # Find index for which derivatives in next long_window steps are all negative or very negative in short_window.
    for i in range(1, len(derivatives) - long_window):
        if all(derivatives.iloc[i : i + long_window] < -0.01) or all(derivatives.iloc[i : i + short_window] < -0.1):
            return i - 1


def lp_filter(data, alpha):
    smoothed = data.copy()
    for i in range(1, len(data)):
        smoothed.iloc[i] = alpha * data.iloc[i] + (1 - alpha) * smoothed.iloc[i - 1]
    return smoothed


def analyze(timestamps, data, electrode, stress):
    smoothing_alpha = 0.2
    experiment_duration = 200  # seconds
    traces = []
    shapes = []
    annotations = []

    # Smooth the data using a low-pass first-order filter.
    smoothed = lp_filter(data, smoothing_alpha)
    # traces.append(go.Scatter(x=timestamps, y=smoothed, mode="lines", name="Smooth"))

    # Compute the derivative of the smoothed data.
    derivative = smoothed.diff().fillna(0)
    # traces.append(go.Scatter(x=timestamps, y=derivative, mode="lines", name="Derivative"))

    # Find the index of the sudden drop in the derivative.
    trigger_index = find_negative_drop(derivative)

    if trigger_index:
        trigger_time = timestamps[trigger_index]
        shapes.append(
            dict(
                type="line",
                x0=trigger_time,
                x1=trigger_time,
                yref="paper",
                y0=0,
                y1=1,  # yref="paper" makes it span the full plot height
                line=dict(color="red", width=2, dash="dash"),
            )
        )

        target_time = trigger_time + experiment_duration

        # Find the value corresponding to the target_time
        future_index = timestamps.searchsorted(target_time)

        if future_index < len(timestamps):
            future_time = timestamps[future_index]
            future_value = data[future_index]
            traces.append(
                go.Scatter(
                    x=[future_time],
                    y=[future_value],
                    mode="markers+text",
                    marker=dict(color="red", size=10),
                    text=[f"{future_value}"],
                    textposition="top center",
                    textfont=dict(size=16),
                    name="Decision Point",
                )
            )

            # Add status rectangle
            test = f"{electrode.lower()}-{stress.lower()}"
            stressed = is_stressed(future_value, test)
            if stressed is None:
                status = "INVALID CONFIG"
                color = "gray"
            elif stressed:
                status = "STRESSED"
                color = "red"
            else:
                status = "GOOD"
                color = "green"
            annotations.append(
                dict(
                    x=1,
                    y=1,
                    xref="paper",
                    yref="paper",
                    text=status,
                    showarrow=False,
                    font=dict(size=32, color="white"),
                    align="center",
                    bgcolor=color,
                    borderpad=10,
                    opacity=0.5,
                )
            )

    return traces, shapes, annotations
