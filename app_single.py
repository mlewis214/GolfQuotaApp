# app_single.py — GolfQuota (PIN-only login, fuzzy CSV upload, player editing, full quota view)
import streamlit as st
import pandas as pd
import json
import uuid
import os
from datetime import datetime
from rapidfuzz import process, fuzz

# ===================== App config & theme =====================
st.set_page_config(page_title="Golf Quota Board", layout="wide")

st.markdown("""
<style>
body, .stApp { background-color:#111 !important; color:#f5f5f5 !important; }
div[data-testid="stSidebar"] { background-color:#000 !important; }
h1,h2,h3,h4,h5,h6,label,p,div,span { color:#f5f5f5 !important; }
div[data-testid="stDataFrame"] div[role="grid"] {
  background:#1e1e1e; color:#f5f5f5; border:1px solid #ccc; border-radius:8px;
}
.stButton>button,.stDownloadButton>button {
  background:#1e1e1e !important; color:#f5f5f5 !important; border:1px solid #ccc !important; border-radius:10px !important;
}
.danger>button { border-color:#ff6b6b !important; }
</style>
""", unsafe_allow_html=True)

# ===================== Data storage =====================
DATA_FILE = "golf_data.json"
ADMIN_PIN = "1215"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"players": {}, "tournaments": {}, "settings": {"admin_pin": ADMIN_PIN}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

data = load_data()

# ===================== Helpers =====================
def _normalize_date(s: str) -> str:
    """Accepts YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY. Returns YYYY-MM-DD or ''."""
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return ""

def tee_for_age(age):
    return "White" if int(age or 65) < 80 else "Gold"

def current_quota(rounds, initial):
    if not rounds:
        return int(initial)
    last9 = rounds[-9:]
    top6 = sorted(last9, reverse=True)[:6]
    from math import ceil
    return int(ceil(sum(top6) / len(top6)))

def aggregate_rounds_from_tournaments(tournaments):
    out = {}
    for tid, t in tournaments.items():
        res = t.get("results", {}) or {}
        for pid, scores in res.items():
            out.setdefault(pid, [])
            for s in scores:
                try: out[pid].append(float(s))
                except: out[pid].append(0.0)
    return out

# ===================== Session State =====================
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# ===================== Sidebar Navigation =====================
st.sidebar.title("Navigation")
public_pages = ["Public Board", "Player Lookup", "Tournaments", "Admin (PIN Login)"]
admin_pages = ["Upload Results (CSV)", "Manage Players", "Reports", "Backup/Restore"]

page = st.sidebar.selectbox(
    "Go to:",
    public_pages + admin_pages if st.session_state.is_admin else public_pages
)

# ===================== Public Board =====================
if page == "Public Board":
    st.header("🏌️ Public Quota Board (Read-Only)")
    rounds_by_player = aggregate_rounds_from_tournaments(data.get("tournaments", {}))

    rows = []
    for pid, p in data.get("players", {}).items():
        pname = (p.get("name", "") or "").title()
        scores = rounds_by_player.get(pid, [])
        quota = current_quota(scores, p.get("initial_quota", 18))
        rows.append({
            "Player": pname,
            "Tees": tee_for_age(p.get("age", 65)),
            "Rounds": len(scores),
            "Current Quota": quota
        })
    df = pd.DataFrame(rows)
    st.dataframe(df.sort_values("Player") if not df.empty else df, use_container_width=True)

