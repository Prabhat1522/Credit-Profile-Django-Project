# Demonstration Guide & Viva Preparation Cheatsheet
## Credit Profile System for E-Commerce Customers (CreditIQ)

**Prepared for**: College viva examination & live demonstration  
**Tech Stack**: Django 6.1 (Python 3.10+), MongoDB Atlas (PyMongo 4.18), SQLite3, Chart.js 4.4, Tailwind CSS  

---

## 1. Five-to-Seven Minute Live Demonstration Sequence

Follow this step-by-step walkthrough during your live demonstration:

### Step 1: Authentication & Dashboard Overview (1.5 Minutes)
1. **Navigate to**: `http://127.0.0.1:8000/`
2. **Observe**: Demonstrates redirect to `/accounts/login/` enforcing access control.
3. **Login with**: Admin credentials (`admin` / `admin123`).
4. **Landing on `/dashboard/`**:
   * Point out the **Live Atlas Aggregations** badge.
   * Explain the **4 primary KPI cards**:
     * Total Customers: 15 (14 active, 1 inactive).
     * Completed Revenue: ₹309,354.00 (strictly completed orders; cancelled and returned orders are excluded).
     * Total Outstanding Debt: ₹65,440.00 across 17 customer invoices.
     * Overdue Balance: ₹40,697.00 with 7 active risk alerts.
   * Showcase the **5 Chart.js visualizations**:
     * Line chart: Monthly completed revenue trend.
     * Bar chart: Outstanding vs. overdue debt.
     * Doughnut chart: Customer risk distribution (Excellent, Good, Fair, Poor, Critical, Insufficient Data).
     * Bar chart: Customer profile status (Established, Limited History, Insufficient Data).
     * Bar chart: Active risk alerts grouped by severity.

### Step 2: Date-Range Filtering (1 Minute)
1. In the top filter bar, enter:
   * **From**: `2026-04-01`
   * **To**: `2026-06-30`
   * Click **Apply**.
2. **Explain**:
   * Completed revenue dynamically filters down to **₹118,083.00** across 5 orders.
   * The line chart narrows to display only `Apr 2026`, `May 2026`, and `Jun 2026`.
3. Click **Reset** to restore the full historical timeline.

### Step 3: Customer Profiles & Credit Score Engine (2 Minutes)
1. Click **Credit Profiles** in the sidebar (`/credit/`).
2. Show the two-tier classification:
   * **Scenario A (Established & Excellent)**: Open **CUST-001** (Aarav Sharma).
     * Score: **782 / 850** (Excellent, Established).
     * Show the 5 component progress bars.
     * Highlight positive factor explanations: *"Flawless payment track record with 2 on-time payments."*
   * **Scenario B (New Account Protection)**: Open **CUST-007** (Kabir Mehta).
     * Score: **391 / 850** (Insufficient Data, Unscored Provisional).
     * Explain viva point: *He is not classified as a critical defaulter despite low score; he has zero history.*
   * **Scenario C (Severe Delinquency)**: Open **CUST-011** (Kavita Reddy).
     * Score: **162 / 850** (Critical, Overdue Delinquent).
     * Show the active delinquency alert.

### Step 4: Payments, Orders & Atomic ID Generation (1.5 Minutes)
1. Navigate to **Orders** (`/orders/`).
   * Show human-readable IDs (`ORD-001`, `ORD-002`).
   * Explain how `find_one_and_update` with `$inc` on `counters` prevents race conditions.
2. Navigate to **Payments** (`/payments/`).
   * Show derived payment statuses: `paid`, `partial`, `pending`, `overdue`.
   * Show that a settled invoice is **never** overdue, even if its due date was months ago.
   * Click **Export CSV** to demonstrate downloadable reports.

### Step 5: MongoDB Architecture Showcase (`/mongo-demo/`) (1 Minute)
1. Click **MongoDB Demo** in the sidebar.
2. Show the examiner:
   * Live collection counts directly from MongoDB Atlas.
   * Two live aggregation pipeline outputs (`$group`, `$sum`, `$sort`) alongside their Python code.
   * The atomic counters collection state.
   * Database-level `$jsonSchema` validation rules.

---

## 2. Key Pages and Test Scenarios to Highlight

| Customer ID | Name | Profile Status | Risk Category | Score | Viva Explanation Point |
|---|---|---|---|---|---|
| **CUST-001** | Aarav Sharma | `ESTABLISHED` | **Excellent** | **782** | Established customer with zero delinquent dues, high spend, and 100% on-time settlement. |
| **CUST-004** | Priya Nair | `LIMITED_HISTORY` | **Good** | **689** | Moderate history with on-time payments; healthy installment progression. |
| **CUST-005** | Vikram Patel | `ESTABLISHED` | **Critical** | **388** | Delinquency override: overdue invoice of ₹14,999 overrides normal status to flag risk. |
| **CUST-007** | Kabir Mehta | `INSUFFICIENT_DATA` | **Insufficient Data** | **391** | Zero orders, zero payments. Protected by two-tier model; not treated as a defaulter. |
| **CUST-011** | Kavita Reddy | `ESTABLISHED` | **Critical** | **162** | Chronic delinquency: 2 overdue payments totaling ₹25,698; triggers Critical risk alert. |

