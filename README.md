# Smart Train Booking & Seat Utilization — Step-by-Step Starter Project

This is a learning prototype for your academic project. It uses:
- Frontend: HTML, CSS, JavaScript
- Backend: Python + Flask
- Database: SQLite
- Analytics: Pandas + Matplotlib (optional chart export)

**Important:** Demo only. It is not connected to IRCTC/Indian Railways. Station timings, trains, and the 1-hour gap are simulated. The proposed gap-seat idea is only a prototype.

## Step 1 — Install Python
Install Python 3.10+ and VS Code.

## Step 2 — Open this folder in VS Code
Open a terminal inside the project folder.

## Step 3 — Create and activate a virtual environment (recommended)
Windows:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```
If PowerShell blocks activation, use Command Prompt:
```bat
.venv\Scripts\activate.bat
```
macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Step 4 — Install libraries
```bash
pip install -r requirements.txt
```

## Step 5 — Run the application
```bash
python app.py
```
Open http://127.0.0.1:5000 in your browser.

## Step 6 — Test normal seat allocation
1. On the home page, create a booking from Chennai to Station 4.
2. Use a different passenger and search Station 3 to Bangalore.
3. If a normal seat is available, the system prioritizes a continuous seat. To test the gap option, make demo bookings until seats on the full segment are occupied or use a seat pattern that creates a gap.
4. Choose the gap option only if you accept the displayed simulated waiting gap.

## Pages
- `/` — search/home
- `/bookings` — booking history/cancellation
- `/tatkal` — add and process demo Tatkal requests in FIFO order
- `/dashboard` — basic analytics

## Step-by-step learning order
1. `templates/index.html` + `static/style.css`: frontend
2. `app.py`: Flask routes/backend
3. `database.py`: SQLite tables and queries
4. `algorithms/seat_allocation.py`: interval overlap and seat selection
5. `algorithms/tatkal_queue.py`: FIFO helper
6. `analytics/analysis.py`: CSV export and Pandas summary

## Prototype limitations
This starter demonstrates the main flow, not a production reservation platform. It has no login/security hardening, payment gateway, real train timetable, official Tatkal rules, real PNR, SMS/email, or production-grade transaction locking. Do not use it for real travel.
