# Nama TIPMS — CI/CD Pipeline: Beginner's Guide

| Field    | Value                              |
|----------|------------------------------------|
| Version  | v1.0                               |
| Date     | May 2026                           |
| Audience | Developers new to CI/CD pipelines  |

---

## Before You Start — What Is This?

### Plain English Summary

Think of this like a **factory assembly line** for your code:

1. You write code on your computer and push it to GitHub.
2. The pipeline **automatically** checks your code (is it formatted right? are there bugs? does it build?).
3. If everything looks good, it **packages** your code into a container image (like a zip file that includes everything needed to run your app).
4. It **deploys** (copies and runs) that package on a server.
5. At each stage, it can **stop and ask a human to approve** before going to the next environment.

```
Your laptop → GitHub → ✅ Check code → 📦 Package it → 🚀 Deploy it
                          (automated)     (automated)    (auto for dev,
                                                          approval needed
                                                          for UAT + Prod)
```

### Key Terms (Plain English)

| Jargon | What it actually means |
|--------|------------------------|
| **CI** (Continuous Integration) | Automatically check and package your code every time you push |
| **CD** (Continuous Deployment) | Automatically copy your code to a server |
| **Pipeline** | A series of automated steps that run in order |
| **Template** | A reusable pipeline that many repos can share |
| **Workflow** | A file (`.yml`) that tells GitHub what steps to run |
| **Caller** | A small file in your app repo that says "use that shared template" |
| **Environment** | A named server stage — `dev`, `uat`, or `production` |
| **Secret** | A password or token stored securely in GitHub (not in your code) |
| **Variable** | A server address or config value stored in GitHub |
| **Container / Image** | A self-contained package with your app + everything it needs to run |
| **GHCR** | GitHub Container Registry — where container images are stored |
| **SHA** | A unique ID (like `a3f9c12`) that GitHub gives every commit |
| **Cosign** | A tool that digitally signs an image so you know it wasn't tampered with |

---

## Table of Contents

