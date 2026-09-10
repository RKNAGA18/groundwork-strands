# Data Security Policy (DSP)

## 1. Purpose
The purpose of this policy is to establish the framework for data classification, handling, and lifecycle management at Acme Cloud Solutions to ensure the protection and privacy of all organizational and customer data.

## 2. Data Classification
Acme Cloud Solutions categorizes all data into four classification levels:
- **Public**: Information intended for public disclosure (e.g., marketing materials, public website content).
- **Internal**: Information intended for internal use only. Unauthorized disclosure could cause minimal harm.
- **Confidential**: Sensitive business information that is not shared externally (e.g., financial records, employee data, intellectual property).
- **Restricted**: Highly sensitive data whose unauthorized disclosure could cause significant harm (e.g., customer PII, customer proprietary data, authentication credentials).

## 3. Data Handling Procedures
All employees must handle data according to its classification level. Restricted data must only be accessed on a strict need-to-know basis and must be encrypted both in transit and at rest. Data loss prevention (DLP) tools are deployed across all company endpoints and network perimeters to monitor and prevent unauthorized exfiltration of Confidential and Restricted data.

## 4. Data Retention and Deletion
- **Financial Data**: Retained for 7 years to comply with regulatory requirements.
- **Operational Data**: Retained for 3 years, after which it is securely archived or deleted.
- **Customer Data**: Retained for the duration of the active contract, plus a standard 30-day grace period post-termination unless otherwise specified.

Data deletion procedures must employ cryptographic erasure for all Restricted and Confidential data to ensure it cannot be recovered. Regular audits are conducted to verify compliance with data retention schedules.
