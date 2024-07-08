import logging
import os
import pathlib
import subprocess
import time
import threading

import dash
import dash_bootstrap_components as dbc
import diskcache
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, State
from dash.long_callback import DiskcacheLongCallbackManager

import utils

# Constants
DEFAULT_DATA_FIELDS_FILE = (
    pathlib.Path.home() / "OrangeBox/drivers/mu_interface/mu_interface/Utilities/config/default_data_fields.yaml"
)
CUSTOM_DATA_FIELDS_FILE = (
    pathlib.Path.home() / "OrangeBox/drivers/mu_interface/mu_interface/Utilities/config/custom_data_fields.yaml"
)
WIFI_FILE = pathlib.Path.home() / "OrangeBox/config/orange_box.config"
EXP_NUMBER_FILE = pathlib.Path.home() / "OrangeBox/status/experiment_number.txt"
ACTIVE_DEVICES_PATH = pathlib.Path.home() / "OrangeBox/status/measuring/"
MEASUREMENT_PATH = pathlib.Path.home() / "measurements"
TEMP_ZIP_PATH = pathlib.Path.home() / "merged_measurements"
ZIP_FILE_PATH = pathlib.Path.home() / "data"
GIT_REPOS_PATHS = [
    pathlib.Path.home() / "OrangeBox",
    pathlib.Path.home() / "OrangeBox/drivers/mu_interface",
    pathlib.Path.home() / "OrangeBox/drivers/BLE_Sink",
    pathlib.Path.home() / "OrangeBox/drivers/Zigbee_Sink"
]
FIGURE_SAVE_PATH = pathlib.Path.home() / "OrangeBox/status"
ENERGY_PATH = MEASUREMENT_PATH / "Power"
DEFAULT_PLOT_WINDOW = 2
DEFAULT_PLOT_SAMPLES = 500
CALL_TRACKER = utils.TimestampMonitor(num_intervals=3, interval_len=10)
CALL_TRACKER_LOCK = threading.Lock()

infoPane = dbc.Col(
    [
        dbc.Row(
            [
                dbc.Col(
                    [html.H3("Orange Box Information")],
                ),
                dbc.Col(
                    [
                        dbc.Button(
                            "Refresh",
                            id="refresh-button",
                            color="primary",
                            className="ml-auto",
                            size="md",
                        ),
                    ]
                ),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col([html.Label("IP address:")], width="auto"),
                dbc.Col([html.Label("N/A", id="orange_box-ip")]),
            ],
        ),
        dbc.Row(
            [
                dbc.Col([html.Label("Hostname:")], width="auto"),
                dbc.Col([html.Label("N/A", id="orange_box-hostname")]),
            ],
        ),
        html.Br(),
        dbc.Row(
            [
                dbc.Col([html.Label("Version:  N/A")], id="orange_box-version", width="auto"),
            ],
        ),
    ]
)

settingsPane = dbc.Col(
    [
        dbc.Row(
            [
                dbc.Col(
                    [html.H3("Orange Box Settings")],
                ),
                dbc.Col(
                    [
                        dbc.Button(
                            "Write",
                            id="update-button",
                            color="primary",
                            className="ml-auto",
                            size="md",
                        ),
                    ],
                    width="auto",
                ),
                dbc.Col(
                    [html.Label(id="wifi-success", children="")],
                ),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col([html.Label("WiFi name:")], width=2),
                dbc.Col(
                    [dbc.Input(id="wifi-name", type="text", value="", size="sm")],
                    width=4,
                ),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col([html.Label("WiFi password:")], width=2),
                dbc.Col(
                    [dbc.Input(id="wifi-password", type="text", value="", size="sm")],
                    width=4,
                ),
            ],
            align="center",
        ),
    ]
)

