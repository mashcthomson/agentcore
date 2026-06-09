#!/usr/bin/env bash
#
# AgentCore workshop — paste-safe gateway setup.
#
# Run this instead of copy-pasting multi-line commands into your terminal.
# Running a downloaded file avoids the hidden carriage-return (\r) corruption
# that mangles ARNs when long lines are pasted from a doc into a shell.
#
#   chmod +x setup.sh && ./setup.sh
#   (or: bash setup.sh)
#
# Optional overrides:
#   GATEWAY_NAME=my-gateway REGION=ap-southeast-2 ROLE_NAME=AgentCoreGatewayExecutionRole ./setup.sh

set -euo pipefail

# ----- configuration (override via environment if you like) -------------------
REGION="${REGION:-ap-southeast-2}"
GATEWAY_NAME="${GATEWAY_NAME:-research-tool-gateway}"
ROLE_NAME="${ROLE_NAME:-AgentCoreGatewayExecutionRole}"
OUTPUT_FILE="${OUTPUT_FILE:-gateway_info.json}"
# S3 bucket holding OpenAPI schema files for OpenAPI targets.
# Defaults to the workshop convention: agentcore-gateway-specs-<account>.
SPECS_BUCKET="${SPECS_BUCKET:-}"

# strip every non-printable byte (CR, LF, NBSP, ...) from a string
sanitize() { printf '%s' "$1" | tr -cd '[:print:]'; }

# ----- 0. preflight -----------------------------------------------------------
command -v aws >/dev/null 2>&1 || { echo "ERROR: aws CLI not found on PATH." >&2; exit 1; }

echo ">>> Verifying AWS credentials..."
if ! CALLER=$(aws sts get-caller-identity --output json 2>/dev/null); then
  echo "ERROR: no valid AWS credentials. Run 'aws sso login' (or configure creds) and retry." >&2
  exit 1
fi
ACCOUNT=$(printf '%s' "$CALLER" | sed -n 's/.*"Account"[ ]*:[ ]*"\([0-9]*\)".*/\1/p')
ACCOUNT=$(printf '%s' "$ACCOUNT" | tr -dc '0-9')   # digits only — bulletproof
if [ -z "$ACCOUNT" ]; then
  echo "ERROR: could not determine AWS account id." >&2
  exit 1
fi
echo "    Account: $ACCOUNT   Region: $REGION"

# ----- 1. resolve the execution role, creating it if missing -----------------
[ -z "$SPECS_BUCKET" ] && SPECS_BUCKET="agentcore-gateway-specs-$ACCOUNT"

TRUST_FILE=$(mktemp)
POLICY_FILE=$(mktemp)
trap 'rm -f "$TRUST_FILE" "$POLICY_FILE"' EXIT

# Trust policy: let the AgentCore service assume this role, scoped to this
# account/region so it can only be used on this account's AgentCore resources.
printf '%s' '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {"aws:SourceAccount": "'"$ACCOUNT"'"},
      "ArnLike": {"aws:SourceArn": "arn:aws:bedrock-agentcore:'"$REGION"':'"$ACCOUNT"':*"}
    }
  }]
}' > "$TRUST_FILE"

