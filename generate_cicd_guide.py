"""
Generates cicd_implementation_guide_v1.2.docx from the markdown source.
Requires: pip install python-docx markdown
Run from the repo root: python generate_cicd_guide.py
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TEAL = RGBColor(0x0D, 0x73, 0x77)
INK = RGBColor(0x1A, 0x2B, 0x3C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
LIGHT_ORANGE = RGBColor(0xFF, 0xF3, 0xE0)
LIGHT_BLUE = RGBColor(0xE3, 0xF2, 0xFD)
WARN_RED = RGBColor(0xB7, 0x1C, 0x1C)
WARN_BG = RGBColor(0xFF, 0xEB, 0xEE)
CODE_BG = RGBColor(0xF5, 0xF5, 0xF5)
CODE_FG = RGBColor(0x1A, 0x23, 0x7E)


def _hex(rgb: RGBColor) -> str:
    """Return 6-digit hex string from an RGBColor (tuple subclass: r, g, b)."""
    return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def shade_cell(cell, rgb: RGBColor):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), _hex(rgb))
    tcPr.append(shd)


def set_cell_text(cell, text, bold=False, color=None, size=10):
    para = cell.paragraphs[0]
    para.clear()
    run = para.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color


def add_heading(doc, text, level=1):
    heading = doc.add_heading(text, level=level)
    for run in heading.runs:
        run.font.color.rgb = TEAL if level == 1 else INK


def add_info_box(doc, text, bg=LIGHT_GREEN, label=None):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    shade_cell(cell, bg)
    para = cell.paragraphs[0]
    if label:
        run = para.add_run(f"{label} ")
        run.bold = True
        run.font.color.rgb = WARN_RED if bg == WARN_BG else INK
    run = para.add_run(text)
    run.font.size = Pt(10)
    doc.add_paragraph()


def add_code_block(doc, code_text):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    shade_cell(cell, CODE_BG)
    para = cell.paragraphs[0]
    run = para.add_run(code_text.strip())
    run.font.name = "Courier New"
    run.font.size = Pt(8.5)
    run.font.color.rgb = CODE_FG
    doc.add_paragraph()


def add_kv_table(doc, rows, headers=None, col_widths=None):
    cols = len(rows[0]) if rows else 2
    table = doc.add_table(rows=len(rows) + (1 if headers else 0), cols=cols)
    table.style = "Table Grid"
    offset = 0
    if headers:
        hrow = table.rows[0]
        for i, h in enumerate(headers):
            set_cell_text(hrow.cells[i], h, bold=True, color=WHITE)
            shade_cell(hrow.cells[i], TEAL)
        offset = 1
    for ri, row_data in enumerate(rows):
        trow = table.rows[ri + offset]
        for ci, cell_text in enumerate(row_data):
            set_cell_text(trow.cells[ci], str(cell_text))
    if col_widths:
        for row in table.rows:
            for ci, w in enumerate(col_widths):
                row.cells[ci].width = Cm(w)
    doc.add_paragraph()


def build_document():
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Cover title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Nama Water Services TIPMS")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = TEAL

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run("CI/CD Pipeline Implementation Guide")
    run.font.size = Pt(14)
    run.font.color.rgb = INK

    add_kv_table(doc, [
        ["Version", "v1.2 — GitHub-hosted runner + all gaps resolved"],
        ["Date", "May 2026"],
        ["Status", "Ready for engineering use"],
        ["Audience", "Backend / DevOps engineers setting up the Nama TIPMS pipeline"],
        ["Based on", "github_cicd_pipeline_v4.drawio"],
        ["Changes", "GitHub-hosted runner replaces self-hosted VM; 5 known gaps closed"],
    ])

    # v1.2 change log
    add_heading(doc, "What Changed in v1.2", level=1)
    add_kv_table(doc, [
        ["1", "All jobs use runs-on: ubuntu-latest (GitHub-hosted)", "Eliminates runner-vm provisioning and maintenance overhead"],
        ["2", "services: block restored for Postgres integration tests", "GitHub-hosted runners fully support service containers"],
        ["3", "Section 10 (Runner VM Setup) removed", "No longer needed"],
        ["4", "DAST added as Stage 7 after every Dev deploy", "Closes gap: auth bypass bugs only appear in a running app"],
        ["5", "Cosign image signing added after GHCR push", "Closes gap: cryptographic proof images came from the pipeline"],
        ["6", "notify-on-failure job added", "Closes gap: developers get WhatsApp alerts on broken builds"],
        ["7", "Flyway undo scripts documented + added to production gate", "Closes gap: schema rollback now has a defined process"],
        ["8", "External uptime monitoring documented in Section 9", "Closes gap: Uptime Kuma inside VPN cannot detect VPC-level outages"],
    ], headers=["#", "Change", "Why"], col_widths=[1, 8, 8])

    doc.add_page_break()

    # Section 1
    add_heading(doc, "1. What This Guide Covers", level=1)
    doc.add_paragraph(
        "This guide walks you through setting up the complete CI/CD pipeline for the Nama TIPMS web application "
        "— from a developer pushing code to a version running safely in production. It covers every moving part: "
        "repository rules, the automated pipeline stages, how Docker images are built and stored, how Dev / UAT / "
        "Production deployments work, and how to roll back quickly if something breaks. Follow the sections in order."
    )
    add_info_box(doc,
        "This guide covers the web portal pipeline only (permit-api + permit-web). "
        "The mobile pipeline (Flutter / iOS) is in Section 10.",
        bg=LIGHT_ORANGE, label="Watch out:")
    add_info_box(doc,
        "All CI/CD jobs run on GitHub-provided ubuntu-latest machines. You do not provision or maintain a runner VM. "
        "GitHub charges per-minute on the paid plan; the free tier covers ~2,000 minutes/month per private repo.",
        bg=LIGHT_BLUE, label="GitHub-hosted runners:")

    # Section 2
    add_heading(doc, "2. Before You Start — Prerequisites", level=1)
    add_heading(doc, "2.1 Accounts and access", level=2)
    for item in [
        "GitHub organisation account with admin rights to the nama-tipms repository",
        "Access to the Omantel / OTech Cloud console to provision VMs",
        "Snyk account — snyk.io (free tier is fine to start)",
        "Codemagic account for iOS builds — codemagic.io",
        "Cosign: no separate account needed — keyless signing uses GitHub Actions OIDC token automatically",
        "WhatsApp Business API access (for deploy and failure alerts)",
        "Better Uptime or Freshping account for external uptime monitoring",
    ]:
        p = doc.add_paragraph(item, style="List Bullet")
        p.runs[0].font.size = Pt(10)

    add_heading(doc, "2.2 Tools on your laptop", level=2)
    add_kv_table(doc, [
        ["Git 2.40+", "Version control"],
        ["Docker Desktop", "Test image builds locally before committing"],
        ["Node.js 20 LTS", "Run scripts and local dev"],
        ["Flyway CLI 10+", "Run database migrations manually if needed"],
        ["Cosign CLI", "brew install cosign — for local image verification only; pipeline installs it automatically"],
        ["SSH client", "With your key pair configured"],
    ], headers=["Tool", "Purpose"])

    add_heading(doc, "2.3 VMs to provision", level=2)
    add_info_box(doc, "No runner-vm needed. CI/CD jobs run on GitHub-hosted machines. The runner-vm from v1.1 is removed.", bg=LIGHT_GREEN)
    add_kv_table(doc, [
        ["monitoring-vm", "2 CPU / 4 GB / 50 GB", "Prometheus, Grafana, Loki, Alertmanager"],
        ["dev-app-vm", "2 CPU / 2 GB / 50 GB", "Dev application containers"],
        ["dev-db-vm", "2 CPU / 4 GB / 100 GB", "Dev PostgreSQL 16"],
        ["uat-app-vm", "2 CPU / 4 GB / 50 GB", "UAT application containers"],
        ["uat-db-vm", "2 CPU / 8 GB / 150 GB", "UAT PostgreSQL 16"],
        ["prod-app-vm-1", "4 CPU / 8 GB / 100 GB", "Production app — node 1 of 2"],
        ["prod-app-vm-2", "4 CPU / 8 GB / 100 GB", "Production app — node 2 of 2"],
        ["prod-db-vm", "4 CPU / 16 GB / 200 GB NVMe", "Production PostgreSQL 16"],
    ], headers=["VM name", "Size", "Purpose"])

    # Section 3
    add_heading(doc, "3. Repository Setup", level=1)
    add_heading(doc, "3.1 Branch strategy", level=2)
    doc.add_paragraph(
        "Feature Branch Promotion (v4 design). Each feature branch is promoted through Dev → UAT → Production. "
        "The same commit SHA is deployed to all three environments — no rebuild between them."
    )
    for item in [
        "Feature branches: feature/short-description, kept alive 2 days maximum",
        "Bug fixes: fix/short-description",
        "Nobody pushes directly to main — ever",
        "Feature branch deleted after merge to main",
    ]:
        doc.add_paragraph(item, style="List Bullet").runs[0].font.size = Pt(10)

    add_heading(doc, "3.2 Branch protection rules for main", level=2)
    add_kv_table(doc, [
        ["Require a pull request before merging", "ON"],
        ["Required approvals", "2"],
        ["Dismiss stale PR approvals when new commits are pushed", "ON"],
        ["Require status checks to pass before merging", "ON — add: validate, test, sast, build, image-scan"],
        ["Require branches to be up to date before merging", "ON"],
        ["Do not allow bypassing the above settings", "ON"],
    ], headers=["Setting", "Value"])

    add_heading(doc, "3.3 Commit message format", level=2)
    add_code_block(doc,
        "feat(permits): add renewal reminder UI\n"
        "fix(lab): correct 3-day SLA calculation to exclude Friday/Saturday\n"
        "chore(deps): bump node from 20.10 to 20.11\n\n"
        "BREAKING CHANGE: remove legacy permit endpoint /api/v1/permits/old"
    )
    add_kv_table(doc, [
        ["feat", "New feature visible to users", "Minor: 1.2.0 → 1.3.0"],
        ["fix", "Bug fix", "Patch: 1.2.0 → 1.2.1"],
        ["chore / docs / refactor", "Internal change, no user impact", "No release"],
        ["BREAKING CHANGE", "Removes or changes existing behaviour", "Major: 1.2.0 → 2.0.0"],
    ], headers=["Prefix", "Meaning", "Version bump"])

    # Section 4
    add_heading(doc, "4. GitHub Secrets and Environments", level=1)
    add_heading(doc, "4.1 Secrets", level=2)
    add_kv_table(doc, [
        ["DB_PASSWORD", "PostgreSQL password for the app user"],
        ["JWT_SECRET_KEY", "64-char random string: openssl rand -hex 32"],
        ["FCM_SERVER_KEY", "Firebase Cloud Messaging server key"],
        ["APNS_AUTH_KEY", "Apple Push Notification .p8 file, base64-encoded"],
        ["ANDROID_KEYSTORE", "Android signing keystore file, base64-encoded"],
        ["ANDROID_KEY_ALIAS", "Key alias inside the keystore"],
        ["ANDROID_KEY_PASSWORD", "Key password"],
        ["ANDROID_STORE_PASSWORD", "Keystore password"],
        ["CODEMAGIC_API_TOKEN", "API token from codemagic.io"],
        ["SRV_DEV_SSH_KEY", "Private SSH key for dev-app-vm and dev-db-vm"],
        ["SRV_UAT_SSH_KEY", "Private SSH key for uat-app-vm and uat-db-vm"],
        ["SRV_PROD_SSH_KEY", "Private SSH key for both prod-app-vms and prod-db-vm"],
        ["SNYK_TOKEN", "API token from snyk.io"],
        ["WHATSAPP_API_TOKEN", "WhatsApp Business API token for notifications"],
        ["WHATSAPP_CHANNEL_ID", "WhatsApp group/channel ID for team alerts"],
    ], headers=["Secret name", "What to put in it"])
    add_info_box(doc,
        "Never commit these values to any file in the repository. "
        "If you accidentally commit a secret, rotate it immediately — "
        "deleting the commit is not enough because the value is in git history.",
        bg=WARN_BG, label="Watch out:")

    add_heading(doc, "4.2 GitHub Environments", level=2)
    add_kv_table(doc, [
        ["dev", "No approval — auto after CI passes on feature branch. Concurrency group active."],
        ["uat", "Dev Lead / QA must approve. workflow_dispatch only. GitHub verifies same SHA as Dev."],
        ["production", "2 reviewers required. Tags matching v*.*.*. workflow_dispatch only. Sunday 03:00–06:00 OST window."],
    ], headers=["Environment", "Rules"])

    # Section 5
    add_heading(doc, "5. The Pipeline — Stage by Stage", level=1)
    add_info_box(doc,
        "All jobs use runs-on: ubuntu-latest — GitHub-hosted runners. No self-hosted VM required.",
        bg=LIGHT_GREEN)

    stages = [
        ("Stage 1 — Validate (~90 seconds)", [
            "ESLint / Prettier / Stylelint — code and format errors",
            "Gitleaks — accidentally committed secrets",
            "npm audit — known CVEs in npm dependencies (fail: HIGH/CRITICAL)",
            "Snyk SCA — deeper dependency scan + licence check",
        ]),
        ("Stage 2 — Test (~3 minutes)", [
            "Vitest (Vue 3 unit tests) — coverage >= 70% enforced in vite.config.ts",
            "Jest (Node.js API tests) — coverage >= 70% enforced in jest.config.js",
            "Integration tests — uses services: postgres:16 (real DB, real schema)",
            "services: block works on GitHub-hosted runners — no docker run workaround needed",
        ]),
        ("Stage 3 — SAST (~2 minutes)", [
            "CodeQL — SQL injection, XSS, OWASP Top 10",
            "CRITICAL/HIGH findings fail the build; MEDIUM flagged for weekly review",
        ]),
        ("Stage 4 — Build Images (~4 minutes, 2 parallel jobs)", [
            "Builds nama-permit-api:{sha} from node:20.11-alpine3.19",
            "Builds nama-permit-web:{sha} from nginx:1.27-alpine",
            "Both pushed to GHCR immediately with push: true so Stage 5 can scan them",
            "Docker BuildKit layer cache: cache-from/cache-to type=gha",
        ]),
        ("Stage 5 — Image Scan (~3 minutes)", [
            "Trivy — OS CVEs in Alpine layers (fail: CRITICAL)",
            "Snyk container — app dependency CVEs inside the image (fail: HIGH/CRITICAL)",
            "Runs on both api and web images via matrix strategy",
        ]),
        ("Stage 6 — Release and Sign (main branch only)", [
            "semantic-release: reads commits, bumps SemVer, creates git tag v1.3.0, generates CHANGELOG",
            "Re-tags both images: {sha} → v1.3.0 → latest",
            "NEW: Cosign keyless signing on SHA-tagged and version-tagged images",
            "id-token: write permission required for OIDC signing — no private key to manage",
            "cancel-in-progress: false — queues releases, never cancels a deploy mid-run",
        ]),
        ("Stage 7 — DAST (after every Dev deploy) [NEW in v1.2]", [
            "OWASP ZAP Baseline Scan against https://dev.permit.nama-water.om",
            "Catches auth bypass, access control bugs, runtime injection flaws that SAST misses",
            "Fails build on any HIGH/CRITICAL finding",
            "ZAP report uploaded as pipeline artifact for every run",
            "Tune rules with .zap/rules.tsv to suppress confirmed false positives",
        ]),
        ("notify-on-failure [NEW in v1.2]", [
            "Runs if: failure() after any stage",
            "Sends WhatsApp message: failed stage name + direct link to run logs",
            "Developer knows within seconds — no need to check GitHub manually",
        ]),
    ]

    for stage_title, bullets in stages:
        add_heading(doc, stage_title, level=2)
        for b in bullets:
            p = doc.add_paragraph(b, style="List Bullet")
            p.runs[0].font.size = Pt(10)

    # Section 5 — Code blocks for key jobs
    add_heading(doc, "Stage 2 — Test job (services: block)", level=3)
    add_code_block(doc, """\
