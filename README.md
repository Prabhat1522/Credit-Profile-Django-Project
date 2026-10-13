# Credit Profile System for E-Commerce Customers (CreditIQ)

> **Building an Explainable Credit Profile and Analytics System for E-Commerce Customers**
> A full-stack web application integrating **Python / Django** with **MongoDB Atlas** using direct **PyMongo** integration (no ODM), an **Explainable 0–850 Credit-Scoring Engine**, real-time **Chart.js Visualizations**, and **Database-Level `$jsonSchema` Validation**.

---

## 🎯 Project Overview & Problem Statement

In modern e-commerce, offering deferred payment arrangements such as "Buy Now, Pay Later" (BNPL), pay-on-delivery credit, and micro-installments requires rapid, reliable credit risk assessment. Traditional banking credit bureaus (e.g. CIBIL, Experian) primarily index formal banking debts, often excluding students, new-to-credit shoppers, and gig workers who nevertheless demonstrate responsible purchasing and repayment habits on e-commerce platforms.

**CreditIQ** addresses this gap by analyzing real customer e-commerce transactions:
1. Translating order frequency, spend volume, on-time repayments, and account tenure into an **explainable 0–850 credit score**.
2. Solving the **new customer cold-start problem** through a two-tier model that prevents brand-new buyers from being flagged as chronic defaulters.
3. Leveraging a **dual-database design**: SQLite powers Django's authentication tables, while **MongoDB Atlas** stores all application business domain entities via direct **PyMongo** execution.
4. Providing real-time **Chart.js** executive dashboards, date-filtered revenue analytics, atomic sequence counters, automated risk surveillance, and downloadable CSV audit reports.

---

## 🏗️ Technology Stack

| Component | Technology | Rationale & Purpose |
|---|---|---|
| **Web Framework** | **Django 6.1** | MVT pattern, secure session authentication, URL routing, middleware, flash messaging |
| **Auth Database** | **SQLite3** | Houses Django internal tables (`auth_user`, `django_session`, `django_admin_log`) |
| **Business Database** | **MongoDB Atlas** | Stores customers, orders, payments, credit profiles, risk alerts, and atomic counters |
| **Database Driver** | **PyMongo 4.18 (Raw)** | Direct native driver execution — **no ODM** (`mongoengine`/`djongo` excluded by design) |
| **Charts & Analytics** | **Chart.js 4.4** | Client-side reactive rendering: Doughnut, Line, and Bar charts via secure `json_script` |
| **UI Styling** | **Tailwind CSS + Custom CSS** | Responsive dashboard, color-coded badges, and score progress bars |
| **Environment** | **python-dotenv** | Secrets and database URIs loaded safely via `.env` (excluded from Git) |

---

## 📂 Project Folder Structure

