# Credit Profile System for E-Commerce Customers

> **Building a System to Create and Analyze Credit Profiles of E-Commerce Customers**  
> A full-stack web application integrating **Python / Django** with **MongoDB Atlas** using direct **PyMongo** integration and an **Explainable 0–850 Credit-Scoring Engine**.

---

## 🎯 Academic Project Overview

This project simultaneously satisfies the learning objectives and evaluation criteria for two subjects:

1. **Python Web Development using Django**: MVC/MVT architecture, modular Django apps, secure authentication, session management, URL routing, CSRF protection, and responsive frontend UI.
2. **Intelligent NoSQL Databases — MongoDB**: Raw PyMongo driver integration (no ODM), database-level `$jsonSchema` validation rules, multi-stage aggregation pipelines (`$match`, `$group`, `$cond`), compound indexes, and atomic sequence generation.

---

## 🏗️ Architecture & Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Framework** | **Django 6.1** | Web framework, URL routing, middleware, session authentication |
| **Auth Database** | **SQLite3** | Django built-in auth models (`auth_user`, sessions, admin) |
| **Business Database** | **MongoDB Atlas (PyMongo)** | All application data: customers, orders, payments, credit profiles, risk alerts, counters |
| **Database Driver** | **PyMongo 4.18 (Raw)** | Direct driver execution — **no ODM** (`mongoengine`/`djongo` excluded by design) |
| **Styling & UI** | **Tailwind CSS + Custom CSS** | Premium responsive interface, color-coded risk badges, and score progress bars |
| **Environment** | **python-dotenv** | Secure credential management via `.env` |

```
                       ┌───────────────────────────────┐
                       │     Browser / Client (UI)     │
                       └───────────────┬───────────────┘
                                       │ HTTP / CSRF
                                       ▼
                       ┌───────────────────────────────┐
                       │       Django Web Server       │
                       └───────┬───────────────┬───────┘
                               │               │
                 Django Auth & │               │ Raw PyMongo Queries
                 Session Store │               │ (No ODM)
                               ▼               ▼
                        [ SQLite3 DB ]   [ MongoDB Atlas ]
                        • auth_user      • customers ($jsonSchema)
                        • sessions       • orders ($jsonSchema)
                                         • payments ($jsonSchema)
                                         • credit_profiles
                                         • risk_alerts
                                         • counters (atomic $inc)
```

---

## 📊 Explainable Credit-Scoring Engine (0–850 Scale)

The credit-scoring engine (`credit/score_engine.py`) evaluates each customer across **5 weighted dimensions** aggregating to 100%, normalized to an explainable $[0, 850]$ score using deterministic `ROUND_HALF_UP` arithmetic:

$$\text{Final Credit Score} = \text{round\_half\_up}\left( \left[ \sum_{i=1}^{5} W_i \times C_i \right] \times 8.5 \right) \in [0, 850]$$

### Weighted Factor Breakdown

| Component | Weight | Data Source | Key Principles |
|---|---|---|---|
| **Payment History** | **35%** | `payments` collection | Single-bucket invoice evaluation. Rewards on-time settlements (100 pts) and current installments (85 pts). Penalizes delinquency based on overdue days and count. |
| **Outstanding Dues** | **25%** | `payments` collection | Distinguishes current billing utilization ($u_{\text{curr}}$) from overdue debt ($u_{\text{overdue}}$). Zero debt = 100 pts. Overdue debt heavily penalized. |
| **Order Frequency** | **15%** | `orders` collection | Evaluates completed orders only (`status == 'completed'`). Cancelled and returned orders are excluded. 10+ orders = 100 pts. |
| **Order Spend Volume** | **15%** | `orders` collection | Cumulative lifetime spend on completed orders. Benchmark of ₹50,000 earns 100 pts. |
| **Account Age / Tenure** | **10%** | `customers` collection | Account longevity in days from `account_created_at`. Benchmark of 365 days earns 100 pts. |

### Two-Tier Classification Model
To prevent misclassifying new accounts as bad debt, the engine separates **data sufficiency** from **numerical risk**:

1. **Profile Status (`profile_status`):**
   - **`ESTABLISHED`**: $\ge 3$ completed orders AND tenure $\ge 30$ days (or active delinquency override).
   - **`LIMITED_HISTORY`**: 1 to 2 completed orders OR tenure $< 30$ days.
   - **`INSUFFICIENT_DATA`**: 0 completed orders AND 0 payments made AND 0 overdue invoices.
