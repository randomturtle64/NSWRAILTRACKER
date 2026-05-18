# NSW Rail Tracker — Setup Guide

## What you need
- Python 3.9 or newer (python.org)
- VS Code (code.visualstudio.com)
- A TfNSW API key (opendata.transport.nsw.gov.au)

---

## Step 1 — Put your API key in

Open `.env` and replace the placeholder:

```
TFNSW_API_KEY=paste_your_key_here
```

---

## Step 2 — Open in VS Code

File → Open Folder → select the `nsw-tracker` folder

---

## Step 3 — Install Python packages

Open the terminal in VS Code (Ctrl + backtick) and run:

```
pip install -r requirements.txt
```

If that fails try:
```
pip3 install -r requirements.txt
```

---

## Step 4 — Load the timetable database (first time only)

In the terminal:

```
python load_gtfs.py
```

This downloads Sydney Trains + Metro timetables (~10-20 MB).
Takes 1-2 minutes. Only need to do this once per day.

---

## Step 5 — Start the server

```
python server.py
```

You'll see:
```
[poll] 350 trains live
 * Running on http://127.0.0.1:5000
```

---

## Step 6 — Open the app

Open `index.html` in your browser.

Or right-click index.html in VS Code → "Open with Live Server"
(install the Live Server extension if you don't have it)

---

## Three tabs

**Live Map** — All trains on a map. Click any train for full detail including:
- Set number / target plate
- Run number  
- Speed, delay, next stop
- Full stopping pattern

**WebTLS** — Schematic view showing which track segments are occupied.
Currently shows the T4 Illawarra line (Central → Carlton) and T2.
Run numbers appear above each occupied segment.
(Note: GPS approximation, not real track circuit data)

**Timetable** — Full day's services with set numbers where trains are live.
Filter by line, search by set number, destination, or run number.
Click any live service to jump to it on the map.

---

## Searching

- By set number: type `A24` or `H13` or `S17`
- By run number: type `172`
- By line: type `T4` or `T2`
- By destination: type `Cronulla`

---

## Troubleshooting

**"Server offline" message:**  
Make sure `python server.py` is running in the terminal.

**No trains showing:**  
Check your API key in `.env` is correct and has no spaces.

**Timetable shows nothing:**  
Run `python load_gtfs.py` first to build the database.

**Port already in use:**  
Change `port=5000` to `port=5001` in server.py and update
`const API = 'http://localhost:5001/api'` in index.html

---

## Refreshing timetable data

Run `python load_gtfs.py` each morning to get the latest timetable.
Or add it to Task Scheduler (Windows) / cron (Mac/Linux) to run at 3am.
