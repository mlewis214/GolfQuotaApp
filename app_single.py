

# app_single.py
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

import streamlit as st

# ---------------------- Config / Secrets ----------------------
import os

def _safe_secret(key: str, default: str) -> str:
    """Try Streamlit secrets (if available), else env var, else default—no file required."""
    try:
        return st.secrets.get(key, os.environ.get(key, default))  # works on Cloud, harmless locally
    except Exception:
        return os.environ.get(key, default)

ADMIN_USER = _safe_secret("ADMIN_USER", "admin")
ADMIN_PASS = _safe_secret("ADMIN_PASS", "pgapro")
DEFAULT_ADMIN_PIN = _safe_secret("ADMIN_PIN", "1215")

# ---------------------- Simple theme accents ----------------------
PRIMARY = "#0B6CFB"
BG_SOFT = "#F5F8FF"
TABLE_BG = "#EEF3FF"

st.markdown(
    f"""
    <style>
      .stApp {{
        background: white;
      }}
      .app-header {{
        padding: 0.6rem 0.9rem;
        background: linear-gradient(90deg, {BG_SOFT}, #ffffff);
        border: 1px solid #e8eefc;
        border-radius: 12px;
        margin-bottom: 12px;
      }}
      .app-header h1, .app-header h2, .app-header h3 {{
        color: {PRIMARY} !important;
        margin: 0;
        padding: 0;
      }}
      .blue-chip {{
        display:inline-block; padding:2px 8px; border-radius:999px;
        background:{TABLE_BG}; color:#0b2a88; font-size:0.82rem; border:1px solid #dfe7ff;
      }}
      .section-card {{
        border:1px solid #e8eefc; border-radius:12px; padding:12px; background:#fff;
      }}
      /* soften dataframes */
      div[data-testid="stDataFrame"] div[role="grid"] {{
        background: {TABLE_BG}10;
        border-radius: 8px;
        border: 1px solid #e8eefc;
      }}
      .stDownloadButton > button, .stButton > button {{
        border-radius:10px !important; border:1px solid #dbe4ff !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------- Config / Secrets ----------------------
ADMIN_USER = st.secrets.get("ADMIN_USER", "admin")
ADMIN_PASS = st.secrets.get("ADMIN_PASS", "pgapro")
DEFAULT_ADMIN_PIN = st.secrets.get("ADMIN_PIN", "1215")

def _data_dir() -> Path:
    """Store golf_data.json next to the EXE when frozen, otherwise next to this file."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

DATA_FILE = _data_dir() / "golf_data.json"

# ---------------------- Data I/O ----------------------
def load_data() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        base = {"players": {}, "tournaments": {}, "settings": {"admin_pin": DEFAULT_ADMIN_PIN}}
        save_data(base)
        return base
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Backfill minimal structure
        data.setdefault("players", {})
        data.setdefault("tournaments", {})
        data.setdefault("settings", {}).setdefault("admin_pin", DEFAULT_ADMIN_PIN)
        return data
    except Exception:
        # recover with blank
        base = {"players": {}, "tournaments": {}, "settings": {"admin_pin": DEFAULT_ADMIN_PIN}}
        save_data(base)
        return base

def save_data(data: Dict[str, Any]) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save data: {e}")

# ---------------------- Helpers ----------------------
def tee_for_age(age: int | float | None) -> str:
    """You can adapt tee logic; using a simple default now."""
    a = 65 if age in (None, "") else int(age)
    if a >= 70: return "Gold"
    if a >= 60: return "White"
    return "Blue"

def _round_up(n: float) -> int:
    import math
    return int(math.ceil(n))

def aggregate_player_rounds_from_tournaments(
    tournaments: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Produce per-player list of rounds with date from tournament results.
    Each 'round' entry is {'score': float, 'date': 'YYYY-MM-DD', 'tournament_id': tid, 'tournament_name': str}
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for tid, t in tournaments.items():
        tdate = t.get("date", "") or ""
        tname = t.get("name", "")
        results: Dict[str, List[float]] = t.get("results", {})
        for pid, scores in (results or {}).items():
            for s in scores or []:
                try:
                    sc = float(s)
                except Exception:
                    sc = 0.0
                out.setdefault(pid, []).append(
                    {"score": sc, "date": tdate, "tournament_id": tid, "tournament_name": tname}
                )
    return out

def quota_current_from_recent_rounds(
    rounds: List[Dict[str, Any]],
    initial_quota: float | int = 18,
) -> int:
    """
    Compute CURRENT quota = average of best 6 of the most recent 9 scores, rounded UP to nearest whole.
    Recency is determined by 'date' descending; empty/invalid dates go last.
    """
    if not rounds:
        return int(initial_quota)

    def _date_key(r):
        d = (r.get("date") or "").strip()
        # Empty strings sort last
        return d

    # Sort newest first by ISO date (YYYY-MM-DD); empty dates at end
    sorted_recent = sorted(rounds, key=_date_key, reverse=True)
    # Take most recent 9 scores
    recent_scores = [float(r.get("score", 0.0)) for r in sorted_recent[:9]]
    # Keep best 6
    best6 = sorted(recent_scores, reverse=True)[:6]
    if not best6:
        return int(initial_quota)
    avg = sum(best6) / len(best6)
    return _round_up(avg)

def ensure_session():
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    if "data" not in st.session_state:
        st.session_state.data = load_data()

ensure_session()
data = st.session_state.data

# ---------------------- Header ----------------------
st.markdown('<div class="app-header"><h2>GolfQuota — Club Quotas & Results</h2></div>', unsafe_allow_html=True)

# ---------------------- Sidebar Navigation ----------------------
st.sidebar.markdown("### Navigation")
page = st.sidebar.selectbox(
    "Go to",
    [
        "Public Board",
        "Player Lookup",
        "Tournaments",
        "Upload Results (CSV)",
        "Reports",
        "Backup/Restore",
        "Admin (Login)",
    ],
)

# ---------------------- Public Board ----------------------
if page == "Public Board":
    st.markdown("#### Public Board — Current Quotas")
    st.caption("Read-only view for members and guests. Shows current quota, tees, and rounds played.")

    # Aggregate player rounds by looking at tournaments
    rounds_by_player = aggregate_player_rounds_from_tournaments(data.get("tournaments", {}))

    rows = []
    for pid, p in data.get("players", {}).items():
        pname = (p.get("name", "") or "").upper()
        player_rounds = rounds_by_player.get(pid, [])
        quota = quota_current_from_recent_rounds(player_rounds, p.get("initial_quota", 18))
        rows.append(
            {
                "PLAYER": pname,
                "TEES": tee_for_age(p.get("age", 65)),
                "ROUNDS": len(player_rounds),
                "CURRENT QUOTA": quota,
            }
        )

    import pandas as pd
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["PLAYER", "TEES", "ROUNDS", "CURRENT QUOTA"])
    if df.empty:
        st.info("No players yet. Admins can upload results in **Upload Results (CSV)**.")
    else:
        st.dataframe(df.sort_values(by=["PLAYER"]), use_container_width=True)

    st.write("---")
    st.markdown(f'<span class="blue-chip">Need to manage data?</span> Use the sidebar → **Admin (Login)**', unsafe_allow_html=True)


# ---------------------- Player Lookup ----------------------
elif page == "Player Lookup":
    st.markdown("#### Player Lookup")
    st.caption("Search a player to see quota details and recent tournaments.")
    all_players = data.get("players", {})
    options = sorted([(pid, p.get("name", "")) for pid, p in all_players.items()], key=lambda x: x[1].casefold())

    if not options:
        st.info("No players yet.")
    else:
        name_map = {f"{n} (ID:{pid[:6]})": pid for pid, n in options}
        choice = st.selectbox("Select player", list(name_map.keys()))
        pid = name_map[choice]
        p = all_players.get(pid, {})
        pname_uc = (p.get("name", "") or "").upper()

        st.markdown(f"### {pname_uc}")
        rounds_by_player = aggregate_player_rounds_from_tournaments(data.get("tournaments", {}))
        prounds = rounds_by_player.get(pid, [])

        # Current quota (best 6 of most recent 9), rounded up
        curr_quota = quota_current_from_recent_rounds(prounds, p.get("initial_quota", 18))
        st.metric("Current Quota", f"{curr_quota}")

        # Show last 5 tournaments (newest first)
        import pandas as pd
        recent = sorted(prounds, key=lambda r: r.get("date", ""), reverse=True)[:5]
        if not recent:
            st.info("No tournaments found for this player.")
        else:
            display = []
            for r in recent:
                display.append(
                    {
                        "DATE": r.get("date", ""),
                        "TOURNAMENT": r.get("tournament_name", ""),
                        "SCORE": r.get("score", 0),
                    }
                )
            st.markdown("##### Recent Tournaments")
            dfr = pd.DataFrame(display)
            st.dataframe(dfr, use_container_width=True)

        # Explain best-6-of-9 calculation (which scores were used)
        # Build recent 9 and top6 listing for transparency
        rec9 = sorted(prounds, key=lambda r: r.get("date", ""), reverse=True)[:9]
        top6 = sorted([float(x.get("score", 0.0)) for x in rec9], reverse=True)[:6]
        if rec9:
            st.markdown("##### Best 6 of Most-Recent 9 — Calculation")
            st.write(f"Recent 9 scores (by date): {[float(x.get('score', 0.0)) for x in rec9]}")
            st.write(f"Top 6 kept: {top6} → Average (rounded up): **{_round_up(sum(top6)/len(top6) if top6 else 0)}**")


# ---------------------- Tournaments (view only) ----------------------
elif page == "Tournaments":
    st.markdown("#### Tournaments (Newest first)")
    ts = data.get("tournaments", {})
    if not ts:
        st.info("No tournaments yet.")
    else:
        # sort by date desc
        sorted_ts = sorted(ts.items(), key=lambda x: (x[1].get("date", "") or ""), reverse=True)
        for tid, t in sorted_ts:
            st.markdown(
                f'<div class="section-card"><b>{t.get("name","(Unnamed)")}</b> '
                f'— <span class="blue-chip">{t.get("date","No date") or "No date"}</span></div>',
                unsafe_allow_html=True,
            )


# ---------------------- Upload Results (CSV) ----------------------
elif page == "Upload Results (CSV)":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        import pandas as pd
        import io
        from datetime import datetime
        from rapidfuzz import process, fuzz
        import uuid

        st.subheader("Upload Tournament Results from CSV")
        st.markdown("""
**CSV must contain:** `Tournament_Name`, `Player_Name`, `Round_1`, `Round_2`, `Round_3`  
*(Optional)*: `Tournament_Date` (MM/DD/YYYY).  
Only **unmatched/uncertain** players will appear for correction.
""")

        # Template
        tmpl = io.BytesIO()
        tmpl.write(
            b"Tournament_Name,Player_Name,Round_1,Round_2,Round_3,Tournament_Date\n"
            b"Spring Championship,John Smith,8,12,7,03/15/2024\n"
            b"Spring Championship,Mary Johnson,15,18,14,03/15/2024\n"
            b"Spring Championship,Bob Wilson,6,9,11,03/15/2024\n"
        )
        tmpl.seek(0)
        st.download_button("Download CSV Template", data=tmpl, file_name="tournament_results_template.csv", mime="text/csv")

        st.write("---")
        tname_override = st.text_input("Tournament Name (optional, overrides CSV)")
        tdate_override = st.date_input("Tournament Date (optional)")

        up = st.file_uploader("Upload CSV", type=["csv"])

        def _mmddyyyy_to_iso(s: str) -> str:
            s = (s or "").strip()
            if not s:
                return ""
            try:
                return datetime.strptime(s, "%m/%d/%Y").strftime("%Y-%m-%d")
            except Exception:
                return ""

        if up is not None:
            try:
                df = pd.read_csv(up, dtype=str).fillna("")
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
                df = None

            if df is not None:
                cols = {c.strip().lower(): c for c in df.columns}
                required = ["tournament_name", "player_name", "round_1", "round_2", "round_3"]
                missing = [r for r in required if r not in cols]
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                else:
                    st.caption("Preview of uploaded file:")
                    st.dataframe(df.head(), use_container_width=True)

                    # Build name map
                    name_to_pid = { (p.get("name","").strip().lower()): pid for pid, p in data.get("players", {}).items() }

                    unmatched = []
                    matched_rows: List[Tuple[str, str, float, str]] = []  # (csv_name, matched_key, score, pid)
                    for _, row in df.iterrows():
                        pname = str(row[cols["player_name"]]).strip()
                        if not pname:
                            continue
                        # fuzzy match
                        match = process.extractOne(pname.lower(), name_to_pid.keys(), scorer=fuzz.WRatio)
                        if match and match[1] >= 90:
                            matched_rows.append((pname, match[0], float(match[1]), name_to_pid[match[0]]))
                        else:
                            unmatched.append(pname)

                    corrections = {}
                    if unmatched:
                        st.warning(f"{len(unmatched)} player(s) need attention. Fix them below before applying.")
                        for raw in sorted(set(unmatched), key=str.casefold):
                            suggestion = process.extractOne(raw.lower(), name_to_pid.keys(), scorer=fuzz.WRatio)
                            suggested_name = suggestion[0].title() if suggestion else ""
                            confidence = int(suggestion[1]) if suggestion else 0

                            st.write("---")
                            st.markdown(f"**Unmatched Player:** `{raw}`  &nbsp; "
                                        f"<span class='blue-chip'>Suggested: {suggested_name or '—'} ({confidence}%)</span>",
                                        unsafe_allow_html=True)
                            c1, c2 = st.columns([2, 2])
                            with c1:
                                final_name = st.text_input(f"Confirm/Correct name for '{raw}'", value=suggested_name, key=f"fix_{raw}")
                            with c2:
                                action = st.radio(f"Action for {raw}", ["Accept (match/create)", "Skip"], horizontal=True, key=f"act_{raw}")
                            corrections[raw] = {"final_name": (final_name or raw).strip(), "action": action}

                    if st.button("Apply Upload"):
                        applied = 0
                        created_tournaments = 0
                        added_players = 0

                        for _, row in df.iterrows():
                            # Tournament meta
                            tname = tname_override or str(row[cols["tournament_name"]]).strip()
                            tdate_csv = str(row[cols["tournament_date"]]).strip() if "tournament_date" in cols else ""
                            tdate_iso = _mmddyyyy_to_iso(str(tdate_override)) if tdate_override else _mmddyyyy_to_iso(tdate_csv)

                            if not tname:
                                # Skip rows with no tournament name
                                continue

                            key_name = tname.strip().lower()
                            tid = f"{key_name}|{tdate_iso}" if tdate_iso else key_name
                            if tid not in data["tournaments"]:
                                data["tournaments"][tid] = {"name": tname, "date": tdate_iso, "results": {}}
                                created_tournaments += 1

                            # Player resolve
                            raw_name = str(row[cols["player_name"]]).strip()
                            if raw_name in corrections:
                                if corrections[raw_name]["action"].startswith("Skip"):
                                    continue
                                final_name = corrections[raw_name]["final_name"]
                            else:
                                final_name = raw_name

                            pid = name_to_pid.get(final_name.lower())
                            if not pid:
                                # Create new player persistently
                                pid = str(uuid.uuid4())[:8]
                                data["players"][pid] = {
                                    "name": final_name.title(),
                                    "age": 65,
                                    "initial_quota": 18,
                                    "rounds": [],  # reserved; we compute from tournaments
                                }
                                name_to_pid[final_name.lower()] = pid
                                added_players += 1

                            # Scores
                            def _f(x):
                                try:
                                    return float(x)
                                except Exception:
                                    return 0.0
                            scores = [_f(row[cols["round_1"]]), _f(row[cols["round_2"]]), _f(row[cols["round_3"]])]

                            data["tournaments"][tid]["results"][pid] = scores
                            applied += 1

                        save_data(data)
                        st.success(
                            f"Applied **{applied}** rows. "
                            f"Created **{created_tournaments}** tournament(s). "
                            f"Added **{added_players}** player(s)."
                        )


# ---------------------- Reports ----------------------
elif page == "Reports":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Reports — Current Quotas")
        rounds_by_player = aggregate_player_rounds_from_tournaments(data.get("tournaments", {}))
        rows = []
        for pid, p in data.get("players", {}).items():
            rows.append({
                "PLAYER": (p.get("name","") or "").upper(),
                "TEES": tee_for_age(p.get("age", 65)),
                "ROUNDS": len(rounds_by_player.get(pid, [])),
                "CURRENT QUOTA": quota_current_from_recent_rounds(rounds_by_player.get(pid, []), p.get("initial_quota", 18)),
            })
        import pandas as pd
        dfr = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["PLAYER", "TEES", "ROUNDS", "CURRENT QUOTA"])
        st.dataframe(dfr.sort_values(by=["PLAYER"]) if not dfr.empty else dfr, use_container_width=True)
        if not dfr.empty:
            st.download_button("Download Report (CSV)", dfr.to_csv(index=False).encode("utf-8"),
                               file_name="report_current_quotas.csv", mime="text/csv")


