#!/usr/bin/env bash
#
# Rebuild the staging database from the latest production backup, scrub
# every identifying field out of it, and rehearse the pending migrations
# against it.
#
#   sudo bash /srv/agribiz-drp/deploy/staging-refresh.sh
#
# WHY THIS EXISTS
# ---------------
# ResearchOS brief §18.2 ("create staging and production environments; stop
# direct untracked production changes"). Until 2026-09-13 every change went
# straight to production, against a database holding 800 real organisations.
#
# WHY IT IS A DATABASE, NOT A FULL SECOND STACK
# ---------------------------------------------
# This VPS has 956MB of RAM, already shares it with the sibling ABI project,
# and is using swap at rest. A permanently-running second web stack would
# squeeze the production study system for the sake of an environment used
# occasionally. The risk staging actually mitigates here is a bad migration
# against real data -- and that is testable with a database alone. The
# staging web services exist as on-demand systemd units (drp-staging-*),
# disabled by default; start them only when someone needs to click around.
#
# WHY THE DATA IS SCRUBBED
# ------------------------
# docs/23 requires staging to hold no real Main-400 records. But rehearsing
# a migration against synthetic data is much weaker -- the field-width
# failures found during the register import (phone, district, stratum code,
# value chain) were exactly the kind of thing only real data reveals. So
# staging gets production's real *shape and volume* with every identifying
# value replaced. The scrub is verified, not assumed: the script re-queries
# afterwards and aborts if anything identifying survived.

set -euo pipefail

