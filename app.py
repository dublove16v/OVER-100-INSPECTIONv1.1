"""
Dealer Inventory Management System
VAuto-style vehicle database + workbook with Inspector & Service notes
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import re

DB_PATH = Path(__file__).parent / "inventory.db"

st.set_page_config(
    page_title="Over 100 Inspection",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Big centered title at the top of every page
st.markdown("<h1 style='text-align: center;'>🚗 Over 100 Inspection</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Dealer Inventory Management System</p>", unsafe_allow_html=True)
st.markdown("---")

# ---------- DB helpers ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql, params=None):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params or [])

def execute(sql, params=None):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        conn.commit()
        return cur.lastrowid

# ---------- Sidebar navigation ----------
st.sidebar.title("🚗 Over 100 Inspection")
st.sidebar.markdown("**Better Way Wholesale Autos**")
page = st.sidebar.radio(
    "Navigation",
    ["Inventory List", "Vehicle Workbook", "Weekly Snapshot", "Archived / Sold", "About"],
    label_visibility="collapsed",
)


st.sidebar.markdown("---")
st.sidebar.caption(f"DB: {DB_PATH.name}")
stats = query_df("SELECT status, COUNT(*) as cnt FROM vehicles GROUP BY status")
for _, r in stats.iterrows():
    st.sidebar.metric(r["status"].title(), r["cnt"])

# ---------- INVENTORY LIST ----------
if page == "Inventory List":
    st.title("Inventory List")
    st.caption("Active vehicles — click Stock# or use Workbook to open detail")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        search = st.text_input("Search stock / VIN / make / model", "")
    with col2:
        make_filter = st.selectbox("Make", ["All"] + sorted(query_df("SELECT DISTINCT make FROM vehicles WHERE status='active' AND make IS NOT NULL ORDER BY make")["make"].tolist()))
    with col3:
        min_age = st.number_input("Min Age (days)", 0, 9999, 0)
    with col4:
        sort_by = st.selectbox("Sort by", ["Age (desc)", "Age (asc)", "Stock#", "List Price", "Make"])

    sql = """
        SELECT id, stock_number, year, make, model_desc, vin, age_days, miles, list_price, cost, key_code,
               etc_date, done3, done4
        FROM vehicles
        WHERE status = 'active'
    """
    params = []
    if search:
        sql += " AND (stock_number LIKE ? OR vin LIKE ? OR make LIKE ? OR model_desc LIKE ? OR full_description LIKE ?)"
        q = f"%{search}%"
        params.extend([q, q, q, q, q])
    if make_filter != "All":
        sql += " AND make = ?"
        params.append(make_filter)
    if min_age > 0:
        sql += " AND age_days >= ?"
        params.append(min_age)

    order_map = {
        "Age (desc)": "age_days DESC",
        "Age (asc)": "age_days ASC",
        "Stock#": "stock_number",
        "List Price": "list_price DESC",
        "Make": "make, year",
    }
    sql += f" ORDER BY {order_map[sort_by]}"

    df = query_df(sql, params)
    st.write(f"**{len(df)} vehicles**")

    if not df.empty:
        # Clickable table via selectbox for simplicity
        display = df.copy()
        display["Vehicle"] = display.apply(lambda r: f"{r['year']} {r['make']} {r['model_desc'] or ''}", axis=1)
        display["Done 3"] = display["done3"].apply(lambda x: "✅" if x else "")
        display["Done 4"] = display["done4"].apply(lambda x: "✅" if x else "")
        display["ETC"] = display["etc_date"].fillna("")
        display = display[["stock_number", "Vehicle", "vin", "age_days", "miles", "list_price", "cost", "ETC", "Done 3", "Done 4", "id"]]
        display.columns = ["Stock#", "Vehicle", "VIN", "Age", "Miles", "List $", "Cost $", "ETC", "Done 3", "Done 4", "id"]

        # Interactive dataframe with row selection
        event = st.dataframe(
            display.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "List $": st.column_config.NumberColumn(format="$%d"),
                "Cost $": st.column_config.NumberColumn(format="$%d"),
                "Miles": st.column_config.NumberColumn(format="%d"),
            },
            key="inventory_table",
        )

        st.markdown("### Open Vehicle Workbook")
        st.caption("Click a row in the table above to highlight a car, then click the button (or just use the dropdown).")

        # Prefer the selected row from the dataframe if the user clicked one
        selected_stock = None
        if event and event.selection and event.selection.rows:
            row_idx = event.selection.rows[0]
            selected_stock = display.iloc[row_idx]["Stock#"]

        # Fallback / also allow dropdown
        stock_list = display["Stock#"].tolist()
        default_idx = stock_list.index(selected_stock) if selected_stock in stock_list else 0
        selected_stock = st.selectbox("Select Stock#", stock_list, index=default_idx, key="stock_select")

        if st.button("Open Workbook", type="primary", use_container_width=True):
            st.session_state["selected_id"] = int(display.loc[display["Stock#"] == selected_stock, "id"].iloc[0])
            st.session_state["goto_workbook"] = True
            st.rerun()

# ---------- VEHICLE WORKBOOK ----------
elif page == "Vehicle Workbook" or st.session_state.get("goto_workbook"):
    if st.session_state.get("goto_workbook"):
        st.session_state["goto_workbook"] = False

    st.subheader("Vehicle Workbook")

    # Selector
    vehicles = query_df("SELECT id, stock_number, year, make, model_desc FROM vehicles WHERE status='active' ORDER BY stock_number")
    if vehicles.empty:
        st.warning("No active vehicles")
        st.stop()

    options = {f"{r['stock_number']} — {r['year']} {r['make']} {r['model_desc'] or ''}": r["id"] for _, r in vehicles.iterrows()}
    default_id = st.session_state.get("selected_id")
    default_idx = 0
    if default_id:
        for i, (k, v) in enumerate(options.items()):
            if v == default_id:
                default_idx = i
                break

    choice = st.selectbox("Select vehicle", list(options.keys()), index=default_idx)
    vid = options[choice]

    v = query_df("SELECT * FROM vehicles WHERE id = ?", [vid]).iloc[0]

    # Header card
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Stock#", v["stock_number"])
    c2.metric("Age (days)", v["age_days"] or "—")
    c3.metric("List Price", f"${v['list_price']:,.0f}" if v["list_price"] else "—")
    c4.metric("Cost", f"${v['cost']:,.0f}" if v["cost"] else "—")
    etc_display = v["etc_date"] if v["etc_date"] else "—"
    c5.metric("ETC", etc_display)

    st.markdown(f"### {v['year']} {v['make']} {v['model_desc'] or ''}")
    done3_icon = "✅" if v["done3"] else "⬜"
    done4_icon = "✅" if v["done4"] else "⬜"
    st.caption(f"VIN: `{v['vin']}`  |  Miles: {v['miles'] or '—'}  |  Key: {v['key_code'] or '—'}  |  Emissions: {v['emissions'] or '—'}  |  Done 3: {done3_icon}  |  Done 4: {done4_icon}")

    # Tabs
    tab_info, tab_inspector, tab_service, tab_all, tab_history = st.tabs(
        ["📋 Info", "🔍 Inspector Notes", "🔧 Service Notes", "📝 All Notes", "📅 History"]
    )

    with tab_info:
        st.subheader("Vehicle Details")
        info_cols = st.columns(2)
        with info_cols[0]:
            st.write(f"**Full Description:** {v['full_description']}")
            st.write(f"**Year / Make:** {v['year']} / {v['make']}")
            st.write(f"**Model:** {v['model_desc']}")
            st.write(f"**VIN:** {v['vin']}")
        with info_cols[1]:
            st.write(f"**Stock#:** {v['stock_number']}")
            st.write(f"**Age:** {v['age_days']} days")
            st.write(f"**Miles:** {v['miles']}")
            st.write(f"**Key Code:** {v['key_code']}")
            st.write(f"**Emissions:** {v['emissions']}")
            st.write(f"**Status:** {v['status']}")
            st.write(f"**First / Last Seen:** {v['first_seen']} → {v['last_seen']}")

        st.markdown("---")
        st.subheader("🚗 Readiness / Completion")
        ready_cols = st.columns(3)
        with ready_cols[0]:
            # ETC date
            current_etc = None
            if v["etc_date"]:
                try:
                    current_etc = datetime.strptime(str(v["etc_date"])[:10], "%Y-%m-%d").date()
                except:
                    current_etc = None
            new_etc = st.date_input("ETC (Estimated Time of Completion)", value=current_etc, key=f"etc_{vid}")
        with ready_cols[1]:
            new_done3 = st.checkbox("Done 3", value=bool(v["done3"]), key=f"done3_{vid}")
        with ready_cols[2]:
            new_done4 = st.checkbox("Done 4", value=bool(v["done4"]), key=f"done4_{vid}")

        if st.button("Save Readiness Fields", type="primary", key=f"save_ready_{vid}"):
            execute(
                "UPDATE vehicles SET etc_date=?, done3=?, done4=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [new_etc.isoformat() if new_etc else None, 1 if new_done3 else 0, 1 if new_done4 else 0, vid]
            )
            st.success("Readiness fields saved")
            st.rerun()

        st.markdown("---")
        st.subheader("Quick Status Update")
        new_status = st.selectbox("Change status", ["active", "sold", "archived"], index=["active", "sold", "archived"].index(v["status"]))
        if st.button("Update Status") and new_status != v["status"]:
            execute("UPDATE vehicles SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", [new_status, vid])
            st.success(f"Status changed to {new_status}")
            st.rerun()

    def render_notes(note_type, title):
        notes = query_df(
            "SELECT * FROM notes WHERE vehicle_id=? AND note_type=? ORDER BY created_at DESC",
            [vid, note_type],
        )
        st.subheader(title)
        if notes.empty:
            st.info("No notes yet.")
        else:
            for _, n in notes.iterrows():
                with st.container():
                    st.markdown(f"**{n['created_at'][:16]}** — *{n['author']}*")
                    st.write(n["content"])
                    st.markdown("---")

        with st.form(f"add_{note_type}"):
            content = st.text_area("Add new note", height=100, key=f"txt_{note_type}")
            author = st.text_input("Your name", value="User", key=f"auth_{note_type}")
            if st.form_submit_button("Save Note", type="primary"):
                if content.strip():
                    execute(
                        "INSERT INTO notes (vehicle_id, note_type, content, author) VALUES (?, ?, ?, ?)",
                        [vid, note_type, content.strip(), author.strip() or "User"],
                    )
                    st.success("Note saved")
                    st.rerun()
                else:
                    st.warning("Note cannot be empty")

    with tab_inspector:
        render_notes("inspector", "Inspector Notes")

    with tab_service:
        render_notes("service", "Service Department Notes")

    with tab_all:
        all_notes = query_df(
            "SELECT * FROM notes WHERE vehicle_id=? ORDER BY created_at DESC",
            [vid],
        )
        if all_notes.empty:
            st.info("No notes.")
        else:
            for _, n in all_notes.iterrows():
                badge = "🔍 Inspector" if n["note_type"] == "inspector" else "🔧 Service" if n["note_type"] == "service" else "📝 General"
                st.markdown(f"{badge} | **{n['created_at'][:16]}** — *{n['author']}*")
                st.write(n["content"])
                st.markdown("---")

        with st.form("add_general"):
            content = st.text_area("Add general note", height=80)
            author = st.text_input("Your name", value="User", key="auth_gen")
            if st.form_submit_button("Save General Note"):
                if content.strip():
                    execute(
                        "INSERT INTO notes (vehicle_id, note_type, content, author) VALUES (?, 'general', ?, ?)",
                        [vid, content.strip(), author.strip() or "User"],
                    )
                    st.success("Saved")
                    st.rerun()

    with tab_history:
        snaps = query_df(
            """
            SELECT ws.snapshot_date, ws.source_file, sv.status_at_snapshot, sv.age_days, sv.list_price
            FROM snapshot_vehicles sv
            JOIN weekly_snapshots ws ON ws.id = sv.snapshot_id
            WHERE sv.vehicle_id = ?
            ORDER BY ws.snapshot_date DESC
            """,
            [vid],
        )
        if snaps.empty:
            st.info("No snapshot history yet.")
        else:
            st.dataframe(snaps, use_container_width=True, hide_index=True)

# ---------- WEEKLY SNAPSHOT ----------
elif page == "Weekly Snapshot":
    st.title("Weekly Snapshot / Import")
    st.markdown(
        """
        Upload a new inventory report (same format as REPORT 10-7-26.xls).
        The system will:
        - Add brand-new vehicles (highlighted as new)
        - Update age / list / miles on existing
        - Mark vehicles missing from the new report as **sold** (or leave active if you prefer)
        """
    )

    uploaded = st.file_uploader("Upload new REPORT .xls / .xlsx", type=["xls", "xlsx"])
    mark_missing_sold = st.checkbox("Automatically mark missing vehicles as SOLD", value=True)
    snapshot_note = st.text_input("Snapshot notes (optional)", "")

    if uploaded and st.button("Process Snapshot", type="primary"):
        try:
            df_new = pd.read_excel(uploaded, header=1)
            df_new.columns = [c.strip() for c in df_new.columns]
            required = ["Stock#", "VIN", "Vehicle Description", "Cost", "List", "Age", "Miles"]
            for col in required:
                if col not in df_new.columns:
                    st.error(f"Missing column: {col}")
                    st.stop()

            df_new = df_new.dropna(subset=["Stock#"])
            today = date.today()

            # Create snapshot record
            snap_id = execute(
                "INSERT INTO weekly_snapshots (snapshot_date, source_file, notes) VALUES (?, ?, ?)",
                [today, uploaded.name, snapshot_note or f"Import {today}"],
            )

            existing = query_df("SELECT id, stock_number, stock_base FROM vehicles")
            existing_map = {r["stock_number"]: r["id"] for _, r in existing.iterrows()}
            existing_bases = {str(r["stock_base"]).lstrip("0"): r["id"] for _, r in existing.iterrows() if r["stock_base"]}

            new_count = 0
            updated_count = 0
            seen_ids = set()

            for _, row in df_new.iterrows():
                stock = str(row["Stock#"]).strip()
                base = re.sub(r"[A-Z]+$", "", stock).strip().lstrip("0")
                vin = str(row["VIN"]) if pd.notna(row.get("VIN")) else None
                full = str(row["Vehicle Description"])
                m = re.match(r"^(\d{2})\s+([A-Z]+)\s+(.+)$", full.strip())
                year, make, model = (m.group(1), m.group(2), m.group(3).strip()) if m else (None, None, full)
                cost = float(row["Cost"]) if pd.notna(row["Cost"]) else None
                listp = float(row["List"]) if pd.notna(row["List"]) else None
                age = int(row["Age"]) if pd.notna(row["Age"]) else None
                miles = int(row["Miles"]) if pd.notna(row["Miles"]) else None
                keyc = str(row.get("KEY CODE", "")) if pd.notna(row.get("KEY CODE")) else None
                emis = str(row.get("EMISSIONS", "")) if pd.notna(row.get("EMISSIONS")) else None

                if stock in existing_map:
                    vid = existing_map[stock]
                    execute(
                        """UPDATE vehicles SET age_days=?, miles=?, list_price=?, cost=?, key_code=?, emissions=?,
                           last_seen=?, status='active', updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        [age, miles, listp, cost, keyc, emis, today, vid],
                    )
                    updated_count += 1
                elif base in existing_bases:
                    vid = existing_bases[base]
                    execute(
                        """UPDATE vehicles SET stock_number=?, age_days=?, miles=?, list_price=?, cost=?, key_code=?, emissions=?,
                           last_seen=?, status='active', updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        [stock, age, miles, listp, cost, keyc, emis, today, vid],
                    )
                    updated_count += 1
                else:
                    vid = execute(
                        """INSERT INTO vehicles (stock_number, stock_base, vin, year, make, model_desc, full_description,
                           cost, list_price, age_days, miles, key_code, emissions, status, first_seen, last_seen)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?)""",
                        [stock, base, vin, year, make, model, full, cost, listp, age, miles, keyc, emis, today, today],
                    )
                    new_count += 1

                seen_ids.add(vid)
                execute(
                    "INSERT INTO snapshot_vehicles (snapshot_id, vehicle_id, age_days, list_price, status_at_snapshot) VALUES (?,?,?,?,?)",
                    [snap_id, vid, age, listp, "active"],
                )

            sold_count = 0
            if mark_missing_sold:
                active = query_df("SELECT id FROM vehicles WHERE status='active'")
                for _, r in active.iterrows():
                    if r["id"] not in seen_ids:
                        execute("UPDATE vehicles SET status='sold', updated_at=CURRENT_TIMESTAMP WHERE id=?", [r["id"]])
                        sold_count += 1

            st.success(f"Snapshot processed: **{new_count} new**, **{updated_count} updated**, **{sold_count} marked sold**")
            st.balloons()
        except Exception as e:
            st.error(f"Error processing file: {e}")

    st.markdown("---")
    st.subheader("Past Snapshots")
    snaps = query_df("SELECT * FROM weekly_snapshots ORDER BY snapshot_date DESC")
    if not snaps.empty:
        st.dataframe(snaps, use_container_width=True, hide_index=True)

# ---------- ARCHIVED / SOLD ----------
elif page == "Archived / Sold":
    st.title("Archived / Sold Vehicles")
    status_filter = st.radio("Show", ["sold", "archived", "both"], horizontal=True)
    if status_filter == "both":
        df = query_df("SELECT stock_number, year, make, model_desc, vin, age_days, list_price, last_seen, status FROM vehicles WHERE status IN ('sold','archived') ORDER BY last_seen DESC")
    else:
        df = query_df("SELECT stock_number, year, make, model_desc, vin, age_days, list_price, last_seen, status FROM vehicles WHERE status=? ORDER BY last_seen DESC", [status_filter])

    st.write(f"**{len(df)} vehicles**")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Restore option
        st.markdown("### Restore to Active")
        stocks = df["stock_number"].tolist()
        to_restore = st.multiselect("Select to restore", stocks)
        if st.button("Restore selected") and to_restore:
            for s in to_restore:
                execute("UPDATE vehicles SET status='active', updated_at=CURRENT_TIMESTAMP WHERE stock_number=?", [s])
            st.success(f"Restored {len(to_restore)} vehicles")
            st.rerun()

# ---------- ABOUT ----------
else:
    st.title("About This System")
    st.markdown(
        """
        ### Dealer Inventory Management (VAuto-style)

        Built from your **REPORT 10-7-26.xls** as the master vehicle database and notes imported from the **10/1/26** sheet of *OVER 100 INSPECTION*.

        **Key features**
        - Clean vehicle list with stock#, VIN, year/make/model, cost, list, age, miles, key code, emissions
        - **Vehicle Workbook** with dedicated tabs for:
          - Inspector Notes
          - Service Department Notes
          - All notes + general notes
          - Snapshot history
        - Weekly Snapshot import: add new cars, update existing, auto-archive / mark sold the ones that disappear
        - Search, filter, sort
        - Multi-user ready when hosted (Streamlit Cloud, internal server, or shared folder + local run)

        **How to run on other computers**
        1. Share the entire `inventory_app` folder (contains `app.py` + `inventory.db`)
        2. On each PC: `pip install streamlit pandas openpyxl`
        3. Run: `streamlit run app.py`
        4. Or deploy free to [Streamlit Community Cloud](https://streamlit.io/cloud) for browser access from anywhere

        **Data location**: All data lives in `inventory.db` (SQLite). Back it up regularly.
        """
    )
    st.info("Tip: Put the folder on a shared Google Drive / OneDrive and have everyone run Streamlit against the same DB file for simple multi-user (close the app when done to avoid lock issues). For heavier multi-user, we can migrate to Postgres later.")
