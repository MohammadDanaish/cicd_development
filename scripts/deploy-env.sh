#!/bin/bash
set -euo pipefail

ENV=$1
NEW_TAG=$2
APP_DIR=/opt/tipms
REGISTRY=ghcr.io/nama-water

echo "==> Deploying $NEW_TAG to $ENV"

# Verify image signature — reject anything not produced by the pipeline
cosign verify \
  $REGISTRY/nama-tipms-api:$NEW_TAG \
  --certificate-identity="https://github.com/nama-water/nama-tipms/.github/workflows/ci-cd.yml@refs/heads/main" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" || {
    echo "ERROR: Image signature verification failed — aborting deploy"
    exit 1
  }

# Save current tag for rollback
PREV_TAG=$(cat $APP_DIR/current_tag 2>/dev/null || echo "latest")
echo $NEW_TAG > $APP_DIR/current_tag

# Run Flyway migrations — app is untouched if this fails
echo "==> Running migrations"
flyway \
  -url="jdbc:postgresql://$DB_HOST:5432/tipms" \
  -user=tipms_app \
  -password="$DB_PASSWORD" \
  -locations="filesystem:$APP_DIR/db/migrations" \
  migrate

# Write secrets to .env
cat > $APP_DIR/.env << EOF
DB_HOST=$DB_HOST
DB_PASSWORD=$DB_PASSWORD
JWT_SECRET_KEY=$JWT_SECRET_KEY
FCM_SERVER_KEY=$FCM_SERVER_KEY
LOG_LEVEL=${LOG_LEVEL:-info}
ENVIRONMENT=$ENV
EOF
chmod 600 $APP_DIR/.env

# Pull and start containers
echo "==> Starting containers"
export IMAGE_TAG=$NEW_TAG
docker compose -f $APP_DIR/docker-compose.yml pull
docker compose -f $APP_DIR/docker-compose.yml up -d

# Health check — 5 attempts × 10 seconds
echo "==> Health check"
for i in 1 2 3 4 5; do
  sleep 10
  if docker compose -f $APP_DIR/docker-compose.yml exec -T api \
      curl -sf http://localhost:3000/health > /dev/null 2>&1; then
    echo "==> Deploy succeeded: $NEW_TAG on $ENV"
    exit 0
  fi
  echo "  Attempt $i/5 failed..."
done

# Rollback on health check failure
echo "==> Health check failed — rolling back to $PREV_TAG"
export IMAGE_TAG=$PREV_TAG
docker compose -f $APP_DIR/docker-compose.yml up -d
echo $PREV_TAG > $APP_DIR/current_tag
exit 1
