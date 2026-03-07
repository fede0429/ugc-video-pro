#!/usr/bin/env bash
# ============================================================
# UGC Video Pro - SSL Certificate Initialization
# ============================================================
# Obtains a Let's Encrypt TLS certificate for your domain
# using the webroot challenge method (nginx must be running).
#
# Usage:
#   chmod +x scripts/init-ssl.sh
#   ./scripts/init-ssl.sh your-domain.com your@email.com
#
# Prerequisites:
#   1. DNS A record for your-domain.com pointing to this server
#   2. Ports 80 and 443 open in your firewall
#   3. docker compose installed (v2 syntax)
#
# What this script does:
#   1. Creates required certbot directory structure
#   2. Starts nginx in HTTP-only mode (temporary config)
#   3. Runs certbot to obtain the initial certificate
#   4. Reloads nginx with full SSL configuration
#   5. Verifies the certificate was obtained successfully
# ============================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No colour

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Argument validation ───────────────────────────────────────
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <domain> <email>"
    echo ""
    echo "  domain  Your domain name, e.g. ugcvideo.pro"
    echo "  email   Your email address for Let's Encrypt notifications"
    echo ""
    echo "Example:"
    echo "  $0 ugcvideo.pro admin@ugcvideo.pro"
    exit 1
fi

DOMAIN="$1"
EMAIL="$2"

# ── Confirm before proceeding ────────────────────────────────
log_info "Initializing SSL certificate for domain: ${DOMAIN}"
log_info "Let's Encrypt account email: ${EMAIL}"
echo ""
read -rp "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    log_warn "Aborted."
    exit 0
fi
echo ""

# ── Step 1: Create certbot directory structure ────────────────
log_info "Creating certbot directories..."
mkdir -p certbot/conf certbot/www
log_success "Directories created: certbot/conf, certbot/www"

# ── Step 2: Patch nginx.conf with the correct domain ─────────
if grep -q "your-domain.com" nginx.conf; then
    log_info "Patching nginx.conf with domain: ${DOMAIN}..."
    # Replace placeholder domain in nginx.conf
    sed -i "s/your-domain\.com/${DOMAIN}/g" nginx.conf
    log_success "nginx.conf updated"
else
    log_warn "nginx.conf does not contain 'your-domain.com' — assuming already patched"
fi

# ── Step 3: Start nginx (HTTP only, to serve ACME challenges) ─
log_info "Starting nginx service..."
if docker compose ps nginx | grep -q "Up"; then
    log_info "nginx is already running — reloading configuration..."
    docker compose exec nginx nginx -s reload
else
    docker compose up -d nginx
    sleep 3
fi
log_success "nginx is running"

# ── Step 4: Verify domain resolves to this server ─────────────
log_info "Verifying HTTP access to http://${DOMAIN}/.well-known/acme-challenge/test..."
if curl -sf --max-time 10 \
       -o /dev/null \
       "http://${DOMAIN}/.well-known/acme-challenge/test" 2>/dev/null; then
    log_success "Domain is reachable via HTTP"
elif curl -sf --max-time 10 \
          -o /dev/null \
          -w "%{http_code}" \
          "http://${DOMAIN}/" 2>/dev/null | grep -qE "^(200|301|302|404)"; then
    log_success "Domain is reachable via HTTP (challenge directory test returned 404 — that's OK)"
else
    log_warn "Could not reach http://${DOMAIN}/ — DNS may not have propagated yet."
    log_warn "Proceeding anyway; certbot will provide a clearer error if unreachable."
fi

# ── Step 5: Obtain the SSL certificate via certbot ─────────────
log_info "Running certbot to obtain certificate for ${DOMAIN}..."
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "${EMAIL}" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "${DOMAIN}" \
    -d "www.${DOMAIN}"

CERTBOT_EXIT=$?
if [[ $CERTBOT_EXIT -ne 0 ]]; then
    log_error "certbot failed with exit code ${CERTBOT_EXIT}"
    log_error "Common causes:"
    log_error "  - DNS A/AAAA record for ${DOMAIN} does not point to this server"
    log_error "  - Port 80 is blocked by your firewall"
    log_error "  - Rate limit hit (5 certificates per domain per week)"
    exit 1
fi
log_success "Certificate obtained for ${DOMAIN}"

# ── Step 6: Reload nginx with full SSL config ─────────────────
log_info "Reloading nginx with SSL configuration..."
docker compose exec nginx nginx -s reload
log_success "nginx reloaded"

# ── Step 7: Verify certificate ────────────────────────────────
log_info "Verifying HTTPS connection to https://${DOMAIN}..."
sleep 2
if curl -sf --max-time 15 -o /dev/null "https://${DOMAIN}/"; then
    log_success "HTTPS is working on https://${DOMAIN}/"
else
    log_warn "Could not reach https://${DOMAIN}/ — nginx may need a moment to apply the cert."
    log_warn "Try: curl -I https://${DOMAIN}/"
fi

# ── Step 8: Start all remaining services ──────────────────────
log_info "Starting all services (app + db + certbot renewal loop)..."
docker compose up -d
log_success "All services started"

echo ""
echo "========================================================"
log_success "SSL initialization complete!"
echo ""
echo "  Domain:      https://${DOMAIN}"
echo "  Certificate: certbot/conf/live/${DOMAIN}/"
echo "  Renewal:     Automatic (every 12h via certbot service)"
echo ""
echo "Next steps:"
echo "  1. Visit https://${DOMAIN} in your browser"
echo "  2. Log in with your admin credentials from .env"
echo "  3. Uncomment HSTS header in nginx.conf once you"
echo "     have verified SSL is working correctly"
echo "========================================================"