configPane = dbc.Col(
    [
        html.Hr(),
        html.H3("Orange Box Configuration"),
        dbc.Row(
            [
                dbc.Col([html.Label("Change measurement frequency (in ms)")], width="auto"),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Input(
                            type="number",
                            id="orange_box-freq",
                            value=10_000,
                            min=100,
                            max=600_000,
                            step=100,
                            debounce=True,
                            className="mb-3",
                        ),
                    ],
                    width=4,
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col([html.Label("System shutdown/reboot")], width="auto"),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Button(
                            "Shutdown", id="orange_box-shutdown", outline=True, color="danger", className="me-1"
                        ),
                        dbc.Button("Reboot", id="orange_box-reboot", outline=True, color="danger", className="me-1"),
                        dbc.Modal(
                            [
                                dbc.ModalHeader(dbc.ModalTitle("IP address of connected Orange Box")),
                                dbc.ModalBody("ip", id="modal-body"),
                                dbc.ModalFooter(
                                    dbc.Button("Close", id="close", className="ms-auto", n_clicks=0)
                                ),
                            ],
                            id="modal",
                            is_open=False,
                        ),
                    ]
                )
            ]
        ),
        # Modal confirm dialog
        dcc.ConfirmDialog(
            id="confirm_shutdown",
            message="Are you sure you want to shutdown the Orange Box?",
        ),
        dcc.ConfirmDialog(
            id="confirm_reboot",
            message="Are you sure you want to reboot the Orange Box?",
        ),
    ],
    width=4,
)

powerPane = dbc.Col(
    [
        html.Hr(),
        html.H3("Live Orange Box Status"),
        dcc.Graph(
            id="energy_plot",
            config={
                "displaylogo": False,
                "edits": {"legendPosition": True},
                "modeBarButtonsToRemove": ["autoScale2d"],
                "scrollZoom": True,
            },
        ),
        dcc.Graph(
            id="env_plot",
            config={
                "displaylogo": False,
                "edits": {"legendPosition": True},
                "modeBarButtonsToRemove": ["autoScale2d"],
                "scrollZoom": True,
            },
        ),
    ],
    width=8,
)

experimentPane = dbc.Row(
    [
        dbc.Col(
            [html.Label("Experiment number:")],
            width="auto",
        ),
        dbc.Col(
            [
                html.Label(id="experiment-number", children=""),
            ],
            width=1,
        ),
        dbc.Col(
            [
                dbc.Button(
                    "New experiment",
                    id="new-experiment",
                    outline=False,
                    color="primary",
                    className="me-1"),
            ]
        ),
        dbc.Col(
            [
                dbc.Button(
                    "Start experiment",
                    id="start-experiment",
                    outline=True,
                    disabled=True,
                    color="primary",
                    className="me-1",
                ),
            ]
        ),
        dbc.Col(
            [
                dbc.Button(
                    "Stop experiment",
                    id="stop-experiment",
                    outline=False,
                    disabled=False,
                    color="primary",
                    className="me-1",
                ),
            ]
        ),
        dbc.Col(
            [
                dbc.Button(
                    "Configure sensors",
                    id="configure-experiment",
                    outline=False,
                    disabled=False,
                    color="primary",
                    className="me-1",
                ),
            ]
        ),
        dbc.Modal(
            [
                dbc.ModalHeader("Select which values will be measured and stored."),
                dbc.ModalBody(
                    [
                        dbc.Checklist(id="data-fields-checklist", switch=True),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button("Save", id="data-fields-save", color="primary"),
                        dbc.Button("Close", id="data-fields-close", color="secondary"),
                    ]
                ),
            ],
            id="data-fields-modal",
            size="lg",
        ),
    ],
    align="center",
)

liveDataSettingsPane = dbc.Row(
    [
        dbc.Col(
            [html.Label("Select sensor node:")],
            width="auto",
        ),
        dbc.Col(
            [
                dcc.Dropdown(
                    id="sensor-select",
                    options=[],
                    value="",
                )
            ],
            width=2,
        ),
        dbc.Col(
            [html.Label("How many hours to display? (0.1 - 12)")],
            width='auto',
        ),
        dbc.Col(
            [
                dbc.Input(
                    type="number",
                    value=DEFAULT_PLOT_WINDOW,
                    min=0.1,
                    max=12,
                    # step=0.5,
                    id="time-select",
                ),
            ],
            width=1,
        ),
        dbc.Col(
            [
                dbc.Button(
                    "Download data",
                    id="download-btn",
                    outline=False,
                    color="info",
                    ),
                dcc.Download(id="download-data")
            ],
            width={"size": "auto", "offset": 2},
        ),
        # Green label to show that the download is working
        dbc.Col(
            [html.Label(id="download-working", children="Working...", style={"color": "green"}, hidden=True)],
            width="auto",
        )
    ],
    align="center",
)

# Set up the Dash app
cache = diskcache.Cache("./cache")
long_callback_manager = DiskcacheLongCallbackManager(cache)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], long_callback_manager=long_callback_manager)
server = app.server

