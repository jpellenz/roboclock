import sys
import subprocess
import threading
import socket
import logging
from time import sleep
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd

# Set up logging to suppress Flask startup messages
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

# Flask app setup
host_name = "0.0.0.0"  # Bind to all IP addresses
port = 5001
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Activate CORS for all routes

# Global variables for countdown and phase management
countdown_time = pd.Timestamp.now() + pd.Timedelta(minutes=5)
current_phase = "---"
next_phase = "---"
server_ip = "---"
df_sorted = None

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/get_countdown', methods=['GET'])
def get_countdown():
    current_time = pd.Timestamp.now()
    if (df_sorted is None) or (df_sorted.empty):
        print("df_sorted is empty")
        mission_time_remaining = 0
        next_team_time = None
    else:
        mission_time_remaining = seconds_to_next_prepare_for_mission(current_time, df_sorted)
        next_team_time = next_prepare_for_mission_time(current_time, df_sorted)
    time_remaining = countdown_time - current_time
    if time_remaining.total_seconds() < 0:
        time_remaining = pd.Timedelta(seconds=0)

    # Compute phase boxes for the current group
    past_time_row = find_past_time_row(df_sorted, current_time)
    phase_boxes = find_phase_boxes(df_sorted, past_time_row)

    return jsonify({
        'server_hour': current_time.hour,
        'server_minute': current_time.minute,
        'server_second': current_time.second,
        'countdown_seconds': int(time_remaining.total_seconds()),
        'current_phase': current_phase,
        'next_phase': next_phase,
        'remaining_mission_time_seconds': mission_time_remaining,
        'server_ip': server_ip,
        'next_team_time': next_team_time.strftime("%H:%M") if next_team_time else "--:--",
        'phase_boxes': phase_boxes
    })


@app.route('/get_data', methods=['GET'])
def get_data():
    global df_sorted
    if df_sorted is None or df_sorted.empty:
        return jsonify([])  # Return an empty list if df_sorted is not initialized
    current_time = pd.Timestamp.now()
    data = df_sorted.to_dict(orient='records')
    past_time_row = find_past_time_row(df_sorted, current_datetime_pd)
    # Mark the current row
    for row in data:
        row['current'] = row['datetime'] == past_time_row['datetime']

    return jsonify(data)


@app.route('/get_current_audio', methods=['GET'])
def get_current_audio():
    """
    Return the current audio file that should be played based on the current phase.
    """
    global current_phase, df_sorted
    current_time = pd.Timestamp.now()
    
    if df_sorted is None or df_sorted.empty:
        return jsonify({
            'audio_file': None,
            'phase': current_phase
        })
    
    past_time_row = find_past_time_row(df_sorted, current_time)
    
    if past_time_row is None:
        return jsonify({
            'audio_file': None,
            'phase': current_phase
        })
    
    audio_file = past_time_row['filename'] if 'filename' in past_time_row and past_time_row['filename'] else None
    
    return jsonify({
        'audio_file': audio_file,
        'phase': current_phase
    })


@app.route('/sounds/<path:filename>')
def serve_sounds(filename):
    """
    Serve audio files from the sounds directory.
    """
    return send_from_directory('sounds', filename)


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


