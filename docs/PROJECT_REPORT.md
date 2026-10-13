# Project Report: Credit Profile System for E-Commerce Customers

**Course / Subject**: Python Web Development using Django & Intelligent NoSQL Databases (MongoDB)  
**Project Title**: Building a System to Create and Analyze Credit Profiles of E-Commerce Customers  
**Platform**: Python 3.10+, Django 6.1, MongoDB Atlas (PyMongo 4.18), SQLite3 (Django Auth), Chart.js 4.4, Tailwind CSS  
**Evaluation Level**: Capstone / End-Semester Academic Project  

---

## Table of Contents
1. [Abstract](#1-abstract)
2. [Introduction and Problem Statement](#2-introduction-and-problem-statement)
3. [Objectives and Scope](#3-objectives-and-scope)
4. [Existing System vs. Proposed Solution](#4-existing-system-vs-proposed-solution)
5. [System Architecture](#5-system-architecture)
6. [Database Design and Collections](#6-database-design-and-collections)
7. [Implementation Details](#7-implementation-details)
8. [MongoDB CRUD and Aggregation Examples](#8-mongodb-crud-and-aggregation-examples)
9. [Credit-Scoring Methodology (0–850 Scale)](#9-credit-scoring-methodology-0850-scale)
10. [Testing and Verification Results](#10-testing-and-verification-results)
11. [Limitations and Future Scope](#11-limitations-and-future-scope)
12. [Conclusion](#12-conclusion)

---

## 1. Abstract

In modern e-commerce platforms, offering deferred payment models such as "Buy Now, Pay Later" (BNPL), pay-on-delivery credit, and micro-installments requires granular credit assessment. Traditional credit bureaus (e.g., CIBIL, Experian) primarily capture formalized credit histories from banking institutions, effectively ignoring unbanked, student, or new-to-credit shoppers who nonetheless possess demonstrated e-commerce purchasing and repayment track records.

This project designs and implements the **Credit Profile System (CreditIQ)**, an end-to-end web application that synthesizes transactional e-commerce activity into an explainable **0–850 credit score**. The system is built on a **dual-database architecture**: SQLite manages Django's internal authentication models, while **MongoDB Atlas** serves as the primary NoSQL datastore accessed exclusively via the raw **PyMongo** driver (no Object-Document Mapper). The solution incorporates database-level `$jsonSchema` validation, multi-stage aggregation pipelines for real-time analytics, concurrency-safe atomic sequence counters, automated risk-alert monitoring, and responsive Chart.js dashboard visualizations.

---

## 2. Introduction and Problem Statement

### 2.1 Context
E-commerce enterprises process high volumes of polymorphic transactional data. Merchant credit systems must rapidly evaluate buyer creditworthiness to mitigate default risk while expanding credit lines to trustworthy consumers.

### 2.2 Problem Statement
Traditional relational databases enforce rigid schemas that struggle with polymorphic items and evolving billing arrangements. Conversely, naive NoSQL implementations often compromise data integrity by omitting database-level validation, creating duplicate primary keys under concurrent requests, or performing heavy arithmetic in application memory instead of leveraging database aggregation pipelines.

Furthermore, traditional credit scoring models often treat new accounts with zero history identically to chronic defaulters, creating severe onboarding friction and misclassification.

---

## 3. Objectives and Scope

### 3.1 Primary Objectives
1. **Develop an Explainable Credit Engine**: Implement a deterministic mathematical engine mapping five behavioral components to an explainable 0–850 scale with exact `ROUND_HALF_UP` rounding.
2. **Raw NoSQL Database Integration**: Implement direct PyMongo integration without an abstraction layer (ODM) to demonstrate core NoSQL principles: `$jsonSchema` validation, multi-stage aggregations, indexing, and atomic updates.
3. **Dual-Database Architecture**: Isolate Django authentication and session tables in SQLite while housing all business domain data in MongoDB Atlas.
4. **Automated Risk Surveillance**: Implement real-time detection, de-duplication, and automatic healing for payment delinquency and credit risk alerts.
5. **Analytics & Visualization Dashboard**: Aggregate real-time Key Performance Indicators (KPIs) and visualize risk distributions using Chart.js.

### 3.2 Scope
* **In Scope**: Customer profile management, dynamic order creation, installment payment records, invoice derivation, credit score calculation, risk alerts, executive analytics dashboard, CSV data exports, and viva inspection tools.
* **Out of Scope**: Integration with official credit bureaus (CIBIL/Experian), external banking APIs, or automated debt collection recovery systems.

---

## 4. Existing System vs. Proposed Solution

| Dimension | Existing / Traditional Approach | Proposed Solution (CreditIQ) |
|---|---|---|
| **Data Storage** | Monolithic RDBMS or rigid relational tables | Hybrid architecture with MongoDB Atlas for flexible documents |
| **Driver Abstraction** | Heavy ORMs/ODMs (MongoEngine/Djongo) | Raw PyMongo execution preserving native MongoDB queries |
| **New Customer Handling** | Flags low/zero history as default risk | Two-tier classification: separates data sufficiency from risk |
| **Aggregation Method** | Application-level looping in Python | Native MongoDB aggregation pipelines (`$group`, `$cond`, `$dateToString`) |
| **Concurrency & IDs** | Table-locking sequences or random UUIDs | Atomic sequence counters via `find_one_and_update` with `$inc` |
| **Validation Layer** | Application-only validation forms | Dual-layer: Django server-side validation + Atlas `$jsonSchema` |

---

## 5. System Architecture

```
                                  +------------------------------------+
                                  |     Web Client / Browser (UI)      |
                                  |   (Tailwind CSS + Chart.js 4.4)    |
                                  +-----------------+------------------+
                                                    | HTTP / CSRF Token
                                                    v
                                  +------------------------------------+
                                  |       Django Web Application       |
                                  |  - Session / Auth Middleware       |
                                  |  - Role-based Access (@login_req)  |
                                  |  - URL Routing & Controller Views  |
                                  +--------+------------------+--------+
                                           |                  |
                       Django Auth (User)  |                  | PyMongo Driver (Raw)
                       & Sessions          |                  | Connection Pooling
                                           v                  v
                                  +-----------------+  +-------------------------------+
                                  |  SQLite3 Store  |  |      MongoDB Atlas Cluster    |
                                  |  (Django Builtin|  |                               |
                                  |   auth_user,    |  |  * customers ($jsonSchema)    |
                                  |   sessions)     |  |  * orders ($jsonSchema)       |
                                  +-----------------+  |  * payments ($jsonSchema)     |
                                                       |  * credit_profiles            |
                                                       |  * risk_alerts                |
                                                       |  * counters (Atomic $inc)     |
                                                       +-------------------------------+
```

### Module Breakdown
* `credit_profile`: Core Django configuration, middleware, and master URL routing.
* `core`: PyMongo database client (`db_client.py`), `$jsonSchema` definitions (`validators.py`), and finance calculation helpers (`finance.py`).
* `accounts`: Administrator login, session handling, and authentication redirects.
* `customers`: Customer management, search, filtering, and CSV export.
* `orders`: Order creation with dynamic line items and automated invoice creation.
* `payments`: Payment recording, partial transactions, overdue calculation, and status derivation.
* `credit`: Mathematical scoring engine (`score_engine.py`), profile recalculation, and risk alert lifecycle (`services.py`).
* `dashboard`: Real-time aggregation pipelines and executive analytics view (`services.py`, `views.py`).
* `mongo_demo`: Interactive viva demonstration suite showcasing live aggregations, schema validation, and sequence counters.

---

## 6. Database Design and Collections

### 6.1 Collection Schema Definitions

#### 1. `customers` Collection
* **Document Structure**:
  ```json
  {
    "_id": ObjectId("..."),
    "customer_id": "CUST-001",
    "full_name": "Aarav Sharma",
    "email": "aarav.sharma@example.com",
    "phone": "+91 98201 11223",
    "is_active": true,
    "kyc_verified": true,
    "account_created_at": ISODate("2024-01-15T10:00:00Z"),
    "address": {
      "street": "42 Marine Drive",
      "city": "Mumbai",
      "state": "Maharashtra",
      "pincode": "400020"
    },
    "tags": ["VIP", "Tech"]
  }
  ```
* **Indexes**: `customer_id` (Unique), `email` (Unique), `is_active`, `account_created_at`.
* **Validation**: Enforced via `$jsonSchema` on `customer_id` regex `^CUST-[0-9]{3,}$`, email RFC-5322 regex, and mandatory fields.

#### 2. `orders` Collection
* **Document Structure**:
  ```json
  {
    "_id": ObjectId("..."),
    "order_id": "ORD-001",
    "customer_id": "CUST-001",
    "order_date": ISODate("2026-04-16T10:33:48Z"),
    "status": "completed",
    "items": [
      {
        "product_name": "Smart 4K LED TV 55-inch",
        "quantity": 1,
        "unit_price": 42999.0,
        "subtotal": 42999.0
      }
    ],
    "total_amount": 42999.0,
    "notes": "Delivered on schedule"
  }
  ```
* **Indexes**: `order_id` (Unique), `customer_id`, `status`, `order_date`.
* **Validation**: Items array must contain $\ge 1$ item with positive integer quantity.

#### 3. `payments` Collection
* **Document Structure**:
  ```json
  {
    "_id": ObjectId("..."),
    "payment_id": "PAY-001",
    "order_id": "ORD-001",
    "customer_id": "CUST-001",
    "amount_due": 42999.0,
    "amount_paid": 42999.0,
    "status": "paid",
    "is_overdue": false,
    "days_overdue": 0,
    "due_date": ISODate("2026-05-01T10:33:48Z"),
    "payment_date": ISODate("2026-04-21T10:33:48Z"),
    "payment_mode": "Card"
  }
  ```
* **Indexes**: `payment_id` (Unique), `customer_id`, `order_id`, `is_overdue`, `due_date`.
* **Status Enum**: `["paid", "partial", "pending", "overdue"]`.

#### 4. `credit_profiles` Collection
* **Document Structure**:
  ```json
  {
    "_id": ObjectId("..."),
    "customer_id": "CUST-001",
    "score": 782,
    "risk_category": "Excellent",
    "profile_status": "ESTABLISHED",
    "component_scores": {
      "payment_history": 100.0,
      "outstanding_dues": 100.0,
      "order_frequency": 36.0,
      "order_value": 100.0,
      "account_age": 100.0
    },
    "positive_factors": ["Flawless payment track record with 2 on-time payments."],
    "negative_factors": [],
    "calculated_at": ISODate("2026-10-13T11:30:00Z")
  }
  ```
* **Indexes**: `customer_id` (Unique).

#### 5. `risk_alerts` Collection
* **Document Structure**:
  ```json
  {
    "_id": ObjectId("..."),
    "customer_id": "CUST-005",
    "alert_type": "OVERDUE_PAYMENT",
    "severity": "CRITICAL",
    "reason": "Payment delinquency: 1 invoice overdue by 12 days.",
    "credit_score": 388,
    "risk_category": "Critical",
    "resolved": false,
    "created_at": ISODate("2026-10-13T10:00:00Z"),
    "last_evaluated_at": ISODate("2026-10-13T11:00:00Z")
  }
  ```
* **Indexes**: `customer_id`, `resolved`.

#### 6. `counters` Collection
* **Document Structure**:
  ```json
  { "_id": "customer_seq", "seq": 15 }
  { "_id": "order_seq",    "seq": 19 }
  { "_id": "payment_seq",  "seq": 17 }
  ```

---

## 7. Implementation Details

### 7.1 Concurrency-Safe Atomic ID Generation
Random UUIDs are difficult to read and remember during administrative tasks. CreditIQ employs human-readable identifiers (`CUST-001`, `ORD-001`, `PAY-001`) backed by MongoDB's atomic `find_one_and_update`:

```python
def _next_seq(counter_name: str) -> int:
    counters_col = get_collection("counters")
    result = counters_col.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return result["seq"]
```
Because MongoDB guarantees document updates with `$inc` are atomic, race conditions are eliminated under concurrent web traffic.

### 7.2 Derived Financial Status & Overdue Rules
Financial status is derived to maintain consistency between list and detail views:
* $\text{Outstanding Balance} = \max(0.0, \text{amount\_due} - \text{amount\_paid})$.
* If $\text{Outstanding} \le 0.0$, the invoice is fully settled and **never** marked overdue.
* If $\text{Outstanding} > 0.0$, overdue status is evaluated:
  $$\text{is\_overdue} = (\text{now} > \text{due\_date})$$
  $$\text{days\_overdue} = \max(0, (\text{now} - \text{due\_date}).\text{days})$$

---

## 8. MongoDB CRUD and Aggregation Examples

### 8.1 Single-Customer Financial Summary
Aggregates order history, count by status, and total spent in a single query:

```python
pipeline = [
    {"$match": {"customer_id": customer_id}},
    {"$group": {
        "_id": "$customer_id",
        "total_orders":     {"$sum": 1},
        "completed_orders": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
        "cancelled_orders": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
        "returned_orders":  {"$sum": {"$cond": [{"$eq": ["$status", "returned"]},  1, 0]}},
        "total_spent": {
            "$sum": {
                "$cond": [{"$eq": ["$status", "completed"]}, "$total_amount", 0]
            }
        }
    }}
]
```

### 8.2 Monthly Completed-Order Revenue Timeline
Aggregates completed revenue grouped by calendar month for the executive line chart:

```python
pipeline = [
    {"$match": {"status": "completed"}},
    {
        "$group": {
            "_id": {
                "$dateToString": {"format": "%Y-%m", "date": "$order_date"}
            },
            "revenue": {"$sum": "$total_amount"},
            "order_count": {"$sum": 1}
        }
    },
    {"$sort": {"_id": 1}}
]
```

### 8.3 Portfolio-Wide Debt Exposure
Aggregates total outstanding dues across all invoices using MongoDB expression operators:

```python
pipeline = [
    {
        "$group": {
            "_id": None,
            "total_outstanding": {
                "$sum": {
                    "$max": [
                        0.0,
                        {"$subtract": [
                            {"$ifNull": ["$amount_due", 0.0]},
                            {"$ifNull": ["$amount_paid", 0.0]}
                        ]}
                    ]
                }
            }
        }
    }
]
```

---

## 9. Credit-Scoring Methodology (0–850 Scale)

### 9.1 Mathematical Formulation
The credit engine evaluates five weighted components, normalizes each to a $[0, 100]$ score, multiplies by their respective weights, and scales to $[0, 850]$ using deterministic `ROUND_HALF_UP` arithmetic:

$$\text{Composite Norm} = (0.35 \times C_{\text{pay}}) + (0.25 \times C_{\text{dues}}) + (0.15 \times C_{\text{freq}}) + (0.15 \times C_{\text{val}}) + (0.10 \times C_{\text{age}})$$

$$\text{Final Score} = \max\left(0, \min\left(850, \text{round\_half\_up}(\text{Composite Norm} \times 8.5)\right)\right)$$

### 9.2 Factor Weights and Evaluation Criteria

| Factor | Weight | Formulation & Scoring Logic |
|---|---|---|
| **Payment History ($C_{\text{pay}}$)** | **35%** | Evaluates on-time payments, installments, and delinquency. On-time = 100 pts, current installments = 85 pts. Delinquency applies severe step deductions based on overdue days ($15 \le \text{days} \le 30 \implies -30\text{ pts}$, $\text{days} > 30 \implies -50\text{ pts}$). |
| **Outstanding Dues ($C_{\text{dues}}$)** | **25%** | Distinguishes current unbilled dues from overdue balance. Zero debt = 100 pts. Current debt is penalized mildly; overdue debt applies heavy deductions. |
| **Order Frequency ($C_{\text{freq}}$)** | **15%** | Evaluates completed orders only. Base score is 20 pts. Each completed order contributes +8 pts up to a maximum cap of 100 pts ($\ge 10$ orders = 100 pts). |
| **Order Value / Spend ($C_{\text{val}}$)** | **15%** | Cumulative lifetime spend on completed orders. Base score is 20 pts. Scales linearly: $20 + (\frac{\text{total\_spent}}{50,000} \times 80)$, capped at 100 pts. |
| **Account Age ($C_{\text{age}}$)** | **10%** | Account longevity in days since registration. Scales linearly up to 365 days: $\max(10, \min(100, \frac{\text{tenure\_days}}{365} \times 100))$. |

### 9.3 Two-Tier Classification Model
To prevent misclassifying new accounts as bad debt, data sufficiency is decoupled from numerical credit risk:

1. **Profile Status (`profile_status`)**:
   * **`ESTABLISHED`**: Customer has $\ge 3$ completed orders AND account age $\ge 30$ days (or active delinquency).
   * **`LIMITED_HISTORY`**: Customer has 1–2 orders OR account age $< 30$ days.
   * **`INSUFFICIENT_DATA`**: Customer has 0 completed orders, 0 payments, and 0 overdue balance.
2. **Risk Category (`risk_category`)**:
   * **Excellent**: 750 – 850
   * **Good**: 650 – 749
   * **Fair**: 550 – 649
   * **Poor**: 400 – 549
   * **Critical**: 0 – 399
   * **Insufficient Data**: Unscored baseline for new accounts.

---

## 10. Testing and Verification Results

### 10.1 Automated Test Suite Execution
Testing was conducted using Django's test runner across four test modules:

```powershell
python manage.py test tests
```

#### Official Test Output
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

### 10.2 Summary of Test Coverage
* **`tests/test_finance.py`** (9 tests):
  * Overdue status derivation for past, future, and settled invoices.
  * Payment status derivations (`paid`, `partial`, `pending`, `overdue`).
  * Customer financial summary aggregations on real seeded data.
* **`tests/test_credit_engine.py`** (16 tests):
  * Exact `ROUND_HALF_UP` boundary tests (416.5 $\to$ 417, 757.9 $\to$ 758).
  * 5 worked scenarios across risk categories.
  * Delinquency overrides preventing masking under `INSUFFICIENT_DATA`.
  * Exclusion of cancelled and returned orders from order value.
* **`tests/test_dashboard.py`** (10 tests):
  * Unauthenticated redirect protection.
  * Authenticated dashboard rendering and context integrity.
  * PyMongo aggregations for customer profile status and risk bands.
  * Financial overview calculations (Revenue, Outstanding, Overdue).
  * Date-range parsing and validation.
  * Empty dataset fallback handling.
* **`tests/test_integration.py`** (8 tests):
  * End-to-end customer creation and detail view.
  * Order creation with automatic invoice creation and partial payments.
  * Credit profile recalculation idempotency without document duplication.
  * Risk alert generation and resolution.
  * Rejection of unauthenticated state-changing POST requests.
  * Malformed date-range filter error handling.
  * CSV export responses for customers, orders, and payments.
  * MongoDB showcase page rendering and authentication.

---

## 11. Limitations and Future Scope

### 11.1 Project Limitations
1. **Academic Credit Scope**: The 0–850 credit score is internally defined based on e-commerce transaction history; it is **not** an official banking score (e.g., CIBIL or FICO).
2. **Synchronous Recalculation**: Profile updates run synchronously on request rather than via an asynchronous worker queue (such as Celery with Redis).
3. **Synthetic Seed Data**: Evaluated against a synthetic dataset of 15 customers, 19 orders, and 17 payments designed to demonstrate all scoring edge cases.

### 11.2 Future Scope
1. **Machine Learning Score Weighting**: Train a supervised credit default model (e.g., XGBoost) to dynamically optimize component weights based on historical default rates.
2. **Asynchronous Background Processing**: Offload batch score recalculations and email alerts to Celery background task workers.
3. **Merchant Rule Engine**: Allow store administrators to customize credit score thresholds and auto-adjust BNPL credit limits.

---

## 12. Conclusion

The **Credit Profile System (CreditIQ)** demonstrates a robust dual-database web application combining **Django** and **MongoDB Atlas** using raw **PyMongo**. By enforcing database-level `$jsonSchema` validation, atomic sequence generation, multi-stage aggregation pipelines, and an explainable mathematical scoring engine, the system delivers real-time credit analytics while preserving data integrity.

All 43 unit and integration tests execute successfully with zero failures, confirming the platform's stability, security, and readiness for college academic evaluation.
