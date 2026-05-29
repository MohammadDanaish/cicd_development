# Nama TIPMS — CI/CD Template Hub: Usage & Testing Guide

| Field    | Value                                          |
|----------|------------------------------------------------|
| Version  | v1.0                                           |
| Date     | May 2026                                       |
| Audience | DevOps / Backend engineers onboarding app repos |
| Repo     | `nama-water/cicd_development`                  |

---

## Table of Contents

1. [How It Works — Big Picture](#1-how-it-works--big-picture)
2. [One-Time Setup (Do This Once)](#2-one-time-setup-do-this-once)
3. [Onboarding an App Repo](#3-onboarding-an-app-repo)
4. [Secrets and Variables Reference](#4-secrets-and-variables-reference)
5. [End-to-End Workflow Walkthrough](#5-end-to-end-workflow-walkthrough)
6. [Testing Steps — Phase by Phase](#6-testing-steps--phase-by-phase)
7. [Triggering Deployments](#7-triggering-deployments)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. How It Works — Big Picture

This repo is a **centralised CI/CD template hub**. All pipeline logic lives here. App repos (FE, BE, Mobile) each have a small caller workflow that delegates to these templates — exactly like Azure DevOps `extends: template`.

```
cicd_development repo (templates)          App repos (callers)
─────────────────────────────────          ─────────────────────────────────
.github/workflows/
  template-ci-node.yml          ◄──────    fe-repo/.github/workflows/ci.yml
  template-ci-node.yml          ◄──────    be-repo/.github/workflows/ci.yml
  template-deploy.yml           ◄──────    be-repo/.github/workflows/deploy.yml
  template-release.yml          ◄──────    fe-repo + be-repo ci.yml (on main)
  template-dast.yml             ◄──────    be-repo/.github/workflows/ci.yml
  template-ci-flutter.yml       ◄──────    mobile-repo/.github/workflows/ci.yml
```

**Why BE repo owns deploy:**
Both the API and Web containers run together via `docker-compose.yml`. The BE repo triggers deploys and passes both `api_tag` (its own SHA) and `web_tag` (FE image tag). This is the single coordination point.

**Image tag flow:**

```
FE feature push → build nama-tipms-web:{sha} → tag as dev-latest
BE feature push → build nama-tipms-api:{sha} → deploy dev with api:{sha} + web:dev-latest
                                              → DAST on dev
Merge to main   → release → semver tag → cosign sign
UAT deploy      → workflow_dispatch → pass specific api_tag + web_tag
Prod deploy     → workflow_dispatch → pass version tags (e.g. v1.3.0)
```

---

## 2. One-Time Setup (Do This Once)

Complete every step in this section before any app repo is onboarded.

### 2.1 Set template repo visibility to Internal

This allows every repo in the `nama-water` org to call the templates using its own `GITHUB_TOKEN` — no personal access token needed.

```
GitHub → nama-water/cicd_development → Settings → Danger Zone
→ Change repository visibility → Internal
```

> **Why Internal not Private:** Private repos cannot be referenced by reusable workflows from other repos in the same org unless you configure additional access. Internal repos can.

### 2.2 Create GitHub Environments in the BE repo

Environments hold the approval gates. Create these in the **BE repo only** — it owns all deploys.

```
GitHub → nama-water/be-repo → Settings → Environments → New environment
```

| Environment   | Required reviewers                        | Deployment branches     |
|---------------|-------------------------------------------|-------------------------|
| `dev`         | None — deploys automatically              | `feature/**`, `fix/**`  |
| `uat`         | Dev Lead + QA Lead (1 must approve)       | Any                     |
| `production`  | 2 team members (both must approve)        | Tags matching `v*.*.*`  |
| `distribution`| None — auto after android + iOS pass      | Any                     |
| `store-release`| 2 team members (cannot be undone)        | Any                     |

### 2.3 Install GitHub App — GHCR access

GHCR (GitHub Container Registry) access is automatic via `GITHUB_TOKEN`. You do not need to create a separate token, as long as:

```
GitHub → nama-water org → Settings → Actions → General
→ Workflow permissions → Read and write permissions → Save
```

Set this on both the template repo and every app repo.

### 2.4 Verify org-level Actions settings

```
GitHub → nama-water org → Settings → Actions → General
→ Allow all actions and reusable workflows → Save
→ Allow GitHub Actions to create and approve pull requests → ON
```

---

## 3. Onboarding an App Repo

Follow this section for each app repo you want to connect to the templates.

### 3.1 FE repo setup

**Step 1 — Copy the caller workflow**

```bash
# In fe-repo root
mkdir -p .github/workflows
# Copy from cicd_development/caller-examples/fe-repo/
cp path/to/cicd_development/caller-examples/fe-repo/.github/workflows/ci.yml \
   .github/workflows/ci.yml
```

Open `.github/workflows/ci.yml` and confirm the `uses:` path matches your org:
```yaml
uses: nama-water/cicd_development/.github/workflows/template-ci-node.yml@main
```

**Step 2 — Add Dockerfile.web**

Copy `cicd_development/docker/Dockerfile.web` and `cicd_development/docker/nginx.conf` to the FE repo root. Adjust `npm run build` output directory if yours differs from `dist`.

**Step 3 — Add supporting config files**

| File | Source | Notes |
|------|--------|-------|
| `.dockerignore` | `cicd_development/.dockerignore` | Copy as-is |
| `.commitlintrc.json` | `cicd_development/.commitlintrc.json` | Update scopes if needed |
| `release.config.js` | `cicd_development/release.config.js` | Copy as-is |
| `.zap/rules.tsv` | `cicd_development/.zap/rules.tsv` | Copy as-is |

**Step 4 — Add secrets to FE repo**

```
GitHub → nama-water/fe-repo → Settings → Secrets and variables → Actions
```

| Secret | Value |
|--------|-------|
| `SNYK_TOKEN` | From snyk.io → Account Settings → API Token |
| `WHATSAPP_API_TOKEN` | WhatsApp Business API token |
| `WHATSAPP_CHANNEL_ID` | WhatsApp group/channel ID for alerts |

**Step 5 — Add `package.json` scripts**

The template expects these script names exactly:

```json
{
  "scripts": {
    "lint": "eslint . --ext .vue,.js,.ts",
    "build": "vite build"
  }
}
```

`prettier --check .` runs directly — no script needed.

---

### 3.2 BE repo setup

**Step 1 — Copy caller workflows**

```bash
mkdir -p .github/workflows
cp path/to/cicd_development/caller-examples/be-repo/.github/workflows/ci.yml \
   .github/workflows/ci.yml
cp path/to/cicd_development/caller-examples/be-repo/.github/workflows/deploy.yml \
   .github/workflows/deploy.yml
```

**Step 2 — Add Dockerfile.api**

Copy `cicd_development/docker/Dockerfile.api` to the BE repo root.

**Step 3 — Add docker-compose.yml on each app VM**

The `docker-compose.yml` lives on the VMs, not in the BE repo. Copy `cicd_development/docker/docker-compose.yml` to `/opt/tipms/docker-compose.yml` on every app VM:

```bash
scp -i ~/.ssh/your_key cicd_development/docker/docker-compose.yml \
    ubuntu@DEV_APP_HOST:/opt/tipms/docker-compose.yml
scp -i ~/.ssh/your_key cicd_development/docker/docker-compose.yml \
    ubuntu@UAT_APP_HOST:/opt/tipms/docker-compose.yml
scp -i ~/.ssh/your_key cicd_development/docker/docker-compose.yml \
    ubuntu@PROD_APP_HOST_1:/opt/tipms/docker-compose.yml
scp -i ~/.ssh/your_key cicd_development/docker/docker-compose.yml \
    ubuntu@PROD_APP_HOST_2:/opt/tipms/docker-compose.yml
```

**Step 4 — Add supporting config files**

Same as FE repo: `.dockerignore`, `.commitlintrc.json`, `release.config.js`, `.zap/rules.tsv`.

**Step 5 — Add secrets to BE repo**

```
GitHub → nama-water/be-repo → Settings → Secrets and variables → Actions
```

| Secret | Value |
|--------|-------|
| `SNYK_TOKEN` | From snyk.io |
| `DB_PASSWORD` | PostgreSQL app user password |
| `JWT_SECRET_KEY` | 64-char random string: `openssl rand -hex 32` |
| `FCM_SERVER_KEY` | Firebase Cloud Messaging server key |
| `SRV_SSH_KEY` | Private SSH key that reaches all app VMs |
| `WHATSAPP_API_TOKEN` | WhatsApp Business API token |
| `WHATSAPP_CHANNEL_ID` | WhatsApp group/channel ID |

**Step 6 — Add variables to BE repo**

```
GitHub → nama-water/be-repo → Settings → Secrets and variables → Actions → Variables tab
```

| Variable | Value |
|----------|-------|
| `DEV_APP_HOST` | Dev app VM private IP e.g. `10.0.1.10` |
| `DEV_DB_HOST` | Dev DB VM private IP e.g. `10.0.1.20` |
| `UAT_APP_HOST` | UAT app VM private IP |
| `UAT_DB_HOST` | UAT DB VM private IP |
| `PROD_APP_HOST_1` | Prod app VM 1 private IP |
| `PROD_APP_HOST_2` | Prod app VM 2 private IP |
| `PROD_DB_HOST` | Prod DB VM private IP |

**Step 7 — Add `package.json` scripts**

```json
{
  "scripts": {
    "lint": "eslint . --ext .js,.ts",
    "build": "tsc",
    "test:integration": "jest --testPathPattern=integration"
  }
}
```

**Step 8 — Prepare app VMs**

SSH into each VM and run:

```bash
# Install Docker
curl -fsSL https://get.docker.com | bash
usermod -aG docker ubuntu

# Install Flyway
wget -qO- https://download.red-gate.com/maven/release/com/redgate/flyway/flyway-commandline/10.12.0/flyway-commandline-10.12.0-linux-x64.tar.gz | tar xz
mv flyway-10.12.0 /opt/flyway
ln -s /opt/flyway/flyway /usr/local/bin/flyway

# Install Cosign
curl -sLO https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
chmod +x cosign-linux-amd64
mv cosign-linux-amd64 /usr/local/bin/cosign

# Create app directory
mkdir -p /opt/tipms/db/migrations
chmod 700 /opt/tipms
```

---

### 3.3 Mobile repo setup

**Step 1 — Copy caller workflow**

```bash
mkdir -p .github/workflows
cp path/to/cicd_development/caller-examples/mobile-repo/.github/workflows/ci.yml \
   .github/workflows/ci.yml
```

**Step 2 — Add secrets and variables**

| Secret | Value |
|--------|-------|
| `ANDROID_KEYSTORE` | `base64 < upload-keystore.jks` |
| `ANDROID_KEY_ALIAS` | Key alias inside keystore |
| `ANDROID_KEY_PASSWORD` | Key password |
| `ANDROID_STORE_PASSWORD` | Keystore password |
| `CODEMAGIC_API_TOKEN` | From codemagic.io → Teams → Integrations |
| `FIREBASE_TOKEN` | From Firebase CLI: `firebase login:ci` |
| `PLAY_STORE_SERVICE_ACCOUNT` | Google Play service account JSON |

| Variable | Value |
|----------|-------|
| `CODEMAGIC_APP_ID` | From Codemagic app settings |
| `FIREBASE_APP_ID` | From Firebase project settings |

---

## 4. Secrets and Variables Reference

### 4.1 Template repo (`cicd_development`) — no secrets needed

The template repo itself does not need secrets. All secrets are defined in the calling app repos and flow through `secrets: inherit`.

### 4.2 Complete secrets map per repo

| Secret | FE repo | BE repo | Mobile repo |
|--------|---------|---------|-------------|
| `SNYK_TOKEN` | ✅ | ✅ | — |
| `DB_PASSWORD` | — | ✅ | — |
| `JWT_SECRET_KEY` | — | ✅ | — |
| `FCM_SERVER_KEY` | — | ✅ | — |
| `SRV_SSH_KEY` | — | ✅ | — |
| `WHATSAPP_API_TOKEN` | ✅ | ✅ | — |
| `WHATSAPP_CHANNEL_ID` | ✅ | ✅ | — |
| `ANDROID_KEYSTORE` | — | — | ✅ |
| `ANDROID_KEY_ALIAS` | — | — | ✅ |
| `ANDROID_KEY_PASSWORD` | — | — | ✅ |
| `ANDROID_STORE_PASSWORD` | — | — | ✅ |
| `CODEMAGIC_API_TOKEN` | — | — | ✅ |
| `FIREBASE_TOKEN` | — | — | ✅ |
| `PLAY_STORE_SERVICE_ACCOUNT` | — | — | ✅ |

### 4.3 Complete variables map per repo

| Variable | FE repo | BE repo | Mobile repo |
|----------|---------|---------|-------------|
| `DEV_APP_HOST` | — | ✅ | — |
| `DEV_DB_HOST` | — | ✅ | — |
| `UAT_APP_HOST` | — | ✅ | — |
| `UAT_DB_HOST` | — | ✅ | — |
| `PROD_APP_HOST_1` | — | ✅ | — |
| `PROD_APP_HOST_2` | — | ✅ | — |
| `PROD_DB_HOST` | — | ✅ | — |
| `CODEMAGIC_APP_ID` | — | — | ✅ |
| `FIREBASE_APP_ID` | — | — | ✅ |

---

## 5. End-to-End Workflow Walkthrough

### 5.1 Developer pushes a feature branch

```
Developer: git push origin feature/INS-123
```

**FE repo triggers:**
```
ci.yml
  └── template-ci-node.yml
        ├── validate       (lint, prettier, gitleaks, snyk SCA)
        ├── test           (vitest + coverage)
        ├── sast           (CodeQL)
        ├── build          (Dockerfile.web → nama-tipms-web:{sha} → GHCR)
        └── image-scan     (Trivy + Snyk container)
              ↓ passes
        FE image tagged:
          ghcr.io/nama-water/nama-tipms-web:{sha}
          ghcr.io/nama-water/nama-tipms-web:dev-latest
```

**BE repo triggers (simultaneously):**
```
ci.yml
  └── template-ci-node.yml    (same stages + integration tests with Postgres)
        ↓ image-scan passes
  └── template-deploy.yml     (environment: dev)
        ├── Cosign verify api image
        ├── Flyway migrate dev DB
        ├── docker compose up (api:{sha} + web:dev-latest)
        └── health check → notify WhatsApp
              ↓ deploy passes
  └── template-dast.yml
        └── OWASP ZAP scan on https://dev.permit.nama-water.om
```

**Total time: ~15–18 minutes**

---

### 5.2 Developer opens PR to main

No deploy happens. CI runs validate → test → SAST → build → image-scan to confirm the code is mergeable. GitHub enforces all 5 status checks before merge is allowed.

```
ci.yml → template-ci-node.yml (all stages, no deploy-dev, no release)
```

---

### 5.3 PR merges to main

```
ci.yml (on push to main)
  └── template-ci-node.yml    (full CI runs again on merged code)
        ↓ image-scan passes
  └── template-release.yml
        ├── npx semantic-release → creates GitHub release + CHANGELOG + bumps version
        ├── re-tags image: {sha} → {v1.3.0} and latest
        └── cosign sign {sha} and {v1.3.0}
```

After this completes, a signed, versioned image is ready in GHCR. The team is notified of the new version.

---

### 5.4 UAT deploy (manual)

A team member goes to the BE repo Actions tab, selects the **Deploy** workflow, and fills in:

- `environment`: `uat`
- `api_tag`: the commit SHA or version from the feature branch (e.g. `a3f9c12`)
- `web_tag`: the FE commit SHA from the same feature branch

GitHub shows the UAT approval gate. Dev Lead and/or QA approves. Then:

```
deploy.yml
  └── template-deploy.yml (environment: uat)
        ├── Cosign verify
        ├── Flyway migrate UAT DB
        ├── docker compose up (api:{sha} + web:{sha})
        ├── health check
        └── WhatsApp notification
              ↓
  └── template-dast.yml
        └── OWASP ZAP scan on https://uat.permit.nama-water.om
```

---

### 5.5 Production deploy (manual)

Only after the PR is merged to main and a signed version tag exists in GHCR.

A team member triggers the **Deploy** workflow:

- `environment`: `production`
- `api_tag`: `v1.3.0`
- `web_tag`: `v1.3.0`

GitHub shows the production approval gate. Two team members approve. Rolling deploy begins — VM-1 updated and healthy first, then VM-2. Both must pass health check or the failing VM auto-rolls back.

---

## 6. Testing Steps — Phase by Phase

Work through these phases in order. Each phase is a checkpoint — do not proceed to the next until all steps in the current phase pass.

---

### Phase 1 — Local Syntax Validation (no GitHub needed)

**Goal:** Catch YAML errors before pushing.

**Step 1.1 — Install actionlint**

```bash
# Windows (winget)
winget install rhysd.actionlint

# Mac
brew install actionlint
```

**Step 1.2 — Lint all template workflows**

```bash
cd d:\nama_project\repo\cicd_development
actionlint .github/workflows/template-ci-node.yml
actionlint .github/workflows/template-ci-flutter.yml
actionlint .github/workflows/template-deploy.yml
actionlint .github/workflows/template-release.yml
actionlint .github/workflows/template-dast.yml
```

Expected output: no errors. If errors appear, fix them before continuing.

**Step 1.3 — Lint caller workflows**

```bash
actionlint caller-examples/fe-repo/.github/workflows/ci.yml
actionlint caller-examples/be-repo/.github/workflows/ci.yml
actionlint caller-examples/be-repo/.github/workflows/deploy.yml
actionlint caller-examples/mobile-repo/.github/workflows/ci.yml
```

**Step 1.4 — Validate deploy script**

```bash
bash -n scripts/deploy-env.sh
```

Expected: exits with no output (no syntax errors).

**Step 1.5 — Validate docker-compose**

```bash
cd d:\nama_project\repo\cicd_development\docker
docker compose config
```

Expected: prints the resolved compose config with no errors.

**Checkpoint:** All five actionlint runs clean, bash -n clean, docker compose config clean. Proceed to Phase 2.

---

### Phase 2 — GitHub Structure Validation (push to GitHub, no app code needed)

**Goal:** Confirm GitHub recognises the workflows and the template/caller linkage is correct.

**Step 2.1 — Push the template repo to GitHub**

```bash
cd d:\nama_project\repo\cicd_development
git add .
git commit -m "ci: add reusable pipeline templates v1.0"
git push origin main
```

**Step 2.2 — Verify templates appear in GitHub**

```
GitHub → nama-water/cicd_development → Actions tab
```

You should see all 5 template workflows listed. They will show as "This workflow has no trigger" — that is correct. They are only triggered when called by other repos.

**Step 2.3 — Create a test caller repo**

Create a minimal test repo in the GitHub org:

```
GitHub → New repository → nama-water/pipeline-test → Internal
```

Create `.github/workflows/test-ci.yml` with this content:

```yaml
name: Test CI Template

on:
  push:
    branches: [main]

jobs:
  ci:
    uses: nama-water/cicd_development/.github/workflows/template-ci-node.yml@main
    with:
      image_name: pipeline-test-image
      dockerfile: Dockerfile.test
      run_integration_tests: false
    secrets: inherit
```

Create a minimal `package.json`:

```json
{
  "name": "pipeline-test",
  "version": "1.0.0",
  "scripts": {
    "lint": "echo 'lint ok'",
    "build": "echo 'build ok'"
  }
}
```

Create a minimal `Dockerfile.test`:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY . .
RUN echo "test build"
```

Push to main and watch the Actions tab on `pipeline-test` repo.

**Step 2.4 — What to look for**

```
Actions → Test CI Template → latest run
  ✅ validate  (will fail on npm audit / snyk if no real deps — that is fine for now)
  ✅ test      (will fail on vitest if not installed — fine for now)
```

The important thing at this phase: the workflow **starts and calls the template**. You should see the jobs appear under the caller repo's Actions run, not the template repo. If you see "Error: Unable to fetch reusable workflow" — the template repo is not set to Internal. Fix that first.

**Checkpoint:** The caller repo's workflow starts and shows jobs from the template. Proceed to Phase 3.

---

### Phase 3 — CI Template with Real App Code

**Goal:** Validate → Test → SAST → Build → Image Scan all pass on the FE repo.

**Step 3.1 — Add SNYK_TOKEN secret to FE repo**

```
GitHub → nama-water/fe-repo → Settings → Secrets → New secret
Name: SNYK_TOKEN
Value: (from snyk.io)
```

**Step 3.2 — Copy the FE caller workflow**

```bash
# In fe-repo
cp cicd_development/caller-examples/fe-repo/.github/workflows/ci.yml \
   .github/workflows/ci.yml
cp cicd_development/docker/Dockerfile.web .
cp cicd_development/docker/nginx.conf .
cp cicd_development/.dockerignore .
cp cicd_development/.commitlintrc.json .
```

**Step 3.3 — Create a feature branch and push**

```bash
git checkout -b feature/pipeline-test
git add .
git commit -m "ci: add CI pipeline"
git push origin feature/pipeline-test
```

**Step 3.4 — Watch the run**

```
GitHub → fe-repo → Actions → CI → latest run
```

Check each job passes in order:
```
validate  → should pass if lint + prettier are configured
test      → should pass if vitest is installed
sast      → CodeQL — first run takes ~5 minutes
build     → should produce an image in GHCR
image-scan → should pass if no CRITICAL/HIGH CVEs in base image
```

**Step 3.5 — Verify image in GHCR**

```
GitHub → fe-repo → Packages (or github.com/orgs/nama-water/packages)
```

You should see `nama-tipms-web` with a tag matching the commit SHA.

**Step 3.6 — Repeat for BE repo**

Same steps. For BE, also confirm the `integration-test` job appears and runs with the Postgres service container.

**Checkpoint:** Both FE and BE repos pass all CI stages. Images appear in GHCR. Proceed to Phase 4.

---

### Phase 4 — Deploy Template (Dev environment)

**Goal:** Confirm the deploy template SSHs into dev-app-vm, runs migrations, starts containers, and health check passes.

**Step 4.1 — Provision dev-app-vm and dev-db-vm**

Follow Section 3.2 Step 8 to install Docker, Flyway, and Cosign on dev-app-vm.

**Step 4.2 — Start PostgreSQL on dev-db-vm**

```bash
ssh ubuntu@DEV_DB_HOST
docker run -d \
  --name postgres \
  --restart unless-stopped \
  -e POSTGRES_PASSWORD=your_db_password \
  -e POSTGRES_DB=tipms \
  -p 5432:5432 \
  postgres:16
```

**Step 4.3 — Add the `SRV_SSH_KEY` secret to BE repo**

Generate a key pair if needed:

```bash
ssh-keygen -t ed25519 -C "cicd-deploy" -f ~/.ssh/cicd_deploy
# Add ~/.ssh/cicd_deploy.pub to authorized_keys on all app VMs
cat ~/.ssh/cicd_deploy.pub | ssh ubuntu@DEV_APP_HOST "cat >> ~/.ssh/authorized_keys"
```

Add the private key to BE repo secrets:
```
Secret name: SRV_SSH_KEY
Value: (contents of ~/.ssh/cicd_deploy — the private key)
```

**Step 4.4 — Add VM variables to BE repo**

```
DEV_APP_HOST = 10.0.x.x  (dev-app-vm private IP)
DEV_DB_HOST  = 10.0.x.x  (dev-db-vm private IP)
```

**Step 4.5 — Push a feature branch from BE repo**

```bash
git checkout -b feature/pipeline-deploy-test
git push origin feature/pipeline-deploy-test
```

Watch the Actions run:
```
ci.yml
  ✅ template-ci-node.yml (all stages)
  ✅ template-deploy.yml (environment: dev)
       → cosign verify
       → flyway migrate
       → docker compose up
       → health check
  ✅ template-dast.yml
       → ZAP scan report uploaded as artifact
```

**Step 4.6 — Verify containers are running on dev-app-vm**

```bash
ssh ubuntu@DEV_APP_HOST
docker compose -f /opt/tipms/docker-compose.yml ps
```

Expected:
```
NAME        IMAGE                                   STATUS
api         ghcr.io/nama-water/nama-tipms-api:sha   Up (healthy)
web         ghcr.io/nama-water/nama-tipms-web:...   Up
pgbouncer   bitnami/pgbouncer:1.22.1                Up
promtail    grafana/promtail:2.9.3                  Up
```

**Step 4.7 — Verify health endpoint**

```bash
curl http://DEV_APP_HOST:3000/health
# Expected: {"status":"ok"}
```

**Checkpoint:** Dev deploy succeeds, containers healthy, ZAP report uploaded. Proceed to Phase 5.

---

### Phase 5 — Release Template (main branch)

**Goal:** Confirm semantic-release creates a version tag and Cosign signs the image.

**Step 5.1 — Merge the feature branch to main via PR**

On GitHub, open a PR from `feature/pipeline-deploy-test` → `main`. Add 2 approvals. Merge.

Watch the Actions run on main:
```
ci.yml (on push to main)
  ✅ template-ci-node.yml
  ✅ template-release.yml
       → npx semantic-release (creates v1.0.0 if this is the first run)
       → docker tag :sha → :v1.0.0 and :latest
       → docker push :v1.0.0 and :latest
       → cosign sign :sha and :v1.0.0
```

**Step 5.2 — Verify version tag in GHCR**

```
GitHub → Packages → nama-tipms-api
```

You should see tags: `{sha}`, `v1.0.0`, `latest`.

**Step 5.3 — Verify Cosign signature**

```bash
# Run locally with cosign installed
cosign verify \
  ghcr.io/nama-water/nama-tipms-api:v1.0.0 \
  --certificate-identity="https://github.com/nama-water/be-repo/.github/workflows/ci.yml@refs/heads/main" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

Expected output includes: `The following checks were performed...` with a tlog entry.

**Checkpoint:** Version tag exists, cosign verify passes. Proceed to Phase 6.

---

### Phase 6 — UAT and Production Deploy

**Goal:** Confirm manual dispatch deploys work with approval gates.

**Step 6.1 — Add UAT VM variables and provision uat-app-vm**

Same steps as dev (Section 4.1–4.4) for UAT VMs.

**Step 6.2 — Trigger UAT deploy**

```
GitHub → be-repo → Actions → Deploy → Run workflow
  environment: uat
  api_tag: {commit sha from feature branch}
  web_tag: {fe commit sha}
```

GitHub will pause at the `uat` environment approval gate. The Dev Lead must approve before it proceeds.

After approval — watch the deploy job run and complete.

**Step 6.3 — Trigger Production deploy**

```
GitHub → be-repo → Actions → Deploy → Run workflow
  environment: production
  api_tag: v1.0.0
  web_tag: v1.0.0
```

Both prod-app-vm-1 and prod-app-vm-2 are updated sequentially (rolling deploy). Watch the log carefully — you should see each host succeed before the next one starts.

**Step 6.4 — Verify WhatsApp notifications**

After each deploy (success or failure), a WhatsApp message should arrive in the configured channel. Confirm the message includes the environment, image tags, and a direct link to the Actions run.

**Checkpoint:** UAT and Production deploys complete with approval gates working. All phases done.

---

## 7. Triggering Deployments

### 7.1 Dev — automatic

No manual trigger needed. Any push to `feature/**` or `fix/**` in the BE repo triggers a dev deploy automatically after CI passes.

### 7.2 UAT — manual dispatch

```
GitHub → be-repo → Actions (left sidebar) → Deploy → Run workflow (top right)
```

Fill in:
- `environment`: `uat`
- `api_tag`: the commit SHA from the feature branch you want in UAT
  - Find it: BE repo → Commits → copy the 7-char or full SHA
- `web_tag`: the FE commit SHA for the same feature
  - Find it: FE repo → Packages → find the image tagged with the feature branch SHA

> **How to find the right tags:** On the feature branch CI run in each repo, look at the "build" job logs — it prints the tag used: `ghcr.io/nama-water/nama-tipms-api:{sha}`. Copy that SHA.

### 7.3 Production — manual dispatch after PR merge

```
GitHub → be-repo → Actions → Deploy → Run workflow
  environment: production
  api_tag: v1.0.0   ← version from semantic-release, find in GHCR
  web_tag: v1.0.0   ← same version from FE repo release
```

Before triggering, verify all 6 production conditions from Section 7.1 of the implementation guide are met, especially that the Flyway undo script is tested in UAT.

---

## 8. Troubleshooting

### Error: "Unable to fetch reusable workflow"

**Cause:** Template repo is Private, not Internal.

**Fix:**
```
GitHub → nama-water/cicd_development → Settings → Danger Zone
→ Change visibility → Internal
```

---

### Error: "Resource not accessible by integration" on GHCR push

**Cause:** Workflow permissions in the org or repo are set to read-only.

**Fix:**
```
GitHub → nama-water org → Settings → Actions → General
→ Workflow permissions → Read and write permissions → Save
```

Also check it on the specific repo:
```
GitHub → [repo] → Settings → Actions → General → Workflow permissions
```

---

### Error: "cosign verify" fails at deploy time

**Cause 1:** The image was not built from `main` branch. Feature branch images are not signed — only images released via `template-release.yml` (which runs on main) are signed.

**Fix:** For dev deploys, the template verifies the API image. If you are testing with a feature branch SHA, the image does not have a cosign signature yet. To test without signing temporarily, remove the cosign verify block from the template. Add it back before UAT.

**Cause 2:** The `--certificate-identity` URL in `template-deploy.yml` does not match your actual repo path.

**Fix:** Open `template-deploy.yml` and update:
```yaml
--certificate-identity="https://github.com/nama-water/nama-tipms-be/.github/workflows/ci.yml@refs/heads/main"
```
Replace `nama-tipms-be` with your actual BE repo name.

---

### Error: "Host key verification failed" during SSH

**Cause:** `StrictHostKeyChecking=no` should suppress this, but sometimes the known_hosts cache on the GitHub runner causes issues.

**Fix:** Ensure the deploy step includes `-o StrictHostKeyChecking=no`. If already there, also add `-o UserKnownHostsFile=/dev/null`:
```bash
ssh -i /tmp/deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$HOST ...
```

---

### Error: Health check fails, containers roll back

**Step 1:** Check what is wrong:
```bash
ssh ubuntu@DEV_APP_HOST
docker compose -f /opt/tipms/docker-compose.yml logs api --tail=50
```

**Step 2:** Common causes:
- `.env` file missing required variable → API crashes on startup
- Database migration failed but deploy continued (should not happen — check Flyway logs)
- Wrong DB_HOST — confirm the private IP is correct in the GitHub variable

**Step 3:** After fixing, re-push the feature branch. The pipeline will redeploy.

---

### Semantic-release creates no new version

**Cause:** No commits on the branch use `feat:` or `fix:` prefix. `chore:`, `docs:`, `refactor:` do not trigger a release.

**Fix:** Ensure at least one commit uses `feat:` or `fix:` before merging to main.

---

### ZAP DAST scan fails on a known false positive

**Fix:** Add the rule ID to `.zap/rules.tsv` with `WARN` status and document the reason:

```tsv
10202	WARN	Anti-CSRF — not applicable, API uses JWT
```

Commit the file and the next pipeline run will respect it.

---

*End of document — v1.0 | Nama TIPMS CI/CD Template Hub*
