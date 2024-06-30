import collections
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    import ruamel.yaml
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.top_level_colon_align = 19
except ImportError:
    import yaml

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    
def get_hostname():
    return socket.gethostname()

def parse_config_file(file_path):
    # Example config file
    # export SSID="WatchPlant"
    # export PASS="zamioculcas"
    # export SINK="127.0.0.1"

    config = {}
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export"):
                line = line.replace("export ", "")
                key, value = line.split("=")
                config[key] = value.replace("\"", "")
    
    return config

def write_config_file(file_path, wifi_ssid, wifi_pass, sink_ip="127.0.0.1"):
    with open(file_path, "w") as f:
        f.write(f"export SSID=\"{wifi_ssid}\"\n")
        f.write(f"export PASS=\"{wifi_pass}\"\n")
        f.write(f"export SINK=\"{sink_ip}\"\n")

def update_experiment_number(file_path, skip_update=False):
    with open(file_path, "r") as f:
        experiment_number = int(f.read().strip())
        
    if not skip_update:
        experiment_number += 1
        with open(file_path, "w") as f:
            f.write(str(experiment_number))

    return experiment_number

def read_data_fields_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            config = yaml.load(file)
        return config if config else {}
    except FileNotFoundError:
        raise FileNotFoundError("File not found", file_path)

def save_date_fields_to_file(config, file_path):
    with open(file_path, 'w') as file:
        yaml.dump(config, file)
        
def read_extra_config(file_path):
    try:
        with open(file_path, 'r') as file:
            config = file.read().strip().split("=")[1].strip('"')
    except FileNotFoundError:
        config = "MU"
        
    if config == "":
        config = "MU"
    
    if config == "all":
        return ["MU", "BLE", "ZB"]
    return config.split("+")

def write_extra_config(values, file_path):
    with open(file_path, 'w') as file:
        config = "+".join(values)
        file.write(f'export RUN_MODE="{config}"')
        
def get_git_versions(paths):
    out = []
    for path in reversed(paths):
        os.chdir(path)
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], stdout=subprocess.PIPE)
        commit_hash = result.stdout.decode('utf-8').strip()
        out.append(f"-- {path.stem}: {commit_hash[:7]}")

    return list(reversed(out))


def merge_measurements(measurements_path, output_path, zip_file_path):
    def load_and_validate_csv(file_path):
        try:
            df = pd.read_csv(file_path)
        except pd.errors.EmptyDataError:
            return None
        if df.empty:
            return None
        return df

    def _merge_measurements(measurements_path, output_path):
        for path in measurements_path.iterdir():
            if path.is_dir() and path.name == 'Power':
                df_dict = {}
                filename_dict = {}
                for csv_file in sorted(path.glob('*.csv')):
                    prefix = csv_file.stem.split('_')[0]
                    df = load_and_validate_csv(csv_file)

                    if df is not None:
                        if prefix in df_dict:
                            df_dict[prefix] = pd.concat([df_dict[prefix], df], ignore_index=True)
                            filename_dict[prefix].append(csv_file)
                        else:
                            df_dict[prefix] = df
                            filename_dict[prefix] = [csv_file]

                for key in df_dict:
                    # print('\n\t'.join(['Merging files:'] + [str(f) for f in merged_df]))
                    sorted_files = sorted(filename_dict[key], key=lambda x: x.stem)
                    base_file_name = sorted_files[0].stem
                    out_dir_structure = 'Power'
                    merged_file_path = output_path / out_dir_structure / f"{base_file_name}_merged_{len(sorted_files)}.csv"
                    merged_file_path.parent.mkdir(parents=True, exist_ok=True)
                    df_dict[key].to_csv(merged_file_path, index=False)
                    # print(f"Merging to {merged_file_path}")

            elif path.suffix == '.csv':
                csv_files = sorted(measurements_path.glob('*.csv'))
                # print('\n\t'.join(['Merging files:'] + [str(f) for f in csv_files]))
                if csv_files:
                    base_file_name = csv_files[0].stem
                    out_dir_structure = path.relative_to(path.parents[3]).parents[2]
                    merged_file_path = output_path / out_dir_structure / f'{base_file_name}_merged_{len(csv_files)}.csv'
                    merged_file_path.parent.mkdir(parents=True, exist_ok=True)

                    df_list = []
                    for f in csv_files:
                        df = load_and_validate_csv(f)
                        if df is not None:
                            df_list.append(df)
                    if df_list:
                        merged_df = pd.concat(df_list, ignore_index=True)
                        merged_df.to_csv(merged_file_path, index=False)
                    # print(f'Merged CSV files in {measurements_path} and saved as {merged_file_path}')
                    return
            else:
                # print(f'Processing {path.resolve()}')
                _merge_measurements(path, output_path)

    measurements_path = Path(measurements_path)
    output_path = Path(output_path)
    _merge_measurements(measurements_path, output_path)

    # Zip output directory and then delete it.
    shutil.make_archive(str(zip_file_path.resolve()), 'zip', output_path.resolve())
    shutil.rmtree(output_path.resolve())


class TimestampMonitor():
    def __init__(self, interval_len, num_intervals):
        self.interval_len = interval_len
        self.num_intervals = num_intervals
        self.timestamps = collections.deque(maxlen=(num_intervals + 1) * 5)
        
    def update_and_check(self):
        now = time.time()
        num_calls = 0
        for entry in self.timestamps:
            if now - entry < self.num_intervals * self.interval_len:
                num_calls += 1
        
        self.timestamps.append(now)
        
        if num_calls / self.num_intervals > 1.5:
            return False, num_calls
        
        return True, num_calls
    
    def reset(self):
        self.timestamps.clear()


class ColoredFormatter(logging.Formatter):
    #These are the sequences need to get colored ouput
    RESET_SEQ = "\033[0m"
    BOLD_SEQ = "\033[1m"

    COLORS = {
        'WARNING': "\033[38;5;130m",
        'INFO': "",
        'DEBUG': "\033[38;5;2m",
        'CRITICAL': "\033[31m",
        'ERROR': "\033[31m",
    }
    
    def __init__(self, fmt=None, datefmt=None):
        logging.Formatter.__init__(self, fmt, datefmt)

    def format(self, record):
        skip_line = False
        if record.msg and record.msg[0] == '\n':
            skip_line = True
            record.msg = record.msg[1:]
        result = logging.Formatter.format(self, record)
        result = ColoredFormatter.COLORS[record.levelname] + result + ColoredFormatter.RESET_SEQ
        if skip_line:
            result = '\n' + result
        return result

def setup_logger(name, level=logging.INFO):
    Path('logs').mkdir(exist_ok=True)
    
    logFormatter = logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s", '%d.%m.%Y. %H:%M:%S')
    colorFormatter = ColoredFormatter("[%(asctime)s] [%(levelname)s]: %(message)s", '%d.%m.%Y. %H:%M:%S')
    rootLogger = logging.getLogger()

    fileHandler = logging.FileHandler(f"logs/{name}-{datetime.now().strftime('%d_%m_%Y-%H_%M_%S')}.log")
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setFormatter(colorFormatter)
    rootLogger.addHandler(consoleHandler)

    rootLogger.setLevel(level)