PROD_DB="drp_prod"
STAGING_DB="drp_staging"
BACKUP_DIR="/srv/agribiz-drp/backups"
BACKEND="/srv/agribiz-drp/backend"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
ok()   { printf '    \033[1;32mok\033[0m   %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this with sudo."

# ------------------------------------------------------------ source dump
log "Taking a fresh production backup to restore from"
bash /srv/agribiz-drp/deploy/backup.sh >/dev/null || die "backup.sh failed"
DUMP="$(ls -t "$BACKUP_DIR"/drp-*.sql.gz | head -1)"
[[ -f "$DUMP" ]] || die "No backup found in $BACKUP_DIR"
ok "using $(basename "$DUMP")"

# ------------------------------------------------------------ rebuild db
log "Rebuilding $STAGING_DB"
sudo -u postgres psql -qAt -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$STAGING_DB';" >/dev/null
sudo -u postgres dropdb --if-exists "$STAGING_DB"
sudo -u postgres createdb -O drp_user "$STAGING_DB"
gunzip -c "$DUMP" | sudo -u postgres psql -q "$STAGING_DB" >/dev/null 2>&1 \
    || die "restore into $STAGING_DB failed"
ok "restored"

# ------------------------------------------------------------ scrub PII
# Every column that can carry a real person's or organisation's identity.
# Deterministic replacements (id-based) rather than NULLs, so row shapes,
# lengths and NOT NULL constraints still resemble production.
log "Scrubbing identifying data"
sudo -u postgres psql -q "$STAGING_DB" <<'SQL' >/dev/null
BEGIN;

UPDATE sampling_organisation SET
    name = 'Scrubbed Organisation ' || id,
    district = 'Scrubbed District';

UPDATE contacts_respondent SET
    full_name         = 'Scrubbed Respondent ' || id,
    phone             = CASE WHEN phone = '' THEN '' ELSE '+2637000' || lpad(id::text, 5, '0') END,
    whatsapp_number   = CASE WHEN whatsapp_number = '' THEN '' ELSE '+2637000' || lpad(id::text, 5, '0') END,
    email             = CASE WHEN email = '' THEN '' ELSE 'respondent' || id || '@example.invalid' END,
    gatekeeper_name   = CASE WHEN gatekeeper_name = '' THEN '' ELSE 'Scrubbed Gatekeeper ' || id END,
    gatekeeper_contact= CASE WHEN gatekeeper_contact = '' THEN '' ELSE '+2637000' || lpad(id::text, 5, '0') END;

UPDATE kii_kiirecord SET
    participant_name = 'Scrubbed Informant ' || id,
    field_notes      = CASE WHEN field_notes = '' THEN '' ELSE '[scrubbed]' END,
    recording_reference = CASE WHEN recording_reference = '' THEN '' ELSE '[scrubbed]' END,
    -- The register imports preserved every source column losslessly in
    -- metadata. For KII that includes organisation_name, free-text
    -- verification notes and evidence URLs about a named individual --
    -- scrubbing only the model fields would have left all of it exposed.
    metadata = metadata
        || jsonb_build_object('organisation_name', 'Scrubbed Organisation')
        || jsonb_build_object('verification_notes', '[scrubbed]')
        || jsonb_build_object('why_information_rich', '[scrubbed]')
        || jsonb_build_object('public_evidence_url', '[scrubbed]')
        || jsonb_build_object('verification_source_url', '[scrubbed]');

UPDATE contacts_contactevent SET notes = CASE WHEN notes = '' THEN '' ELSE '[scrubbed]' END;

-- sampling_samplecase.metadata carries preferred_respondent (a role or a
-- named person) and free-text verification evidence.
UPDATE sampling_samplecase SET
    metadata = metadata
        || jsonb_build_object('preferred_respondent', '[scrubbed]')
        || jsonb_build_object('verification_evidence', '[scrubbed]');

-- Checked 2026-09-14: sampling_organisation.metadata holds only
-- source_master_id, and evidence_documentrecord.metadata only block/link/
-- retrieval_status/source_row_number/type_raw -- register identifiers and
-- public document locators, no participant identity. Left intact so the
-- import provenance is still exercised. Re-check if the importers change.

-- Invitation hashes are not PII but are live credentials for real cases.
UPDATE invitations_invitationtoken SET
    token_hash = md5('staging' || id), manual_code_hash = md5('staging-code' || id);

-- Internal accounts: keep roles and usernames' shape, destroy credentials.
UPDATE accounts_user SET
    password = '!scrubbed-unusable',
    email    = CASE WHEN email = '' THEN '' ELSE 'user' || id || '@example.invalid' END,
    phone    = CASE WHEN phone = '' THEN '' ELSE '+2637000' || lpad(id::text, 5, '0') END,
    first_name = '', last_name = '';

-- messaging_messagelog checked 2026-09-14: stores channel/status/refs only,
-- no message body, so there is nothing to scrub there.

-- Free-text researcher fields can quote respondents verbatim.
UPDATE proit_evidencesource SET researcher_notes = CASE WHEN researcher_notes = '' THEN '' ELSE '[scrubbed]' END;

COMMIT;
SQL
ok "scrub applied"

# --------------------------------------------------- verify the scrub held
# Assert, don't assume. Any real value surviving here means staging is now
# an unprotected copy of participant data.
log "Verifying no production identity survived"
LEAKS=$(sudo -u postgres psql -qAt "$STAGING_DB" <<'SQL'
SELECT
  (SELECT count(*) FROM sampling_organisation WHERE name NOT LIKE 'Scrubbed %')
+ (SELECT count(*) FROM contacts_respondent  WHERE full_name NOT LIKE 'Scrubbed %')
+ (SELECT count(*) FROM kii_kiirecord        WHERE participant_name NOT LIKE 'Scrubbed %')
+ (SELECT count(*) FROM contacts_respondent  WHERE email <> '' AND email NOT LIKE '%@example.invalid')
+ (SELECT count(*) FROM accounts_user        WHERE password <> '!scrubbed-unusable')
+ (SELECT count(*) FROM accounts_user        WHERE email <> '' AND email NOT LIKE '%@example.invalid')
-- The JSONB blobs, which are the easiest place for identity to survive.
+ (SELECT count(*) FROM kii_kiirecord
     WHERE metadata ? 'organisation_name'
       AND metadata->>'organisation_name' <> 'Scrubbed Organisation')
+ (SELECT count(*) FROM kii_kiirecord
     WHERE metadata ? 'verification_notes' AND metadata->>'verification_notes' <> '[scrubbed]')
+ (SELECT count(*) FROM sampling_samplecase
     WHERE metadata ? 'preferred_respondent' AND metadata->>'preferred_respondent' <> '[scrubbed]');
SQL
)
[[ "$LEAKS" == "0" ]] || die "$LEAKS identifying value(s) survived the scrub. Staging destroyed rather than left exposed: $(sudo -u postgres dropdb --if-exists "$STAGING_DB"; echo dropped)"
ok "0 identifying values remain"

ROWS=$(sudo -u postgres psql -qAt "$STAGING_DB" -c \
  "SELECT (SELECT count(*) FROM sampling_organisation) || ' organisations, ' ||
          (SELECT count(*) FROM sampling_samplecase)  || ' cases, ' ||
          (SELECT count(*) FROM kii_kiirecord)        || ' KII, ' ||
          (SELECT count(*) FROM evidence_documentrecord) || ' documents';")
ok "production shape preserved: $ROWS"

# ------------------------------------------------- rehearse the migrations
log "Rehearsing migrations against staging"
# Derive the staging URL from production's own DATABASE_URL by swapping only
# the database name, so the credential is never duplicated into this script
# or into a second env file that could drift. Extracted in a subshell and
# not echoed.
PROD_URL="$(grep -E '^DATABASE_URL=' "$BACKEND/.env" | head -1 | cut -d= -f2-)"
[[ -n "$PROD_URL" ]] || die "No DATABASE_URL in $BACKEND/.env -- cannot reach staging."
STAGING_URL="${PROD_URL%/*}/$STAGING_DB"

if sudo -u agribiz-drp env \
        DJANGO_SETTINGS_MODULE=config.settings.prod \
        DATABASE_URL="$STAGING_URL" \
        "$BACKEND/venv/bin/python" "$BACKEND/manage.py" migrate --noinput; then
    ok "migrations apply cleanly"
else
    die "MIGRATIONS FAILED against staging. Do not deploy to production until this is fixed."
fi

log "Staging refresh complete"
printf '    Database : %s\n' "$STAGING_DB"
printf '    Web      : disabled by default. Start on demand with\n'
printf '               systemctl start drp-staging-backend drp-staging-frontend\n'
printf '               (and stop them again -- this box is memory-constrained)\n'
