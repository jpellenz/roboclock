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


def add_date_today_or_tomorrow(row, currentdate_time):
    """
    Adjust the time in a DataFrame row to today or tomorrow based on the current date and time.
    """
    adjusted_datetime = pd.Timestamp.now()
    adjusted_datetime = adjusted_datetime.replace(hour=row['hour'], minute=row['minute'], second=row['second'],
                                                  microsecond=0)
    if adjusted_datetime < (currentdate_time - pd.Timedelta(hours=12)):
        adjusted_datetime += pd.Timedelta(days=1)
    return adjusted_datetime


def read_csv_to_df(filename):
    """
    Read a CSV file into a DataFrame, expand rows with '*' into separate rows for each hour, and sort by time.
    """
    df = pd.read_csv(filename, delimiter=';')
    current_datetime = pd.Timestamp.now()
    star_rows = df[df['hour'] == '*']
    expanded_rows = []
    for _, row in star_rows.iterrows():
        for hour in range(24):
            new_row = row.copy()
            new_row['hour'] = hour
            expanded_rows.append(new_row)
    expanded_df = pd.DataFrame(expanded_rows)
    df = pd.concat([df[df['hour'] != '*'], expanded_df], ignore_index=True)
    df['hour'] = df['hour'].astype(int)
    df['minute'] = df['minute'].astype(int)
    df['second'] = df['second'].astype(int)
    df['time'] = df.apply(add_date_today_or_tomorrow, axis=1, currentdate_time=current_datetime)
    df_sorted = df.sort_values(by='time')

    return df_sorted


def find_future_time_row(df_sorted, current_datetime_pd, offset):
    """
    Find the row in the DataFrame that is closest to the current time in the future.
    """
    future_times = df_sorted[df_sorted['time'] >= current_datetime_pd]
    if not future_times.empty:
        closest_future_time_row = future_times.iloc[offset]
    else:
        closest_future_time_row = None
    return closest_future_time_row


def find_past_time_row(df_sorted, current_datetime_pd):
    """
    Find the row in the DataFrame that is closest to the current time in the past.
    """
    past_times = df_sorted[df_sorted['time'] < current_datetime_pd]
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
    play("sounds/gong.mp3")

    sa = sys.argv
    lsa = len(sys.argv)
    if lsa != 2:
        print("Usage: [ python3 ] roboclock.py timefile.csv")
        sys.exit(1)

    while True:
        # Read and process CSV file
        df_sorted = read_csv_to_df(sa[1])
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)

        current_datetime = pd.Timestamp.now()
        current_datetime_pd = pd.to_datetime(current_datetime)
        print(current_datetime_pd)

        past_time_row = find_past_time_row(df_sorted, current_datetime_pd)
        next_time_row = find_future_time_row(df_sorted, current_datetime_pd, 0)
        future_time_row = find_future_time_row(df_sorted, current_datetime_pd, 1)

        closest_future_time = next_time_row['time']
        time_difference = closest_future_time - current_datetime_pd
        time_difference_seconds = time_difference.total_seconds()
        next_time = next_time_row['time']

        countdown_time = next_time
        current_phase = past_time_row['phase']
        next_phase = next_time_row['phase']

        if time_difference_seconds > 12:
            sleep(10)
        else:
            set_alarm(time_difference_seconds, next_time_row['filename'], next_time_row['phase'],
                      future_time_row['time'], future_time_row['phase'])
