import os
import subprocess
from pathlib import Path

from telegram_bot.telegram_bot import broadcast_message


MEASUREMENTS_PATH = Path.home() / "measurements"
NUM_FILES_TO_KEEP = 2
NUM_FILES_TO_DELETE = 4
DISK_WARNING = 70
DISK_CRITICAL = 80


def cleanup_files(measurements_path):
    def _cleanup_files(measurements_path):
        cleaned_dirs = []
        for path in measurements_path.iterdir():
            if path.suffix == '.csv':
                csv_files = sorted(measurements_path.glob('*.csv'))
                # print('\n\t'.join(['Available files:'] + [str(f) for f in csv_files]))
                if len(csv_files) >= NUM_FILES_TO_KEEP + NUM_FILES_TO_DELETE:
                    files_to_delete = csv_files[:NUM_FILES_TO_DELETE]
                    # print('\n\t'.join(['Deleting files:'] + [str(f) for f in files_to_delete]))
                    for f in files_to_delete:
                        os.remove(f)
                    return [measurements_path.stem]
            else:
                # print(f'Processing {path.resolve()}')
                cleaned_dirs.extend(_cleanup_files(path))
        
        return cleaned_dirs

    measurements_path = Path(measurements_path)
    return _cleanup_files(measurements_path)


if __name__=='__main__':
    command = "df -h / | awk '{print $5}' | grep -oP '\\d+%'"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    percentage_info = result.stdout.strip()
    disk_usage = int(percentage_info.strip("%"))
    
    print(f"Disk usage: {disk_usage}%")
    
    if DISK_WARNING <= disk_usage < DISK_CRITICAL:
        broadcast_message(f"Disk usage is above {DISK_WARNING} %. Old files will soon be deleted.")
    elif disk_usage >= 70:
        cleaned_dirs = cleanup_files(MEASUREMENTS_PATH)
        message = (
            f"Disk usage is above {DISK_CRITICAL} %.\n"
            f"Deleted {NUM_FILES_TO_DELETE * len(cleaned_dirs)} files from {len(cleaned_dirs)} directories:\n"
            f"{cleaned_dirs}"
        )
        broadcast_message(message)
        print(message)
                    