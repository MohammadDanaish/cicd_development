# Nama Water Services TIPMS — CI/CD Pipeline Implementation Guide

| Field    | Value                                                              |
|----------|--------------------------------------------------------------------|
| Version  | v1.2 — GitHub-hosted runner + all gaps resolved                   |
| Date     | May 2026                                                           |
| Status   | Ready for engineering use                                          |
| Audience | Backend / DevOps engineers setting up the Nama TIPMS pipeline      |
| Based on | github_cicd_pipeline_v4.drawio                                     |
| Changes  | GitHub-hosted runner replaces self-hosted VM; 5 known gaps closed  |

---

## What Changed in v1.2

| # | Change | Why |
|---|--------|-----|
| 1 | All jobs use `runs-on: ubuntu-latest` (GitHub-hosted) instead of `self-hosted` | Eliminates runner-vm provisioning and maintenance overhead |
| 2 | `services:` block restored for Postgres integration tests | GitHub-hosted runners fully support service containers; the manual `docker run` workaround was only needed on bare VM runners |
| 3 | Section 10 (Runner VM Setup) removed | No longer needed |
| 4 | DAST added as Stage 7 after every staging deploy | Closes gap: auth bypass and access control bugs only appear in a running app |
| 5 | Cosign image signing added after GHCR push | Closes gap: cryptographic proof that images came from the pipeline |
| 6 | `notify-on-failure` job added to pipeline | Closes gap: developers now get WhatsApp alerts on broken builds |
| 7 | Flyway undo scripts documented and added to production gate checklist | Closes gap: schema rollback now has a defined process |
| 8 | External uptime monitoring documented in Section 9 | Closes gap: Uptime Kuma inside VPN cannot detect VPC-level outages |

---

## Table of Contents

