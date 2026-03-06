#!/bin/bash
# say -v Alex “end of mobility, start dexterity.” -o end_mobility_start_dexterity
say -v Alex “end of dexterity, start victim identification.” -o end_dexterity_start_victimid
# Convert AIFF to M4A (browser-compatible)
for f in *.aiff; do
    [ -f "$f" ] || continue
    base="${f%.aiff}"
    ffmpeg -y -i "$f" -c:a aac -b:a 128k "${base}.m4a"
done