```text
Credit-Profile-Django-Project/
├── .env.example                 # Template for environment configuration
├── .gitignore                    # Excludes .env, sqlite, pycache, media, logs
├── README.md                     # Main documentation & setup guide
├── requirements.txt              # Pinned Python package dependencies
├── manage.py                     # Django administrative management script
├── seed_data.py                  # Seed script: 15 customers, 19 orders, 17 payments
│
├── accounts/                     # User authentication & session views
│   ├── views.py                  # Login / logout controller views
│   └── urls.py                   # /accounts/login/ and /accounts/logout/
│
├── core/                         # Shared utilities, database client & validation
│   ├── db_client.py              # PyMongo Atlas singleton connection client
│   ├── validators.py             # $jsonSchema validation rules for collections
│   ├── finance.py                # Financial calculation helpers & atomic counters
│   └── setup_collections.py      # Idempotent collection, index & validator setup
│
├── credit/                       # Credit scoring engine & risk alert management
│   ├── score_engine.py           # Pure 0–850 credit scoring engine (ROUND_HALF_UP)
│   ├── services.py               # Profile upserts, search, filtering & alert syncing
│   ├── views.py                  # Profile list, customer detail, and alert views
│   ├── urls.py                   # /credit/ routing
│   └── templates/credit/         # List, detail, and risk alert templates
│
├── customers/                    # Customer profile management
│   ├── services.py               # Customer queries, mutations & dropdown lists
│   ├── views.py                  # Customer CRUD, detail view & CSV export
│   ├── urls.py                   # /customers/ routing
│   └── templates/customers/      # Customer forms, detail, and list templates
│
├── orders/                       # Purchase order management
│   ├── services.py               # Order creation, line items, and status transitions
│   ├── views.py                  # Order CRUD, detail view & CSV export
│   ├── urls.py                   # /orders/ routing
│   └── templates/orders/         # Order forms and list templates
│
├── payments/                     # Invoice & installment payments
│   ├── services.py               # Payment records, partial transactions & statuses
│   ├── views.py                  # Payment list, record payment & CSV export
│   ├── urls.py                   # /payments/ routing
│   └── templates/payments/       # Payment records and transaction forms
│
├── dashboard/                    # Executive analytics & charts
│   ├── services.py               # PyMongo aggregations, date filtering & chart payloads
│   ├── views.py                  # Analytics view with @login_required & db_status
│   └── urls.py                   # /dashboard/ routing
│
├── mongo_demo/                   # Interactive MongoDB viva showcase
│   ├── views.py                  # Live aggregations, collection counts & schema display
│   └── urls.py                   # /mongo-demo/ routing
│
├── templates/                    # Shared master templates
│   ├── base.html                 # Master layout (sidebar, topbar, navigation)
│   ├── base_auth.html            # Standalone layout for login
│   ├── accounts/login.html       # Admin login page
│   ├── dashboard/index.html      # Executive analytics dashboard with Chart.js
│   └── mongo_demo/index.html     # Viva demonstration and NoSQL showcase page
│
├── docs/                         # Submission documentation
│   ├── PROJECT_REPORT.md         # Formal academic report (12 sections)
│   └── DEMO_AND_VIVA.md          # 5-7 minute demonstration sequence & 25 viva Q&As
│
└── tests/                        # Comprehensive automated test suite (43 tests)
    ├── test_credit_engine.py     # 16 unit tests for score formulas & rounding
    ├── test_finance.py           # 9 unit tests for overdue & status rules
    ├── test_dashboard.py         # 10 tests for aggregations, views & date filters
    └── test_integration.py       # 8 integration tests for end-to-end workflows
```

---

## 🗄️ MongoDB Collections & Schema Design

All business data resides in **MongoDB Atlas** across six dedicated collections:

```
+--------------------------------------------------------------------------------+
|                             MongoDB Atlas Collections                          |
+--------------------------------------------------------------------------------+
| 1. customers        : Customer master profiles ($jsonSchema validated)          |
| 2. orders           : Multi-item customer purchases ($jsonSchema validated)    |
| 3. payments         : Invoices, dues, and repayment records ($jsonSchema)      |
| 4. credit_profiles  : Generated 0-850 credit scores, factors & component bars |
| 5. risk_alerts      : Automated delinquency surveillance (Critical/High)       |
| 6. counters         : Atomic sequence counters for human-readable IDs          |
+--------------------------------------------------------------------------------+
```

### 1. Database-Level Schema Validation (`$jsonSchema`)
Enforced at the Atlas engine level using `collMod`:
* **`customers`**: Requires `customer_id` (`^CUST-[0-9]{3,}$`), `full_name`, `email` (RFC-5322 regex), `is_active`, `account_created_at`.
* **`orders`**: Requires `order_id` (`^ORD-[0-9]{3,}$`), `customer_id`, `order_date`, `status`, and `items` array with at least 1 item containing positive unit prices and quantities.
* **`payments`**: Requires `payment_id` (`^PAY-[0-9]{3,}$`), `order_id`, `customer_id`, `amount_due` $\ge 0$, `amount_paid` $\ge 0$, `is_overdue`, and enum status (`paid`, `partial`, `pending`, `overdue`).