1. [What This Guide Covers](#1-what-this-guide-covers)
2. [Before You Start — Prerequisites](#2-before-you-start--prerequisites)
3. [Repository Setup](#3-repository-setup)
4. [GitHub Secrets and Environments](#4-github-secrets-and-environments)
5. [The Pipeline — Stage by Stage](#5-the-pipeline--stage-by-stage)
6. [Staging / Dev / UAT Deployment](#6-staging--dev--uat-deployment)
7. [Production Deployment](#7-production-deployment)
8. [Application Logging](#8-application-logging)
9. [Monitoring Setup](#9-monitoring-setup)
10. [Mobile App Pipeline](#10-mobile-app-pipeline)
11. [Known Gaps — All Resolved](#11-known-gaps--all-resolved)
12. [Rollback Decision Tree](#12-rollback-decision-tree)

---

## 1. What This Guide Covers

This guide walks you through setting up the complete CI/CD pipeline for the Nama TIPMS web application — from a developer pushing code to a version running safely in production. It covers every moving part: repository rules, the automated pipeline stages, how Docker images are built and stored, how Dev / UAT / Production deployments work, and how to roll back quickly if something breaks.

Follow the sections in order. Each one builds on the previous.

> **Watch out:** This guide covers the web portal pipeline only (`permit-api` + `permit-web`). The mobile pipeline (Flutter / iOS) is in [Section 10](#10-mobile-app-pipeline).

> **GitHub-hosted runners:** All CI/CD jobs run on GitHub-provided `ubuntu-latest` machines. You do not provision or maintain a runner VM. GitHub charges per-minute on the paid plan; the free tier covers ~2,000 minutes/month per private repo. For a team of 5–8 developers the pipeline uses roughly 30–50 minutes per full run, so factor in usage accordingly.

---

## 2. Before You Start — Prerequisites

### 2.1 Accounts and access

- GitHub organisation account with admin rights to the `nama-tipms` repository
- Access to the Omantel / OTech Cloud console to provision VMs
- A Snyk account — snyk.io (free tier is fine to start)
- A Codemagic account for iOS builds — codemagic.io
- A Sigstore / Fulcio account is **not** needed — Cosign keyless signing uses the GitHub Actions OIDC token automatically
- WhatsApp Business API access (for deploy and failure alerts)
- A Better Uptime or Freshping account for external uptime monitoring

### 2.2 Tools on your laptop

- Git 2.40+
- Docker Desktop (to test image builds locally before committing)
- Node.js 20 LTS
- Flyway CLI 10+ — for running database migrations manually if needed
- Cosign CLI — `brew install cosign` or download from sigstore/cosign releases (for local verification only; the pipeline installs it automatically)
- SSH client with your key pair configured

### 2.3 VMs to provision

Provision all VMs in Omantel cloud **before** touching any pipeline config. All VMs run Ubuntu 22.04 LTS.

> **No runner-vm needed.** CI/CD jobs run on GitHub-hosted machines. The runner-vm from v1.1 is removed.

| VM name         | Size                     | Purpose                                  |
|-----------------|--------------------------|------------------------------------------|
| monitoring-vm   | 2 CPU / 4 GB / 50 GB    | Prometheus, Grafana, Loki, Alertmanager  |
| dev-app-vm      | 2 CPU / 2 GB / 50 GB    | Dev application containers               |
| dev-db-vm       | 2 CPU / 4 GB / 100 GB   | Dev PostgreSQL 16                        |
| uat-app-vm      | 2 CPU / 4 GB / 50 GB    | UAT application containers               |
| uat-db-vm       | 2 CPU / 8 GB / 150 GB   | UAT PostgreSQL 16                        |
| prod-app-vm-1   | 4 CPU / 8 GB / 100 GB   | Production app — node 1 of 2             |
| prod-app-vm-2   | 4 CPU / 8 GB / 100 GB   | Production app — node 2 of 2             |
| prod-db-vm      | 4 CPU / 16 GB / 200 GB NVMe | Production PostgreSQL 16             |

After provisioning, record the private IP addresses — you will need them in Sections 6 and 7:

| VM            | Private IP (fill in) |
|---------------|----------------------|
| monitoring-vm | 10.0.___.___|
| dev-app-vm    | 10.0.___.___|
| dev-db-vm     | 10.0.___.___|
| uat-app-vm    | 10.0.___.___|
| uat-db-vm     | 10.0.___.___|
| prod-app-vm-1 | 10.0.___.___|
| prod-app-vm-2 | 10.0.___.___|
| prod-db-vm    | 10.0.___.___|

> **Network note:** All VM-to-VM traffic uses private IPs. GitHub-hosted runners reach your VMs over SSH through a VPN gateway or a bastion host — configure your VPN/bastion to allow inbound SSH from GitHub Actions IP ranges (published at https://api.github.com/meta, field `actions`). Only the load balancer needs inbound port 443 from the internet.

---

## 3. Repository Setup

### 3.1 Branch strategy

The project uses **Feature Branch Promotion** (v4 design). Each feature branch is promoted through Dev → UAT → Production. The same commit SHA is deployed to all three environments — no rebuild between them.

- Feature branches: `feature/short-description`, kept alive **2 days maximum**
- Bug fixes: `fix/short-description`
- Nobody pushes directly to `main` — ever
- Feature branch is deleted after it merges to `main`

### 3.2 Branch protection rules for `main`

GitHub → Settings → Branches → Add rule, branch name pattern: `main`

| Setting | Value |
|---------|-------|
| Require a pull request before merging | ON |
| Required approvals | 2 |
| Dismiss stale PR approvals when new commits are pushed | ON |
| Require status checks to pass before merging | ON — add: `validate`, `test`, `sast`, `build`, `image-scan` |
| Require branches to be up to date before merging | ON |
| Do not allow bypassing the above settings | ON |

### 3.3 Commit message format

Every commit must follow this format. The pipeline uses it to decide the version number automatically.

```
feat(permits): add renewal reminder UI
fix(lab): correct 3-day SLA calculation to exclude Friday/Saturday
chore(deps): bump node from 20.10 to 20.11

BREAKING CHANGE: remove legacy permit endpoint /api/v1/permits/old
```

| Prefix | Meaning | Version bump |
|--------|---------|--------------|
| `feat` | New feature visible to users | Minor: 1.2.0 → 1.3.0 |
| `fix` | Bug fix | Patch: 1.2.0 → 1.2.1 |
| `chore` / `docs` / `refactor` | Internal change, no user impact | No release |
| `BREAKING CHANGE` | Removes or changes existing behaviour | Major: 1.2.0 → 2.0.0 |

> **Tip:** Install commitlint to enforce this automatically. Add a `.commitlintrc.json` file to the repo root and badly formatted commits will be rejected before they are pushed.

---

## 4. GitHub Secrets and Environments

### 4.1 Add these secrets

GitHub → Settings → Secrets and variables → Actions → New repository secret:

| Secret name | What to put in it |
|-------------|-------------------|
| `DB_PASSWORD` | PostgreSQL password for the app user |
| `JWT_SECRET_KEY` | 64-char random string — generate with: `openssl rand -hex 32` |
| `FCM_SERVER_KEY` | Firebase Cloud Messaging server key (from Firebase console) |
| `APNS_AUTH_KEY` | Apple Push Notification `.p8` file contents, base64-encoded |
| `ANDROID_KEYSTORE` | Android signing keystore file, base64-encoded |
| `ANDROID_KEY_ALIAS` | Key alias inside the keystore |
| `ANDROID_KEY_PASSWORD` | Key password |
| `ANDROID_STORE_PASSWORD` | Keystore password |
| `CODEMAGIC_API_TOKEN` | API token from codemagic.io → Teams → Integrations |
| `SRV_DEV_SSH_KEY` | Private SSH key that can reach dev-app-vm and dev-db-vm |
| `SRV_UAT_SSH_KEY` | Private SSH key that can reach uat-app-vm and uat-db-vm |
| `SRV_PROD_SSH_KEY` | Private SSH key that can reach both prod-app-vms and prod-db-vm |
| `SNYK_TOKEN` | API token from snyk.io → Account Settings → API Token |
| `WHATSAPP_API_TOKEN` | WhatsApp Business API token for pipeline notifications |
| `WHATSAPP_CHANNEL_ID` | WhatsApp group/channel ID for team alerts |

> **Watch out:** Never commit these values to any file in the repository. If you accidentally commit a secret, rotate it immediately — deleting the commit is not enough because the value is in git history.

### 4.2 Create GitHub Environments

Settings → Environments → New environment:

**`dev`**
- No approval required — deploys automatically after CI passes on a feature branch
- Concurrency group active (no parallel deploys)

**`uat`**
- Required reviewers: Dev Lead + QA (at least 1 must approve)
- Triggered via `workflow_dispatch` only — never auto-fires
- GitHub verifies same commit SHA as Dev

**`production`**
- Required reviewers: 2 team members who must approve every production release
- Deployment branches: Tags matching `v*.*.*`
- Triggered via `workflow_dispatch` only after PR merges to `main`
- Deployment window enforced: Sunday 03:00–06:00 OST

---

## 5. The Pipeline — Stage by Stage

The pipeline lives in `.github/workflows/ci-cd.yml`. Every run goes through these stages in order. If any stage fails, everything after it stops — except `notify-on-failure`, which always runs on failure.

> **All jobs use `runs-on: ubuntu-latest`** — GitHub-hosted runners. No self-hosted VM required.

### Stage 1 — Validate (~90 seconds)

Runs on every push and every pull request. First safety net — catches problems before any code is built.

| Tool | What it checks | What causes failure |
|------|---------------|---------------------|
| ESLint | JavaScript / Vue code style errors | Any lint error |
| Prettier | Code formatting | Any file not formatted correctly |
| Stylelint | CSS errors | Any CSS lint error |
| Gitleaks | Accidentally committed secrets | Any secret pattern in the diff |
| npm audit | Known CVEs in npm dependencies | Critical or high severity CVEs |
| Snyk SCA | Deeper dependency scan + licence check | Critical/high CVEs, disallowed licences |

```yaml
validate:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: npm
    - run: npm ci
    - run: npm run lint
    - run: npx prettier --check .
    - uses: gitleaks/gitleaks-action@v2
    - run: npm audit --audit-level=high
    - uses: snyk/actions/node@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        args: --severity-threshold=high
```

> **Tip:** Add a `.snyk` file to the repo root to suppress known false positives. Snyk will respect it and skip those findings.

### Stage 2 — Test (~3 minutes)

Runs unit tests and integration tests. Integration tests use a real PostgreSQL service container.

> **Fixed from v1.1:** GitHub-hosted runners fully support `services:` blocks. The manual `docker run` workaround is no longer needed and has been removed.

```yaml
test:
  needs: validate
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_PASSWORD: test_password
        POSTGRES_DB: tipms_test
      ports:
        - 5432:5432
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: npm
    - run: npm ci
    - name: Run unit tests
      run: npx vitest run --coverage
    - name: Run API tests
      run: npx jest --coverage
    - name: Run integration tests
      env:
        DB_HOST: 127.0.0.1
        DB_PORT: 5432
        DB_PASSWORD: test_password
      run: npm run test:integration
```

Coverage thresholds must be configured in the test tool config files — the `--coverage` flag alone only generates a report, it does not block the pipeline.

In `vite.config.ts`:
```ts
export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      thresholds: {
        lines: 70,
        branches: 70,
        functions: 70,
        statements: 70,
      }
    }
  }
})
```

In `jest.config.js`:
```js
module.exports = {
  coverageThreshold: {
    global: {
      lines: 70,
      branches: 70,
      functions: 70,
      statements: 70,
    }
  }
}
```

### Stage 3 — SAST (~2 minutes)

Reads source code looking for security bugs — SQL injection, XSS, broken access control, OWASP Top 10. Does not need to run the app.

```yaml
sast:
  needs: validate
  runs-on: ubuntu-latest
  permissions:
    security-events: write
  steps:
    - uses: actions/checkout@v4
    - uses: github/codeql-action/init@v3
      with:
        languages: javascript
    - uses: github/codeql-action/analyze@v3
```

CRITICAL and HIGH findings fail the build. MEDIUM findings are flagged but do not block — they are reviewed in the weekly security meeting.

### Stage 4 — Build Images (~4 minutes, 2 parallel jobs)

Builds two Docker images and pushes them to GHCR immediately, tagged with the commit SHA.

```yaml
build:
  needs: [test, sast]
  runs-on: ubuntu-latest
  strategy:
    matrix:
      image: [api, web]
  steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    - uses: docker/build-push-action@v5
      with:
        context: .
        file: Dockerfile.${{ matrix.image }}
        push: true
        tags: ghcr.io/nama-water/nama-tipms-${{ matrix.image }}:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

**Dockerfile.api**

```dockerfile
FROM node:20.11-alpine3.19 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20.11-alpine3.19
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY package*.json ./
RUN npm ci --only=production
COPY --from=builder /app/dist ./dist
USER appuser
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

**Dockerfile.web**

```dockerfile
FROM node:20.11-alpine3.19 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

> **Note:** Both Dockerfiles must exist in the repo root. Create a `.dockerignore` file that excludes `node_modules`, `.git`, test files, and local `.env` files.

### Stage 5 — Image Scan (~3 minutes)

Pulls the images Stage 4 just pushed to GHCR and scans them with two scanners.

```yaml
image-scan:
  needs: build
  runs-on: ubuntu-latest
  strategy:
    matrix:
      image: [api, web]
  steps:
    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    - name: Trivy scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ghcr.io/nama-water/nama-tipms-${{ matrix.image }}:${{ github.sha }}
        severity: CRITICAL,HIGH
        exit-code: 1
    - name: Snyk container scan
      uses: snyk/actions/docker@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        image: ghcr.io/nama-water/nama-tipms-${{ matrix.image }}:${{ github.sha }}
        args: --severity-threshold=high
```

### Stage 6 — Release and Sign (main branch only)

Runs only on merges to `main`. Creates the semantic version, re-tags images, then signs them with Cosign keyless signing so every deployment can verify the image came from this pipeline.

> **New in v1.2:** Cosign signing closes the image tampering gap. No private key to manage — signing uses the GitHub Actions OIDC identity automatically.

```yaml
release:
  needs: image-scan
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  permissions:
    contents: write
    packages: write
    id-token: write   # required for Cosign OIDC keyless signing
  concurrency:
    group: deploy-${{ github.ref }}
    cancel-in-progress: false   # queue releases, never cancel mid-deploy
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: npm
    - run: npm ci

    - name: Run semantic-release
      run: npx semantic-release
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - uses: sigstore/cosign-installer@v3

    - name: Re-tag and sign images
      env:
        SHA: ${{ github.sha }}
        REGISTRY: ghcr.io/nama-water
      run: |
        VERSION=$(node -p "require('./package.json').version")
        echo "Releasing version $VERSION"

        for IMAGE in nama-tipms-api nama-tipms-web; do
          docker pull $REGISTRY/$IMAGE:$SHA

          docker tag $REGISTRY/$IMAGE:$SHA $REGISTRY/$IMAGE:$VERSION
          docker tag $REGISTRY/$IMAGE:$SHA $REGISTRY/$IMAGE:latest

          docker push $REGISTRY/$IMAGE:$VERSION
          docker push $REGISTRY/$IMAGE:latest

          # Sign both the SHA-tagged and version-tagged images
          cosign sign --yes $REGISTRY/$IMAGE:$SHA
          cosign sign --yes $REGISTRY/$IMAGE:$VERSION
        done
```

To **verify** a signed image on any VM before deploying, add this to your deploy scripts:

```bash
cosign verify \
  ghcr.io/nama-water/nama-tipms-api:$IMAGE_TAG \
  --certificate-identity="https://github.com/nama-water/nama-tipms/.github/workflows/ci-cd.yml@refs/heads/main" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

If verification fails, the deploy script exits immediately — the image was not produced by the pipeline.

### Stage 7 — DAST (after every Dev deploy)

> **New in v1.2:** Dynamic Application Security Testing runs against the live Dev environment after every successful deploy. Catches auth bypass, access control bugs, and runtime injection flaws that SAST cannot find in static code.

```yaml
dast:
  needs: deploy-dev
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: OWASP ZAP Baseline Scan
      uses: zaproxy/action-baseline@v0.12.0
      with:
        target: 'https://dev.permit.nama-water.om'
        rules_file_name: '.zap/rules.tsv'
        fail_action: true
        cmd_options: '-a'

    - name: Upload ZAP report
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: zap-report-${{ github.sha }}
        path: report_html.html
```

Create a `.zap/rules.tsv` file in the repo root to tune which rules fail the build vs. warn only. Start with all rules failing, then suppress specific rule IDs that are confirmed false positives for this app. At minimum, the following rules must always fail: SQL Injection (40018), XSS Reflected (40012), XSS Persistent (40014), Path Traversal (6), Remote File Inclusion (7).

> **Tip:** ZAP scans an authenticated app by making a first request with credentials and recording the session. Add a `zap-auth.sh` script to handle the login flow if the Dev environment requires authentication. See the OWASP ZAP docs on authenticated scanning.

### Notify on Failure

> **New in v1.2:** Developers now get an immediate WhatsApp alert when any pipeline stage fails, with the failed stage name and a direct link to the run logs.

```yaml
notify-on-failure:
  needs: [validate, test, sast, build, image-scan, release]
  if: failure()
  runs-on: ubuntu-latest
  steps:
    - name: Send WhatsApp failure alert
      run: |
        MESSAGE="❌ CI/CD Failed%0A"
        MESSAGE+="Repo: ${{ github.repository }}%0A"
        MESSAGE+="Branch: ${{ github.ref_name }}%0A"
        MESSAGE+="Commit: ${{ github.sha }}%0A"
        MESSAGE+="Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"

        curl -s -X POST "https://graph.facebook.com/v18.0/${{ secrets.WHATSAPP_CHANNEL_ID }}/messages" \
          -H "Authorization: Bearer ${{ secrets.WHATSAPP_API_TOKEN }}" \
          -H "Content-Type: application/json" \
          -d "{\"messaging_product\":\"whatsapp\",\"to\":\"${{ secrets.WHATSAPP_CHANNEL_ID }}\",\"type\":\"text\",\"text\":{\"body\":\"$MESSAGE\"}}"
```

---

## 6. Staging / Dev / UAT Deployment

### 6.1 Environment flow

```
feature/INS-123  →  [CI passes]  →  Deploy Dev (auto)
                                          ↓
                                     Gate 1: Dev Lead / QA approves
                                          ↓
                                     Deploy UAT (same SHA)
                                          ↓
                                     Gate 2: UAT Lead + BA sign off
                                          ↓
                                     PR merged to main
```

### 6.2 What happens on each deploy, step by step

GitHub-hosted runner SSH-es into the target App VM using the environment-specific SSH key secret.

1. Current running image tag saved: `echo $CURRENT_TAG > /opt/tipms/prev_tag`
2. Cosign verification of the image before pulling (see Stage 6)
3. Flyway runs migrations against the target DB VM. If any migration fails, the deploy stops — the app is not touched
4. A `.env` file is written to `/opt/tipms/.env` with the secrets passed from GitHub
5. `docker compose pull` downloads the new images from GHCR
6. `docker compose up -d` restarts containers with the new images
7. Health check: calls `/health` on port 3000 every 10 seconds, up to 5 tries
8. Pass → notify team via WhatsApp. Fail → auto rollback to saved previous tag

### 6.3 Deploy script (`scripts/deploy-env.sh`)

This script is used for Dev, UAT, and Production (with different env vars). Pass the target environment as `$1` and image tag as `$2`.

```bash
#!/bin/bash
set -e

ENV=$1          # dev | uat | prod
NEW_TAG=$2
APP_DIR=/opt/tipms
REGISTRY=ghcr.io/nama-water

# Step 1: Verify image signature before pulling
cosign verify \
  $REGISTRY/nama-tipms-api:$NEW_TAG \
  --certificate-identity="https://github.com/nama-water/nama-tipms/.github/workflows/ci-cd.yml@refs/heads/main" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" || {
    echo "Image signature verification failed — aborting deploy"
    exit 1
  }

# Step 2: Save current version for rollback
PREV_TAG=$(cat $APP_DIR/current_tag 2>/dev/null || echo "latest")
echo $NEW_TAG > $APP_DIR/current_tag

# Step 3: Run migrations first — if this fails, app is untouched
flyway -url=jdbc:postgresql://$DB_HOST:5432/tipms \
  -user=$DB_USER -password=$DB_PASSWORD migrate

# Step 4: Write secrets to .env file
cat > $APP_DIR/.env << EOF
DB_HOST=$DB_HOST
DB_PASSWORD=$DB_PASSWORD
JWT_SECRET_KEY=$JWT_SECRET_KEY
FCM_SERVER_KEY=$FCM_SERVER_KEY
LOG_LEVEL=${LOG_LEVEL:-info}
ENVIRONMENT=$ENV
EOF
chmod 600 $APP_DIR/.env

# Step 5: Pull and start containers
export IMAGE_TAG=$NEW_TAG
docker compose -f $APP_DIR/docker-compose.yml pull
docker compose -f $APP_DIR/docker-compose.yml up -d

# Step 6: Health check inside the container network
for i in 1 2 3 4 5; do
  sleep 10
  if docker compose -f $APP_DIR/docker-compose.yml exec -T api \
      curl -sf http://localhost:3000/health; then
    echo "Deploy succeeded: $NEW_TAG on $ENV"
    exit 0
  fi
done

# Step 7: Rollback if health check never passed
echo "Health check failed — rolling back to $PREV_TAG"
export IMAGE_TAG=$PREV_TAG
docker compose -f $APP_DIR/docker-compose.yml up -d
exit 1
```

### 6.4 `docker-compose.yml`

```yaml
version: "3.9"
services:
  api:
    image: ghcr.io/nama-water/nama-tipms-api:${IMAGE_TAG}
    restart: unless-stopped
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:3000/health"]
      interval: 10s
      retries: 5
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"

  web:
    image: ghcr.io/nama-water/nama-tipms-web:${IMAGE_TAG}
    restart: unless-stopped
    ports: ["80:80"]

  pgbouncer:
    image: bitnami/pgbouncer:1.22.1
    restart: unless-stopped
    env_file: .env

  promtail:
    image: grafana/promtail:2.9.3
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /etc/promtail/config.yml:/etc/promtail/config.yml:ro
    restart: unless-stopped
```

> **Watch out:** The `.env` file on the VM contains real secrets. Ensure `/opt/tipms` is only readable by root (`chmod 700 /opt/tipms`). The deploy script already sets `chmod 600` on the `.env` file itself.

---

## 7. Production Deployment

Production deploys are completely manual. Nothing is ever auto-deployed to production.

### 7.1 Conditions before starting a production deploy

All **six** must be true (updated from v1.1 — Flyway undo script added as a required condition):

| # | Condition |
|---|-----------|
| 1 | Version tag exists in GHCR and has passed all pipeline stages |
| 2 | UAT has been running that version for at least 24 hours without errors |
| 3 | Two team members have approved in GitHub Environments |
| 4 | Nama client sign-off received via GitHub Issue |
| 5 | Database backup taken less than 4 hours ago |
| 6 | **Flyway undo script written, reviewed, and tested in UAT for this version** |

### 7.2 Flyway undo scripts — process and checklist

> **New in v1.2:** This section closes the highest-risk operational gap from v1.1. Flyway does not auto-undo migrations. If a migration runs as part of a broken deploy, rolling back the application code does not roll back the schema change. The old app may break on the new schema.

**For every database migration file, write a corresponding undo file:**

```
db/migrations/
  V3__add_lab_results_index.sql          ← forward migration
  U3__add_lab_results_index.sql          ← undo migration (new requirement)
```

**Naming convention:** `U{version}__{description}.sql` — same version number, same description, `U` prefix instead of `V`.

**Example pair:**

`V3__add_lab_results_index.sql`:
```sql
CREATE INDEX idx_lab_results_sample_id ON TEST_RESULTS(SAMPLE_ID);
ALTER TABLE SAMPLES ADD COLUMN processed_at TIMESTAMPTZ;
```

`U3__add_lab_results_index.sql`:
```sql
ALTER TABLE SAMPLES DROP COLUMN IF EXISTS processed_at;
DROP INDEX IF EXISTS idx_lab_results_sample_id;
```

**Rules for writing undo scripts:**
- Every `CREATE` has a corresponding `DROP IF EXISTS`
- Every `ADD COLUMN` has a corresponding `DROP COLUMN IF EXISTS`
- Every `ALTER TABLE ... ALTER COLUMN` has a corresponding alter back to the original type
- `DROP TABLE` forward migrations cannot be undone — mark these explicitly in the production gate checklist and require extra approval
- Test the undo in UAT before every production deploy: run the forward migration, verify the app works, run the undo, verify the old app version still works

**Pre-production deploy checklist addition:**

Add this item to the GitHub Issue used for production approval:

```
- [ ] Flyway undo script U{version}__*.sql exists and has been tested in UAT
      Command used to test: flyway -url=jdbc:postgresql://UAT_DB:5432/tipms undo
      Confirmed old app version (vX.Y.Z) still starts after undo: YES / NO
```

**If rollback is triggered and a migration has already run:**

```bash
# 1. Run the undo migration manually
flyway -url=jdbc:postgresql://$PROD_DB_HOST:5432/tipms \
  -user=$DB_USER -password=$DB_PASSWORD \
  undo

# 2. Then restart the old app version
export IMAGE_TAG=v1.2.9
docker compose -f /opt/tipms/docker-compose.yml up -d
```

### 7.3 How to trigger

GitHub → Actions → CI/CD Pipeline → Run workflow → select the version tag (e.g. `v1.3.0`) → Click Run workflow.

The workflow pauses at the approval gate — the two required reviewers receive a notification. Once both approve, the rolling deploy begins.

> **Watch out:** Production deploys run in the **Sunday 03:00–06:00 OST** maintenance window only. Emergency fixes outside this window need project manager sign-off.

### 7.4 Rolling deploy — what happens

Updates one VM at a time so at least one VM is always serving traffic. Zero downtime.

1. VM-1 removed from load balancer — traffic goes to VM-2 only
2. Cosign image verification on VM-1
3. Flyway migrations run against the production database
4. New images pulled and containers restarted on VM-1
5. Health check on VM-1 passes → VM-1 added back to load balancer
6. VM-2 removed — traffic goes to VM-1 only
7. Same steps 2–5 for VM-2
8. Both VMs on new version → monitor Grafana for 30 minutes

### 7.5 Rollback

```bash
# Option A: Trigger via workflow_dispatch with the previous tag
# GitHub → Actions → Run workflow → select v1.2.9

# Option B: SSH direct if pipeline is unavailable
export IMAGE_TAG=v1.2.9
docker compose -f /opt/tipms/docker-compose.yml up -d

# If a Flyway migration already ran, undo it first (see Section 7.2)
```

> **Tip:** GHCR keeps all tagged versions. All signed images can be verified before rolling back to confirm they are pipeline-produced.

---

## 8. Application Logging

Logs from all containers flow to Grafana Loki on the monitoring VM. Search logs in Grafana without SSH-ing into VMs.

### 8.1 How the pipeline works

```
Node.js API (pino JSON)
  → Docker json-file driver
  → Promtail (on each App VM)
  → Loki (on monitoring-vm)
  → Grafana
```

### 8.2 pino setup in the Node.js API

```js
const pino = require("pino");
const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  formatters: {
    level: (label) => ({ level: label }),
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

// Always include context as the first argument so logs are searchable in Loki
logger.info({ userId: "abc123", permitId: "P-2026-001" }, "permit issued");
logger.error({ err: error, req: { url, method } }, "request failed");
```

### 8.3 Promtail configuration

Save as `/etc/promtail/config.yml` on each App VM. Replace `MONITORING_VM_IP` with the actual IP from Section 2.3.

> **Watch out:** The Loki push URL must be a real IP address, not a placeholder hostname. Using a descriptive name will fail silently — Promtail will drop all logs with no visible error.

```yaml
server:
  http_listen_port: 9080

clients:
  - url: http://MONITORING_VM_IP:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: [__meta_docker_container_name]
        target_label: container
      - source_labels: [__meta_docker_compose_service]
        target_label: service
```

> **Tip:** After starting Promtail, verify logs are arriving: in Grafana, go to Explore → select Loki → run `{job="docker"}` — you should see log lines within 30 seconds of app activity.

---

## 9. Monitoring Setup

### 9.1 Install the monitoring stack on monitoring-vm

```bash
curl -fsSL https://get.docker.com | bash
mkdir -p /opt/monitoring && cd /opt/monitoring
# Create docker-compose.yml (see below), then:
docker compose up -d
```

| Service | Port | What it does |
|---------|------|--------------|
| Prometheus | 9090 | Scrapes metrics from all VMs every 15 seconds |
| Grafana | 3000 | Dashboards and alert rules — access via VPN only |
| Loki | 3100 | Receives and stores logs from Promtail on App VMs |
| Alertmanager | 9093 | Routes alerts to WhatsApp and PagerDuty |
| Uptime Kuma | 3001 | Internal health checks from inside the VPC |

### 9.2 External uptime monitoring

> **New in v1.2:** Uptime Kuma is deployed inside the VPC and cannot detect VPC-level outages or load balancer failures. External monitoring from outside the network is required.

**Required setup:** Subscribe to **Better Uptime** (https://betteruptime.com) or **Freshping** (https://freshping.io). Configure it to:

1. HTTP-check `https://permit.nama-water.om` every 1 minute from at least 3 geographic locations
2. Alert the on-call engineer via WhatsApp and phone call if the check fails from 2+ locations for more than 2 consecutive minutes
3. Alert the on-call engineer via WhatsApp and phone call if the UAT environment `https://uat.permit.nama-water.om` is down for more than 5 minutes

> **Why two levels:** Uptime Kuma detects container-level and application-level failures (the app crashed, wrong response code). The external service detects infrastructure-level failures (the whole VM is down, the load balancer is unreachable from the internet, DNS has broken). Both are needed.

### 9.3 First alerts to configure in Grafana

- API container down for more than 1 minute → WhatsApp alert to on-call
- API response time above 3 seconds for more than 5 minutes → WhatsApp alert
- Database disk usage above 80% → WhatsApp alert
- Production deploy succeeded or failed → WhatsApp notification to team channel
- **CI/CD pipeline failure** → WhatsApp alert (now handled by the `notify-on-failure` job in the pipeline — no Grafana rule needed for this)

---

## 10. Mobile App Pipeline

The mobile pipeline is in `.github/workflows/mobile-build.yml`. All jobs run on `runs-on: ubuntu-latest` except the iOS Codemagic step, which delegates to Codemagic's macOS fleet.

| Stage | What it does | Time |
|-------|-------------|------|
| Lint + Type check | `flutter analyze` + TypeScript type check | ~1 min |
| Unit tests | `flutter test` — validators, API transformers, nav guards | ~2 min |
| Android build | `flutter build appbundle` — signs with `ANDROID_KEYSTORE` secret | ~8 min |
| iOS — Codemagic | Sends build request to Codemagic; polls every 60s for result; GitHub job fails if CM fails | ~20 min |
| Distribute | Android → Firebase App Distribution, iOS → TestFlight via Codemagic | ~3 min |
| Manual gate | 2 approvals required before store release — cannot be undone | Human |
| Store release | Android → Play Store via Fastlane, iOS → App Store Connect | ~5 min |

> **Watch out:** Store releases cannot be rolled back. Once an APK is live on the Play Store, users download it immediately. The only fix is a new release. Test thoroughly on Firebase App Distribution before approving the store release gate.

---

## 11. Known Gaps — All Resolved

All five gaps from v1.1 are now closed. This table records what was done for traceability.

| Gap | Status | Resolution |
|-----|--------|-----------|
| DAST — Dynamic Testing | ✅ Resolved | OWASP ZAP Baseline scan added as Stage 7, runs after every Dev deploy. Report uploaded as pipeline artifact. See Section 5, Stage 7. |
| Flyway undo scripts | ✅ Resolved | Undo script process documented in Section 7.2. Undo script verified in UAT is now a required condition (condition 6) before any production deploy is approved. |
| CI failure notifications | ✅ Resolved | `notify-on-failure` job added to pipeline (Section 5). Sends WhatsApp message with failed stage name and direct link to run logs. |
| Image signing | ✅ Resolved | Cosign keyless signing added to Stage 6 (Section 5). Signature verification added to deploy scripts in Section 6.3. Unsigned images are rejected at deploy time. |
| External uptime monitoring | ✅ Resolved | Better Uptime / Freshping subscription documented in Section 9.2 with specific check configuration. Uptime Kuma retained for internal checks; external service covers VPC-level outages. |

---

## 12. Rollback Decision Tree

Something went wrong after a deploy. Use this to decide what to do without panicking.

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Health check failed during Dev/UAT deploy | New code crashed on startup | Automatic rollback already happened — check Loki for the startup error |
| Dev/UAT is up but behaving wrongly | Logic bug in new code | Trigger a new deploy with the previous tag manually |
| Cosign verification failed at deploy time | Image was not produced by the pipeline or was tampered with | Stop the deploy. Investigate the GHCR image provenance. Re-run the pipeline to produce a fresh verified image. |
| Prod health check failed mid-rolling deploy | New code crashed on the VM being updated | That VM auto-rolled back — the other VM was never touched, service continues. Fix the bug and redeploy. |
| Prod deploy succeeded but users report errors | Bug that health check did not catch | Trigger `workflow_dispatch` with the previous version tag immediately. Do not wait. |
| DB queries failing after deploy | Migration broke something | Run Flyway undo script manually (see Section 7.2), then roll back the app code |
| App works but no logs appearing in Loki | Promtail not running or wrong Loki IP | SSH into App VM: `docker logs promtail` — look for connection errors |
| External uptime monitor alerts but internal checks pass | Load balancer or VPC-level failure | Escalate to Omantel cloud support. SSH into VMs via VPN to investigate. |
| ZAP DAST scan fails on a known false positive | ZAP rule too strict for this app | Add the rule ID to `.zap/rules.tsv` with `IGNORE` status, document the reason, and re-run the pipeline |

---

*End of document — v1.2 | GitHub-hosted runner + all gaps resolved*
