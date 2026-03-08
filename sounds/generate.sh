#!/bin/bash
# Generate announcement sounds using macOS text-to-speech

# say -v Alex "end of mobility, start dexterity." -o end_mobility_start_dexterity
# say -v Alex "end of dexterity, start victim identification." -o end_dexterity_start_victimid

say -v Alex "Prepare for the next mission." -o prepare_for_the_next_mission
say -v Alex "Begin operation." -o begin_operation
say -v Alex "End of operation, start sensor assessment." -o end_of_operation_start_sensor_assessment
say -v Alex "End of sensor assessment, clear the arena." -o end_of_sensor_assessment_clear_the_arena

# Convert AIFF to M4A (browser-compatible)
for f in *.aiff; do
    [ -f "$f" ] || continue
    base="${f%.aiff}"
    ffmpeg -y -i "$f" -c:a aac -b:a 128k "${base}.m4a"
done