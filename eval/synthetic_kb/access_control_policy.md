# Access Control Policy (IAM)

## 1. Objective
This policy defines the rules and procedures for managing access to Acme Cloud Solutions' information systems, ensuring that only authorized individuals have access to company resources.

## 2. Access Provisioning
Access to all systems is governed by the Principle of Least Privilege and implemented using a Role-Based Access Control (RBAC) model.
- Access rights are granted based solely on the requirements of an employee's job function.
- Automated provisioning and deprovisioning processes ensure that access is updated or revoked within 24 hours of a role change or termination.

## 3. Authentication Requirements
- **Multi-Factor Authentication (MFA)**: MFA is strictly required for all users accessing Acme Cloud Solutions' internal systems, production environments, and VPNs.
- **Single Sign-On (SSO)**: The organization utilizes SSO via SAML 2.0 to centralize authentication and enforce security policies consistently across applications.

## 4. Password Policy
Where SSO is not applicable, local accounts must adhere to the following password requirements:
- Minimum length of 12 characters.
- Complexity requiring at least one uppercase letter, one lowercase letter, one number, and one special character.
- Mandatory 90-day password rotation.
- Password history enforced to prevent reuse of the last 5 passwords.

## 5. Access Reviews
Quarterly access reviews are conducted by system owners and IT administrators to verify that user access rights remain appropriate for their current roles. Discrepancies are remediated immediately.