# ===================== Player Lookup =====================
elif page == "Player Lookup":
    st.header("🔎 Player Lookup")
    st.caption("View player history, tournaments, and quota calculation.")

    # Build display list
    players = data.get("players", {})
    display_names = sorted([(pid, p["name"]) for pid, p in players.items()], key=lambda x: x[1].lower())
    if not display_names:
        st.info("No players found.")
        st.stop()

    sel_name = st.selectbox("Select player", [n for _, n in display_names])
    pid = next(pid for pid, n in display_names if n == sel_name)
    p = players[pid]

    pname = p["name"].title()
    st.subheader(pname)

    # Show tournaments (newest first)
    ts = data.get("tournaments", {})
    tournaments = sorted(ts.items(), key=lambda x: (x[1].get("date", "") or ""), reverse=True)
    rows = []
    for tid, t in tournaments:
        if pid in t.get("results", {}):
            scores = t["results"][pid]
            rows.append({
                "Date": t.get("date", ""),
                "Tournament": t.get("name", ""),
                "Round 1": scores[0] if len(scores) > 0 else "",
                "Round 2": scores[1] if len(scores) > 1 else "",
                "Round 3": scores[2] if len(scores) > 2 else "",
            })
    if rows:
        st.markdown("##### Recent Tournaments")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No tournaments found for this player.")

    # Quota calculation: last 9 → best 6
    flat_scores = []
    for tid, t in ts.items():
        date = t.get("date", "")
        name = t.get("name", "")
        for s in t.get("results", {}).get(pid, []):
            try:
                val = float(s)
                flat_scores.append({"Date": date, "Tournament": name, "Score": val})
            except:
                pass
    flat_scores = sorted(flat_scores, key=lambda r: r["Date"], reverse=True)[:9]

    if flat_scores:
        from math import ceil
        top6 = sorted([r["Score"] for r in flat_scores], reverse=True)[:6]
        avg = sum(top6) / len(top6)
        quota_now = ceil(avg)
        df9 = pd.DataFrame(flat_scores)
        df9["Kept (Top 6)"] = df9["Score"].isin(top6)
        st.markdown("##### Quota Calculation (Most-Recent 9 → Keep Top 6)")
        st.dataframe(df9, use_container_width=True)
        st.metric("Current Quota (rounded up)", f"{quota_now}")
        st.caption(f"Top 6 kept: {top6} → average = {avg:.2f} → rounded up = {quota_now}")
    else:
        st.metric("Current Quota", f"{p.get('initial_quota', 18)}")
        st.caption("No recorded scores yet.")