---

## 3. Top 25 Project-Specific Viva Questions & Model Answers

### Category A: Architecture & Dual-Database Design

#### Q1: Why did you choose a dual-database architecture with SQLite and MongoDB?
**Answer**: Django's built-in authentication and session framework (`django.contrib.auth`, `django.contrib.sessions`) relies on relational schema conventions with foreign keys and migrations. Rather than forcing MongoDB through an unstable ORM compatibility layer, we isolate Django authentication in SQLite while housing all business domain entities (customers, orders, payments, credit profiles, risk alerts, and sequence counters) in MongoDB Atlas using PyMongo.

#### Q2: Why did you use raw PyMongo instead of an Object-Document Mapper (ODM) like MongoEngine or Djongo?
**Answer**: Using raw PyMongo allows us to execute native NoSQL database operations directly. ODMs often abstract away MongoDB features, hide aggregation pipelines, and add latency. PyMongo enables us to write multi-stage aggregation pipelines (`$group`, `$cond`, `$dateToString`), enforce `$jsonSchema` validators at the database engine level, and execute atomic operations (`find_one_and_update`) directly.

#### Q3: How is the MongoDB connection managed in Django? Is a new connection opened on every HTTP request?
**Answer**: No. In `core/db_client.py`, we implement a singleton pattern wrapping `pymongo.MongoClient`. PyMongo maintains an internal connection pool across thread workers. A single client instance is reused throughout the application lifecycle, avoiding connection handshake overhead.

---

### Category B: MongoDB Schema, Indexing & Validation

#### Q4: MongoDB is often called "schemaless." How do you guarantee data integrity in your project?
**Answer**: While MongoDB is schema-flexible, we enforce database-level validation using `$jsonSchema` through the `collMod` command in `core/setup_collections.py`. MongoDB Atlas rejects any insert or update that violates data types, minimum lengths, or regular expressions (e.g. `^CUST-[0-9]{3,}$`), regardless of whether the write originates from Python or another client.

#### Q5: What indexes did you create and why are they necessary?
**Answer**:
1. **Unique Indexes**: On `customer_id` and `email` in `customers`, `order_id` in `orders`, `payment_id` in `payments`, and `customer_id` in `credit_profiles`. These enforce uniqueness and prevent duplicate records.
2. **Single-field Lookups**: On `is_active`, `account_created_at`, `status`, and `due_date` to accelerate filtered search and sorting queries.
3. **Foreign-key-like Lookups**: On `customer_id` in `orders` and `payments` to ensure $O(\log N)$ joins and summaries.

#### Q6: How does your ID generation strategy work under concurrent requests?
**Answer**: We use an atomic sequence counter on a dedicated `counters` collection. Instead of querying the highest ID in Python (which creates race conditions), we execute `find_one_and_update({"_id": "customer_seq"}, {"$inc": {"seq": 1}}, return_document=ReturnDocument.AFTER)`. MongoDB guarantees that `$inc` is atomic, so two concurrent web requests will never receive the same sequential ID.

---

### Category C: Financial Calculations & Aggregations

#### Q7: How do you prevent double-counting order revenue and payment balances?
**Answer**:
* **Order Revenue**: The aggregation pipeline applies `{"$match": {"status": "completed"}}`. Cancelled and returned orders are excluded.
* **Outstanding Debt**: Each payment invoice calculates $\max(0.0, \text{amount\_due} - \text{amount\_paid})$. Order amounts and invoice dues are kept separate so they are not summed together.

#### Q8: How is the "overdue" state determined for an invoice?
**Answer**: Overdue status is strictly **derived** rather than manually set. An invoice is overdue if and only if $\text{outstanding balance} > 0$ AND $\text{now} > \text{due\_date}$. If $\text{outstanding} \le 0$, the invoice is 100% settled and can never be overdue, even if its due date was in the past.

#### Q9: Can you explain the monthly revenue aggregation pipeline used for the Chart.js line chart?
**Answer**:
```python
[
    {"$match": {"status": "completed"}},
    {
        "$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$order_date"}},
            "revenue": {"$sum": "$total_amount"},
            "order_count": {"$sum": 1}
        }
    },
    {"$sort": {"_id": 1}}
]
```
`$dateToString` truncates the ISO order timestamp into a `YYYY-MM` month key. `$group` sums the total amount and counts orders per month, and `$sort` orders the buckets chronologically.

---

### Category D: Credit-Scoring Engine

