#!/usr/bin/env bash
# R2's S3 credentials derived from CLOUDFLARE_API_TOKEN (key id = the token's id, secret = its
# SHA-256), masked, into $GITHUB_ENV for `aws s3 cp` (large uploads wrangler cannot take).
verify() { curl -sf -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["id"])'; }
id=$(verify https://api.cloudflare.com/client/v4/user/tokens/verify || verify "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/tokens/verify" || true)
secret=$(printf %s "$CLOUDFLARE_API_TOKEN" | sha256sum | cut -d' ' -f1)
echo "::add-mask::$id"
echo "::add-mask::$secret"
{ echo "AWS_ACCESS_KEY_ID=$id"; echo "AWS_SECRET_ACCESS_KEY=$secret"; echo "AWS_DEFAULT_REGION=auto"; } >> "$GITHUB_ENV"
