# Strype Cloud Enterprise Deployment

## Target Shape

- FastAPI monolith on ECS Fargate
- PostgreSQL on RDS
- Private S3 buckets for media and reports
- Secrets in AWS Secrets Manager
- ALB with `/api/health` and `/api/ready` health gates
- Terraform as the only supported infrastructure path

## Required Environment

Production now treats `DATABASE_URL` as canonical. `DATABASE_PATH` is only for local development and tests.

Core variables:

- `ENV=production`
- `DATABASE_URL`
- `SECRET_KEY`
- `CORS_ORIGINS`
- `FRONTEND_URL`
- `OBJECT_STORAGE_BACKEND=s3`
- `AWS_REGION`
- `S3_PRIVATE_BUCKET`
- `S3_REPORTS_BUCKET`
- `ACCESS_TOKEN_EXPIRE_MINUTES=60`
- `MAX_UPLOAD_BYTES`

Optional but recommended:

- `SENTRY_DSN`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SENDGRID_API_KEY`
- `FROM_EMAIL`

## AWS Provisioning

Terraform lives in [infra/terraform](/Users/mabou/Downloads/robot/infra/terraform).

Provisioning covers:

- VPC, public/private subnets, NAT
- ALB and target group
- ECS cluster, task definition, service
- ECR repository
- RDS PostgreSQL
- Private S3 buckets with versioning
- CloudWatch log group and baseline alarms

Use:

```bash
cd infra/terraform
terraform init
terraform apply \
  -var="image_url=<ecr-image-uri>" \
  -var="database_username=<db-user>" \
  -var="database_password=<db-password>" \
  -var="database_url_secret_arn=<secret-arn>" \
  -var="secret_key_secret_arn=<secret-arn>" \
  -var="frontend_url=https://app.example.com" \
  -var="cors_origins=https://app.example.com"
```

## Database Migration

The one-time SQLite to PostgreSQL migration tool is [scripts/migrate_sqlite_to_postgres.py](/Users/mabou/Downloads/robot/scripts/migrate_sqlite_to_postgres.py).

Example:

```bash
python scripts/migrate_sqlite_to_postgres.py ^
  --sqlite-path backend/data/strype.db ^
  --database-url postgresql+asyncpg://user:pass@host:5432/strype
```

Run order:

1. Apply Terraform and create the target RDS instance.
2. Generate the final PostgreSQL `DATABASE_URL`.
3. Run the migration script against a staging copy first.
4. Deploy the ECS task with the PostgreSQL secret.
5. Verify `/api/ready` before sending external traffic.

## CI/CD

GitHub Actions now includes:

- [`.github/workflows/test.yml`](/Users/mabou/Downloads/robot/.github/workflows/test.yml) for tests
- [`.github/workflows/security.yml`](/Users/mabou/Downloads/robot/.github/workflows/security.yml) for dependency audit, Trivy, and secret scanning
- [`.github/workflows/deploy-aws.yml`](/Users/mabou/Downloads/robot/.github/workflows/deploy-aws.yml) for build, push, and Terraform apply

The deploy workflow assumes the repo has these secrets:

- `AWS_DEPLOY_ROLE_ARN`
- `AWS_REGION`
- `AWS_CERTIFICATE_ARN`
- `ECR_REPOSITORY_URL`
- `DB_USERNAME`
- `DB_PASSWORD`
- `DATABASE_URL_SECRET_ARN`
- `SECRET_KEY_SECRET_ARN`
- `FRONTEND_URL`
- `CORS_ORIGINS`

## Cutover Checklist

1. Run backend tests and smoke tests against staging.
2. Snapshot the SQLite file.
3. Run the SQLite to PostgreSQL migration.
4. Deploy the new ECS task definition.
5. Verify `/api/health` and `/api/ready`.
6. Exercise login, org switching, work-order verification, report download, and media upload.
7. Keep the pre-cutover task definition and the RDS snapshot as rollback anchors.