1. [How the System Is Organised](#1-how-the-system-is-organised)
2. [One-Time Setup (Admin Does This Once)](#2-one-time-setup-admin-does-this-once)
3. [Connecting an App Repo to the Pipeline](#3-connecting-an-app-repo-to-the-pipeline)
4. [Secrets & Variables — Where Do They Go?](#4-secrets--variables--where-do-they-go)
5. [What Happens When You Push Code](#5-what-happens-when-you-push-code)
6. [How to Test the Pipeline Step by Step](#6-how-to-test-the-pipeline-step-by-step)
7. [How to Deploy to UAT or Production](#7-how-to-deploy-to-uat-or-production)
8. [Something Broke — Common Fixes](#8-something-broke--common-fixes)
9. [Quick Reference Card](#9-quick-reference-card)

---

## 1. How the System Is Organised

### The "Template Hub" Idea

Instead of copy-pasting the same pipeline into every repo, we store **one set of templates** in a central repo called `cicd_development`. Each app repo just has a tiny file that says "use those templates".

```
┌─────────────────────────────────────────┐
│   cicd_development  (template hub)      │
│                                         │
│   template-ci-node.yml    ← CI checks   │
│   template-deploy.yml     ← Deploy      │
│   template-release.yml    ← Versioning  │
│   template-dast.yml       ← Security    │
│   template-ci-flutter.yml ← Mobile CI   │
└──────────┬──────────────────────────────┘
           │  "use this template"
    ┌──────┴────────────────────────────────┐
    │                  |                     │
    ▼                  ▼                    ▼
fe-repo             be-repo             mobile-repo
(Frontend)          (Backend)           (Flutter App)
```

**Why does this matter?**
If you need to update the pipeline (e.g., upgrade Node.js version), you change it in **one place** — the template hub. All app repos automatically get the update.

### Who Deploys What?

The **BE (Backend) repo** is in charge of all deployments — both the API and the web frontend together. Here's why: the two apps run side-by-side using Docker Compose, so one repo needs to coordinate them.

```
BE repo push → runs CI → deploys BOTH api container + web container to a server
FE repo push → runs CI → just builds and stores the web container (does NOT deploy alone)
```

---

## 2. One-Time Setup (Admin Does This Once)

> 🛑 **Only do this section once**, before any app repos are connected. Usually done by the DevOps lead.

### Step 1 — Make the template repo "Internal"

**Why:** GitHub only lets repos in the same organisation share workflows if the template repo is set to *Internal* (not *Private*).

```
1. Go to: github.com/nama-water/cicd_development
2. Click: Settings (top menu)
3. Scroll to the bottom → "Danger Zone"
4. Click: "Change repository visibility"
5. Select: Internal
6. Confirm
```

### Step 2 — Create Deployment Environments in the BE repo

**Why:** Environments are where you set up approval gates. UAT requires a manager to approve; Production requires two people to approve. Dev has no gate — it deploys automatically.

```
1. Go to: github.com/nama-water/be-repo
2. Click: Settings → Environments → "New environment"
3. Create these 5 environments:
```

| Environment    | Who needs to approve?                      | When?                          |
|----------------|--------------------------------------------|--------------------------------|
| `dev`          | Nobody — deploys automatically             | Every feature branch push      |
| `uat`          | Dev Lead OR QA Lead (1 person)             | When you manually trigger UAT  |
| `production`   | 2 team members (both must approve)         | When you manually trigger Prod |
| `distribution` | Nobody — auto after mobile tests pass      | Mobile only                    |
| `store-release`| 2 team members (cannot be undone!)         | App store release              |

### Step 3 — Allow GitHub to push to the container registry

**Why:** The pipeline builds a container image and needs permission to save it to GitHub's storage.

```
1. Go to: github.com/organizations/nama-water/settings/actions
2. Under "Workflow permissions" → select "Read and write permissions"
3. Save
4. Repeat this on every individual app repo too
```

### Step 4 — Allow reusable workflows

```
1. Still in: github.com/organizations/nama-water/settings/actions
2. Under "Actions permissions" → select "Allow all actions and reusable workflows"
3. Also turn ON: "Allow GitHub Actions to create and approve pull requests"
4. Save
```

---

## 3. Connecting an App Repo to the Pipeline

> Each app repo only needs a **small caller file** that points to the shared templates.

### 3A — Frontend (FE) Repo

**Step 1 — Copy the caller workflow file**

This file is like a "delegation note" — it tells GitHub to run the shared template.

```bash
# Run this inside the fe-repo directory
mkdir -p .github/workflows

# Copy the example caller file from the template hub
cp path/to/cicd_development/caller-examples/fe-repo/.github/workflows/ci.yml \
   .github/workflows/ci.yml
```

Open the copied `ci.yml` and confirm this line is present (update org name if needed):
```yaml
uses: nama-water/cicd_development/.github/workflows/template-ci-node.yml@main
```

**Step 2 — Copy the Docker files**

These tell Docker how to package your app into a container:

```bash
cp cicd_development/docker/Dockerfile.web  .
cp cicd_development/docker/nginx.conf      .
cp cicd_development/.dockerignore          .
```

**Step 3 — Copy config files**

```bash
cp cicd_development/.commitlintrc.json  .
cp cicd_development/release.config.js   .
cp cicd_development/.zap/rules.tsv      .zap/rules.tsv
```

> 📝 `.commitlintrc.json` enforces commit message style (e.g. `feat:`, `fix:`). This matters because the release step reads commit messages to decide the version number.

**Step 4 — Add Secrets to GitHub**

```
GitHub → nama-water/fe-repo → Settings → Secrets and variables → Actions → New secret
```

| Secret Name          | What it is                           | Where to get it                        |
|----------------------|--------------------------------------|----------------------------------------|
| `SNYK_TOKEN`         | Scans code for known vulnerabilities | snyk.io → Account Settings → API Token |
| `WHATSAPP_API_TOKEN` | Sends deploy notifications           | WhatsApp Business API dashboard        |
| `WHATSAPP_CHANNEL_ID`| The group/channel to send alerts to  | WhatsApp Business API dashboard        |

**Step 5 — Add required script names to `package.json`**

The pipeline looks for these exact script names:

```json
{
  "scripts": {
    "lint":  "eslint . --ext .vue,.js,.ts",
    "build": "vite build"
  }
}
```

---

### 3B — Backend (BE) Repo

**Step 1 — Copy caller workflow files**

The BE repo has **two** caller files — one for CI, one for deploy:

```bash
mkdir -p .github/workflows

cp cicd_development/caller-examples/be-repo/.github/workflows/ci.yml     .github/workflows/ci.yml
cp cicd_development/caller-examples/be-repo/.github/workflows/deploy.yml .github/workflows/deploy.yml
```

**Step 2 — Copy Docker file**

```bash
cp cicd_development/docker/Dockerfile.api .
```

**Step 3 — Copy the docker-compose file onto every app server**

> ⚠️ This file goes on the **server**, not in the repo. The pipeline SSHs into the server and uses this file to start the containers.

```bash
scp cicd_development/docker/docker-compose.yml  ubuntu@DEV_APP_HOST:/opt/tipms/docker-compose.yml
scp cicd_development/docker/docker-compose.yml  ubuntu@UAT_APP_HOST:/opt/tipms/docker-compose.yml
scp cicd_development/docker/docker-compose.yml  ubuntu@PROD_APP_HOST_1:/opt/tipms/docker-compose.yml
scp cicd_development/docker/docker-compose.yml  ubuntu@PROD_APP_HOST_2:/opt/tipms/docker-compose.yml
```

**Step 4 — Add Secrets to GitHub**

```
GitHub → nama-water/be-repo → Settings → Secrets and variables → Actions → New secret
```

| Secret Name              | What it is                                          | Where to get it                          |
|--------------------------|-----------------------------------------------------|------------------------------------------|
| `SNYK_TOKEN`             | Vulnerability scanner token                         | snyk.io                                  |
| `DB_PASSWORD`            | PostgreSQL database password                        | Your DBA / infrastructure team           |
| `JWT_SECRET_KEY`         | Secret used to sign auth tokens (64-char string)    | Run: `openssl rand -hex 32`              |
| `FCM_SERVER_KEY`         | Firebase push notification key                      | Firebase console                         |
| `SRV_SSH_KEY`            | Private SSH key to access app servers               | See Step 5 below                         |
| `WHATSAPP_API_TOKEN`     | Sends deploy notifications                          | WhatsApp Business API                    |
| `WHATSAPP_CHANNEL_ID`    | WhatsApp group ID for alerts                        | WhatsApp Business API                    |

**Step 5 — Create the SSH key for server access**

The pipeline SSHs into your servers to deploy. You need a key pair:

```bash
# Create a new SSH key (run this once on your local machine)
ssh-keygen -t ed25519 -C "cicd-deploy" -f ~/.ssh/cicd_deploy

# This creates two files:
#   ~/.ssh/cicd_deploy       ← PRIVATE key (goes into GitHub secret)
#   ~/.ssh/cicd_deploy.pub   ← PUBLIC key  (goes onto each server)

# Copy the public key to each app server (so it allows the pipeline to connect)
cat ~/.ssh/cicd_deploy.pub | ssh ubuntu@DEV_APP_HOST "cat >> ~/.ssh/authorized_keys"
cat ~/.ssh/cicd_deploy.pub | ssh ubuntu@UAT_APP_HOST "cat >> ~/.ssh/authorized_keys"
cat ~/.ssh/cicd_deploy.pub | ssh ubuntu@PROD_APP_HOST_1 "cat >> ~/.ssh/authorized_keys"
cat ~/.ssh/cicd_deploy.pub | ssh ubuntu@PROD_APP_HOST_2 "cat >> ~/.ssh/authorized_keys"
```

Then paste the **private key** (`~/.ssh/cicd_deploy`) as the value of the `SRV_SSH_KEY` secret in GitHub.

**Step 6 — Add Variables to GitHub**

Variables are not secret — they're just server addresses (IPs).

```
GitHub → nama-water/be-repo → Settings → Secrets and variables → Actions → Variables tab → New variable
```

| Variable Name    | Example Value  | What it is                  |
|------------------|----------------|-----------------------------|
| `DEV_APP_HOST`   | `10.0.1.10`    | Dev app server IP address   |
| `DEV_DB_HOST`    | `10.0.1.20`    | Dev database server IP      |
| `UAT_APP_HOST`   | `10.0.2.10`    | UAT app server IP           |
| `UAT_DB_HOST`    | `10.0.2.20`    | UAT database server IP      |
| `PROD_APP_HOST_1`| `10.0.3.10`    | Production server 1 IP      |
| `PROD_APP_HOST_2`| `10.0.3.11`    | Production server 2 IP      |
| `PROD_DB_HOST`   | `10.0.3.20`    | Production database IP      |

**Step 7 — Add required scripts to `package.json`**

```json
{
  "scripts": {
    "lint":             "eslint . --ext .js,.ts",
    "build":            "tsc",
    "test:integration": "jest --testPathPattern=integration"
  }
}
```

**Step 8 — Prepare each app server (one-time)**

SSH into each app server and run:

```bash
# Install Docker (the container engine)
curl -fsSL https://get.docker.com | bash
usermod -aG docker ubuntu

# Install Flyway (runs database migration scripts)
wget -qO- https://download.red-gate.com/maven/release/com/redgate/flyway/flyway-commandline/10.12.0/flyway-commandline-10.12.0-linux-x64.tar.gz | tar xz
mv flyway-10.12.0 /opt/flyway
ln -s /opt/flyway/flyway /usr/local/bin/flyway

# Install Cosign (verifies that container images haven't been tampered with)
curl -sLO https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
chmod +x cosign-linux-amd64
mv cosign-linux-amd64 /usr/local/bin/cosign

# Create the app directory
mkdir -p /opt/tipms/db/migrations
chmod 700 /opt/tipms
```

---

### 3C — Mobile Repo

**Step 1 — Copy caller workflow**

```bash
mkdir -p .github/workflows
cp cicd_development/caller-examples/mobile-repo/.github/workflows/ci.yml .github/workflows/ci.yml
```

**Step 2 — Add Secrets and Variables**

| Secret Name                 | What it is                                    |
|-----------------------------|-----------------------------------------------|
| `ANDROID_KEYSTORE`          | App signing keystore: `base64 < upload.jks`   |
| `ANDROID_KEY_ALIAS`         | Alias inside the keystore                     |
| `ANDROID_KEY_PASSWORD`      | Key password                                  |
| `ANDROID_STORE_PASSWORD`    | Keystore password                             |
| `CODEMAGIC_API_TOKEN`       | From codemagic.io → Teams → Integrations      |
| `FIREBASE_TOKEN`            | Run `firebase login:ci` to get this           |
| `PLAY_STORE_SERVICE_ACCOUNT`| Google Play service account JSON              |

| Variable Name       | What it is                      |
|---------------------|---------------------------------|
| `CODEMAGIC_APP_ID`  | From your Codemagic app page    |
| `FIREBASE_APP_ID`   | From Firebase project settings  |

---

## 4. Secrets & Variables — Where Do They Go?

Here is a quick summary of which secrets belong in which repo:

| Secret / Variable        | FE repo | BE repo | Mobile repo |
|--------------------------|:-------:|:-------:|:-----------:|
| `SNYK_TOKEN`             | ✅      | ✅      |             |
| `DB_PASSWORD`            |         | ✅      |             |
| `JWT_SECRET_KEY`         |         | ✅      |             |
| `FCM_SERVER_KEY`         |         | ✅      |             |
| `SRV_SSH_KEY`            |         | ✅      |             |
| `WHATSAPP_API_TOKEN`     | ✅      | ✅      |             |
| `WHATSAPP_CHANNEL_ID`    | ✅      | ✅      |             |
| `ANDROID_KEYSTORE`       |         |         | ✅          |
| `CODEMAGIC_API_TOKEN`    |         |         | ✅          |
| `FIREBASE_TOKEN`         |         |         | ✅          |
| `PLAY_STORE_SERVICE_ACCOUNT` |     |         | ✅          |
| `DEV_APP_HOST` (variable)|         | ✅      |             |
| `UAT_APP_HOST` (variable)|         | ✅      |             |
| `PROD_APP_HOST_1` (variable)|      | ✅      |             |

> 💡 **The template repo (`cicd_development`) needs no secrets at all.** Secrets flow from the calling repo into the template automatically.

---

## 5. What Happens When You Push Code

### Scenario A — You push a feature branch

```bash
git push origin feature/INS-123
```

**In the FE repo:**
```
1. validate   → checks formatting (Prettier), linting (ESLint), secrets scan (Gitleaks), dependency CVEs (Snyk)
2. test        → runs unit tests (Vitest) and generates a coverage report
3. sast        → scans code for security issues (CodeQL) — first run takes ~5 min
4. build       → packages your app into a container image, pushes to GHCR
5. image-scan  → scans the container for known vulnerabilities (Trivy + Snyk)
```
After image-scan passes → your image is stored as:
`ghcr.io/nama-water/nama-tipms-web:{your-commit-sha}`
and also tagged as `dev-latest`

**In the BE repo (runs at the same time):**
```
1–5. Same CI steps as FE, plus integration tests with a real Postgres database
6. deploy to dev → SSH into dev server, run database migrations, start containers
7. health check  → hits /health endpoint, confirms the app is running
8. security scan → OWASP ZAP scans the live dev URL for vulnerabilities
```

**Total time: about 15–18 minutes**

---

### Scenario B — You open a Pull Request to main

No deployment happens. The pipeline just **re-runs all CI checks** to make sure the code is safe to merge. GitHub blocks the merge button until all 5 checks pass.

---

### Scenario C — PR is merged to main

```
1. Full CI runs again on the merged code
2. Semantic-release reads commit messages and picks a version number:
   - "feat: ..." → minor version bump (e.g. 1.2.0 → 1.3.0)
   - "fix: ..."  → patch version bump (e.g. 1.2.0 → 1.2.1)
3. The image gets re-tagged: {sha} → v1.3.0 and latest
4. Cosign signs the image (proves it was built by your CI, not tampered with)
5. GitHub Release is created with an auto-generated CHANGELOG
```

---

## 6. How to Test the Pipeline Step by Step

Work through these phases **in order**. Don't skip ahead — each phase builds on the last.

---

### Phase 1 — Check Files for Errors (No GitHub Needed)

**What you're checking:** Are the YAML pipeline files valid?

**Install the checker tool:**

```bash
# Windows
winget install rhysd.actionlint

# Mac
brew install actionlint
```

**Run it:**

```bash
# Check all template files
actionlint .github/workflows/template-ci-node.yml
actionlint .github/workflows/template-ci-flutter.yml
actionlint .github/workflows/template-deploy.yml
actionlint .github/workflows/template-release.yml
actionlint .github/workflows/template-dast.yml

# Check caller files too
actionlint caller-examples/fe-repo/.github/workflows/ci.yml
actionlint caller-examples/be-repo/.github/workflows/ci.yml
actionlint caller-examples/be-repo/.github/workflows/deploy.yml
actionlint caller-examples/mobile-repo/.github/workflows/ci.yml

# Check the deploy shell script
bash -n scripts/deploy-env.sh

# Check docker-compose
cd docker
docker compose config
```

**✅ Pass:** All commands finish with no error messages.

---

### Phase 2 — Confirm GitHub Can See the Templates

**What you're checking:** Does GitHub recognise your workflow files and can one repo call another?

**Step 1 — Push the template hub to GitHub:**

```bash
git add .
git commit -m "ci: add reusable pipeline templates v1.0"
git push origin main
```

**Step 2 — Verify it looks right on GitHub:**

```
Go to: github.com/nama-water/cicd_development → Actions tab
```

You should see 5 workflows listed. They will say "This workflow has no trigger" — **this is expected**. They only run when called by another repo.

**Step 3 — Create a minimal test repo:**

```
GitHub → New repository → name it: nama-water/pipeline-test → set to Internal
```

Add these three files to it:

**`.github/workflows/test-ci.yml`**
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

**`package.json`**
```json
{
  "name": "pipeline-test",
  "version": "1.0.0",
  "scripts": {
    "lint":  "echo 'lint ok'",
    "build": "echo 'build ok'"
  }
}
```

**`Dockerfile.test`**
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY . .
RUN echo "test build"
```

Push to main and go to the `pipeline-test` repo's Actions tab.

**✅ Pass:** You see jobs appear and start running. If you see "Unable to fetch reusable workflow" — the template repo is still set to Private. Fix that first (Section 2, Step 1).

---

### Phase 3 — Test CI with Real App Code

**What you're checking:** All 5 CI stages pass on the FE and BE repos.

**Steps:**

1. Add `SNYK_TOKEN` secret to FE repo (see Section 3A, Step 4)
2. Copy the caller workflow and Docker files (see Section 3A, Steps 1–3)
3. Create a test branch and push it:

```bash
git checkout -b feature/pipeline-test
git add .
git commit -m "ci: add CI pipeline"
git push origin feature/pipeline-test
```

4. Watch the run:

```
GitHub → fe-repo → Actions → CI → click the latest run
```

You should see these jobs running one after another:
```
validate  ✅ or ❌ (fix lint errors if it fails)
test      ✅ or ❌ (install vitest if missing)
sast      ✅        (CodeQL — takes ~5 min on first run)
build     ✅        (produces image in GHCR)
image-scan ✅       (no critical vulnerabilities found)
```

5. Check the image was stored:

```
GitHub → fe-repo → Packages
```

You should see `nama-tipms-web` with a tag that matches your commit SHA.

**✅ Pass:** Both FE and BE repos show all 5 green checkmarks. Images appear in GHCR.

---

### Phase 4 — Test Deployment to Dev Server

**What you're checking:** The pipeline can SSH into a server, run migrations, start containers, and pass a health check.

**Step 1 — Set up the dev server** (see Section 3B, Step 8)

**Step 2 — Start PostgreSQL on the database server:**

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

**Step 3 — Add the SSH key and VM addresses** (see Section 3B, Steps 5–6)

**Step 4 — Push a feature branch from the BE repo:**

```bash
git checkout -b feature/deploy-test
git push origin feature/deploy-test
```

**Step 5 — Watch the Actions run on GitHub:**

```
be-repo → Actions → CI → latest run
```

After the CI jobs finish, you should see two more jobs start:
- `deploy-dev` → connects to your server, migrates the database, starts containers
- `dast` → runs security scan against the live dev URL

**Step 6 — Confirm the containers are running:**

```bash
ssh ubuntu@DEV_APP_HOST
docker compose -f /opt/tipms/docker-compose.yml ps
```

You should see 4 containers in `Up` state:
```
api          ← Your backend app
web          ← Your frontend app
pgbouncer    ← Database connection pooler
promtail     ← Log collector
```

**Step 7 — Hit the health endpoint:**

```bash
curl http://DEV_APP_HOST:3000/health
# Should return: {"status":"ok"}
```

**✅ Pass:** Deploy job green, containers Up, health check returns `{"status":"ok"}`.

---

### Phase 5 — Test Versioning (After Merge to Main)

**What you're checking:** When code is merged to main, does a version tag get created and signed?

**Step 1 — Open a PR** from `feature/deploy-test` → `main`, get 2 approvals, merge it.

**Step 2 — Watch the Actions run on main:**

```
be-repo → Actions → CI → latest run (on main branch)
```

After the CI jobs, a `release` job should appear:
```
release → creates v1.0.0 (or whatever is next)
        → tags image with v1.0.0
        → cosign signs the image
```

**Step 3 — Verify in GHCR:**

```
GitHub → Packages → nama-tipms-api
```

You should see THREE tags now: `{sha}`, `v1.0.0`, `latest`.

**✅ Pass:** Version tag exists in GHCR.

---

### Phase 6 — Test UAT and Production Deploys

**What you're checking:** Manual approval gates work correctly.

**UAT deploy:**

```
GitHub → be-repo → Actions (left sidebar) → Deploy → "Run workflow" (top right button)
```

Fill in:
- `environment`: `uat`
- `api_tag`: the commit SHA from your feature branch (7 characters is fine, e.g. `a3f9c12`)
- `web_tag`: the FE commit SHA for the same feature

After clicking Run, GitHub will **pause** and show an approval request. The Dev Lead must click Approve. Then the deploy runs.

**Production deploy:**

```
Same as above, but:
  environment: production
  api_tag: v1.0.0
  web_tag: v1.0.0
```

Production will ask for **two** approvals before continuing.

**✅ Pass:** Both deploys complete, WhatsApp notifications arrive, approval gates worked correctly.

---

## 7. How to Deploy to UAT or Production

> These are always triggered manually. Never automatic.

### Deploy to UAT

```
1. Go to: github.com/nama-water/be-repo
2. Click: Actions tab (in the top menu)
3. On the left sidebar, click: "Deploy"
4. Click the grey "Run workflow" button (top right of the workflow list)
5. Fill in the form:
      environment: uat
      api_tag:     [the commit SHA from the BE feature branch]
      web_tag:     [the commit SHA from the FE feature branch]
6. Click "Run workflow"
7. Wait for GitHub to show the approval gate
8. Dev Lead or QA Lead clicks "Approve"
9. Watch the deploy run
```

**How to find the right SHA:**
- Go to the BE repo → Actions → CI → click the feature branch run → open the "build" job → look for a log line like:
  `Pushing ghcr.io/nama-water/nama-tipms-api:a3f9c12` → the SHA is `a3f9c12`

### Deploy to Production

Same steps, but:
- `environment`: `production`
- `api_tag`: the **version number** (e.g. `v1.0.0`), not a SHA
- `web_tag`: same version number
- Two people must approve (they will both get a notification)

> ⚠️ **Production deploys are rolling** — Server 1 updates first, health check runs, then Server 2 updates. If Server 1 fails its health check, it rolls back automatically and Server 2 is never touched.

---

## 8. Something Broke — Common Fixes

### ❌ "Unable to fetch reusable workflow"

**What happened:** The template repo (`cicd_development`) is set to Private. Other repos can't see it.

**Fix:**
```
1. Go to: github.com/nama-water/cicd_development → Settings
2. Scroll to bottom → "Danger Zone" → "Change repository visibility"
3. Change to: Internal
```

---

### ❌ "Resource not accessible by integration" when pushing to GHCR

**What happened:** The GitHub Actions workflow doesn't have write permission to the container registry.

**Fix:**
```
1. Go to: github.com/organizations/nama-water/settings/actions
2. Under "Workflow permissions" → select "Read and write permissions" → Save
3. Repeat on the specific repo:
   github.com/nama-water/[repo-name]/settings/actions
```

---

### ❌ "cosign verify" fails during deploy

**Cause A:** You're deploying a feature branch image. Feature branch images are NOT signed — only images released from `main` (via the release template) get a signature.

**Fix for testing:** Temporarily comment out the cosign verify step in `template-deploy.yml` while testing on feature branches. Uncomment before UAT.

**Cause B:** The certificate identity URL in the template doesn't match your actual repo name.

**Fix:** Open `template-deploy.yml` and find this line:
```yaml
--certificate-identity="https://github.com/nama-water/nama-tipms-be/.github/workflows/ci.yml@refs/heads/main"
```
Replace `nama-tipms-be` with your actual BE repo name.

---

### ❌ "Host key verification failed" during SSH

**Fix:** Make sure the SSH command includes both these flags:
```bash
ssh -i /tmp/deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$HOST ...
```

---

### ❌ Health check fails, deploy rolls back

**Step 1 — Check the container logs:**

```bash
ssh ubuntu@DEV_APP_HOST
docker compose -f /opt/tipms/docker-compose.yml logs api --tail=50
```

**Step 2 — Common causes:**

| Symptom in logs             | Fix                                                              |
|-----------------------------|------------------------------------------------------------------|
| `Missing env variable: X`   | The `.env` file on the server is missing a required variable     |
| `ECONNREFUSED` to DB        | Check `DEV_DB_HOST` variable — is the IP address correct?       |
| `Flyway migration failed`   | A SQL migration script has an error — check the Flyway logs      |

**Step 3 — After fixing, just push again.** The pipeline will re-deploy automatically.

---

### ❌ Merge to main creates no new version tag

**Cause:** None of your commits use `feat:` or `fix:` as a prefix. The release tool (`semantic-release`) only creates a new version when it sees these.

**Fix:** Make sure at least one commit on the branch looks like:
```
feat: add permit expiry notification
fix: correct date calculation for Oman weekend
```

Commits like `chore: update README` or `refactor: rename variable` do not trigger a release.

---

### ❌ ZAP security scan keeps failing on a false positive

**Fix:** Add the rule ID to `.zap/rules.tsv` with status `WARN` and a comment explaining why it's safe:

```tsv
10202	WARN	Anti-CSRF — not applicable, API uses JWT tokens
```

Commit the file. Next pipeline run will skip that rule.

---

## 9. Quick Reference Card

Cut out and keep this section handy.

### Common Tasks

| Task | Where to do it |
|------|---------------|
| Push a feature branch | `git push origin feature/your-branch` |
| Watch CI run | repo → Actions → CI → latest run |
| Find an image SHA | repo → Actions → CI → build job → logs |
| Deploy to UAT | be-repo → Actions → Deploy → Run workflow |
| Deploy to Production | be-repo → Actions → Deploy → Run workflow |
| Add a secret | repo → Settings → Secrets → Actions → New secret |
| Add a variable | repo → Settings → Secrets → Actions → Variables tab → New variable |
| Check containers on server | `docker compose -f /opt/tipms/docker-compose.yml ps` |
| View app logs | `docker compose -f /opt/tipms/docker-compose.yml logs api --tail=50` |

### Commit Message Format

| Prefix | When to use | Effect |
|--------|-------------|--------|
| `feat:` | New feature or capability | Bumps minor version (1.2.0 → 1.3.0) |
| `fix:` | Bug fix | Bumps patch version (1.2.0 → 1.2.1) |
| `chore:` | Maintenance, no logic change | No release |
| `docs:` | Documentation update | No release |
| `refactor:` | Code restructure, no behaviour change | No release |

### Pipeline Stage Summary

```
validate → test → sast → build → image-scan
   │          │       │       │         │
   │          │       │       │         └─ Trivy + Snyk: no critical CVEs
   │          │       │       └─ Builds container image, pushes to GHCR
   │          │       └─ CodeQL: no code-level security issues
   │          └─ Vitest: unit tests pass, coverage meets threshold
   └─ ESLint + Prettier + Gitleaks + Snyk SCA: code quality + no leaked secrets
```

---

*End of document — Beginner's Guide v1.0 | Nama TIPMS CI/CD*
