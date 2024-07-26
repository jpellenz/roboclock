import sys
from time import sleep
import subprocess
from flask import Flask, jsonify
from flask_cors import CORS
import threading
import pandas as pd
import socket
import logging

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
next_half_hour = "00:00"


@app.route('/get_countdown', methods=['GET'])
def get_countdown():
    """
    Flask route to return the current countdown and server status.
    """
    current_time = pd.Timestamp.now()
    mission_time_remaining = seconds_to_next_hour_or_half_hour(current_time)
    time_remaining = countdown_time - current_time
    if time_remaining.total_seconds() < 0:
        time_remaining = pd.Timedelta(seconds=0)

    return jsonify({
        'server_hour': current_time.hour,
        'server_minute': current_time.minute,
        'server_second': current_time.second,
        'minutes': time_remaining.seconds // 60,
        'seconds': time_remaining.seconds % 60,
        'current_phase': current_phase,
        'next_phase': next_phase,
        'remaining_mission_time_minutes': mission_time_remaining // 60,
        'remaining_mission_time_seconds': mission_time_remaining % 60,
        'server_ip': server_ip,
        'next_half_hour': next_half_hour.strftime("%H:%M")
    })


def get_local_ip():
    """
    Determine the local IP address by connecting to an external server.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception as e:
        local_ip = '127.0.0.1'  # Fall back to loopback address if an error occurs
    return local_ip


def seconds_to_next_hour_or_half_hour(now):
    """
    Calculate the seconds until the next hour or half-hour.
    """
    global next_half_hour
    if now.minute < 30:
        next_half_hour = now.replace(minute=30, second=0, microsecond=0)
    else:
        next_half_hour = (now + pd.Timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    seconds_to_half_hour = (next_half_hour - now).seconds
    return int(seconds_to_half_hour)


def combine_date_time(row, base_date):
    return row['date'] + pd.Timedelta(hours=row['hour'], minutes=row['minute'], seconds=row['second'])

def expand_hour_ranges(hour_ranges):
    """Expand hour ranges into a list of individual hours, including handling '*'."""
    hours = set()

    if hour_ranges == '*':
        # Include all hours from 0 to 23
        hours.update(range(24))
    else:
        for part in hour_ranges.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                hours.update(range(start, end + 1))
            else:
                hours.add(int(part))

    return sorted(hours)

def read_csv_to_df(filename, current_datetime_pd):
    """
    Read a CSV file into a DataFrame, expand rows with regex patterns into specified hours, and sort by time.
    """
    df = pd.read_csv(filename, delimiter=';')
    expanded_rows = []

    for _, row in df.iterrows():
        hours_range = expand_hour_ranges(row['hour'])
        for hour in hours_range:
            new_row = row.copy()
            new_row['date'] = current_datetime_pd.normalize()
            new_row['hour'] = time.hour
            new_row['minute'] = time.minute
            new_row['second'] = time.second
            new_row['datetime'] = time
            expanded_rows.append(new_row)

    expanded_df = pd.DataFrame(expanded_rows)
    expanded_df['hour'] = expanded_df['hour'].astype(int)
    expanded_df['minute'] = expanded_df['minute'].astype(int)
    expanded_df['second'] = expanded_df['second'].astype(int)

    # Apply the function to create a new datetime column
    expanded_df['datetime'] = expanded_df.apply(combine_date_time, base_date=current_datetime_pd, axis=1)
    df_sorted = expanded_df.sort_values(by='datetime')
    df_sorted.index = range(1, len(expanded_df) + 1)

    return df_sorted


def find_future_time_row(df_sorted, current_datetime_pd, offset):
    """
    Find the row in the DataFrame that is closest to the current time in the future.
    """
    future_times = df_sorted[df_sorted['datetime'] >= current_datetime_pd]
    if not future_times.empty:
        closest_future_time_row = future_times.iloc[offset]
    else:
        closest_future_time_row = None
    return closest_future_time_row


def find_past_time_row(df_sorted, current_datetime_pd):
    """
    Find the row in the DataFrame that is closest to the current time in the past.
    """
    past_times = df_sorted[df_sorted['datetime'] < current_datetime_pd]
    if not past_times.empty:
        closest_past_time_row = past_times.iloc[-1]
    else:
        closest_past_time_row = None
    return closest_past_time_row


def play(audio_file_path):
    """
    Play an audio file using mplayer.
    """
    print("playing %s" % audio_file_path)
    subprocess.call(["mplayer", audio_file_path])


def set_alarm(seconds, sound_filename, c_phase, next_time, n_phase):
    """
    Set an alarm by sleeping for a specified number of seconds and playing a series of sounds.
    """
    global current_phase, next_phase, countdown_time
    try:
        if seconds > 0:
            print("Sleeping light for %s secs." % (str(seconds),))
            sleep(seconds - 1)
        print("Wake up")
        countdown_time = next_time
        current_phase = c_phase
        next_phase = n_phase
        play("sounds/%s" % ("gong.mp3",))
        sleep(1)
        play("sounds/%s" % (sound_filename,))
        sleep(1)
        play("sounds/%s" % (sound_filename,))
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    # Get local IP address
    server_ip = get_local_ip()
    print("Server IP: ", server_ip)

    # Start Flask server in a separate thread
    threading.Thread(target=lambda: app.run(host=host_name, port=port, debug=True, use_reloader=False)).start()

    # Initial sound to indicate the server is running
    # play("sounds/gong.mp3")

    sa = sys.argv
    lsa = len(sys.argv)
    if lsa < 2:
        print("Usage: [ python3 ] roboclock.py timefile.csv")
        sys.exit(1)

    while True:
        current_datetime = pd.Timestamp.now()
        current_datetime_pd = pd.to_datetime(current_datetime)
        print(current_datetime_pd)

        # Read and process CSV file
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        df_sorted = read_csv_to_df(sa[1], current_datetime_pd)
        print (df_sorted)

        past_time_row = find_past_time_row(df_sorted, current_datetime_pd)
        next_time_row = find_future_time_row(df_sorted, current_datetime_pd, 0)
        future_time_row = find_future_time_row(df_sorted, current_datetime_pd, 1)

        closest_future_time = next_time_row['datetime']
        time_difference = closest_future_time - current_datetime_pd
        time_difference_seconds = time_difference.total_seconds()
        next_time = next_time_row['datetime']

        countdown_time = next_time
        if past_time_row is None:
            current_phase = "[break]"
        else:
            current_phase = past_time_row['phase']
        next_phase = next_time_row['phase']

        if time_difference_seconds > 12:
            sleep(10)
        else:
            set_alarm(time_difference_seconds, next_time_row['filename'], next_time_row['phase'],
                      future_time_row['datetime'], future_time_row['phase'])
