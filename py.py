import streamlit as st
import pandas as pd
import datetime
import os
import time
from thefuzz import fuzz, process

LOG_FILE = "workout_log.csv"

# --- Muscle Detection ---
muscle_keywords = {
    "Chest": ["bench", "press", "pec", "fly", "incline", "decline"],
    "Back": ["row", "pull", "lat", "deadlift"],
    "Shoulders": ["shoulder", "overhead", "military", "lateral", "raise"],
    "Biceps": ["curl", "biceps", "preacher"],
    "Triceps": ["triceps", "dips", "pushdown", "extension"],
    "Forearms": ["reverse", "wrist", "hammer", "forearm"],
    "Legs": ["squat", "leg", "lunge", "hamstring", "quad", "calf"],
    "Core": ["abs", "crunch", "plank", "sit-up", "core"]
}
all_muscles = list(muscle_keywords.keys()) + ["Other"]


def detect_body_part(exercise_name):
    name = exercise_name.lower()
    best_match = None
    best_score = 0
    for group, keywords in muscle_keywords.items():
        for keyword in keywords:
            score = fuzz.partial_ratio(keyword, name)
            if score > best_score and score >= 80:
                best_score = score
                best_match = group
    return best_match


def detect_intensity(reps):
    if reps < 6:
        return "Too Heavy"
    elif 6 <= reps <= 12:
        return "Moderate Heavy"
    else:
        return "Light Weight"


def append_log(df):
    df.to_csv(LOG_FILE, mode='a', index=False, header=not os.path.exists(LOG_FILE))


def get_previous_logs(exercise_name):
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame()

    df = pd.read_csv(LOG_FILE)
    if df.empty or "exercise" not in df:
        return pd.DataFrame()

    exercise_name_lower = exercise_name.lower()
    unique_exercises = df['exercise'].unique()

    best_match, score = process.extractOne(exercise_name_lower, unique_exercises, scorer=fuzz.partial_ratio)

    if score >= 85:
        df = df[df['exercise'].str.lower() == best_match.lower()]
        df = df.sort_values(by="date", ascending=False)
        recent_dates = df["date"].unique()[:2]
        df = df[df["date"].isin(recent_dates)]
        return df.reset_index(drop=True)

    return pd.DataFrame()


# --- Streamlit App ---
st.set_page_config(page_title="Smart Workout Logger", layout="centered")
st.title("🏋️ Smart Workout Logger")

date = st.date_input("📅 Workout Date", datetime.date.today())

if "exercise_blocks" not in st.session_state:
    st.session_state.exercise_blocks = [{"id": 0}]
    st.session_state.next_id = 1

log_rows = []


def render_exercise_block(block, is_first=False):
    block_id = block["id"]
    st.markdown(f"### 🏋️ Exercise #{block_id + 1}")

    cols = st.columns([5, 1])
    with cols[0]:
        raw = st.text_input("Exercise Name", key=f"ex_name_{block_id}")
        name = raw.title().strip() if raw else ""
    with cols[1]:
        if not is_first:
            if st.button("❌", key=f"delete_{block_id}"):
                st.session_state.exercise_blocks = [
                    b for b in st.session_state.exercise_blocks if b["id"] != block_id
                ]
                st.rerun()

    if name:
        body_part = detect_body_part(name)
        if body_part:
            st.success(f"🧠 Detected Muscle Group: **{body_part}**")
        else:
            body_part = st.selectbox("❓ Couldn't detect, select manually:",
                                     options=all_muscles,
                                     key=f"manual_select_{block_id}")

        prev_logs = get_previous_logs(name)
        if not prev_logs.empty:
            st.markdown("#### 🕘 Previous Logs (Last 2 sessions)")
            recent_dates = prev_logs["date"].unique()[:2][::-1]
            for d in recent_dates:
                subset = prev_logs[prev_logs["date"] == d]
                st.markdown(f"**📅 {d}**")
                for _, row in subset.iterrows():
                    st.markdown(f"- Set {int(row['set'])}: {row['weight']} kg × {int(row['reps'])} reps")

        sets = st.number_input(f"Sets for {name}", min_value=1, max_value=10, value=3, key=f"sets_{block_id}")

        for s in range(1, sets + 1):
            c1, c2 = st.columns(2)

            weight_input = c1.text_input(f"Set {s} - Weight (kg)", key=f"w_{block_id}_{s}", placeholder="e.g. 60.0")
            reps_input = c2.text_input(f"Set {s} - Reps", key=f"r_{block_id}_{s}", placeholder="e.g. 10")

            try:
                weight = float(weight_input) if weight_input else 0.0
            except ValueError:
                weight = 0.0
                st.warning(f"⚠️ Invalid weight for Set {s}. Using 0.0.")

            try:
                reps = int(reps_input) if reps_input else 0
            except ValueError:
                reps = 0
                st.warning(f"⚠️ Invalid reps for Set {s}. Using 0.")

            volume = weight * reps
            intensity = detect_intensity(reps)

            # Progress Suggestion
            if not prev_logs.empty:
                same_weight_set = prev_logs[(prev_logs["weight"] == weight) & (prev_logs["set"] == s)]
                if not same_weight_set.empty:
                    last_reps = same_weight_set.sort_values("date").iloc[-1]["reps"]
                    target_reps = int(last_reps) + 1

                    placeholder = st.empty()
                    if reps < last_reps:
                        placeholder.error(f"Push harder! Last time Set {s} at {int(weight)}kg → {int(last_reps)} reps. Try for {target_reps}!")
                    elif reps == last_reps:
                        placeholder.info(f"Match achieved: {int(reps)} reps. Next time aim for {target_reps}!")
                    else:
                        placeholder.success(f"Great! You beat your last Set {s} at {int(weight)}kg with {int(reps)} reps!")
                    time.sleep(4)
                    placeholder.empty()

            log_rows.append([date, name, body_part, s, weight, reps, volume, intensity])


render_exercise_block(st.session_state.exercise_blocks[0], is_first=True)

for block in st.session_state.exercise_blocks[1:]:
    render_exercise_block(block)

if st.button("➕ Add Exercise"):
    st.session_state.exercise_blocks.append({"id": st.session_state.next_id})
    st.session_state.next_id += 1
    st.rerun()

if st.button("✅ Save Workout Log"):
    if log_rows:
        df = pd.DataFrame(log_rows, columns=[
            "date", "exercise", "body_part", "set", "weight", "reps", "volume", "intensity"
        ])
        append_log(df)
        st.success("✅ Workout log saved!")

        st.download_button(
            label="⬇️ Download Log as CSV",
            data=df.to_csv(index=False).encode(),
            file_name=f"{date}_workout_log.csv",
            mime="text/csv"
        )
    else:
        st.warning("Please log at least one exercise.")
