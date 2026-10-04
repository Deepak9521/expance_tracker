# Private 3-Person Shared Expense Tracker

A streamlined, robust web application built specifically for three fixed housemates/flatmates who live together and frequently purchase shared items. Any one of the three can record an expense, and every expense is automatically divided equally among all three members.

---

## 🎯 Purpose & Philosophy

This application is **strictly** for three fixed people. It is not an open, multi-tenant expense platform.
- **No group invitations or public user registrations.**
- **No integrated payment gateways, UPI handlers, or banking links.** (All settlements are resolved personally at the end of the week via personal UPI or cash).
- **Exact equal 3-way split:** Every expense is split into three equal parts ($1/3$ each).
- **No floating-point inaccuracy:** Uses Python's `Decimal` arithmetic for financial integrity and exact rounding.
- **Strict weekly locks:** Closing a week locks historical records from unauthorized modification.
- **Automated settlement engine:** Computes the minimal number of transfers (at most 2 transactions for 3 people).

---

## 🚀 Tech Stack

- **Frontend & App Framework:** [Streamlit](https://streamlit.io/)
- **Programming Language:** Python 3.10+
- **Database:** PostgreSQL with [SQLAlchemy 2.0](https://www.sqlalchemy.org/) ORM
- **Database Driver:** [psycopg 3](https://www.psycopg.org/) (`psycopg[binary]`)
- **Authentication & Security:** [bcrypt](https://pypi.org/project/bcrypt/) password hashing & session management
- **Data Visualizations:** [Plotly](https://plotly.com/python/)
- **Configuration Management:** [python-dotenv](https://pypi.org/project/python-dotenv/)
- **Testing:** [pytest](https://docs.pytest.org/)
- **Cloud Deployment:** [Render](https://render.com/)

---

## 📁 Project Structure

```
tracker/
├── app.py                     # Main Streamlit application and page router
├── requirements.txt           # Project dependencies
├── render.yaml                # Render Infrastructure-as-Code blueprint
├── .env                       # Local environment variables (git-ignored)
├── .env.example               # Template for environment variables
├── .gitignore                 # Standard Python/Git ignore rules
├── README.md                  # Comprehensive project documentation
│
├── database/                  # Database connectivity and ORM models
│   ├── __init__.py
│   ├── connection.py          # SQLAlchemy engine, connection pooling, and session contexts
│   └── models.py              # User, Expense, and WeeklySummary models
│
├── services/                  # Core domain logic (kept independent of UI)
│   ├── __init__.py
│   ├── calculations.py        # Decimal calculation engine and INR currency formatter
│   ├── settlement.py          # Minimum transaction settlement algorithm
│   └── expenses.py            # Expense CRUD, week closure, validation, and retention
│
├── auth/                      # Authentication and session handling
│   ├── __init__.py
│   └── auth.py                # bcrypt hashing, verification, and session state guards
│
├── pages/                     # Streamlit UI page views
│   ├── __init__.py
│   ├── dashboard.py           # Main overview, KPI cards, and daily chart
│   ├── add_expense.py         # Expense entry form with real-time fair share preview
│   ├── expenses.py            # Full history with filters, edit, and delete controls
│   ├── daily.py               # Day-by-day itemization and Plotly breakdown
│   ├── settlement.py          # Weekly settlement instructions & week closure
│   └── weekly_history.py      # Permanent archives of closed weeks & retention management
│
├── scripts/                   # Administrative and CLI maintenance utilities
│   ├── seed_users.py          # Initializes tables and seeds the 3 fixed users
│   └── cleanup_expenses.py    # Safe 60-day data retention cleanup
│
└── tests/                     # Unit test suite
    ├── __init__.py
    ├── test_calculations.py   # Tests for 3-way split, balances, and rounding
    ├── test_settlement.py     # Tests for greedy settlement optimization
    └── test_expenses.py       # Tests for permissions, closed-week locks, and retention
```

---

## 🧮 How Calculations and Settlement Work

### 1. The Expense Rule
Every single expense logged is automatically shared equally ($1/3$ share) by all 3 people:
$$\text{Fair Share} = \frac{\text{Total Spending}}{3}$$
$$\text{User Balance} = \text{Amount Paid by User} - \text{Fair Share}$$

- **Positive Balance ($+$):** The person paid more than their share and **receives** money from the group.
- **Negative Balance ($-$)**: The person paid less than their share and **owes** money to the group.
- **Zero Balance ($0$):** Exactly even / settled.

### 2. Example (Final Acceptance Test Scenario)
During one week:
- **Person 1** pays: ₹900 (groceries) + ₹300 (electricity) = **₹1,200.00**
- **Person 2** pays: ₹600 (food) = **₹600.00**
- **Person 3** pays: ₹300 (transport) = **₹300.00**

**Calculation:**
- Total Weekly Expenses = ₹1,200 + ₹600 + ₹300 = **₹2,100.00**
- Fair Share Per Person = $\frac{₹2,100}{3} =$ **₹700.00 each**

**Net Balances:**
- **Person 1:** Paid ₹1,200.00 − Share ₹700.00 = **+₹500.00** *(Receives ₹500.00)*
- **Person 2:** Paid ₹600.00 − Share ₹700.00 = **-₹100.00** *(Owes ₹100.00)*
- **Person 3:** Paid ₹300.00 − Share ₹700.00 = **-₹400.00** *(Owes ₹400.00)*

**Minimum Settlement Transactions:**
1. **Person 2 → Person 1:** ₹100.00
2. **Person 3 → Person 1:** ₹400.00

Total received by Person 1 = ₹500.00. All balances are fully resolved in exactly **2 transactions**.

---

## 🔒 Week Closure & Immutability Rules

A week is considered closed **only when a user explicitly clicks "Close & Save Week"** on the Settlement page:
1. Calculates final weekly totals and fair shares.
2. Persists a record in `WEEKLY_SUMMARIES`.
3. **Locks modification:** No expenses within that week can be added, updated, or deleted.
4. **Prevents duplicate summaries:** Database unique constraint on `(week_start, week_end)` ensures a week can never be saved twice.
5. Preserves the historical summary for permanent viewing.

---

## 🧹 60-Day Data Retention Policy

To keep individual expense tables lean:
- Individual expense entries older than ~60 days are eligible for cleanup.
- **Safety guarantee:** The cleanup function checks whether weekly summaries have been saved for those dates. If any week was not yet closed, it auto-generates the `WeeklySummary` first before deleting individual item records.
- Run via CLI:
  ```bash
  python scripts/cleanup_expenses.py --dry-run
  python scripts/cleanup_expenses.py
  ```
- Or run through the **Weekly History** page in the UI under **Retention Cleanup Controls**.

---

## 💻 Local Setup & Installation

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- PostgreSQL server (local or cloud like Neon/Supabase/Render)

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env   # Windows
# or: cp .env.example .env  # Linux/macOS
```

Edit `.env` with your PostgreSQL database URL and custom names:
```ini
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/tracker_db
SECRET_KEY=super-secret-random-key

PERSON_1_NAME=Deepak
PERSON_1_USERNAME=deepak
PERSON_1_PASSWORD=password123

PERSON_2_NAME=Rahul
PERSON_2_USERNAME=rahul
PERSON_2_PASSWORD=password123

PERSON_3_NAME=Amit
PERSON_3_USERNAME=amit
PERSON_3_PASSWORD=password123
```

### 5. Initialize & Seed Database
Run the seed script to create tables and generate the 3 users with bcrypt-hashed passwords:
```bash
python scripts/seed_users.py
```

To update user passwords from `.env`:
```bash
python scripts/seed_users.py --reset-passwords
```

### 6. Run Unit Tests
Execute the full pytest suite:
```bash
pytest tests/ -v
```

### 7. Run the Application
Launch Streamlit:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` and sign in with any of the three configured accounts.

---

## ☁️ Deployment on Render

### Step 1: Create a PostgreSQL Database on Render
1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **PostgreSQL**.
3. Name it: `expense-tracker-db`.
4. Click **Create Database**.
5. Once created, copy the **Internal Database URL** (if deploying both on Render) or **External Database URL**.

### Step 2: Create a Web Service on Render
1. Click **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Choose **Python** as runtime.
4. Set **Build Command**:
   ```bash
   pip install -r requirements.txt
   ```
5. Set **Start Command**:
   ```bash
   streamlit run app.py --server.port $PORT --server.address 0.0.0.0
   ```

### Step 3: Configure Environment Variables on Render
Add the following environment variables under **Environment**:
- `DATABASE_URL`: Your Render PostgreSQL connection string (psycopg handles `postgres://` or `postgresql://` automatically).
- `SECRET_KEY`: A secure random string.
- `PERSON_1_NAME`: Name of Person 1
- `PERSON_1_USERNAME`: Username for Person 1
- `PERSON_1_PASSWORD`: Password for Person 1
- `PERSON_2_NAME`: Name of Person 2
- `PERSON_2_USERNAME`: Username for Person 2
- `PERSON_2_PASSWORD`: Password for Person 2
- `PERSON_3_NAME`: Name of Person 3
- `PERSON_3_USERNAME`: Username for Person 3
- `PERSON_3_PASSWORD`: Password for Person 3

### Step 4: Initialize the Database on Render
After the first deployment completes:
1. Go to your Web Service dashboard on Render.
2. Open the **Shell** tab.
3. Run:
   ```bash
   python scripts/seed_users.py
   ```
4. Tables will be created and the 3 users seeded.

### Step 5: (Optional) Scheduled 60-Day Cleanup Cron Job
Create a **Cron Job** on Render:
- Command: `python scripts/cleanup_expenses.py`
- Schedule: `0 0 1 * *` (Runs on the 1st of every month)
