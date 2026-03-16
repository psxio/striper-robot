# Strype Cloud — Deployment Guide

## Architecture

- **Backend**: FastAPI + aiosqlite (single-file SQLite DB)
- **Frontend**: Static HTML/JS/CSS served from `site/`
- **Auth**: JWT Bearer tokens with refresh token rotation
- **Billing**: Stripe Checkout + webhooks
- **Email**: SendGrid transactional email

## Railway Deployment

### 1. Create a Railway Project

1. Create a new project at [railway.app](https://railway.app)
2. Connect your GitHub repo (`psxio/striper-robot`)
3. Railway auto-detects the Dockerfile in the repo root

### 2. Configure Environment Variables

Set all variables from `.env.example` in the Railway dashboard under **Variables**. Critical ones:

| Variable | Notes |
|----------|-------|
| `ENV` | Set to `production` |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `CORS_ORIGINS` | Your domain, e.g. `https://strype.io` |
| `FRONTEND_URL` | Same as above |
| `ADMIN_EMAIL` | Your admin email |
| `STRIPE_SECRET_KEY` | From Stripe dashboard |
| `STRIPE_WEBHOOK_SECRET` | From webhook endpoint config |
| `SENDGRID_API_KEY` | From SendGrid dashboard |
| `FROM_EMAIL` | Verified sender in SendGrid |

### 3. Persistent Storage

Railway provides ephemeral disks by default. For SQLite persistence:

1. Add a **Volume** to the service
2. Mount at `/data`
3. Set `DATABASE_PATH=/data/strype.db`

### 4. Custom Domain

1. In Railway service settings, add your domain
2. Point DNS CNAME to the Railway-provided hostname
3. Railway auto-provisions TLS certificates

## Stripe Setup

### Products & Prices

Create two products in Stripe Dashboard:

1. **Strype Pro** — $99/month recurring
   - Copy the Price ID → `STRIPE_PRICE_ID`
2. **Strype Robot** — $299/month recurring
   - Copy the Price ID → `STRIPE_ROBOT_PRICE_ID`

### Webhook Endpoint

1. In Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://your-domain.com/api/webhooks/stripe`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
4. Copy the signing secret → `STRIPE_WEBHOOK_SECRET`

## SendGrid Setup

1. Create a SendGrid account and verify your sender domain
2. Create an API key with Mail Send permissions
3. Set `SENDGRID_API_KEY` and `FROM_EMAIL` in environment

Email is used for:
- Email verification on signup
- Password reset links
- Subscription confirmations

## NTRIP / RTK Base Station Options

For field deployment, the robot needs RTK corrections. Options:

| Option | Cost | Setup |
|--------|------|-------|
| **Network NTRIP** (recommended) | $0–50/mo | Use state DOT CORS or commercial NTRIP (e.g., Point One Nav). Configure UM982 with NTRIP client credentials via Mission Planner. No hardware needed. |
| **Own Base Station** | $200–500 one-time | Second UM982 or u-blox F9P on a survey point. Run `str2str` or SNIP to serve corrections. |
| **Phone NTRIP Relay** | Free w/ phone plan | Android app (e.g., Lefebure NTRIP Client) relays corrections via Bluetooth to UM982. |

## Health Check

The app exposes a health endpoint at `GET /api/health` which returns `{"status": "ok"}` with HTTP 200. Use this for Railway health checks: set the Health Check Path to `/api/health`. The Docker HEALTHCHECK is already configured to probe this endpoint.

## Monitoring

- Logs: Railway dashboard → Deployments → Logs
- Errors: The app returns structured JSON for all errors (global exception handler)
- Metrics: Check `GET /api/admin/stats` for user/lot/job counts
