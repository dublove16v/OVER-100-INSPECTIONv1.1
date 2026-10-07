# Dealer Inventory DMS (VAuto-style)

Web-based dealer inventory management system built from your REPORT 10-7-26.xls + OVER 100 INSPECTION notes.

## Features
- Master vehicle database (stock#, VIN, description, cost, list, age, miles, key, emissions)
- Vehicle Workbook with separate **Inspector Notes** and **Service Department Notes**
- Weekly Snapshot import: adds new cars, updates existing, marks missing ones as SOLD
- Search / filter / sort
- Archive & restore

## Quick Start (any computer)

```bash
cd inventory_app
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL shown (usually http://localhost:8501)

## Multi-user
- Easiest: put this folder on shared Google Drive / OneDrive / network share. Everyone runs `streamlit run app.py` against the same `inventory.db`.
- Better: deploy to Streamlit Community Cloud (free) so everyone just opens a browser link.
- For heavier concurrent use we can later switch the backend to Postgres / Google Sheets.

## Files
- `app.py` – the Streamlit web app
- `inventory.db` – SQLite database (all your data)
- `requirements.txt` – Python dependencies

## Initial Data
- 116 vehicles loaded from REPORT 10-7-26.xls
- 192 notes (inspector + service) matched from the 10/1/26 sheet of OVER 100 INSPECTION
