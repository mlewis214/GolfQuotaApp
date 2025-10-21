import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import os

st.set_page_config(page_title="17 Cent Club Quotas", layout="wide")

DATA_FILE = Path("golf_data.json")
ADMIN_USER = "Admin"
ADMIN_PASS = "pgapro"
DEFAULT_ADMIN_PIN = "1215"

# -------------------------- Load / Save --------------------------
def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if "settings" not in loaded:
                    loaded["settings"] = {"admin_pin": ""}
                else:
                    if "admin_pin" not in loaded["settings"]:
                        loaded["settings"]["admin_pin"] = ""
                return loaded
        except Exception:
            pass
    return {"players": {}, "tournaments": {}, "settings": {"admin_pin": ""}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

data = load_data()
# ensure PIN is set
data.setdefault("settings", {})
data["settings"]["admin_pin"] = DEFAULT_ADMIN_PIN
save_data(data)

# --- one-time migration: accept old list-based data and normalize to dicts
import uuid

def _normalize_data(d):
    if not isinstance(d, dict):
        return {"players": {}, "tournaments": {}, "settings": {"admin_pin": ""}}

    # ensure settings
    d.setdefault("settings", {})
    d["settings"].setdefault("admin_pin", "")

    # 1) players: list -> dict
    if isinstance(d.get("players"), list):
        new_players = {}
        for p in d["players"]:
            # build a stable key: prefer embedded id, else name, else random
            pid = (p.get("id") or (p.get("name") or "").strip().lower() or str(uuid.uuid4()))
            try:
                rounds = [float(x) for x in (p.get("rounds") or [])]
            except Exception:
                rounds = []
            new_players[pid] = {
                "name": p.get("name", "").strip(),
                "age": int(p.get("age", 65) or 65),
                "initial_quota": int(p.get("initial_quota", 18) or 18),
                "rounds": rounds,
                "temp_bonus": int(p.get("temp_bonus", 0) or 0),
            }
        d["players"] = new_players

    # name->id map for fixing tournament results
    name_to_pid = {v["name"].strip().lower(): k for k, v in d.get("players", {}).items()}

    # 2) tournaments: list -> dict
    if isinstance(d.get("tournaments"), list):
        new_t = {}
        for t in d["tournaments"]:
            tid = (t.get("id") or f"{t.get('name','').strip().lower()}|{t.get('date','')}" or str(uuid.uuid4()))
            # normalize results keys to player ids
            raw_res = t.get("results") or {}
            # if results is a list like [{"player": "...", "r1":..}, ...], convert it
            if isinstance(raw_res, list):
                tmp = {}
                for r in raw_res:
                    pname = (r.get("player") or r.get("name") or "").strip().lower()
                    pid = name_to_pid.get(pname, pname or str(uuid.uuid4()))
                    rr = [float(r.get("r1", 0) or 0), float(r.get("r2", 0) or 0), float(r.get("r3", 0) or 0)]
                    tmp[pid] = rr
                raw_res = tmp
            # if dict keyed by names, map to pids
            if isinstance(raw_res, dict):
                fixed = {}
                for k, rr in raw_res.items():
                    pname = str(k).strip().lower()
                    pid = name_to_pid.get(pname, pname)
                    try:
                        vals = [float(x) for x in (rr or [])]
                    except Exception:
                        vals = [0.0, 0.0, 0.0]
                    fixed[pid] = (vals + [0.0, 0.0, 0.0])[:3]  # ensure length 3
                raw_res = fixed

            new_t[tid] = {
                "name": t.get("name", "").strip(),
                "date": t.get("date", ""),
                "results": raw_res,
            }
        d["tournaments"] = new_t

    # 3) if tournaments already dict but results keyed by names, fix them too
    if isinstance(d.get("tournaments"), dict):
        for tid, t in d["tournaments"].items():
            res = t.get("results") or {}
            if isinstance(res, dict):
                any_name_keys = any(isinstance(k, str) and k.strip().lower() in name_to_pid for k in res.keys())
                if any_name_keys:
                    fixed = {}
                    for k, rr in res.items():
                        pid = name_to_pid.get(str(k).strip().lower(), k)
                        try:
                            vals = [float(x) for x in (rr or [])]
                        except Exception:
                            vals = [0.0, 0.0, 0.0]
                        fixed[pid] = (vals + [0.0, 0.0, 0.0])[:3]
                    t["results"] = fixed

    return d

data = _normalize_data(data)
save_data(data)  # persist normalized structure


# -------------------------- Helpers --------------------------
def tee_for_age(age):
    if age >= 80:
        return "Forward"
    elif age >= 65:
        return "Gold"
    else:
        return "White"

def display_name(name: str) -> str:
    # Display-only: ALL CAPS for player names
    return (name or "").upper()

def current_quota(rounds, initial_quota):
    """Return quota rounded to the nearest whole number (0 decimals)."""
    if not rounds:
        return int(round(initial_quota))
    recent = rounds[-9:]
    best6 = sorted(recent, reverse=True)[:6]
    return int(round(sum(best6) / 6)) if best6 else int(round(initial_quota))


def format_date_usa(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return date_str

# -------------------------- UI Navigation --------------------------
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar:
    st.header("Navigation")
    if st.session_state.is_admin:
        nav_pages = [
            "Dashboard",
            "Public Board",
            "Player Lookup",
            "Players",
            "Tournaments",
            "Upload Results (CSV)",
            "Reports",
            "Backup/Restore",
            "Admin (Login)",
        ]
        st.caption("Admin: logged in")
        if st.button("Log out"):
            st.session_state.is_admin = False
    else:
        nav_pages = ["Dashboard", "Public Board", "Player Lookup", "Admin (Login)"]
    page = st.radio("Go to", nav_pages)

# -------------------------- Dashboard --------------------------
if page == "Dashboard":
    st.title("🏌️ 17 Cent Club Quota System")
    st.write("Manage tournaments, players, and quotas with public and admin views.")
    st.info(
        "Use **Public Board** for public quotas, **Player Lookup** to view details, "
        "and **Admin (Login)** to unlock management features."
    )

# -------------------------- Public Board --------------------------
elif page == "Public Board":
    st.subheader("Public Board — Current Quotas")
    st.caption("Read-only view for members and guests. Shows current quota, tees, and rounds played.")

    # Admin login expander
    with st.expander("Admin login", expanded=False):
        st.caption("You can log in with ENV credentials (ADMIN_USER/ADMIN_PASS) or a numeric PIN saved in app data.")
        auth_mode = st.radio("Auth method", ["User/Pass", "PIN"], horizontal=True, key="pub_auth_mode")
        if auth_mode == "User/Pass":
            u = st.text_input("Username", value="", key="pub_user")
            p = st.text_input("Password", type="password", value="", key="pub_pass")
            if st.button("Log in", key="pub_login_btn_up"):
                effective_user = ADMIN_USER or "admin"
                effective_pass = ADMIN_PASS
                if effective_pass is None:
                    st.error("Password not set via ADMIN_PASS; use PIN method or set env var.")
                elif u == effective_user and p == effective_pass:
                    st.session_state.is_admin = True
                    st.success("Logged in as admin.")
                else:
                    st.error("Invalid credentials.")
        else:
            pin_in = st.text_input("Admin PIN", type="password", key="pub_pin")
            if st.button("Log in", key="pub_login_btn_pin"):
                saved_pin = data.get("settings", {}).get("admin_pin", "")
                if saved_pin and pin_in == saved_pin:
                    st.session_state.is_admin = True
                    st.success("Logged in as admin via PIN.")
                else:
                    st.error("Invalid PIN or no PIN set.")

    q = st.text_input("Search player (name contains)", "").strip()

    # Build rows (ALL CAPS names, no Age, whole-number quota)
    rows = []
    for pid, p in data["players"].items():
        rows.append(
            {
                "Player": (p["name"] or "").upper(),
                "Tees": tee_for_age(p["age"]),
                "Rounds": len(p["rounds"]),
                "Current Quota": current_quota(p["rounds"], p["initial_quota"]),
            }
        )

    # Table + download
    df_all = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Player", "Tees", "Rounds", "Current Quota"])
    df_view = df_all[df_all["Player"].str.contains(q, case=False, na=False)] if q else df_all
    st.dataframe(df_view.sort_values(by=["Player"]) if not df_view.empty else df_view, use_container_width=True)

    if not df_all.empty:
        st.download_button(
            label="Download Quotas (CSV)",
            data=df_all.to_csv(index=False).encode("utf-8"),
            file_name="current_quotas.csv",
            mime="text/csv",
        )

# -------------------------- Player Lookup --------------------------
elif page == "Player Lookup":
    st.subheader("Player Lookup — Details")
    st.caption("Search a player to view tees, quota, last 9 rounds, and recent tournament results.")

    # Use PIDs in the select box, format label to ALL CAPS names
    options = [""] + list(data["players"].keys())
    sel = st.selectbox(
        "Select player",
        options=options,
        format_func=lambda pid: (data["players"][pid]["name"] or "").upper() if pid else ""
    )
    if sel:
        pid = sel
        p = data["players"][pid]

        # Top metrics (remove Age, whole-number quota)
        c1, c2, c3 = st.columns(3)
        c1.metric("Player", (p["name"] or "").upper())
        c2.metric("Tees", tee_for_age(p["age"]))
        c3.metric("Current Quota", current_quota(p["rounds"], p["initial_quota"]))

        # Recent rounds
        st.markdown("### Recent Rounds (last 9)")
        last9 = p["rounds"][-9:] if p.get("rounds") else []
        if last9:
            df9 = pd.DataFrame({"Round #": list(range(len(last9), 0, -1))[::-1], "Points": last9})
            st.dataframe(df9, use_container_width=True)
        else:
            st.info("No rounds recorded yet.")

        # Best 6 of last 9 math
        if last9:
            best6 = sorted(last9, reverse=True)[:6]
            sum6 = sum(best6)
            quota_calc = int(round(sum6 / 6))
            st.markdown("### Best 6 of Last 9 — Calculation")
            st.write(f"Top 6 scores: **{best6}**")
            st.write(f"Sum of best 6 = **{sum6}** → Quota = round({sum6} / 6) = **{quota_calc}**")

        # Recent tournaments (unchanged)
        st.markdown("### Recent Tournaments")
        tour_rows = []
        for tid, t in data.get("tournaments", {}).items():
            rr = t.get("results", {}).get(pid)
            if rr:
                tour_rows.append(
                    {
                        "Tournament": t.get("name", "Unknown"),
                        "Date": format_date_usa(t.get("date", "No date")),
                        "R1": rr[0],
                        "R2": rr[1],
                        "R3": rr[2],
                        "Total": sum(rr),
                    }
                )
        if tour_rows:
            df_t = pd.DataFrame(tour_rows).sort_values(by=["Date"], ascending=False)
            st.dataframe(df_t, use_container_width=True)
        else:
            st.info("Player has no recorded tournament results.")
# -------------------------- Players (Admin) --------------------------
elif page == "Players":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Players — Admin")
        # table of players
        plist = []
        for pid, p in data.get("players", {}).items():
            plist.append({
                "ID": pid,
                "Player": (p["name"] or "").upper(),
                "Tees": tee_for_age(p.get("age", 65)),
                "Initial Quota": int(round(p.get("initial_quota", 18))),
                "Rounds": len(p.get("rounds", [])),
                "Current Quota": current_quota(p.get("rounds", []), p.get("initial_quota", 18)),
            })
        dfp = pd.DataFrame(plist) if plist else pd.DataFrame(
            columns=["ID", "Player", "Tees", "Initial Quota", "Rounds", "Current Quota"]
        )
        st.dataframe(dfp, use_container_width=True)

        st.markdown("### Add / Edit Player")
        cols = st.columns(4)
        name = cols[0].text_input("Name").strip()
        age = cols[1].number_input("Age", min_value=8, max_value=100, value=65, step=1)
        init_q = cols[2].number_input("Initial Quota", min_value=0, max_value=60, value=18, step=1)
        pid_edit = cols[3].selectbox("Edit existing (optional)", options=[""] + list(data["players"].keys()))

        if st.button("Save Player"):
            if not name:
                st.error("Name is required.")
            else:
                if pid_edit:
                    pid = pid_edit
                else:
                    # generate a simple id based on name (fallback to suffix)
                    base = name.strip().lower().replace(" ", "_")
                    pid = base
                    i = 2
                    while pid in data["players"]:
                        pid = f"{base}_{i}"
                        i += 1
                data["players"][pid] = {
                    "name": name,
                    "age": int(age),
                    "initial_quota": int(init_q),
                    "rounds": data["players"].get(pid, {}).get("rounds", []),
                    "temp_bonus": data["players"].get(pid, {}).get("temp_bonus", 0),
                }
                save_data(data)
                st.success(f"Saved player {name} (ID: {pid}).")

        # delete player
        del_id = st.selectbox("Delete player (danger)", options=[""] + list(data["players"].keys()))
        if st.button("Delete Selected Player"):
            if del_id:
                del_name = data["players"][del_id]["name"]
                data["players"].pop(del_id, None)
                # also strip from tournament results
                for t in data.get("tournaments", {}).values():
                    t.get("results", {}).pop(del_id, None)
                save_data(data)
                st.success(f"Deleted player {del_name}.")

# -------------------------- Tournaments (Admin) --------------------------
elif page == "Tournaments":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Tournaments — Admin")
        # table of tournaments
        tlist = []
        for tid, t in data.get("tournaments", {}).items():
            tlist.append({
                "ID": tid,
                "Tournament": t.get("name", ""),
                "Date": t.get("date", ""),
                "Entries": len((t.get("results") or {})),
            })
        dft = pd.DataFrame(tlist) if tlist else pd.DataFrame(columns=["ID", "Tournament", "Date", "Entries"])
        st.dataframe(dft, use_container_width=True)

        st.markdown("### Add / Edit Tournament")
        c1, c2, c3 = st.columns(3)
        t_name = c1.text_input("Tournament Name").strip()
        t_date = c2.date_input("Date", value=datetime.today()).strftime("%Y-%m-%d")
        t_edit = c3.selectbox("Edit existing (optional)", options=[""] + list(data.get("tournaments", {}).keys()))
        if st.button("Save Tournament"):
            if not t_name:
                st.error("Tournament name is required.")
            else:
                tid = t_edit or f"{t_name.strip().lower()}|{t_date}"
                if tid not in data["tournaments"]:
                    data["tournaments"][tid] = {"name": t_name, "date": t_date, "results": {}}
                else:
                    data["tournaments"][tid]["name"] = t_name
                    data["tournaments"][tid]["date"] = t_date
                save_data(data)
                st.success(f"Saved tournament {t_name} ({t_date}).")

        st.markdown("### Enter / Edit Results")
        tid_sel = st.selectbox("Tournament", options=[""] + list(data.get("tournaments", {}).keys()))
        pid_sel = st.selectbox("Player", options=[""] + list(data.get("players", {}).keys()),
                               format_func=lambda pid: (data["players"][pid]["name"].upper() if pid else ""))
        rcols = st.columns(3)
        r1 = rcols[0].number_input("R1", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
        r2 = rcols[1].number_input("R2", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
        r3 = rcols[2].number_input("R3", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
        if st.button("Save Results"):
            if tid_sel and pid_sel:
                data["tournaments"].setdefault(tid_sel, {}).setdefault("results", {})[pid_sel] = [r1, r2, r3]
                save_data(data)
                st.success("Results saved.")
            else:
                st.error("Select a tournament and a player.")

# -------------------------- Upload Results (CSV) --------------------------
elif page == "Upload Results (CSV)":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Upload Tournament Results from CSV")

        # Clear instructions + sample format
        st.markdown("""
**CSV should contain columns:** `Tournament_Name`, `Player_Name`, `Round_1`, `Round_2`, `Round_3`

📅 **Important:** For tournament dates, use **MM/DD/YYYY** (e.g., `03/15/2024`).  
*(Optional)* You may include a `Tournament_Date` column in **MM/DD/YYYY** to attach a date.

**View expected CSV format:**
""")

        # Downloadable template
        import io
        template = io.BytesIO()
        template.write(
            b"Tournament_Name,Player_Name,Round_1,Round_2,Round_3,Tournament_Date (optional MM/DD/YYYY)\n"
            b"Spring Championship,John Smith,8,12,7,03/15/2024\n"
            b"Spring Championship,Mary Johnson,15,18,14,03/15/2024\n"
            b"Spring Championship,Bob Wilson,6,9,11,03/15/2024\n"
        )
        template.seek(0)
        st.download_button(
            "Download CSV Template",
            data=template,
            file_name="tournament_results_template.csv",
            mime="text/csv",
        )

        st.write("---")
        st.caption("Upload your CSV below:")
        up = st.file_uploader("Upload CSV", type=["csv"])

        def _mmddyyyy_to_iso(datestr: str) -> str:
            """Convert MM/DD/YYYY -> YYYY-MM-DD; return '' if invalid/empty."""
            from datetime import datetime
            s = (datestr or "").strip()
            if not s:
                return ""
            try:
                return datetime.strptime(s, "%m/%d/%Y").strftime("%Y-%m-%d")
            except Exception:
                return ""

        if up is not None:
            import pandas as pd
            try:
                dfu = pd.read_csv(up, dtype=str).fillna("")
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
                dfu = None

            if dfu is not None:
                # Normalize headers (case-insensitive match)
                cols = {c.strip().lower(): c for c in dfu.columns}
                required = ["tournament_name", "player_name", "round_1", "round_2", "round_3"]
                missing = [r for r in required if r not in cols]
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                else:
                    st.write("Preview:")
                    st.dataframe(dfu.head(), use_container_width=True)

                    if st.button("Apply Upload"):
                        applied = 0
                        created_tournaments = 0
                        unknown_players = set()

                        # Build a fast name→pid map (case-insensitive)
                        name_to_pid = { (p.get("name","").strip().lower()): pid for pid, p in data.get("players", {}).items() }

                        for _, row in dfu.iterrows():
                            tname = str(row[cols["tournament_name"]]).strip()
                            pname = str(row[cols["player_name"]]).strip()
                            r1 = str(row[cols["round_1"]]).strip()
                            r2 = str(row[cols["round_2"]]).strip()
                            r3 = str(row[cols["round_3"]]).strip()
                            # Optional date
                            tdate_iso = ""
                            if "tournament_date" in cols:
                                tdate_iso = _mmddyyyy_to_iso(str(row[cols["tournament_date"]]))

                            if not tname or not pname:
                                continue

                            # find/create tournament
                            # Keying scheme: lowercased name + '|' + date (if present)
                            key_name = tname.strip().lower()
                            tid = f"{key_name}|{tdate_iso}" if tdate_iso else None

                            # If date provided, use (name|date) key. Else try any existing by name; if none, create undated key.
                            if tdate_iso:
                                if tid not in data["tournaments"]:
                                    data["tournaments"][tid] = {"name": tname, "date": tdate_iso, "results": {}}
                                    created_tournaments += 1
                            else:
                                # try to find existing tournament(s) with same name (any date)
                                found_tid = None
                                for _tid, t in data.get("tournaments", {}).items():
                                    if (t.get("name","").strip().lower() == key_name):
                                        found_tid = _tid
                                        break
                                if found_tid:
                                    tid = found_tid
                                else:
                                    tid = key_name  # undated key
                                    if tid not in data["tournaments"]:
                                        data["tournaments"][tid] = {"name": tname, "date": "", "results": {}}
                                        created_tournaments += 1

                            # Find player id (case-insensitive)
                            pid = name_to_pid.get(pname.strip().lower())
                            if not pid:
                                unknown_players.add(pname)
                                continue

                            # Coerce rounds to floats
                            def _f(x):
                                try:
                                    return float(x)
                                except Exception:
                                    return 0.0
                            rr = [_f(r1), _f(r2), _f(r3)]

                            data["tournaments"].setdefault(tid, {}).setdefault("results", {})[pid] = rr
                            applied += 1

                        save_data(data)
                        st.success(f"Applied {applied} rows."
                                  + (f" Created {created_tournaments} tournament(s)." if created_tournaments else ""))

                        if unknown_players:
                            st.warning("These player names were not found (case-insensitive match):  \n- " +
                                       "\n- ".join(sorted(unknown_players)))


# -------------------------- Reports (Admin) --------------------------
elif page == "Reports":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Reports — Admin")
        st.caption("Simple current-quota report.")
        rows = []
        for pid, p in data["players"].items():
            rows.append({
                "Player": (p["name"] or "").upper(),
                "Tees": tee_for_age(p.get("age", 65)),
                "Rounds": len(p.get("rounds", [])),
                "Current Quota": current_quota(p.get("rounds", []), p.get("initial_quota", 18)),
            })
        dfr = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Player", "Tees", "Rounds", "Current Quota"])
        st.dataframe(dfr.sort_values(by=["Player"]) if not dfr.empty else dfr, use_container_width=True)
        if not dfr.empty:
            st.download_button("Download Report (CSV)", dfr.to_csv(index=False).encode("utf-8"),
                               file_name="report_current_quotas.csv", mime="text/csv")

# -------------------------- Backup/Restore (Admin) --------------------------
elif page == "Backup/Restore":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Backup & Restore — Admin")
        raw = json.dumps(data, indent=2).encode("utf-8")
        st.download_button("Download golf_data.json", data=raw, file_name="golf_data.json", mime="application/json")

        st.write("---")
        st.write("**Restore from a JSON backup**")
        up = st.file_uploader("Upload golf_data.json", type=["json"], key="restore_json_admin")
        if up is not None:
            try:
                new_data = json.loads(up.read().decode("utf-8"))
                if "players" in new_data and "tournaments" in new_data:
                    st.session_state.data = new_data
                    data.clear()
                    data.update(new_data)
                    save_data(data)
                    st.success("Data restored.")
                else:
                    st.error("Invalid JSON format (missing 'players'/'tournaments').")
            except Exception as e:
                st.error(f"Failed to load JSON: {e}")


# -------------------------- Admin (Login) --------------------------
elif page == "Admin (Login)":
    st.subheader("Admin Login")
    if st.session_state.is_admin:
        st.success("You are already logged in.")
        st.write("Use the sidebar to access admin pages.")
        with st.expander("Admin PIN settings", expanded=False):
            st.caption("You can set or change a numeric PIN stored in golf_data.json → settings.admin_pin.")
            new_pin = st.text_input("Set new PIN (numbers recommended)", type="password")
            if st.button("Save PIN"):
                data.setdefault("settings", {})
                data["settings"]["admin_pin"] = new_pin.strip()
                save_data(data)
                st.success("Admin PIN updated.")
        if st.button("Log out now"):
            st.session_state.is_admin = False
    else:
        st.caption("Login with ENV (ADMIN_USER/ADMIN_PASS) or PIN if configured.")
        auth_tab = st.radio("Auth method", ["User/Pass", "PIN"], horizontal=True)
        if auth_tab == "User/Pass":
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Log in"):
                effective_user = ADMIN_USER or "admin"
                effective_pass = ADMIN_PASS
                if effective_pass is None:
                    st.error("Password not set via ADMIN_PASS; use PIN method or set env var.")
                elif u == effective_user and p == effective_pass:
                    st.session_state.is_admin = True
                    st.success("Logged in. Admin pages unlocked in the sidebar.")
                else:
                    st.error("Invalid credentials.")
        else:
            pin_try = st.text_input("Admin PIN", type="password")
            if st.button("Log in with PIN"):
                saved_pin = data.get("settings", {}).get("admin_pin", "")
                if saved_pin and pin_try == saved_pin:
                    st.session_state.is_admin = True
                    st.success("Logged in via PIN.")
                else:
                    st.error("Invalid PIN or no PIN set.")
