# Encryption and Key Management Policy (CEK)

## 1. Scope
This policy mandates the cryptographic controls used to protect the confidentiality and integrity of Acme Cloud Solutions' sensitive data.

## 2. Data in Transit
All network traffic containing sensitive or confidential data must be encrypted during transmission over untrusted networks. 
- Transport Layer Security (TLS) version 1.3 is the minimum required standard for securing data in transit. Older versions (e.g., TLS 1.0, 1.1) are explicitly disabled.

## 3. Data at Rest
All Confidential and Restricted data stored on Acme Cloud Solutions' servers, databases, and backup media must be encrypted at rest.
- The Advanced Encryption Standard (AES) with a 256-bit key length (AES-256) is the mandated standard for data at rest.

## 4. Key Management
Cryptographic keys are managed using AWS Key Management Service (KMS).
- **Storage**: Master keys are protected by FIPS 140-2 Level 3 compliant Hardware Security Modules (HSMs).
- **Rotation**: All cryptographic keys must undergo annual key rotation.
- **Customer Keys**: Currently, Acme Cloud Solutions does not support customer-managed keys (Bring Your Own Key - BYOK). This is designated as a future roadmap item.

## 5. Certificate Management
Digital certificates used for encryption and identity verification are managed via an automated renewal system to prevent expiration and associated service outages.
