import sys
from time import sleep
import csv
import datetime
import subprocess


def play(audio_file_path):
    print("playing %s" % audio_file_path)
    subprocess.call(["mplayer", audio_file_path])


def read_csv(args):
    # print "Reading %s" % (args)
    next_time = None
    time_delta = -1
    for argument in args:
        with open(argument, 'r') as f:
            csv_reader = csv.DictReader(f, delimiter=';', quotechar='"')
            now = datetime.datetime.now()
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
                        time = time + datetime.timedelta(hours=1)
                    print("  Variable time adjusted to %s" % (time,))
                if (time > now) and ((next_time is None) or (time < next_time)):
                    next_time = time
                    sound_filename = row['filename']
                    time_delta = next_time - now
                    # print "  Time diff is %s" % (time_diff, )
    print("  Next alarm at %s (file %s) in %s secs." % (next_time, sound_filename, time_delta.total_seconds()))
    return time_delta.total_seconds(), sound_filename


def set_alarm(seconds, sound_filename):
    try:
        if seconds > 0:
            print("Sleeping light for %s secs." % (str(seconds),))
            sleep(seconds)
        print("Wake up")
        play("sounds/%s" % ("gong.mp3",))
        sleep (1)
        play("sounds/%s" % (sound_filename,))
        sleep (1)
        play("sounds/%s" % (sound_filename,))
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    play("sounds/gong.mp3")
    sa = sys.argv
    lsa = len(sys.argv)
    if lsa != 2:
        print("Usage: [ python3 ] roboclock.py timefile.csv")
        sys.exit(1)
    while 1:
        (time_diff, filename) = read_csv(sa[1:])
        if time_diff < 0:
            print("No more alarms set")
            sys.exit(0)
        if time_diff > 12:
            # print "Sleeping deep for %s seconds" % (time_diff, )
            sleep(10)
        else:
            set_alarm(time_diff, filename)
