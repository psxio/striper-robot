# Strype Cloud Enterprise Deployment

## Railway (Primary)

The production backend is live on Railway and should be the default deployment path.

Live service:

- Project: `strype`
- Service: `backend`
- Environment: `production`

Required Railway service variables:

- `ENV=production`
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `SECRET_KEY=<64+ random chars>` (example: `python -c "import secrets; print(secrets.token_urlsafe(64))"`)
- `CORS_ORIGINS=https://your-frontend.example.com`
- `FRONTEND_URL=https://your-frontend.example.com`

For local development only, you may add localhost origins in non-production environments.

Deploy from local CLI:

```bash
railway up --service backend --environment production --detach
```

### Persistent Storage (Railway Volume)

SQLite databases are ephemeral by default in Railway containers. To persist data across deploys:

1. In the Railway dashboard, open your **backend** service → **Volumes** tab.
2. Click **Add Volume** and set the mount path to `/app/backend/data`.
3. Railway will mount a persistent volume at that path for every deployment.

The `Dockerfile` already declares `VOLUME ["/app/backend/data"]` so Railway recognises the mount point automatically.

If you are using PostgreSQL (recommended for production), skip the Volume — set `DATABASE_URL` to your Postgres connection string instead and leave `DATABASE_PATH` unset.

Deploy from GitHub Actions:

- Workflow: `.github/workflows/deploy-railway.yml`
- Required secret: `RAILWAY_TOKEN`

The repo already includes `railway.toml` and Docker-based deploy settings. Health checks use `/api/ready`.

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

## AWS Provisioning (Secondary Option)

Terraform lives in [infra/terraform](../infra/terraform).

The CI deploy workflow expects Terraform remote state in S3. Configure repository variables:

- `TF_STATE_BUCKET` (required)
- `TF_STATE_LOCK_TABLE` (optional, recommended for state locking)

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

- `AWS_DEPLOY_ROLE_ARN` (recommended) or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`
- `AWS_CERTIFICATE_ARN`
- `DB_USERNAME`
- `DB_PASSWORD`
- `DATABASE_URL_SECRET_ARN`
- `SECRET_KEY_SECRET_ARN`
- `FRONTEND_URL`
- `CORS_ORIGINS`

Optional secrets:

- `STRIPE_SECRET_KEY_SECRET_ARN`
- `STRIPE_WEBHOOK_SECRET_ARN`
- `SENDGRID_API_KEY_SECRET_ARN`
- `SENTRY_DSN_SECRET_ARN`

Repository variables used by the workflow:

- `AWS_REGION` (defaults to `us-east-1`)
- `PROJECT_NAME` (defaults to `strype`)
- `ENVIRONMENT` (defaults to `production`)
- `TF_STATE_BUCKET` (required)
- `TF_STATE_LOCK_TABLE` (optional)

## Cutover Checklist

1. Run backend tests and smoke tests against staging.
2. Snapshot the SQLite file.
3. Run the SQLite to PostgreSQL migration.
4. Deploy the new ECS task definition.
5. Verify `/api/health` and `/api/ready`.
6. Exercise login, org switching, work-order verification, report download, and media upload.
7. Keep the pre-cutover task definition and the RDS snapshot as rollback anchors.
