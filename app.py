import streamlit as st
import timetable_core as tc
import datetime

st.set_page_config(page_title="MSc Maths Timetable Generator", layout="centered")

st.title(" IITB MSc Maths Timetable")
st.markdown("Select your enrolled courses below. The app will automatically map your slots and generate a personalized weekly timetable image.")

# --- 1. Department Course Selection ---
st.header("1. Select Core Courses")
available_courses = sorted(list(tc.COURSE_SLOTS.keys()))
selected_codes = st.multiselect("Choose your M.Sc. courses:", available_courses)

enrolled = []
if selected_codes:
    st.subheader("Section Preferences")
    for code in selected_codes:
        if tc.needs_section_choice(code):
            sections = tc.get_sections(code)
            instructors = [s["instructor"] for s in sections]
            choice = st.selectbox(f"Select instructor for {code}:", instructors)
            enrolled.append({"code": code, "instructor": choice})
        else:
            enrolled.append({"code": code})

# --- 2. Custom Institute Electives ---
st.header("2. Add Institute Electives (Optional)")
st.markdown("Add courses outside the department. You can enter generic slots (e.g., `4`) or comma-separated concrete slots (e.g., `4A, 4B, X1`).")

if "electives" not in st.session_state:
    st.session_state.electives = []

with st.expander("➕ Add an elective not listed above"):
    e_name = st.text_input("Course Code/Name (e.g., HS 101)")
    
    col1, col2 = st.columns(2)
    with col1:
        e_l_slots = st.text_input("Lecture Slots (L.Slot)", placeholder="e.g., 4, or 4A, 4B")
    with col2:
        e_t_slots = st.text_input("Tutorial Slots (T.Slot)", placeholder="e.g., X1, X2")
    
    if st.button("Add Elective"):
        if not e_name:
            st.error("Please provide a course name.")
        elif not e_l_slots and not e_t_slots:
            st.error("Please provide at least one Lecture or Tutorial slot.")
        else:
            invalid_slots = []

            # Helper function rewritten to return a boolean instead of using nonlocal
            def process_slots(slot_string, slot_type):
                did_add = False
                # Split by comma, strip spaces, ignore empty strings
                raw_slots = [s.strip().upper() for s in slot_string.split(",") if s.strip()]
                
                for raw_slot in raw_slots:
                    # Expand generic slots (like '4') to concrete ('4A', '4B')
                    concrete_slots = tc.SLOT_GROUPS.get(raw_slot, [raw_slot])
                    
                    for c_slot in concrete_slots:
                        if c_slot in tc.SLOT_TIMINGS:
                            timing = tc.SLOT_TIMINGS[c_slot]
                            st.session_state.electives.append({
                                "name": e_name,
                                "day": timing["day"],
                                "start": timing["start"],
                                "end": timing["end"],
                                "type": slot_type,
                                "slot": c_slot
                            })
                            did_add = True
                        else:
                            invalid_slots.append(c_slot)
                return did_add

            # Process both input fields
            added_l = process_slots(e_l_slots, "Lecture")
            added_t = process_slots(e_t_slots, "Tutorial")
            added_any = added_l or added_t

            if invalid_slots:
                st.warning(f"Added valid slots, but these were unrecognized in the grid: {', '.join(invalid_slots)}")
            elif added_any:
                st.success(f"Added {e_name} successfully!")

# Display currently added electives
if st.session_state.electives:
    st.write("**Current Custom Electives:**")
    added_names = set(el["name"] for el in st.session_state.electives)
    for name in added_names:
        st.write(f"- {name}")
    
    if st.button("Clear Electives"):
        st.session_state.electives = []
        st.rerun()


# --- 3. Generation & Rendering ---
st.header("3. Generate")
output_format = st.radio("Select Output Format:", ["JPG", "PDF"], horizontal=True)

if st.button("Generate Timetable", type="primary"):
    if not enrolled and not st.session_state.electives:
        st.error("Please select at least one course or add an elective to generate a schedule.")
    else:
        with st.spinner("Building your schedule..."):
            schedule, warnings = tc.build_schedule(enrolled, st.session_state.electives)
            conflicts = tc.detect_conflicts(schedule)

            for w in warnings:
                st.warning(w)
            for c in conflicts:
                st.error(f"Time Conflict Detected: {c}")

            ext = output_format.lower()
            output_file = f"my_timetable.{ext}"
            mime_type = "image/jpeg" if ext == "jpg" else "application/pdf"

            tc.render_timetable_image(schedule, output_file)

            if ext == "jpg":
                st.image(output_file, caption="Your Generated Timetable", use_container_width=True)
            else:
                st.success("PDF generated successfully! Click below to download.")

            with open(output_file, "rb") as file:
                st.download_button(
                    label=f"Download {output_format}",
                    data=file,
                    file_name=f"iitb_timetable.{ext}",
                    mime=mime_type
                )
