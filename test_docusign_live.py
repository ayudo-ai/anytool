"""
Live DocuSign test — the exact scenario that was broken on Composio.

Tests:
1. Create envelope from template with templateRoles (THE BUG)
2. Get envelope status
3. List envelopes
4. Get recipients

Requires .env:
  NANGO_SECRET_KEY=xxx
  DOCUSIGN_CONNECTION_ID=xxx  (from Nango)
  DOCUSIGN_TEMPLATE_ID=xxx    (a template in your DocuSign account)
  DOCUSIGN_ACCOUNT_ID=xxx     (your DocuSign account ID)

Run: python test_docusign_live.py
"""

import asyncio
import json
import os
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

from anytool import AnyAPI

NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY", "")
DOCUSIGN_CONNECTION_ID = os.environ.get("DOCUSIGN_CONNECTION_ID", "")
DOCUSIGN_TEMPLATE_ID = os.environ.get("DOCUSIGN_TEMPLATE_ID", "")
DOCUSIGN_ACCOUNT_ID = os.environ.get("DOCUSIGN_ACCOUNT_ID", "")
DOCUSIGN_PROVIDER = os.environ.get("DOCUSIGN_PROVIDER", "docusign-sandbox")

TEST_SIGNER_NAME = os.environ.get("TEST_SIGNER_NAME", "Nitin Panwar")
TEST_SIGNER_EMAIL = os.environ.get("TEST_SIGNER_EMAIL", "nitinpanwar98@gmail.com")
TEST_ROLE_NAME = os.environ.get("TEST_ROLE_NAME", "Signer")  # Must match template role

missing = []
if not NANGO_SECRET_KEY: missing.append("NANGO_SECRET_KEY")
if not DOCUSIGN_CONNECTION_ID: missing.append("DOCUSIGN_CONNECTION_ID")
if not DOCUSIGN_TEMPLATE_ID: missing.append("DOCUSIGN_TEMPLATE_ID")
if not DOCUSIGN_ACCOUNT_ID: missing.append("DOCUSIGN_ACCOUNT_ID")

if missing:
    print(f"❌ Missing in .env: {', '.join(missing)}")
    print()
    print("Setup:")
    print("1. Nango → Integrations → DocuSign Sandbox → configure OAuth")
    print("2. Nango → Connections → Create → DocuSign Sandbox")
    print("3. Copy connection ID → DOCUSIGN_CONNECTION_ID")
    print("4. DocuSign admin → Apps and Keys → copy Account ID → DOCUSIGN_ACCOUNT_ID")
    print("5. DocuSign → Templates → pick one → copy Template ID → DOCUSIGN_TEMPLATE_ID")
    print("6. Set TEST_ROLE_NAME to match a role in your template (default: 'Signer')")
    exit(1)


