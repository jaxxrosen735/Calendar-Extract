#!/usr/bin/env python3
"""Verify calendar data quality"""

from ics import Calendar

# Read combined calendar
with open('toronto_screenings.ics', 'r', encoding='utf-8') as f:
    cal = Calendar(f.read())

# Count events with end times
has_end = 0
no_end = 0
for event in cal.events:
    if hasattr(event, 'end') and event.end:
        has_end += 1
    else:
        no_end += 1

print(f"Total events: {len(cal.events)}")
print(f"Events with end times: {has_end}")
print(f"Events without end times: {no_end}")
print(f"\nPercentage with accurate end times: {(has_end/len(cal.events)*100):.1f}%")

# Sample TIFF events (should have end times)
print("\n" + "=" * 100)
print("Sample TIFF Events (with accurate end times):")
count = 0
targets = ["A Poet", "Inherent Vice", "Arco", "All That's Left of You"]
for event in cal.events:
    for target in targets:
        if target in event.name and count < 5:
            start = event.begin
            end = event.end if hasattr(event, 'end') and event.end else None
            if end:
                duration = (end - start).total_seconds() / 60
                print(f"  {event.name:30} | {start.strftime('%Y-%m-%d %H:%M')} | {end.strftime('%H:%M')} | {int(duration)}m")
                count += 1
            break
