# Automated Pharmaceutical Stock and Expiry Management System

## Project Overview
[cite_start]This is a web-based automated inventory management system designed specifically for small-scale retail pharmacies in Kenya[cite: 12, 145]. [cite_start]The system aims to solve the critical challenge of manual expiry tracking, helping pharmacies reduce waste from "dead stock" and improve overall cash flow[cite: 10, 18, 380]. 

[cite_start]This project was developed by Manyali Timothy Mulongo as part of the BSc in Software Development program at KCA University[cite: 116, 119].

## Key Features
* [cite_start]**User Authentication:** Secure, role-based access for Administrators and Pharmacists[cite: 151, 166, 169].
* [cite_start]**Inventory Management:** Complete batch tracking including manufacturing dates, expiry dates, and unit prices[cite: 147].
* [cite_start]**Expiry Alert System:** Automated dashboard notifications categorizing near-expiry stock into Critical (≤ 30 days), Warning (≤ 60 days), and Advisory (≤ 90 days) tiers[cite: 13, 148, 209, 210, 211].
* [cite_start]**FIFO Point of Sale (POS):** An intelligent sales interface that utilizes First-In-First-Out logic to automatically suggest and deduct stock from the earliest expiring batch[cite: 14, 149].
* [cite_start]**Reporting:** Automated generation of Sales History and Critical Expiry reports[cite: 150].
* [cite_start]**Receipt Generation:** Printable transaction receipts for customers[cite: 221].

## Technologies Used
* [cite_start]**Architecture:** Model-View-Controller (MVC) [cite: 44]
* [cite_start]**Backend:** Python 3, Django Web Framework [cite: 173]
* [cite_start]**Frontend:** HTML5, Bootstrap 5, JavaScript [cite: 174]
* [cite_start]**Database:** SQLite (Development) / MySQL 8.x (Production) [cite: 32]

---

## Local Setup & Installation Guide

Follow these steps to run the project on your local machine.

### 1. Clone the Repository
Open your terminal and clone this project to your local computer:
```bash
git clone [https://github.com/Timothy-M-M/PharmacySystem.git](https://github.com/Timothy-M-M/PharmacySystem.git)
cd PharmacySystem
