import sys
from time import sleep
import subprocess
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import threading
import pandas as pd

host_name = "127.0.0.1"
port = 5000
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # CORS für alle Routen aktivieren

countdown_time = datetime.now() + timedelta(minutes=5)
current_phase = "---"
next_phase = "---"

@app.route('/get_countdown', methods=['GET'])
def get_countdown():
    current_time = datetime.now()
    time_remaining = countdown_time - current_time
    if time_remaining.total_seconds() < 0:
        time_remaining = timedelta(seconds=0)
    print("  Countdown time is %s in %s:%s (phase %s)." % (countdown_time, time_remaining.seconds // 60, time_remaining.seconds % 60, current_phase))
    return jsonify({
        'minutes': time_remaining.seconds // 60,
        'seconds': time_remaining.seconds % 60,
        'current_phase': current_phase,
        'next_phase': next_phase
    })


def read_csv_to_df(filename):
    df = pd.read_csv(filename, delimiter=';')
    # Iterate over rows with '*' and create new rows for each hour
    star_rows = df[df['hour'] == '*']
    expanded_rows = []
    for _, row in star_rows.iterrows():
        for hour in range(24):
            new_row = row.copy()
            new_row['hour'] = hour
            expanded_rows.append(new_row)
    expanded_df = pd.DataFrame(expanded_rows)
    df = pd.concat([df[df['hour'] != '*'], expanded_df], ignore_index=True)
    # Create a 'time' column for sorting with today's date
    df['hour'] = df['hour'].astype(int)
    df['minute'] = df['minute'].astype(int)
    df['second'] = df['second'].astype(int)
    today_str = datetime.today().strftime('%Y-%m-%d')
    df['time'] = pd.to_datetime(df[['hour', 'minute', 'second']].apply(lambda x: f'{today_str} {x[0]:02}:{x[1]:02}:{x[2]:02}', axis=1))
    # Sort the DataFrame by the 'time' column
    df_sorted = df.sort_values(by='time')
    return df_sorted

# Function to find the row closest to the current time (in the future)
def find_future_time_row(df_sorted, current_time, offset):
    closest_time_row = df_sorted[df_sorted['time'].dt.time >= current_time].iloc[offset]

    return closest_time_row

# Function to find the row closest to the current time (in the past)
def find_past_time_row(df_sorted, current_time):
    past_time_row = df_sorted[df_sorted['time'].dt.time < current_time].iloc[-1]
    return past_time_row

def play(audio_file_path):
    print("playing %s" % audio_file_path)
    subprocess.call(["mplayer", audio_file_path])

def set_alarm(seconds, sound_filename, c_phase, next_time, n_phase):
    global current_phase, next_phase, countdown_time
    try:
        if seconds > 0:
            print("Sleeping light for %s secs." % (str(seconds),))
            sleep(seconds)
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
    threading.Thread(target=lambda: app.run(host=host_name, port=port, debug=True, use_reloader=False)).start()
    # play("sounds/gong.mp3")
    sa = sys.argv
    lsa = len(sys.argv)
    if lsa != 2:
        print("Usage: [ python3 ] roboclock.py timefile.csv")
        sys.exit(1)
    while 1:
        df_sorted = read_csv_to_df(sa[1])
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)

        current_time = datetime.now().time()
        past_time_row = find_past_time_row(df_sorted, current_time)
        future_time_row = find_future_time_row(df_sorted, current_time, 0)
        future_future_time_row = find_future_time_row(df_sorted, current_time, 1)

        closest_future_time = future_time_row['time'].time()
        time_difference = datetime.combine(datetime.today(), closest_future_time) - datetime.combine(datetime.today(), current_time)
        time_difference_seconds = time_difference.total_seconds()
        next_time = datetime.combine(datetime.today(), future_time_row['time'].time())

        countdown_time = next_time
        current_phase = past_time_row['phase']
        next_phase = future_time_row['phase']

        if time_difference_seconds > 12:
            sleep(10)
        else:
            set_alarm(time_difference_seconds, future_time_row['filename'],
                    future_time_row['phase'],
                    datetime.combine(datetime.today(), future_future_time_row['time'].time()),
                    future_future_time_row['phase'],)