# Define the layout
app.layout = dbc.Container(
    [
        html.Div(id="dummy-div-default", style={"display": "none"}),
        html.Div(id="dummy-div-plot", style={"display": "none"}),
        html.Div(id="dummy-div-other", style={"display": "none"}),
        # Name
        dbc.Row(
            [
                dbc.Col(
                    [html.H1(f"WatchPlant Dashboard | {utils.get_hostname()}")],
                    width=True,
                ),
                dbc.Col(
                    [
                        dbc.Button("Settings", id="settings-button", color="primary", className="ml-auto", size="lg"),
                    ],
                    width=1,
                    className="ml-auto",
                ),
            ],
            style={"margin-top": "20px"},
        ),
        # Collapsable settings menu
        dbc.Collapse(
            [
                html.Hr(),
                dbc.Row(
                    [
                        infoPane,
                        settingsPane
                    ]
                ),
            ],
            id="settings-collapse",
            is_open=False,
        ),
        # Experiment information
        html.Hr(),
        dbc.Row(
            [dbc.Col([html.H3("Experiment Information")], width=True)],
        ),
        experimentPane,
        # Live plot settings
        html.Hr(),
        dbc.Row(
            [dbc.Col([html.H3("Live data plotting")], width=True)],
        ),
        liveDataSettingsPane,
        # Live plot graph
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(
                            id="mu_plot",
                            config={
                                "displaylogo": False,
                                "edits": {"legendPosition": True},
                                "modeBarButtonsToRemove": ["autoScale2d"],
                                "scrollZoom": True,
                            },
                        )
                    ],
                    width=12,
                )
            ],
            style={"margin-top": "20px"},  # "title": "Measurement Data"},
        ),
        # User controls and energy plot
        dbc.Row(
            [
                configPane,
                powerPane
            ],
            style={"margin-top": "20px"},
        ),
        # Auto refresh
        dcc.Interval(
            id="plot-interval",
            interval=10 * 1000,
            n_intervals=0,
        ),
        dcc.Interval(
            id="connections-interval",
            interval=10 * 1000,
            n_intervals=0,
        ),
        # Storage elements
        dcc.Store(id="data-path-store", data=[]),
        # Notification modal
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Success!")),
                dbc.ModalBody("Action completed successfully!"),
                dbc.ModalFooter(
                    dbc.Button(
                        "OK", id="notify-modal-OK", className="ms-auto", n_clicks=0
                    )
                ),
            ],
            id="notify-modal",
            is_open=False,
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Warning!")),
                dbc.ModalBody("Multiple instances of user interface are open! Please close the other windows or tabs."),
                dbc.ModalFooter(
                    dbc.Button(
                        "OK", id="warn-modal-OK", className="ms-auto", n_clicks=0
                    )
                ),
            ],
            id="warn-modal",
            backdrop="static",
            is_open=False,
        ),
    ],
    fluid=True,
)


# Interactive callbacks
#######################
@app.callback(
    Output("orange_box-ip", "children"),
    Output("orange_box-hostname", "children"),
    Output("wifi-name", "value"),
    Output("wifi-password", "value"),
    Output("orange_box-version", "children"),
    Input("refresh-button", "n_clicks"),
)
def refresh_infoPane(value):
    ip_address = utils.get_ip_address()
    hostname = utils.get_hostname()

    wifi_config = utils.parse_config_file(WIFI_FILE)
    wifi_name = wifi_config.get("SSID", "N/A")
    wifi_password = wifi_config.get("PASS", "N/A")
    
    hashes = utils.get_git_versions(GIT_REPOS_PATHS)
    versions = ["Version:"] + [item for pair in zip([html.Br()]*len(hashes), hashes) for item in pair]

    return ip_address, hostname, wifi_name, wifi_password, versions


@app.callback(
    Output("wifi-success", "children"),
    Output("notify-modal", "is_open", allow_duplicate=True),
    Input("update-button", "n_clicks"),
    State("wifi-name", "value"),
    State("wifi-password", "value"),
    prevent_initial_call='initial_duplicate'
)
def write_settingsPane(n_clicks, wifi_name, wifi_password):
    if n_clicks is None:
        raise dash.exceptions.PreventUpdate

    try:
        utils.write_config_file(WIFI_FILE, wifi_name, wifi_password)
        subprocess.run("rm /home/rock/OrangeBox/status/wifi_connect_success.txt", shell=True)
        subprocess.run("sudo rm /etc/NetworkManager/system-connections/*", shell=True)
        return "success", True
    except Exception as e:
        logging.error(f"Error while writing WiFi settings: {e}")
        return f"Error: {e}", False