test:
  needs: validate
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_PASSWORD: test_password
        POSTGRES_DB: tipms_test
      ports: ["5432:5432"]
      options: >-
        --health-cmd pg_isready
        --health-interval 10s --health-retries 5
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: 20, cache: npm }
    - run: npm ci
    - run: npx vitest run --coverage
    - run: npx jest --coverage
    - env: { DB_HOST: 127.0.0.1, DB_PASSWORD: test_password }
      run: npm run test:integration""")

    add_heading(doc, "Stage 6 — Release and Sign (Cosign)", level=3)
    add_code_block(doc, """\
release:
  needs: image-scan
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  permissions:
    contents: write
    packages: write
    id-token: write        # required for Cosign OIDC keyless signing
  concurrency:
    group: deploy-${{ github.ref }}
    cancel-in-progress: false
  steps:
    - uses: actions/checkout@v4
      with: { fetch-depth: 0 }
    - run: npm ci
    - run: npx semantic-release
      env: { GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
    - uses: docker/login-action@v3
      with: { registry: ghcr.io, username: ${{ github.actor }},
              password: ${{ secrets.GITHUB_TOKEN }} }
    - uses: sigstore/cosign-installer@v3
    - name: Re-tag and sign images
      env: { SHA: ${{ github.sha }}, REGISTRY: ghcr.io/nama-water }
      run: |
        VERSION=$(node -p "require('./package.json').version")
        for IMAGE in nama-tipms-api nama-tipms-web; do
          docker pull $REGISTRY/$IMAGE:$SHA
          docker tag $REGISTRY/$IMAGE:$SHA $REGISTRY/$IMAGE:$VERSION
          docker tag $REGISTRY/$IMAGE:$SHA $REGISTRY/$IMAGE:latest
          docker push $REGISTRY/$IMAGE:$VERSION
          docker push $REGISTRY/$IMAGE:latest
          cosign sign --yes $REGISTRY/$IMAGE:$SHA
          cosign sign --yes $REGISTRY/$IMAGE:$VERSION
        done""")

    add_heading(doc, "Stage 7 — DAST (OWASP ZAP)", level=3)
    add_code_block(doc, """\
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
        path: report_html.html""")

    add_heading(doc, "notify-on-failure job", level=3)
    add_code_block(doc, """\
notify-on-failure:
  needs: [validate, test, sast, build, image-scan, release]
  if: failure()
  runs-on: ubuntu-latest
  steps:
    - name: Send WhatsApp failure alert
      run: |
        MESSAGE="CI/CD Failed | ${{ github.repository }} | Branch: ${{ github.ref_name }}"
        MESSAGE+=" | Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
        curl -s -X POST "https://graph.facebook.com/v18.0/.../messages" \\
          -H "Authorization: Bearer ${{ secrets.WHATSAPP_API_TOKEN }}" \\
          -H "Content-Type: application/json" \\
          -d "{\"type\":\"text\",\"text\":{\"body\":\"$MESSAGE\"}}" """)

    # Section 6
    add_heading(doc, "6. Dev / UAT Deployment", level=1)
    doc.add_paragraph(
        "The deploy script (scripts/deploy-env.sh) is shared across Dev and UAT. "
        "It receives the environment name and image tag as arguments. "
        "It verifies the Cosign signature before pulling, runs Flyway migrations before touching the app, "
        "writes secrets to .env, pulls and starts containers, health-checks, and auto-rolls back on failure."
    )

    add_heading(doc, "Cosign verification in deploy script", level=2)
    add_code_block(doc, """\
cosign verify \\
  ghcr.io/nama-water/nama-tipms-api:$IMAGE_TAG \\
  --certificate-identity="https://github.com/nama-water/nama-tipms/.github/workflows/ci-cd.yml@refs/heads/main" \\
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" || {
    echo "Image signature verification failed — aborting deploy"
    exit 1
  }""")

    add_info_box(doc,
        "The .env file on the VM contains real secrets. "
        "Ensure /opt/tipms is only readable by root (chmod 700 /opt/tipms). "
        "The deploy script sets chmod 600 on the .env file itself.",
        bg=WARN_BG, label="Watch out:")

    # Section 7
    add_heading(doc, "7. Production Deployment", level=1)

    add_heading(doc, "7.1 Conditions before starting (6 required)", level=2)
    add_kv_table(doc, [
        ["1", "Version tag exists in GHCR and has passed all pipeline stages"],
        ["2", "UAT has been running that version for at least 24 hours without errors"],
        ["3", "Two team members have approved in GitHub Environments"],
        ["4", "Nama client sign-off received via GitHub Issue"],
        ["5", "Database backup taken less than 4 hours ago"],
        ["6", "Flyway undo script written, reviewed, and tested in UAT for this version [NEW]"],
    ], headers=["#", "Condition"])

    add_heading(doc, "7.2 Flyway undo scripts — process [NEW in v1.2]", level=2)
    add_info_box(doc,
        "Flyway does not auto-undo migrations. If a migration runs as part of a broken deploy, "
        "rolling back the application code does not roll back the schema change. "
        "The old app may break on the new schema. This was the highest-risk operational gap in v1.1.",
        bg=WARN_BG, label="Why this matters:")
    doc.add_paragraph(
        "For every migration file V{n}__{desc}.sql, write a corresponding undo file U{n}__{desc}.sql:"
    )
    add_code_block(doc, """\