# ===================== Tournaments (with delete for admin) =====================
elif page == "Tournaments":
    st.header("🏆 Tournaments")
    ts = data.get("tournaments", {})
    if not ts:
        st.info("No tournaments yet.")
    else:
        for tid, t in sorted(ts.items(), key=lambda x: (x[1].get("date", "") or ""), reverse=True):
            st.subheader(f"{t.get('name', '(Unnamed)')} — {t.get('date', 'No date')}")
            rows = []
            for pid, scores in t.get("results", {}).items():
                pname = data["players"].get(pid, {}).get("name", "Unknown")
                rows.append({
                    "Player": pname.title(),
                    "Round 1": scores[0] if len(scores) > 0 else "",
                    "Round 2": scores[1] if len(scores) > 1 else "",
                    "Round 3": scores[2] if len(scores) > 2 else "",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            if st.session_state.is_admin:
                if st.button(f"Delete {t.get('name','(Unnamed)')}", key=f"del_{tid}", type="primary"):
                    del data["tournaments"][tid]
                    save_data(data)
                    st.success("Tournament deleted.")
                    st.experimental_rerun()

# ===================== Upload Results (CSV) =====================
elif page == "Upload Results (CSV)" and st.session_state.is_admin:
    st.header("📤 Upload Tournament Results (CSV)")
    st.caption("Format: Tournament_Name, Player_Name, Round_1, Round_2, Round_3, Tournament_Date")

    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        df = pd.read_csv(file, dtype=str)
        df.columns = [c.strip().replace("\ufeff", "").lower() for c in df.columns]
        required = ["tournament_name", "player_name", "round_1", "round_2", "round_3"]
        if any(r not in df.columns for r in required):
            st.error(f"Missing columns. Found: {df.columns.tolist()}")
            st.stop()

        st.dataframe(df.head(), use_container_width=True)

        name_to_pid = {p["name"].lower(): pid for pid, p in data["players"].items()}
        existing_names = [p["name"] for p in data["players"].values()]
        unmatched = [str(r["player_name"]).strip() for _, r in df.iterrows()
                     if str(r["player_name"]).strip().lower() not in name_to_pid]

        corrections = {}
        if unmatched:
            st.warning(f"{len(unmatched)} unmatched player(s). Resolve below:")
            for raw in sorted(set(unmatched)):
                st.write("---")
                st.markdown(f"**Unmatched:** `{raw}`")
                matches = process.extract(raw, existing_names, scorer=fuzz.token_sort_ratio, limit=5)
                suggested = [m[0] for m in matches if m[1] >= 70]
                if suggested:
                    st.caption("Suggested: " + ", ".join(suggested))

                mode = st.radio(f"Action for {raw}",
                                ["Match to Existing Player", "Add New Player"],
                                key=f"mode_{raw}", horizontal=True)

                if mode == "Match to Existing Player" and existing_names:
                    pick = st.selectbox(f"Select existing player for {raw}",
                                        options=existing_names, key=f"pick_{raw}")
                    corrections[raw] = {"action": "match", "final_name": pick}
                else:
                    new_name = st.text_input(f"Enter new name for {raw}",
                                             value=raw.title(), key=f"new_{raw}")
                    corrections[raw] = {"action": "create", "final_name": new_name}

        if st.button("Apply Upload"):
            applied = created = added = 0
            for _, row in df.iterrows():
                tname = str(row.get("tournament_name", "")).strip()
                tdate_raw = str(row.get("tournament_date", "")).strip()
                tdate = _normalize_date(tdate_raw) or datetime.today().strftime("%Y-%m-%d")
                tid = f"{tname.lower()}|{tdate}"

                if tid not in data["tournaments"]:
                    data["tournaments"][tid] = {"name": tname, "date": tdate, "results": {}}
                    created += 1

                pname = str(row.get("player_name", "")).strip()
                pid = name_to_pid.get(pname.lower())
                if not pid and pname in corrections:
                    fix = corrections[pname]
                    if fix["action"] == "match":
                        pid = name_to_pid.get(fix["final_name"].lower())
                    elif fix["action"] == "create":
                        pid = str(uuid.uuid4())[:8]
                        nm = fix["final_name"].title()
                        data["players"][pid] = {"name": nm, "age": 65, "initial_quota": 18, "rounds": []}
                        name_to_pid[nm.lower()] = pid
                        added += 1
                if not pid:
                    continue

                scores = [float(row.get(f"round_{i}", 0) or 0) for i in range(1, 4)]
                data["tournaments"][tid]["results"][pid] = scores
                applied += 1

            save_data(data)
            st.success(f"Applied {applied} rows — Created {created} tournaments — Added {added} players.")

# ===================== Manage Players =====================
elif page == "Manage Players" and st.session_state.is_admin:
    st.header("🧑‍💼 Manage Players")
    for pid, p in sorted(data["players"].items(), key=lambda x: x[1]["name"].lower()):
        with st.expander(p["name"].title()):
            new_name = st.text_input("Name", p["name"], key=f"name_{pid}")
            new_age = st.number_input("Age", min_value=10, max_value=100, value=int(p.get("age", 65)), key=f"age_{pid}")
            new_quota = st.number_input("Initial Quota", min_value=0, max_value=60, value=int(p.get("initial_quota", 18)), key=f"quota_{pid}")
            if st.button("Save", key=f"save_{pid}"):
                p.update({"name": new_name.title(), "age": new_age, "initial_quota": new_quota})
                save_data(data)
                st.success("Updated.")

# ===================== Reports =====================
elif page == "Reports" and st.session_state.is_admin:
    st.header("📊 Reports")

    # Player Quotas
    st.subheader("Player Quotas")
    rounds_by_player = aggregate_rounds_from_tournaments(data.get("tournaments", {}))
    rows = []
    for pid, p in data["players"].items():
        scores = rounds_by_player.get(pid, [])
        rows.append({
            "Player": p["name"].title(),
            "Tees": tee_for_age(p.get("age", 65)),
            "Rounds": len(scores),
            "Quota": current_quota(scores, p.get("initial_quota", 18))
        })
    st.dataframe(pd.DataFrame(rows).sort_values("Player"), use_container_width=True)

    # Tournament Summary
    st.subheader("Tournament Summary")
    ts = data.get("tournaments", {})
    summary = [{"Tournament": t["name"], "Date": t["date"], "Players": len(t["results"])} for t in ts.values()]
    st.dataframe(pd.DataFrame(summary).sort_values("Date", ascending=False), use_container_width=True)

# ===================== Backup & Restore =====================
elif page == "Backup/Restore" and st.session_state.is_admin:
    st.header("💾 Backup & Restore")
    raw = json.dumps(data, indent=2).encode("utf-8")
    st.download_button("Download Backup", data=raw, file_name="golf_data.json", mime="application/json")
    up = st.file_uploader("Restore Backup", type=["json"])
    if up:
        new_data = json.loads(up.read().decode("utf-8"))
        if "players" in new_data and "tournaments" in new_data:
            save_data(new_data)
            st.session_state.data = new_data
            st.success("Backup restored. Restart app to apply.")

# ===================== Admin (PIN Login) =====================
elif page == "Admin (PIN Login)":
    st.header("🔐 Admin Login (PIN Only)")
    if st.session_state.is_admin:
        st.success("You are logged in as Admin.")
        if st.button("Log Out"):
            st.session_state.is_admin = False
            st.experimental_rerun()
    else:
        pin = st.text_input("Enter PIN", type="password")
        if st.button("Login"):
            if pin == data.get("settings", {}).get("admin_pin", ADMIN_PIN):
                st.session_state.is_admin = True
                st.success("Login successful! Admin menus unlocked.")
                st.experimental_rerun()
            else:
                st.error("Incorrect PIN.")
