# Privacy Policy — Oura Self-Analysis

**Last updated:** 30 October 2026

## 1. What this project is

Oura Self-Analysis is an independent, experimental project maintained for personal use by the owner of [this repository](https://github.com/daniele21/oura-self-analysis). Its purpose is to let the owner access, store, and analyze **their own** Oura Ring data using Oura's authorized API.

**Current status:** this repository contains registration information and documentation, but does **not** currently operate a hosted service that receives or stores Oura data. The processing described below is the intended behavior of a future local integration, not a statement that a deployed service is already running.

## 2. Data and permissions

If and when the owner completes OAuth authorization and installs the local integration, it may access only the categories approved during Oura authorization, such as daily sleep, activity, readiness, heart rate, workouts, tags, and blood-oxygen summaries. Availability varies by device, membership, granted scopes, and Oura API features.

An OAuth client ID, client secret, access tokens, and refresh tokens may be required to complete authorization. **Secrets and tokens must be stored privately, not committed to this public repository.**

## 3. Purpose and legal context

Data will be used for personal recordkeeping, visualizations, trends, and exploratory analysis. It is not intended for advertising, profiling other individuals, marketing, sale of personal data, or medical diagnosis. This project does not currently invite other Oura users to connect their accounts.

## 4. Storage, sharing, and third parties

No server-side Oura data collection is currently deployed for this project. The planned first implementation stores authorized data and credentials on the owner's own device, outside this repository.

The integration necessarily communicates with Oura's systems for authorization and API requests. Oura handles data under its own privacy terms. At this stage this project does not intentionally transmit Oura health data to cloud analytics services, external AI models, advertisers, or other independent recipients.

If cloud storage, external AI processing, or a hosted service is introduced, this policy will be updated beforehand to describe the providers, purposes, data locations, retention, and safeguards. **This public GitHub repository is never an appropriate destination for health-data exports or OAuth credentials.**

## 5. Retention and deletion

Because the initial integration has not yet been deployed, no application-controlled Oura health-data retention period is currently running. For the planned local-only implementation, the owner will control copies of exported data and may delete them from the local device. Deleting local copies does not delete data held by Oura.

Authorization to the app can be revoked through Oura's account controls, where available. Revoking authorization prevents future access by this integration but does not automatically erase copies already exported.

## 6. Security

The intended implementation follows data-minimization and least-privilege practices: limited OAuth scopes, private storage of credentials and raw exports, and exclusion of secrets and health records from version control. No claim of absolute security is made.

## 7. Changes

This policy will be revised if the way data is processed changes. The latest published version is available in this repository.

## 8. Contact

For questions about this project, contact the repository maintainer through [GitHub](https://github.com/daniele21). Please **do not** disclose sensitive health data, credentials, or private account details in a public GitHub issue.

For privacy or account requests about data held by Oura itself, contact Oura directly through its official channels.

---

This document describes a personal experimental project. It is not Oura's privacy policy and does not imply any affiliation or endorsement.
