#!/bin/bash
# Upload app icons for new apps to S3
# Run from a machine with AWS CLI configured and internet access
#
# Usage: bash scripts/upload_icons.sh

set -e

BUCKET="ayudo-dev"
PREFIX="app_icons"
TMP_DIR=$(mktemp -d)

declare -A LOGO_URLS=(
  ["airtable"]="https://logo.clearbit.com/airtable.com"
  ["asana"]="https://logo.clearbit.com/asana.com"
  ["calendly"]="https://logo.clearbit.com/calendly.com"
  ["clickup"]="https://logo.clearbit.com/clickup.com"
  ["intercom"]="https://logo.clearbit.com/intercom.com"
  ["jira"]="https://logo.clearbit.com/atlassian.com"
  ["linear"]="https://logo.clearbit.com/linear.app"
  ["monday"]="https://logo.clearbit.com/monday.com"
  ["notion"]="https://logo.clearbit.com/notion.so"
  ["salesforce"]="https://logo.clearbit.com/salesforce.com"
  ["shopify"]="https://logo.clearbit.com/shopify.com"
  ["stripe"]="https://logo.clearbit.com/stripe.com"
  ["trello"]="https://logo.clearbit.com/trello.com"
  ["twilio"]="https://logo.clearbit.com/twilio.com"
)

echo "Downloading and uploading icons..."
echo ""

for app in "${!LOGO_URLS[@]}"; do
  url="${LOGO_URLS[$app]}"
  file="${TMP_DIR}/${app}.png"
  s3_key="${PREFIX}/${app}.png"
  
  echo -n "  ${app}... "
  if curl -sL "$url" -o "$file" && [ -s "$file" ]; then
    aws s3 cp "$file" "s3://${BUCKET}/${s3_key}" --content-type "image/png" --acl public-read --quiet
    echo "✓ uploaded → ${s3_key}"
  else
    echo "✗ download failed"
  fi
done

echo ""
echo "Done! Update registry.py with icon_url paths."
echo ""
echo "Add to APPS dict in anytool/apps/registry.py:"
for app in "${!LOGO_URLS[@]}"; do
  echo "    \"${app}\": AppConfig(name=\"$(echo ${app^})\", slug=\"${app}\", icon_url=\"${PREFIX}/${app}.png\"),"
done

rm -rf "$TMP_DIR"
