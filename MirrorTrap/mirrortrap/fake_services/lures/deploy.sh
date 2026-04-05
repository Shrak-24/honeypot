#!/bin/bash
# deploy.sh — Acme Corp production deploy script
# Owned by: DevOps <devops@acmecorp.internal>
# WARNING: Contains service account credentials — restricted access

set -e

# ── AWS Environment ─────────────────────────────────────────────────────────
export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7CORP1XA"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYCORPKEY12"
export AWS_DEFAULT_REGION="us-east-1"

# ── EC2 / S3 Config ──────────────────────────────────────────────────────────
S3_BUCKET="acme-prod-artifacts-us-east-1"
EC2_TARGET="i-0a1b2c3d4e5f67890"
DEPLOY_USER="ec2-user"
DEPLOY_KEY="/opt/deploy/.ssh/acme_prod_rsa"

# ── Database Migration ────────────────────────────────────────────────────────
DB_HOST="db-prod-01.acmecorp.internal"
DB_USER="app_user_prod"
DB_PASS="Pr0d#DBp4ss!9q2z"
DB_NAME="acme_production"

echo "[*] Uploading artifact to S3..."
aws s3 cp ./dist/app.tar.gz s3://$S3_BUCKET/releases/$(date +%Y%m%d_%H%M%S)/

echo "[*] Running DB migrations..."
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f ./migrations/latest.sql

echo "[*] Restarting app servers..."
ssh -i $DEPLOY_KEY $DEPLOY_USER@$EC2_TARGET "sudo systemctl restart acme-app"

echo "[+] Deployment complete."