# Execution-role permissions covering every target type this workshop uses:
#  - Lambda targets:        lambda:InvokeFunction
#  - OpenAPI/API-key/OAuth: fetch the outbound credential from the token vault.
#    NOTE: bedrock-agentcore:GetResourceApiKey is authorized at runtime against
#    BOTH the workload-identity-directory AND the token-vault root resources
#    (not the apikeycredentialprovider sub-resource the docs show), so we grant
#    the credential actions on both directories and their children.
#  - OpenAPI schema in S3:  s3:GetObject on the specs bucket.
#  - Secrets Manager:       read the secret backing the API key credential.
printf '%s' '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeLambdaTargets",
      "Effect": "Allow",
      "Action": ["lambda:InvokeFunction"],
      "Resource": "arn:aws:lambda:'"$REGION"':'"$ACCOUNT"':function:*"
    },
    {
      "Sid": "OutboundCredentials",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetWorkloadAccessToken",
        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        "bedrock-agentcore:GetResourceApiKey",
        "bedrock-agentcore:GetResourceOauth2Token"
      ],
      "Resource": [
        "arn:aws:bedrock-agentcore:'"$REGION"':'"$ACCOUNT"':workload-identity-directory/default",
        "arn:aws:bedrock-agentcore:'"$REGION"':'"$ACCOUNT"':workload-identity-directory/default/*",
        "arn:aws:bedrock-agentcore:'"$REGION"':'"$ACCOUNT"':token-vault/default",
        "arn:aws:bedrock-agentcore:'"$REGION"':'"$ACCOUNT"':token-vault/default/*"
      ]
    },
    {
      "Sid": "GetApiKeySecret",
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:'"$REGION"':'"$ACCOUNT"':secret:bedrock-agentcore-identity!default/apikey/*"
    },
    {
      "Sid": "ReadOpenApiSchemaFromS3",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::'"$SPECS_BUCKET"'/*"
    }
  ]
}' > "$POLICY_FILE"

echo ">>> Resolving execution role '$ROLE_NAME'..."
if ! ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null); then
  echo "    Role not found — creating '$ROLE_NAME'..."
  ROLE_ARN=$(aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TRUST_FILE" \
    --description "AgentCore gateway execution role (workshop)" \
    --query 'Role.Arn' --output text)
  NEW_ROLE=1
fi

# Always (re)attach the policy so existing roles are healed too (idempotent).
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "AgentCoreGatewayTargetAccess" \
  --policy-document "file://$POLICY_FILE"
echo "    Attached policy 'AgentCoreGatewayTargetAccess' (Lambda + OpenAPI/API-key + S3 + Secrets)."

if [ "${NEW_ROLE:-0}" = "1" ]; then
  echo "    Created role; waiting 10s for IAM propagation before it can be assumed..."
  sleep 10
fi

ROLE_ARN=$(sanitize "$ROLE_ARN")
case "$ROLE_ARN" in
  arn:aws:iam::"$ACCOUNT":role/*) : ;;   # looks good
  *) echo "ERROR: resolved ROLE_ARN looks wrong: [$ROLE_ARN]" >&2; exit 1 ;;
esac
echo "    ROLE_ARN: [$ROLE_ARN]"

# ----- 2. create the gateway (idempotent: reuse if it already exists) ---------
EXISTING_ID=$(aws bedrock-agentcore-control list-gateways --region "$REGION" \
  --query "items[?name=='$GATEWAY_NAME'].gatewayId | [0]" --output text 2>/dev/null || true)

if [ -n "$EXISTING_ID" ] && [ "$EXISTING_ID" != "None" ]; then
  echo ">>> Gateway '$GATEWAY_NAME' already exists ($EXISTING_ID) — reusing it."
  GATEWAY_ID="$EXISTING_ID"
  aws bedrock-agentcore-control get-gateway \
    --gateway-identifier "$GATEWAY_ID" --region "$REGION" > "$OUTPUT_FILE"
else
  echo ">>> Creating gateway '$GATEWAY_NAME'..."
  aws bedrock-agentcore-control create-gateway \
    --name "$GATEWAY_NAME" \
    --role-arn "$ROLE_ARN" \
    --protocol-type MCP \
    --authorizer-type AWS_IAM \
    --protocol-configuration '{"mcp": {"searchType": "SEMANTIC"}}' \
    --region "$REGION" > "$OUTPUT_FILE"
  GATEWAY_ID=$(sed -n 's/.*"gatewayId"[ ]*:[ ]*"\([^"]*\)".*/\1/p' "$OUTPUT_FILE")
fi

echo ">>> Done. Details written to $OUTPUT_FILE"
echo "    gatewayId: $GATEWAY_ID"