-- V3__add_lab_results_index.sql (forward)
CREATE INDEX idx_lab_results_sample_id ON TEST_RESULTS(SAMPLE_ID);
ALTER TABLE SAMPLES ADD COLUMN processed_at TIMESTAMPTZ;

-- U3__add_lab_results_index.sql (undo)
ALTER TABLE SAMPLES DROP COLUMN IF EXISTS processed_at;
DROP INDEX IF EXISTS idx_lab_results_sample_id;""")

    doc.add_paragraph("Rules for writing undo scripts:")
    for item in [
        "Every CREATE has a corresponding DROP IF EXISTS",
        "Every ADD COLUMN has a corresponding DROP COLUMN IF EXISTS",
        "DROP TABLE forward migrations cannot be undone — mark explicitly, require extra approval",
        "Test the undo in UAT: run forward migration, verify app, run undo, verify old app still starts",
    ]:
        doc.add_paragraph(item, style="List Bullet").runs[0].font.size = Pt(10)

    doc.add_paragraph("If rollback is triggered after a migration has already run:")
    add_code_block(doc, """\
# 1. Run the undo migration manually
flyway -url=jdbc:postgresql://$PROD_DB_HOST:5432/tipms \\
  -user=$DB_USER -password=$DB_PASSWORD undo

