# Strype AWS Deployment Runbook

## Scope

This is the canonical deployment path for the production Strype Cloud monolith:

- FastAPI app on ECS Fargate
- PostgreSQL on RDS
- Private S3 buckets for media and reports
- Terraform-managed infrastructure
- GitHub Actions staged promotion: `staging -> smoke -> production`

Railway remains optional for lightweight preview hosting. It is not the production path.

## Required Inputs

Repository variables:

- `AWS_REGION`
- `PROJECT_NAME`
- `TF_STATE_BUCKET`
- `TF_STATE_LOCK_TABLE` (recommended)
- `MIGRATION_REHEARSED=true` before production cutover

Environment-scoped secrets for both `staging` and `production`:

- `AWS_DEPLOY_ROLE_ARN` or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`
- `DB_USERNAME`
- `DB_PASSWORD`
- `DATABASE_URL_SECRET_ARN`
- `SECRET_KEY_SECRET_ARN`
- `FRONTEND_URL`
- `CORS_ORIGINS`
- `PUBLIC_BASE_URL`
- `SMOKE_EMAIL`
- `SMOKE_PASSWORD`

Optional environment-scoped secrets:

- `AWS_CERTIFICATE_ARN`
- `ALARM_TOPIC_ARN`
- `STRIPE_SECRET_KEY_SECRET_ARN`
- `STRIPE_WEBHOOK_SECRET_ARN`
- `SENDGRID_API_KEY_SECRET_ARN`
- `SENTRY_DSN_SECRET_ARN`
- `SMOKE_ORG_ID`

## Bootstrap

1. Create the Terraform remote-state S3 bucket and optional DynamoDB lock table.
2. Create GitHub `staging` and `production` environments.
3. Add the required secrets to each environment.
4. Store the application secrets in AWS Secrets Manager.
5. Ensure the production certificate exists in ACM if HTTPS should terminate at the ALB.

## Staging Deploy

Trigger `.github/workflows/deploy-aws.yml`.

The workflow will:

1. validate Terraform
2. bootstrap the staging ECR repository
3. build one image and push it
4. plan and apply staging Terraform
5. run `scripts/smoke_check.py` against staging

The smoke check verifies:

- `/api/ready`
- auth login
- organization lookup
- org-scoped lot creation
- auto-linked site lookup
- site scan creation
- simulation creation
- work-order creation

## Production Promotion

Production promotion is blocked unless:

- staging deploy succeeded
- staging smoke succeeded
- `MIGRATION_REHEARSED=true`

The same image built for staging is promoted to production. Do not rebuild a second image for production.

## Database Migration and Cutover

Production uses `DATABASE_URL`. SQLite is only for local/test use.

Use the one-time migration tool:

```bash
python scripts/migrate_sqlite_to_postgres.py ^
  --sqlite-path backend/data/strype.db ^
  --database-url postgresql+asyncpg://user:pass@host:5432/strype
```

Cutover order:

1. rehearse the migration on staging data
2. freeze schema changes for cutover
3. snapshot the SQLite source
4. run the SQLite-to-Postgres migration
5. verify Alembic head is current
6. run staged deploy workflow
7. promote to production only after smoke passes

## Rollback

Before external traffic is considered restored, keep these rollback anchors:

- previous ECS task definition
- latest RDS snapshot
- S3 object versions

Rollback order:

1. stop traffic promotion if smoke fails
2. redeploy the previous ECS task definition
3. if database rollback is required, restore the RDS snapshot
4. rerun smoke checks before reopening traffic

## Recovery Checks

After any deploy or restore, confirm:

- `/api/health`
- `/api/ready`
- auth login
- workspace switch
- lot creation
- site scan creation
- simulation creation
- work-order creation
- report listing and download
