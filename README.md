# AETHRA – AI Gold Assessment Platform

## How To Run The Project

### Step 1 — Clone Repository

```bash
git clone https://github.com/srushtikakad187-ui/Aethra-Project.git
```

---

### Step 2 — Open Project

Open the project folder in VS Code.

---

### Step 3 — Install Backend Dependencies

Open terminal inside the `Backend` folder and run:

```bash
pip install fastapi uvicorn python-multipart opencv-python numpy pillow
```

---

### Step 4 — Start Backend Server

Inside the `Backend` folder run:

```bash
python -m uvicorn backend:app --reload
```

Backend starts on:

```bash
http://127.0.0.1:8000
```

---

### Step 5 — Start Frontend

Open the `aethra_main` folder in VS Code.

Right click on:

```bash
login.html
```

Click:

```bash
Open with Live Server
```

---

# Application Flow

```text
Login Page
   ↓
Upload Jewelry Image
   ↓
AI Processing
   ↓
Assessment Dashboard
   ↓
Download Audit Report
```