@app.callback(
    Output("experiment-number", "children"),
    Output("data-path-store", "data"),
    Input("new-experiment", "n_clicks"),
    Input("orange_box-hostname", "children"),
)
def new_experiment(n_clicks, hostname):
    skip_update = False
    if n_clicks is None:
        skip_update = True

    experiment_number = utils.update_experiment_number(EXP_NUMBER_FILE, skip_update=skip_update)

    return experiment_number, f"{MEASUREMENT_PATH}/{hostname}_{experiment_number}"


@app.callback(
    Output("stop-experiment", "disabled"),
    Output("start-experiment", "disabled"),
    Output("start-experiment", "outline"),
    Output("stop-experiment", "outline"),
    Input("start-experiment", "n_clicks"),
    Input("stop-experiment", "n_clicks"),
    prevent_initial_call=True,
)
def start_stop_experiment(start, stop):
    button_id = ctx.triggered_id if not None else ""

    if button_id == "start-experiment":
        subprocess.run(f"tmuxinator start -p ~/OrangeBox/sensors.yaml {os.getenv('RUN_MODE', '')}", shell=True)
        return False, True, True, False
    elif button_id == "stop-experiment":
        subprocess.run("tmux send-keys -t sensors C-c", shell=True)
        time.sleep(2)
        subprocess.run("tmux kill-session -t sensors", shell=True)
        return True, False, False, True


@app.long_callback(
    Output("download-data", "data"),
    Input("download-btn", "n_clicks"),
    running=[
        (Output("download-btn", "disabled"), True, False),
        (Output("download-working", "hidden"), False, True),
    ],
    prevent_initial_call=True
)
def download_data(n_clicks):
    if n_clicks is None:
        raise dash.exceptions.PreventUpdate

    utils.merge_measurements(MEASUREMENT_PATH, TEMP_ZIP_PATH, ZIP_FILE_PATH)

    return dcc.send_file(f"{ZIP_FILE_PATH}.zip")

@app.callback(
    Output("dummy-div-other", "children", allow_duplicate=True),
    Output("notify-modal", "is_open", allow_duplicate=True),
    Input("orange_box-freq", "value"),
    prevent_initial_call=True,
)
def update_measure_freq(value):
    subprocess.run(f"sed -i 's/MEAS_INT=.*/MEAS_INT={value}/' ~/.bashrc", shell=True)
    return None, True


@app.callback(
    Output("confirm_shutdown", "displayed"),
    Input("orange_box-shutdown", "n_clicks")
)
def shutdown_button(n_clicks):
    if n_clicks is None:
        raise dash.exceptions.PreventUpdate
    return True


@app.callback(
    Output("confirm_reboot", "displayed"),
    Input("orange_box-reboot", "n_clicks")
)
def reboot_button(n_clicks):
    if n_clicks is None:
        raise dash.exceptions.PreventUpdate
    return True


@app.callback(
    Output("time-select", "invalid"),
    Input("time-select", "value"),
)
def validate_time_select(value):
    if value is None:
        return True
    return False


# Modal callbacks
#################
@app.callback(
    Output("orange_box-shutdown", "color"),
    Input("confirm_shutdown", "submit_n_clicks"),
)
def confirm_shutdown(submit_n_clicks):
    if submit_n_clicks:
        subprocess.run("~/OrangeBox/scripts/shutdown.sh", shell=True)
    return "danger"  # if n%2==0 else "danger"


@app.callback(
    Output("orange_box-reboot", "color"),
    Input("confirm_reboot", "submit_n_clicks"),
)
def confirm_reboot(submit_n_clicks):
    if submit_n_clicks:
        subprocess.run("sudo shutdown -r now", shell=True)
    return "danger"  # if n%2==0 else "danger"


@app.callback(
    Output("settings-collapse", "is_open"),
    Output("settings-button", "color"),
    Input("settings-button", "n_clicks"),
    State("settings-collapse", "is_open"),
)
def toggle_collapse(n, is_open):
    if n is None:
        raise dash.exceptions.PreventUpdate

    return not is_open, "primary" if is_open else "secondary"


