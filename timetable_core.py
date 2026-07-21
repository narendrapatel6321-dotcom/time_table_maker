"""
timetable_core.py — modular timetable builder for MSc Maths (IITB) students.
"""
import json
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

def _load_json(name):
    with open(os.path.join(DATA_DIR, name)) as f:
        return json.load(f)

COURSE_SLOTS = _load_json("course_slots.json")
SLOT_TIMINGS = _load_json("slot_timings.json")
SLOT_GROUPS = _load_json("slot_groups.json")

def course_exists(code):
    return code.strip() in COURSE_SLOTS

def get_sections(code):
    info = COURSE_SLOTS.get(code.strip())
    return info["sections"] if info else []

def needs_section_choice(code):
    return len(get_sections(code)) > 1

def _resolve_l_slot(raw_slot):
    return SLOT_GROUPS.get(raw_slot, [raw_slot])

def _time_str(start, end):
    def fmt(t):
        h, m = map(int, t.split(":"))
        suffix = "am" if h < 12 else "pm"
        h12 = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
        return f"{h12}:{m:02d}{suffix}"
    return f"{fmt(start)} - {fmt(end)}"

def _sort_key(row):
    return datetime.strptime(row[0].split(" - ")[0], "%I:%M%p")

def build_schedule(enrolled, electives=None):
    electives = electives or []
    schedule = {d: [] for d in DAY_ORDER}
    warnings = []

    for item in enrolled:
        code = item.get("code", "").strip()
        if not course_exists(code):
            warnings.append(f"'{code}' not found in course_slots.json — skipped.")
            continue

        info = COURSE_SLOTS[code]
        sections = info["sections"]

        if len(sections) > 1:
            chosen_instructor = item.get("instructor")
            match = next((s for s in sections if s["instructor"] == chosen_instructor), None)
            if match is None:
                warnings.append(f"'{code}' requires instructor selection — skipped.")
                continue
            l_slot = match["L_slot"]
        else:
            l_slot = sections[0]["L_slot"]

        # Process Lecture meetings
        for concrete in _resolve_l_slot(l_slot):
            if concrete not in SLOT_TIMINGS:
                warnings.append(f"'{code}': slot '{concrete}' has no known timing.")
                continue
            t = SLOT_TIMINGS[concrete]
            schedule[t["day"]].append([
                _time_str(t["start"], t["end"]), concrete, f"{code} - {info['name']}", "Lecture"
            ])

        # Process Tutorial meetings
        for t_slot in info["T_slots"]:
            if t_slot not in SLOT_TIMINGS:
                warnings.append(f"'{code}': tutorial slot '{t_slot}' has no known timing.")
                continue
            t = SLOT_TIMINGS[t_slot]
            schedule[t["day"]].append([
                _time_str(t["start"], t["end"]), t_slot, f"{code} - {info['name']}", "Tutorial"
            ])

    # Process manual electives
    for e in electives:
        day = e.get("day")
        if day not in DAY_ORDER:
            continue
        try:
            time_str = _time_str(e["start"], e["end"])
            schedule[day].append([
                time_str, e.get("slot", "—"), e.get("name", "Institute Elective"),
                e.get("type", "Lecture")
            ])
        except Exception:
            warnings.append(f"Elective '{e.get('name')}' has an invalid time — skipped.")

    for day in schedule:
        schedule[day].sort(key=_sort_key)

    return schedule, warnings

def detect_conflicts(schedule):
    conflicts = []
    for day, rows in schedule.items():
        parsed = []
        for row in rows:
            start_s, end_s = row[0].split(" - ")
            start = datetime.strptime(start_s, "%I:%M%p")
            end = datetime.strptime(end_s, "%I:%M%p")
            parsed.append((start, end, row[2]))
        parsed.sort()
        for i in range(len(parsed) - 1):
            if parsed[i][1] > parsed[i + 1][0]:
                conflicts.append(f"{day}: '{parsed[i][2]}' overlaps with '{parsed[i + 1][2]}'")
    return conflicts

def render_timetable_image(schedule, output_path, title="My Timetable"):
    try:
        FONT_DIR = "/usr/share/fonts/truetype/dejavu"
        font_bold = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 20)
        font_day = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 17)
        font_header = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 13)
        font_cell = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 13)
    except IOError:
        # Fallback if custom fonts are missing on the deployment server
        font_bold = font_day = font_header = font_cell = ImageFont.load_default()

    col_widths = [140, 60, 380, 100]
    row_h = 30
    day_gap = 14
    margin = 30
    width = margin * 2 + sum(col_widths)

    height = margin + 40
    for day in DAY_ORDER:
        rows = schedule.get(day, [])
        height += 28 + row_h + (row_h * max(len(rows), 1)) + day_gap

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    y = margin
    draw.text((margin, y), title, font=font_bold, fill="black")
    y += 40

    header_bg, row_bg, border = (220, 220, 220), (245, 245, 245), (150, 150, 150)

    for day in DAY_ORDER:
        rows = schedule.get(day, [])
        draw.text((margin, y), day, font=font_day, fill="black")
        y += 28

        x = margin
        draw.rectangle([x, y, x + sum(col_widths), y + row_h], fill=header_bg, outline=border)
        for w, h in zip(col_widths, ["Time", "Slot", "Course", "Type"]):
            draw.text((x + 5, y + 6), h, font=font_header, fill="black")
            x += w
        y += row_h

        if not rows:
            draw.rectangle([margin, y, margin + sum(col_widths), y + row_h], fill=row_bg, outline=border)
            draw.text((margin + 5, y + 6), "— Free —", font=font_cell, fill=(120, 120, 120))
            y += row_h
        else:
            for row in rows:
                x = margin
                draw.rectangle([x, y, x + sum(col_widths), y + row_h], fill=row_bg, outline=border)
                for w, val in zip(col_widths, row):
                    draw.text((x + 5, y + 6), str(val), font=font_cell, fill="black")
                    x += w
                y += row_h
        y += day_gap

    img.save(output_path)
    return output_path