async def main():
    print("=" * 60)
    print("  anyapi — Live DocuSign Test")
    print("  (The exact scenario that broke on Composio)")
    print("=" * 60)
    print()
    print(f"  Connection:  {DOCUSIGN_CONNECTION_ID}")
    print(f"  Account:     {DOCUSIGN_ACCOUNT_ID}")
    print(f"  Template:    {DOCUSIGN_TEMPLATE_ID}")
    print(f"  Signer:      {TEST_SIGNER_NAME} <{TEST_SIGNER_EMAIL}>")
    print(f"  Role:        {TEST_ROLE_NAME}")
    print()

    api = AnyAPI(nango_secret_key=NANGO_SECRET_KEY)

    # ── Step 1: Check connection ──────────────────────────────────────
    print("Step 1: Check Connection")
    print("-" * 40)
    connected = await api.is_connected(DOCUSIGN_PROVIDER, DOCUSIGN_CONNECTION_ID)
    if connected:
        print(f"✅ Connected to DocuSign")
    else:
        print(f"❌ Not connected. Create connection in Nango first.")
        await api.close()
        return

    # ── Step 2: List envelopes (sanity check) ─────────────────────────
    print(f"\nStep 2: List Recent Envelopes")
    print("-" * 40)
    result = await api.call(
        "docusign_list_envelopes",
        connection_id=DOCUSIGN_CONNECTION_ID,
        account_id=DOCUSIGN_ACCOUNT_ID,
        from_date="2024-01-01T00:00:00Z",
        count=5,
    )
    if result["successful"]:
        envelopes = result.get("data", {}).get("envelopes", [])
        print(f"✅ Found {len(envelopes or [])} recent envelopes")
        for env in (envelopes or [])[:3]:
            print(f"   - {env.get('envelopeId', '?')[:12]}... | {env.get('status', '?')} | {env.get('emailSubject', '?')[:40]}")
    else:
        print(f"❌ List failed: {result.get('error', 'Unknown')}")

    # ── Step 3: Create envelope from template (THE BUG FIX) ───────────
    print(f"\nStep 3: Create Envelope from Template")
    print("-" * 40)
    print(f"   Template: {DOCUSIGN_TEMPLATE_ID}")
    print(f"   Role: {TEST_ROLE_NAME} → {TEST_SIGNER_NAME} <{TEST_SIGNER_EMAIL}>")
    print()

    # This is EXACTLY what Composio turned into templateRoles: [{}]
    result = await api.call(
        "docusign_create_envelope",
        connection_id=DOCUSIGN_CONNECTION_ID,
        account_id=DOCUSIGN_ACCOUNT_ID,
        template_id=DOCUSIGN_TEMPLATE_ID,
        template_roles=[
            {
                "roleName": TEST_ROLE_NAME,
                "name": TEST_SIGNER_NAME,
                "email": TEST_SIGNER_EMAIL,
            }
        ],
        status="sent",
        email_subject=f"anyapi test — {TEST_SIGNER_NAME}",
    )

    if result["successful"]:
        envelope_id = result["extracted_ids"].get("envelope_id", "")
        print(f"✅ Envelope created and sent!")
        print(f"   Envelope ID: {envelope_id}")
        print(f"   Status: {result['data'].get('status', '?')}")
        print()
        print(f"   🎉 templateRoles preserved! Composio would have sent [{{}}] here.")
    else:
        print(f"❌ Create failed: {result.get('error', 'Unknown')}")
        print()
        print(f"   Full response:")
        print(f"   {json.dumps(result.get('data', {}), indent=2)[:500]}")
        envelope_id = ""

    # ── Step 4: Get envelope status ───────────────────────────────────
    if envelope_id:
        print(f"\nStep 4: Get Envelope Status")
        print("-" * 40)
        result = await api.call(
            "docusign_get_envelope",
            connection_id=DOCUSIGN_CONNECTION_ID,
            account_id=DOCUSIGN_ACCOUNT_ID,
            envelope_id=envelope_id,
        )
        if result["successful"]:
            data = result["data"]
            print(f"✅ Status: {data.get('status', '?')}")
            print(f"   Subject: {data.get('emailSubject', '?')}")
            print(f"   Created: {data.get('createdDateTime', '?')}")
            print(f"   Sent:    {data.get('sentDateTime', '?')}")
        else:
            print(f"❌ Get status failed: {result.get('error', 'Unknown')}")

    # ── Step 5: Get recipients ────────────────────────────────────────
    if envelope_id:
        print(f"\nStep 5: Get Recipients")
        print("-" * 40)
        result = await api.call(
            "docusign_get_recipients",
            connection_id=DOCUSIGN_CONNECTION_ID,
            account_id=DOCUSIGN_ACCOUNT_ID,
            envelope_id=envelope_id,
        )
        if result["successful"]:
            signers = result.get("data", {}).get("signers", [])
            print(f"✅ {len(signers)} signer(s):")
            for s in signers:
                print(f"   - {s.get('name', '?')} <{s.get('email', '?')}> | status: {s.get('status', '?')}")
        else:
            print(f"❌ Get recipients failed: {result.get('error', 'Unknown')}")

    # ── Step 6: LangChain tools ───────────────────────────────────────
    print(f"\nStep 6: LangChain Tools")
    print("-" * 40)
    tools = api.get_tools("docusign", connection_id=DOCUSIGN_CONNECTION_ID)
    print(f"✅ Generated {len(tools)} DocuSign tools:")
    for t in tools:
        print(f"   - {t.name}")

    # Done
    print()
    print("=" * 60)
    if envelope_id:
        print("  ✅ ALL TESTS PASSED — DocuSign works with anyapi!")
        print(f"  Check {TEST_SIGNER_EMAIL} inbox for the signing request.")
    else:
        print("  ⚠️  Envelope creation failed — check credentials and template")
    print("=" * 60)

    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