@app.callback(
    Output("data-fields-checklist", "options"),
    Output("data-fields-checklist", "value"),
    Input("configure-experiment", "n_clicks"),
)
def update_checklist_options(n_clicks):
    config_file = CUSTOM_DATA_FIELDS_FILE if CUSTOM_DATA_FIELDS_FILE.exists() else DEFAULT_DATA_FIELDS_FILE
    config = utils.read_data_fields_from_file(config_file)
    options = [{"label": label, "value": label} for label in config]
    value = [label for label, value in config.items() if value]
    return options, value


@app.callback(
    Output("data-fields-modal", "is_open", allow_duplicate=True),
    Input("configure-experiment", "n_clicks"),
    Input("data-fields-close", "n_clicks"),
    State("data-fields-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_datafields_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


# Callback to save the current configuration to the file
@app.callback(
    Output("data-fields-modal", "is_open", allow_duplicate=True),
    Input("data-fields-save", "n_clicks"),
    State("data-fields-checklist", "value"),
    prevent_initial_call=True,
)
def save_configuration(n_clicks, current_values):
    current_values = set(current_values)
    config_file = CUSTOM_DATA_FIELDS_FILE if CUSTOM_DATA_FIELDS_FILE.exists() else DEFAULT_DATA_FIELDS_FILE
    old_config = utils.read_data_fields_from_file(config_file)
    for key in old_config:
        old_config[key] = key in current_values

    utils.save_date_fields_to_file(old_config, CUSTOM_DATA_FIELDS_FILE)
    return False


@app.callback(
    Output("notify-modal", "is_open", allow_duplicate=True),
    Input("notify-modal-OK", "n_clicks"),
    State("notify-modal", "is_open"),
    prevent_initial_call='initial_duplicate'
)
def toggle_notify_modal(n_clicks, is_open):
    if n_clicks:
        return False
    return is_open


@app.callback(
    Output("warn-modal", "is_open", allow_duplicate=True),
    Input("warn-modal-OK", "n_clicks"),
    State("warn-modal", "is_open"),
    prevent_initial_call='initial_duplicate'
)
def toggle_warn_modal(n_clicks, is_open):
    if n_clicks:
        with CALL_TRACKER_LOCK:
            CALL_TRACKER.reset()
        return False
    return is_open


# Periodic callbacks
####################
@app.callback(
    Output("sensor-select", "options"),
    Input("plot-interval", "n_intervals"),
    Input("data-path-store", "data")
)
def update_storages(n, data_path):
    experiment_path = pathlib.Path(data_path)
    try:
        nodes = [node.name for node_type in experiment_path.iterdir() for node in node_type.iterdir()]
        active_nodes = [node.name.split("_")[0] for node in ACTIVE_DEVICES_PATH.iterdir()]
        filtered_nodes = [node for node in nodes if node in active_nodes]
    except FileNotFoundError:
        return []

    return [{"label": entry, "value": entry} for entry in sorted(filtered_nodes)]


@app.callback(
    Output("warn-modal", "is_open", allow_duplicate=True),
    Input("connections-interval", "n_intervals"),
    State("warn-modal", "is_open"),
    prevent_initial_call=True
)
def update_connections(n, is_open):
    with CALL_TRACKER_LOCK:
        ok, num_calls = CALL_TRACKER.update_and_check()
        if not ok:
            logging.warning("Maybe multiple windows are open")
            return True
    return is_open


def read_dataframe(data_dir, time_window, fmt=None):
    try:
        file_names = os.listdir(data_dir)
        file_names.sort()
        df = pd.read_csv(data_dir / file_names[-1])
        df["datetime"] = pd.to_datetime(df["datetime"], format=fmt)
        if time_window is not None:
            df = df.loc[df["datetime"] > pd.Timestamp.now() - pd.Timedelta(**time_window)]
        return df
    except (FileNotFoundError, IndexError):
        logging.error("File for live plotting not found.")
        return None


@app.callback(
    Output("mu_plot", "figure"),
    Output("energy_plot", "figure"),
    Output("env_plot", "figure"),
    Input("plot-interval", "n_intervals"),
    State("sensor-select", "value"),
    State("time-select", "value"),
    State("data-path-store", "data"),
)
def update_plots(n, sensor_select, time_select, data_path):
    fig_data = dict()
    fig_power = dict()
    fig_env = dict()
    
    if time_select is None:
        raise dash.exceptions.PreventUpdate

    if sensor_select.startswith("CYB"):
        sensor_type = "MU"
        data_fields = [
            "temp_external",
            "light_external",
            "humidity_external",
            "differential_potential_ch1",
            "differential_potential_ch2",
            "RMS_CH1",
            "RMS_CH2",
            "transpiration",
        ]
    elif sensor_select.startswith("PN"):
        sensor_type = "BLE"
        data_fields = "all"
    elif sensor_select.startswith("Z"):
        sensor_type = "Zigbee"
        data_fields = [
            "temp_external",
            "humidity_external",
            "air_pressure",
            "mag_X",
            "mag_Y",
            "mag_Z"
        ]
    else:
        sensor_type = ""
        data_fields = []
     
    # With longer selected time windows, we need to downsample the data to keep the plot responsive.   
    resample = f"{round(time_select * 3600 / DEFAULT_PLOT_SAMPLES)}s"

    # MEASUREMENT DATA PLOT
    if sensor_type:
        data_dir = pathlib.Path(data_path) / sensor_type / sensor_select
        df = read_dataframe(data_dir, {"seconds": int(time_select*3600)}, fmt="%Y-%m-%d %H:%M:%S:%f")
        if df is not None:
            df = df.resample(resample, on="datetime").mean().dropna()
            if data_fields == "all":
                data_fields = df.columns.to_list()
                data_fields.remove("datetime")
                
            fig_data = dict(
                data=[
                    go.Scatter(
                        x=df.index,
                        y=df[field],
                        name=field,
                        mode="lines",
                    ) 
                    for field in data_fields
                ],
                layout=go.Layout(
                    title_text="Measurement Data",
                    xaxis=dict(title="datetime"),
                    yaxis=dict(title="values"),
                    plot_bgcolor="#E5ECF6",
                    # Prevent the plot from changing user interaction settings (zoom, pan, etc.)
                    # Not well documented. Probably any value will work as long as it's constant.
                    uirevision="constant",
                )
            )
            
    # ENERGY DATA PLOT
    df = read_dataframe(ENERGY_PATH, {"seconds": int(time_select*3600)})
    if df is not None:
        df = df.resample(resample, on="datetime").mean().dropna()
        fig_power = dict(
            data=[
                go.Scatter(
                    x=df.index,
                    y=df["bus_voltage_battery"],
                    name="Voltage battery",
                    mode="lines",
                    line_color="red",
                ),
                go.Scatter(
                    x=df.index,
                    y=df["bus_voltage_solar"],
                    name="Voltage solar",
                    mode="lines",
                    line_color="red",
                    line=dict(dash="dash"),
                ),
                go.Scatter(
                    x=df.index,
                    y=df["current_battery"],
                    name="Current battery",
                    mode="lines",
                    line_color="blue",
                    yaxis="y2",
                ),
                go.Scatter(
                    x=df.index,
                    y=df["current_solar"],
                    name="Current solar",
                    mode="lines",
                    line_color="blue",
                    line=dict(dash="dash"),
                    yaxis="y2",
                ),
            ],
            layout=go.Layout(
                title_text="Energy Consumption",
                xaxis=dict(title="datetime"),
                yaxis=dict(
                    title="voltage [V]",
                    color="red",
                ),
                yaxis2=dict(
                    title="current [mA]",
                    color="blue",
                    overlaying="y",
                    side="right",
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                plot_bgcolor="#E5ECF6",
                uirevision="constant",
            )
        )
        
    # TEMP & HUMIDITY PLOT
    if df is not None and "temperature" in df.columns and "humidity" in df.columns:
        fig_env = dict(
            data=[
                go.Scatter(
                    x=df.index,
                    y=df["temperature"],
                    name="temperature",
                    mode="lines",
                    line_color="red",
                ),
                go.Scatter(
                    x=df.index,
                    y=df["humidity"],
                    name="humidity",
                    mode="lines",
                    line_color="blue",
                    yaxis="y2",
                ),
            ],
            layout=go.Layout(
                title_text="Temp. & Humidity inside the box",
                xaxis=dict(title="datetime"),
                yaxis=dict(
                    title="temperature [°C]",
                    color="red",
                ),
                yaxis2=dict(
                    title="humidity [%]",
                    color="blue",
                    overlaying="y",
                    side="right",
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                plot_bgcolor="#E5ECF6",
                uirevision="constant",
            )
        )
        
    # Return the updated figures
    return fig_data, fig_power, fig_env


# Run the app
if __name__ == "__main__":
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    utils.setup_logger('user_app', level=logging.INFO)
    
    app.run_server(host="0.0.0.0", debug=True)
    # app.run_server(host='0.0.0.0', port=8050)