### 2. Indexes and Uniqueness Guarantees
* **Unique B-Tree Indexes**: `customers.customer_id`, `customers.email`, `orders.order_id`, `payments.payment_id`, `credit_profiles.customer_id`.
* **Compound & Filter Indexes**: `payments.is_overdue`, `payments.due_date`, `orders.status`, `orders.order_date`, `risk_alerts.resolved`.

### 3. Concurrency-Safe Atomic Sequences
To avoid primary key race conditions under concurrent requests, IDs are generated via MongoDB's atomic `find_one_and_update` on the `counters` collection:
```python
def generate_customer_id() -> str:
    res = db.counters.find_one_and_update(
        {"_id": "customer_seq"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return f"CUST-{res['seq']:03d}"
```

---

## 📊 Explainable Credit-Scoring Engine (0–850 Scale)

The credit engine (`credit/score_engine.py`) maps customer behavior across **five weighted components** aggregating to 100%:

$$\text{Composite Norm} = (0.35 \times C_{\text{pay}}) + (0.25 \times C_{\text{dues}}) + (0.15 \times C_{\text{freq}}) + (0.15 \times C_{\text{val}}) + (0.10 \times C_{\text{age}})$$

$$\text{Final Credit Score} = \text{round\_half\_up}(\text{Composite Norm} \times 8.5) \in [0, 850]$$

| Factor | Weight | Evaluation Criteria |
|---|---|---|
| **Payment History ($C_{\text{pay}}$)** | **35%** | Evaluates on-time payments (100 pts) and current installments (85 pts). Delinquencies apply progressive deductions based on days late ($15\text{–}30\text{ days} \implies -30\text{ pts}$, $>30\text{ days} \implies -50\text{ pts}$). |
| **Outstanding Dues ($C_{\text{dues}}$)** | **25%** | Distinguishes current unbilled dues from overdue balance. Zero debt = 100 pts. Overdue debt heavily penalized. |
| **Order Frequency ($C_{\text{freq}}$)** | **15%** | Evaluates completed orders only (`status == 'completed'`). Base 20 pts + 8 pts per order, capped at 100 pts ($\ge 10$ orders). |
| **Order Spend Volume ($C_{\text{val}}$)** | **15%** | Lifetime completed order spend. Base 20 pts + linear progression to benchmark ₹50,000 (100 pts). |
| **Account Age ($C_{\text{age}}$)** | **10%** | Longevity in days since registration. Scales linearly to benchmark 365 days (100 pts). |

### Two-Tier Classification Model
To resolve the cold-start problem, data sufficiency is decoupled from risk categorization:
1. **Profile Status (`profile_status`)**:
   * `ESTABLISHED`: $\ge 3$ completed orders AND tenure $\ge 30$ days (or active delinquency override).
   * `LIMITED_HISTORY`: 1 to 2 completed orders OR tenure $< 30$ days.
   * `INSUFFICIENT_DATA`: 0 completed orders AND 0 payments made AND 0 overdue invoices.
2. **Risk Categories (`risk_category`)**:
   * **Excellent**: 750 – 850 (Emerald)
   * **Good**: 650 – 749 (Blue)
   * **Fair**: 550 – 649 (Amber)
   * **Poor**: 400 – 549 (Orange)
   * **Critical**: 0 – 399 (Red)
   * **Insufficient Data**: Unscored baseline for new accounts.

---

## 📈 Chart.js Visualizations & Dashboard Analytics