#### Q10: What are the 5 weighted components of your credit-scoring formula?
**Answer**:
1. **Payment History (35%)**: Evaluates on-time payments, installments, and delinquency step-deductions.
2. **Outstanding Dues (25%)**: Evaluates current billing utilization vs. overdue debt.
3. **Order Frequency (15%)**: Evaluates completed order volume (capped at 10 orders).
4. **Order Spend Volume (15%)**: Cumulative lifetime spend (benchmark ₹50,000).
5. **Account Age / Tenure (10%)**: Account longevity in days (benchmark 365 days).

#### Q11: Why is your score on a 0–850 scale rather than the standard 300–900 or 300–850 scale?
**Answer**: A 0–850 scale provides an intuitive ratio where 0 represents absolute failure or maximum delinquency, and 850 represents credit excellence. Component scores are normalized to 0–100, multiplied by their weights, and scaled by $8.5$ ($100 \times 8.5 = 850$).

#### Q12: Why did you use `ROUND_HALF_UP` from Python's `decimal` module instead of the built-in `round()`?
**Answer**: Python's built-in `round()` uses bankers' rounding (round-to-even), meaning `round(416.5)` yields `416` while `round(417.5)` yields `418`. In financial systems, boundary rounding must be deterministic. `Decimal(val).quantize(Decimal("1"), rounding=ROUND_HALF_UP)` guarantees that `.5` always rounds up to the next integer.

#### Q13: How does your system solve the "New Customer Cold Start" problem?
**Answer**: We decouple data sufficiency from credit risk into two separate fields:
* `profile_status`: `ESTABLISHED`, `LIMITED_HISTORY`, `INSUFFICIENT_DATA`.
* `risk_category`: `Excellent`, `Good`, `Fair`, `Poor`, `Critical`.
A new customer with zero transactions receives `INSUFFICIENT_DATA` with a provisional rating. They are not assigned `Critical` risk because they have no history of delinquency.

#### Q14: What happens if a customer with zero completed orders has an unpaid, overdue invoice?
**Answer**: Delinquency takes priority. In `credit/score_engine.py`, the delinquency override rule detects $(\text{overdue count} > 0 \lor \text{overdue balance} > 0)$ and prevents the customer from receiving `INSUFFICIENT_DATA`, ensuring demonstrated delinquency is never masked.

---

### Category E: Risk Alerts & Security

#### Q15: How do you prevent duplicate risk alerts from accumulating in MongoDB?
**Answer**: In `credit/services.py`, `_sync_risk_alerts` checks for existing unresolved alerts matching `(customer_id, alert_type, resolved=False)`. If found, it updates the evaluation timestamp and reason without inserting a new document. When a customer pays off their debt, the engine auto-resolves the alert with `resolved: True`.

#### Q16: How is Chart.js data passed securely from Django to the browser?
**Answer**: We use Django's built-in `json_script` template tag (`{{ charts_payload|json_script:"dashboard-charts-data" }}`). This escapes HTML entities and renders data inside a `<script type="application/json">` tag. The client-side JavaScript reads it via `JSON.parse(document.getElementById(...).textContent)`. This prevents Cross-Site Scripting (XSS) and syntax errors from raw template interpolation.

#### Q17: How is CSRF protection maintained across the application?
**Answer**: Django's `CsrfViewMiddleware` is enabled. All HTML `<form>` elements sending `POST` requests include `{% csrf_token %}`. State-changing views (e.g. `credit_recalculate`, `risk_alert_resolve`) are decorated with `@require_POST` and `@login_required`.

#### Q18: What are the main limitations of your project's credit score?
**Answer**:
1. It is a merchant-specific behavioral score based on e-commerce transaction data, not an official credit bureau score (like CIBIL or FICO).
2. It does not ingest external bank statements, tax returns, or external credit lines.
3. Component weights are statically defined rather than trained through a supervised default prediction machine learning model.

---

### Category F: Viva Quick-Fire Definitions

* **NoSQL**: Non-relational database architecture offering horizontal scaling, flexible document schemas (BSON/JSON), and high-throughput operations.
* **PyMongo**: The official Python distribution library for communicating directly with MongoDB.
* **$jsonSchema**: An official standard implementation in MongoDB to enforce schema validation rules on document inserts and updates.
* **BSON**: Binary JSON format used internally by MongoDB to store documents with support for additional data types (Date, ObjectId, Decimal128).
* **Idempotency**: An operation that can be applied multiple times without changing the result beyond the initial application (e.g., our `setup_collections.py` and profile upserts).
* **ROUND_HALF_UP**: A rounding mode where half-way values (e.g. 0.5) always round to the next higher integer value.
* **Aggregation Pipeline**: A MongoDB framework for data processing where documents pass through a sequence of stages (e.g. `$match`, `$group`, `$sort`) to transform and compute aggregated results.