# ---------------------- Backup / Restore ----------------------
elif page == "Backup/Restore":
    if not st.session_state.is_admin:
        st.warning("Admin only. Please log in.")
    else:
        st.subheader("Backup & Restore")
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


# ---------------------- Admin Login ----------------------
elif page == "Admin (Login)":
    st.subheader("Admin Login")
    if st.session_state.is_admin:
        st.success("You are already logged in.")
        st.write("Use the sidebar to access admin pages (Upload, Reports, Backup/Restore).")
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
        st.caption("Login with username/password or PIN.")
        tab = st.radio("Auth method", ["User/Pass", "PIN"], horizontal=True)
        if tab == "User/Pass":
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Log in"):
                if u == ADMIN_USER and p == ADMIN_PASS:
                    st.session_state.is_admin = True
                    st.success("Logged in. Admin pages unlocked in the sidebar.")
                else:
                    st.error("Invalid credentials.")
        else:
            pin_try = st.text_input("Admin PIN", type="password", value="")
            if st.button("Log in with PIN"):
                saved_pin = data.get("settings", {}).get("admin_pin", DEFAULT_ADMIN_PIN)
                if pin_try == saved_pin:
                    st.session_state.is_admin = True
                    st.success("Logged in via PIN.")
                else:
                    st.error("Invalid PIN.")