def get_local_ip():
    """
    Determine the local IP address by connecting to an external server.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
    except Exception:
        local_ip = '127.0.0.1'
    return local_ip

def next_prepare_for_mission_time(now, df_sorted):
    prepare_for_mission_row = find_prepare_for_mission_row(df_sorted, now)
    if prepare_for_mission_row is not None and not prepare_for_mission_row.empty:
        prepare_for_mission_time = prepare_for_mission_row['datetime']
    else:
        prepare_for_mission_time = None
    return prepare_for_mission_time


def seconds_to_next_prepare_for_mission(now, df_sorted):
    """
    Calculate the seconds until the next "Prepare for mission" phase.
    """
    t = next_prepare_for_mission_time(now, df_sorted)
    if t is not None:
        s = (t - now).total_seconds()
    else:
        s = 0
    return int(s)


def combine_date_time(row, base_date):
    return row['date'] + pd.Timedelta(hours=row['hour'], minutes=row['minute'], seconds=row['second'])

def generate_times(start_hour, start_minute, cycle_min, repetitions, base_date):
    """
    Generate a list of timestamps based on start hour, start minute, cycle in minutes, and repetitions.
    """
    times = []
    start_time = base_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    for i in range(repetitions):
        times.append(start_time + pd.Timedelta(minutes=cycle_min * i))
    return times

def read_csv_to_df(filename, current_datetime_pd):
    """
    Read a CSV file into a DataFrame, expand rows into specified times, and sort by time.
    """
    df = pd.read_csv(filename, delimiter=';')
    expanded_rows = []

    for _, row in df.iterrows():
        times = generate_times(row['start_hour'], row['start_minute'], row['cycle_min'], row['repetitions'], current_datetime_pd)
        for slot_index, time in enumerate(times):
            new_row = row.copy()
            new_row['date'] = current_datetime_pd.normalize()
            new_row['hour'] = time.hour
            new_row['minute'] = time.minute
            new_row['second'] = time.second
            new_row['datetime'] = time
            new_row['slot_index'] = slot_index
            expanded_rows.append(new_row)
            new_row_tomorrow = new_row.copy()
            new_row_tomorrow['date'] = current_datetime_pd.normalize() + pd.Timedelta(days=1)
            expanded_rows.append(new_row_tomorrow)

    expanded_df = pd.DataFrame(expanded_rows)
    expanded_df['start_hour'] = expanded_df['start_hour'].astype(int)
    expanded_df['start_minute'] = expanded_df['start_minute'].astype(int)
    expanded_df['cycle_min'] = expanded_df['cycle_min'].astype(int)
    expanded_df['repetitions'] = expanded_df['repetitions'].astype(int)

    # Apply the function to create a new datetime column
    expanded_df['datetime'] = expanded_df.apply(combine_date_time, base_date=current_datetime_pd, axis=1)
    return expanded_df.sort_values(by='datetime').reset_index(drop=True)

def find_phase_boxes(df_sorted, current_row):
    """
    Find all phases in the same group and slot as the current row.
    Returns a list of dicts with phase name and whether it's active.
    """
    if current_row is None:
        return []
    group = current_row.get('group', '')
    if not group or (isinstance(group, float) and pd.isna(group)):
        # No group — return single box for current phase
        return [{'phase': current_row['phase'], 'active': True}]
    slot_index = current_row.get('slot_index', None)
    current_date = current_row.get('date', None)
    # Find all rows in the same group + slot_index + date
    mask = (df_sorted['group'] == group) & (df_sorted['slot_index'] == slot_index) & (df_sorted['date'] == current_date)
    group_rows = df_sorted[mask].sort_values(by='datetime')
    boxes = []
    for _, row in group_rows.iterrows():
        duration = row.get('duration_min', '')
        if isinstance(duration, float) and pd.isna(duration):
            duration = ''
        else:
            duration = int(duration) if duration != '' else ''
        boxes.append({
            'phase': row['phase'],
            'active': row['datetime'] == current_row['datetime'],
            'duration_min': duration
        })
    return boxes


def find_future_time_row(df_sorted, current_datetime_pd, offset):
    """
    Find the row in the DataFrame that is closest to the current time in the future.
    """
    future_times = df_sorted[df_sorted['datetime'] >= current_datetime_pd]
    return future_times.iloc[offset] if not future_times.empty else None
    if not future_times.empty:
        closest_future_time_row = future_times.iloc[offset]
    else:
        closest_future_time_row = None
    return closest_future_time_row

# function to find the next row in df_sorted that starts a new group cycle in the future
def find_prepare_for_mission_row(df_sorted, current_datetime_pd):
    """
    Find the next row that starts a new group cycle (different slot_index from current).
    Falls back to the first future row with a non-empty group.
    """
    past_time_row = find_past_time_row(df_sorted, current_datetime_pd)
    if past_time_row is not None:
        current_group = past_time_row.get('group', '')
        current_slot = past_time_row.get('slot_index', None)
        if current_group and not (isinstance(current_group, float) and pd.isna(current_group)):
            # Find next row in same group but different (next) slot
            future_times = df_sorted[
                (df_sorted['group'] == current_group) &
                (df_sorted['slot_index'] == current_slot + 1) &
                (df_sorted['datetime'] >= current_datetime_pd)
            ]
            if not future_times.empty:
                return future_times.iloc[0]
    # Fallback: find next future row that has a group
    future_with_group = df_sorted[
        (df_sorted['datetime'] >= current_datetime_pd) &
        (df_sorted['group'].notna()) &
        (df_sorted['group'] != '')
    ]
    if not future_with_group.empty:
        return future_with_group.iloc[0]
    return None

def find_past_time_row(df_sorted, current_datetime_pd):
    """
    Find the row in the DataFrame that is closest to the current time in the past.
    """
    past_times = df_sorted[df_sorted['datetime'] < current_datetime_pd]
    return past_times.iloc[-1] if not past_times.empty else None
    if not past_times.empty:
        closest_past_time_row = past_times.iloc[-1]
    else:
        closest_past_time_row = None
    return closest_past_time_row

def play(audio_file_path):
    """
    Play an audio file using mplayer.
    """
    print(f"Playing {audio_file_path}")
    subprocess.call(["mplayer", audio_file_path])

def set_alarm(seconds, sound_filename, c_phase, next_time, n_phase):
    """
    Set an alarm by sleeping for a specified number of seconds and updating the phase.
    Sound playback has been moved to the client side.
    """
    global current_phase, next_phase, countdown_time
    try:
        if seconds > 1:
            print(f"Sleeping for {seconds} seconds.")
            sleep(seconds - 1)
        elif seconds > 0:
            sleep(seconds)
        print("Wake up")
        countdown_time = next_time
        current_phase = c_phase
        next_phase = n_phase
        # Die lokale Audiowiedergabe wurde entfernt und wird nun vom Client ausgeführt
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    server_ip = get_local_ip()
    print("Server IP: ", server_ip)

    threading.Thread(target=lambda: app.run(host=host_name, port=port, debug=True, use_reloader=False)).start()

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)

    current_datetime_pd = pd.Timestamp.now()
    df_sorted = read_csv_to_df(sys.argv[1], current_datetime_pd)

    if len(sys.argv) < 2:
        print("Usage: [ python3 ] roboclock.py timefile.csv")
        sys.exit(1)
    # Die lokale Audiowiedergabe beim Start wurde entfernt
    # play("sounds/%s" % ("gong.mp3",))

    while True:
        current_datetime_pd = pd.Timestamp.now()
        df_sorted = read_csv_to_df(sys.argv[1], current_datetime_pd)

        past_time_row = find_past_time_row(df_sorted, current_datetime_pd)
        next_time_row = find_future_time_row(df_sorted, current_datetime_pd, 0)
        future_time_row = find_future_time_row(df_sorted, current_datetime_pd, 1)

        if next_time_row is None:
            # No more future events — wait and retry
            current_phase = past_time_row['phase'] if past_time_row is not None else "[break]"
            next_phase = "---"
            sleep(10)
            continue

        closest_future_time = next_time_row['datetime']
        time_difference_seconds = (closest_future_time - current_datetime_pd).total_seconds()

        countdown_time = closest_future_time
        current_phase = past_time_row['phase'] if past_time_row is not None else "[break]"
        next_phase = next_time_row['phase']

        if time_difference_seconds > 12:
            sleep(10)
        elif future_time_row is not None:
            set_alarm(time_difference_seconds, next_time_row['filename'], next_time_row['phase'], future_time_row['datetime'], future_time_row['phase'])
        else:
            # Last event — just sleep through it
            set_alarm(time_difference_seconds, next_time_row['filename'], next_time_row['phase'], closest_future_time + pd.Timedelta(seconds=1), "---")
