import sys
from time import sleep
import csv
import subprocess
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import threading
host_name = "127.0.0.1"
port = 5000
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # CORS für alle Routen aktivieren

countdown_time = datetime.now() + timedelta(minutes=5)
current_phase = "---"
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
        'current_phase': current_phase
    })


def play(audio_file_path):
    print("playing %s" % audio_file_path)
    subprocess.call(["mplayer", audio_file_path])


def read_csv(args):
    global countdown_time
    # print "Reading %s" % (args)
    next_time = None
    time_delta = -1
    for argument in args:
        with open(argument, 'r') as f:
            csv_reader = csv.DictReader(f, delimiter=';', quotechar='"')
            now = datetime.now()
            print("Now: %s" % (now,))
            for row in csv_reader:
                s = row['hour']
                if s.startswith("#"):
                    continue
                if row['hour'] != '*':
                    time = now.replace(hour=int(row['hour']), minute=int(row['minute']), second=int(row['second']),
                                       microsecond=0)
                else:
                    time = now.replace(minute=int(row['minute']), second=int(row['second']), microsecond=0)
                    if time < now:
                        time = time + timedelta(hours=1)
                    print("  Variable time adjusted to %s" % (time,))
                if (time > now) and ((next_time is None) or (time < next_time)):
                    next_time = time
                    sound_filename = row['filename']
                    phase = row['phase']
                    time_delta = next_time - now
                    # print "  Time diff is %s" % (time_diff, )
    print("  Next alarm at %s (file %s) in %s secs." % (next_time, sound_filename, time_delta.total_seconds()))
    countdown_time = next_time
    return time_delta.total_seconds(), sound_filename, phase, next_time


def set_alarm(seconds, sound_filename, phase, next_time):
    global current_phase
    global countdown_time
    try:
        if seconds > 0:
            print("Sleeping light for %s secs." % (str(seconds),))
            sleep(seconds)
        print("Wake up")
        countdown_time = next_time
        current_phase = phase
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
    play("sounds/gong.mp3")
    sa = sys.argv
    lsa = len(sys.argv)
    if lsa != 2:
        print("Usage: [ python3 ] roboclock.py timefile.csv")
        sys.exit(1)
    while 1:
        (time_diff, filename, phase, next_time) = read_csv(sa[1:])
        if time_diff < 0:
            print("No more alarms set")
            sys.exit(0)
        if time_diff > 12:
            # print "Sleeping deep for %s seconds" % (time_diff, )
            sleep(10)
        else:
            set_alarm(time_diff, filename, phase, next_time)
