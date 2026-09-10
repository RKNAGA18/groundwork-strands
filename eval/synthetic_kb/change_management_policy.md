# Change Management Policy (CCC)

## 1. Introduction
The Change Management Policy ensures that all modifications to Acme Cloud Solutions' production IT environment are thoroughly evaluated, tested, approved, and tracked.

## 2. Change Request Process
- All changes must be tracked via Jira tickets.
- **Major Changes**: Significant architectural changes or high-risk modifications require formal review and approval by the Change Advisory Board (CAB) during weekly meetings.

## 3. CI/CD and Code Review
Acme Cloud Solutions utilizes an automated Continuous Integration/Continuous Deployment (CI/CD) pipeline.
- All code changes require mandatory peer review with at least two (2) approved sign-offs before merging into the main branch.
- Changes must successfully pass automated testing in a staging environment that mirrors production before deployment.

## 4. Configuration Management
Infrastructure as Code (IaC) principles are applied utilizing Terraform. All infrastructure configurations are version-controlled, allowing for consistent deployments and rapid rollback capabilities.

## 5. Rollback and Change Freezes
- Every change request must include a documented and tested rollback procedure.
- To ensure stability during critical business periods, change freeze windows are enforced during quarter-end financial close periods. Only emergency fixes are permitted during these times.