2. **Risk Categories (`risk_category`):**
   - **Excellent**: 750 – 850 (Emerald)
   - **Good**: 650 – 749 (Blue)
   - **Fair**: 550 – 649 (Amber)
   - **Poor**: 400 – 549 (Orange)
   - **Critical**: 0 – 399 (Red)
   - *Under `INSUFFICIENT_DATA`:* Displayed with neutral badge **`Insufficient Data (Provisional)`** and an onboarding advisory notice.

---

## 🗄️ MongoDB Collections & Schema Validation

1. **`customers`** (`$jsonSchema` enforced):
   - Required: `customer_id` (regex: `^CUST-[0-9]{3}$`), `full_name`, `email`, `phone`, `account_created_at`, `is_active`.
   - Embedded subdocument: `address` (`street`, `city`, `state`, `pincode`).
2. **`orders`** (`$jsonSchema` enforced):
   - Required: `order_id` (regex: `^ORD-[0-9]{3}$`), `customer_id`, `order_date`, `items`, `total_amount`, `status`.
   - Items array: minItems 1 with `product_name`, `quantity` (int $\ge 1$), `unit_price`, `subtotal`.
3. **`payments`** (`$jsonSchema` enforced):
   - Required: `payment_id` (regex: `^PAY-[0-9]{3}$`), `order_id`, `customer_id`, `amount_due`, `amount_paid`, `status`, `is_overdue`.
   - Payment modes: `COD`, `UPI`, `Card`, `EMI`, `Wallet`.
4. **`credit_profiles`**:
   - Unique index on `customer_id`. Stores overall score, 5 sub-scores, weights, positive/negative factor explanations, and calculation timestamp.
5. **`risk_alerts`**:
   - Stores automated delinquency detections (`OVERDUE_PAYMENT`, `HIGH_OUTSTANDING`, `CRITICAL_SCORE`) with resolution tracking and de-duplication.
6. **`counters`**:
   - Stores atomic sequence counters (`customer_seq`, `order_seq`, `payment_seq`) incremented via `find_one_and_update` with `$inc`.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10+
- A free [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) cluster (or local MongoDB 6.0+)
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/Prabhat1522/Credit-Profile-Django-Project.git
cd Credit-Profile-Django-Project

# Create and activate a virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the template environment file:
```bash
# Windows:
copy .env.example .env
# Linux/macOS:
cp .env.example .env
```
Open `.env` and fill in your MongoDB Atlas connection string:
```ini
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/credit_profile?retryWrites=true&w=majority
MONGODB_DB_NAME=credit_profile
DJANGO_SECRET_KEY=your-random-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Initialize Database & Collections
```bash
# Apply Django SQLite migrations (for authentication)
python manage.py migrate

# Create MongoDB collections, indexes, and $jsonSchema validators
python core/setup_collections.py

# Seed the 15-customer demonstration dataset (19 orders, 17 payments, atomic counters)
python seed_data.py
```

### 5. Create Superuser & Run the Server
```bash
# Create admin account
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🧪 Automated Test Suite

Run the comprehensive test suite (25 automated unit & integration tests):
```bash
python manage.py test tests
```
Tests cover:
- Overdue derivation and customer financial aggregations (`tests/test_finance.py`).
- Decimal `ROUND_HALF_UP` exact boundary tests (`tests/test_credit_engine.py`).
- Canonical invoice bucket evaluation and contradictory field reconciliation.
- The 5 core test scenarios + delinquency edge cases.
- Exclusion of cancelled/returned orders from spending totals.
- HTTP view integration for profiles, breakdowns, and risk alerts.

---

## 💡 Academic Viva Demonstration Cheatsheet

1. **Why raw PyMongo instead of Django ORM or an ODM like MongoEngine?**  
   *Using raw PyMongo demonstrates true NoSQL database concepts: writing native MongoDB queries, utilizing atomic document updates (`find_one_and_update`), constructing multi-stage aggregation pipelines (`$match`, `$group`, `$cond`), and managing database-level `$jsonSchema` validators directly.*

2. **How are race conditions prevented during ID generation?**  
   *Instead of fetching the max ID in Python, we use MongoDB's atomic `find_one_and_update` with the `$inc` operator on a dedicated `counters` collection with `ReturnDocument.AFTER`. Even under concurrent web requests, MongoDB guarantees unique sequential IDs (`CUST-NNN`, `ORD-NNN`, `PAY-NNN`).*

3. **How does the system distinguish new customers from chronic defaulters?**  
   *We implement a two-tier model separating `profile_status` from `risk_category`. A brand-new customer with 0 completed orders receives an `Insufficient Data` provisional baseline score, whereas a `Critical` defaulter rating requires demonstrated unpaid delinquency past the due date.*

---

## 📄 License
This project was developed for academic coursework in **Python Web Development** and **Intelligent NoSQL Databases**.
