import plotly.graph_objects as go


def is_stressed(data0, data1, sample, stress):
    if sample == "ros" and stress == "water":
        return None, None

    if sample == "aba":
        data_delta = abs(data1 - data0)
        if stress == "water":
            return data_delta < 2.65, data_delta
        else:  # stress == "ozone"
            return data_delta < 0.66, data_delta
    else:  # sample == "ros"
        concentration = (data1 + 0.0084) / 0.0156
        return concentration > 19.8, concentration


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


def analyze(timestamps, data, sample, stress):
    sample = sample.lower()
    stress = stress.lower()
    timestamps = timestamps.to_series()

    smoothing_alpha = 0.2
    experiment_duration = 200 if sample == "aba" else 60  # seconds
    traces = []
    shapes = []
    annotations = []

    # Smooth the data using a low-pass first-order filter.
    smoothed = lp_filter(data, smoothing_alpha)
    # traces.append(go.Scatter(x=timestamps, y=smoothed, mode="lines", name="Smooth"))

    # Compute the derivative of the smoothed data.
    derivative = smoothed.diff().fillna(0)
    # traces.append(go.Scatter(x=timestamps, y=derivative, mode="lines", name="Derivative"))

    # print(timestamps)
    # print(data)

    # Find the index of the sudden drop in the derivative.
    if sample == "aba":
        trigger_index = find_negative_drop(derivative)
    else:
        trigger_index = 0

    if trigger_index is not None:
        trigger_time = timestamps[trigger_index]
        trigger_value = data[trigger_index]
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

            dec_point_min = trigger_value if sample == "aba" else min(data)
            dec_point_max = future_value
            annotation_val = trigger_value - future_value if sample == "aba" else future_value

            # Add decision point annotation
            traces.append(
                go.Scatter(
                    x=[future_time, future_time],
                    y=[dec_point_min, dec_point_max],
                    mode='lines+markers',
                    line=dict(color='red'),
                    marker=dict(line_color='red', size=15, symbol='line-ew', line_width=2),
                    name='Height Difference'
                )
            )

            # print(trigger_index, trigger_time, trigger_value, target_time, future_index, future_time, future_value)

            annotations.append(
                dict(
                    x=future_time,
                    y=(dec_point_min + dec_point_max) / 2,
                    text=f'Value: {annotation_val:.2f}',
                    showarrow=False,
                    font=dict(size=12, color='black'),
                    bgcolor='white'
                )
            )

            # Add status rectangle
            stressed, value = is_stressed(trigger_value, future_value, sample, stress)
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