The executive dashboard (`/dashboard/`) computes real-time portfolio metrics via native PyMongo aggregation pipelines:
1. **Monthly Completed Revenue Trend (Line Chart)**: Smooth tension curve displaying historical revenue grouped by `YYYY-MM`.
2. **Outstanding vs. Overdue Debt (Bar Chart)**: Compares total open customer credit (₹65,440.00) against overdue delinquent balance (₹40,697.00).
3. **Customers by Risk Category (Doughnut Chart)**: Visualizes score band distribution across all accounts with percentage tooltips.
4. **Customer Profile Status (Bar Chart)**: Shows maturity partitions (`Established`, `Limited History`, `Insufficient Data`).
5. **Active Alerts by Severity (Bar Chart)**: Groups active risk alerts by severity level (`Critical`, `High`, `Medium`, `Low`).
6. **Date-Range Filtering**: Server-side validated date filtering (`start_date`, `end_date`) that dynamically updates the completed revenue card and line chart.

---

## 🔒 Security & Authentication

* **Access Control**: All operational pages protected by Django's `@login_required` decorator. Unauthenticated requests redirect to `/accounts/login/`.
* **State Protection**: Modifying operations (`POST`) are protected against Cross-Site Request Forgery (`{% csrf_token %}`) and decorated with `@require_POST`.
* **Credential Isolation**: `.env` is excluded in `.gitignore`. Secrets, database connection strings, and secret keys are loaded exclusively from environment variables.
* **XSS Defense**: Chart data is passed via Django's secure `{{ charts_payload|json_script:"dashboard-charts-data" }}` tag, preventing unsafe JavaScript interpolation.

---

## 🚀 Environment Setup & Local Execution

### 1. Prerequisites
* Python 3.10+
* MongoDB Atlas Cluster (or local MongoDB 6.0+)
* Git

### 2. Installation
```bash
# Clone repository
git clone https://github.com/Prabhat1522/Credit-Profile-Django-Project.git
cd Credit-Profile-Django-Project

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
# Copy template
copy .env.example .env
```
Edit `.env` with your settings:
```ini
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/credit_profile?retryWrites=true&w=majority
MONGODB_DB_NAME=credit_profile
DJANGO_SECRET_KEY=your-secure-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Database Setup & Seeding
```bash
# 1. Apply SQLite migrations for Django Auth
python manage.py migrate

# 2. Setup MongoDB collections, indexes, and $jsonSchema validators
python core/setup_collections.py

# 3. Seed demonstration dataset (15 customers, 19 orders, 17 payments)
python seed_data.py

# 4. Create admin superuser
python manage.py createsuperuser
```

### 5. Run Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Open `http://127.0.0.1:8000/` in your browser.

---

## 🧪 Automated Test Suite (43 Tests)

Run the test suite:
```bash
python manage.py test tests
```

### Execution Results
```text
Creating test database for alias 'default'...
...........................................
----------------------------------------------------------------------
Ran 43 tests in 16.836s

OK
Destroying test database for alias 'default'...
Found 43 test(s).
System check identified no issues (0 silenced).
[DB] [OK] Connected to MongoDB Atlas successfully.
```

* **`tests/test_finance.py`** (9 tests): Overdue rules, status derivations, financial summaries.
* **`tests/test_credit_engine.py`** (16 tests): Boundary rounding (`ROUND_HALF_UP`), 5 worked scenarios, delinquency overrides.
* **`tests/test_dashboard.py`** (10 tests): Analytics aggregations, date filtering, empty dataset fallbacks, Chart.js payload structures.
* **`tests/test_integration.py`** (8 tests): End-to-end customer/order creation, partial payments, profile recalculation idempotency, alert resolution, CSRF/login rejection, CSV exports, MongoDB showcase view.

---

## 📑 College Submission & Viva Reference Links

* **Detailed Academic Report**: [`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md) (12 sections: Abstract, System Architecture, Database Design, Credit Methodology, Test Results, Limitations)
* **Viva Cheatsheet & Demo Script**: [`docs/DEMO_AND_VIVA.md`](docs/DEMO_AND_VIVA.md) (5-7 minute demonstration sequence + 25 viva questions & answers)
* **Interactive MongoDB Demo**: Visit `/mongo-demo/` on the running application to demonstrate live aggregations, indexes, and schema validation.