# 2. Then restart the old app version
export IMAGE_TAG=v1.2.9
docker compose -f /opt/tipms/docker-compose.yml up -d""")

    add_heading(doc, "7.3 Rolling deploy — zero downtime", level=2)
    add_kv_table(doc, [
        ["1", "Remove VM-1 from load balancer — traffic goes to VM-2 only"],
        ["2", "Cosign image verification on VM-1"],
        ["3", "Flyway migrations run against production database"],
        ["4", "New images pulled and containers restarted on VM-1"],
        ["5", "Health check on VM-1 passes → VM-1 added back to load balancer"],
        ["6", "Remove VM-2, repeat steps 2–5"],
        ["7", "Both VMs on new version → monitor Grafana for 30 minutes"],
    ], headers=["Step", "Action"])

    # Section 8
    add_heading(doc, "8. Application Logging", level=1)
    doc.add_paragraph(
        "Node.js API (pino JSON) → Docker json-file driver → Promtail (on each App VM) → "
        "Loki (on monitoring-vm, 30-day retention) → Grafana. "
        "Search logs in Grafana without SSH-ing into VMs."
    )
    add_info_box(doc,
        "The Loki push URL in Promtail config must be a real IP address, not a placeholder hostname. "
        "Using a descriptive name fails silently — Promtail drops all logs with no visible error.",
        bg=WARN_BG, label="Watch out:")

    # Section 9
    add_heading(doc, "9. Monitoring Setup", level=1)
    add_kv_table(doc, [
        ["Prometheus", "9090", "Scrapes metrics from all VMs every 15 seconds"],
        ["Grafana", "3000", "Dashboards and alerts — access via VPN only"],
        ["Loki", "3100", "Receives and stores logs from Promtail on App VMs"],
        ["Alertmanager", "9093", "Routes alerts to WhatsApp and PagerDuty"],
        ["Uptime Kuma", "3001", "Internal health checks from inside the VPC"],
    ], headers=["Service", "Port", "What it does"])

    add_heading(doc, "9.1 External uptime monitoring [NEW in v1.2]", level=2)
    add_info_box(doc,
        "Uptime Kuma is inside the VPN and cannot detect VPC-level outages or load balancer failures. "
        "External monitoring from outside the network is required.",
        bg=WARN_BG, label="Watch out:")
    doc.add_paragraph(
        "Subscribe to Better Uptime (betteruptime.com) or Freshping (freshping.io) and configure:"
    )
    for item in [
        "HTTP-check https://permit.nama-water.om every 1 minute from at least 3 geographic locations",
        "Alert on-call via WhatsApp + phone call if check fails from 2+ locations for 2+ consecutive minutes",
        "HTTP-check https://uat.permit.nama-water.om — alert if down for more than 5 minutes",
    ]:
        doc.add_paragraph(item, style="List Bullet").runs[0].font.size = Pt(10)

    # Section 10
    add_heading(doc, "10. Mobile App Pipeline", level=1)
    doc.add_paragraph(
        "All jobs use runs-on: ubuntu-latest. iOS builds delegate to Codemagic's macOS fleet."
    )
    add_kv_table(doc, [
        ["Lint + Type check", "flutter analyze + tsc --noEmit", "~1 min"],
        ["Unit tests", "flutter test — validators, API transformers, nav guards", "~2 min"],
        ["Android build", "flutter build appbundle — signs with ANDROID_KEYSTORE secret", "~8 min"],
        ["iOS — Codemagic", "Sends build request; polls 60s; GitHub job fails if CM fails", "~20 min"],
        ["Distribute", "Android → Firebase App Distribution, iOS → TestFlight", "~3 min"],
        ["Manual gate", "2 approvals required — cannot be undone", "Human"],
        ["Store release", "Android → Play Store via Fastlane, iOS → App Store Connect", "~5 min"],
    ], headers=["Stage", "What it does", "Time"])
    add_info_box(doc,
        "Store releases cannot be rolled back. Once an APK is live on the Play Store, users download it immediately. "
        "Test thoroughly on Firebase App Distribution before approving the store release gate.",
        bg=WARN_BG, label="Watch out:")

    # Section 11
    add_heading(doc, "11. Known Gaps — All Resolved", level=1)
    add_kv_table(doc, [
        ["DAST", "✅ Resolved", "OWASP ZAP Baseline scan runs as Stage 7 after every Dev deploy. Report uploaded as artifact."],
        ["Flyway undo scripts", "✅ Resolved", "Process documented in Section 7.2. Undo script tested in UAT is condition 6 of the production gate."],
        ["CI failure notifications", "✅ Resolved", "notify-on-failure job sends WhatsApp alert with failed stage name and link to logs."],
        ["Image signing", "✅ Resolved", "Cosign keyless signing in Stage 6. Signature verified in deploy script — unsigned images rejected."],
        ["External uptime monitoring", "✅ Resolved", "Better Uptime / Freshping documented in Section 9.1 with specific check configuration."],
    ], headers=["Gap", "Status", "Resolution"])

    # Section 12
    add_heading(doc, "12. Rollback Decision Tree", level=1)
    add_kv_table(doc, [
        ["Health check failed during Dev/UAT deploy", "New code crashed on startup", "Auto rollback already happened — check Loki for startup error"],
        ["Cosign verification failed at deploy", "Image not from pipeline or tampered", "Stop deploy. Investigate GHCR provenance. Re-run pipeline for a fresh signed image."],
        ["Dev/UAT up but behaving wrongly", "Logic bug in new code", "Trigger new deploy with previous tag manually"],
        ["Prod health check failed mid-rolling deploy", "New code crashed on one VM", "That VM auto-rolled back — other VM still serving. Fix bug and redeploy."],
        ["Prod deploy succeeded but users report errors", "Bug health check did not catch", "Trigger workflow_dispatch with previous version tag immediately"],
        ["DB queries failing after deploy", "Migration broke something", "Run Flyway undo script (Section 7.2), then roll back app code"],
        ["No logs appearing in Loki", "Promtail not running or wrong Loki IP", "SSH into App VM: docker logs promtail — look for connection errors"],
        ["External uptime alerts but internal checks pass", "Load balancer or VPC-level failure", "Escalate to Omantel cloud support. SSH into VMs via VPN to investigate."],
        ["ZAP DAST scan fails on known false positive", "ZAP rule too strict for this app", "Add rule ID to .zap/rules.tsv with IGNORE status, document reason, re-run pipeline"],
    ], headers=["Symptom", "Likely cause", "Action"])

    out_path = Path("documents/cicd_implementation_guide_v1.2.docx")
    doc.save(out_path)
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    build_document()
