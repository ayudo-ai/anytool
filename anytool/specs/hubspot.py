"""
HubSpot CRM API v3 specs.

Auth: OAuth2 via Nango.
Base URL: https://api.hubapi.com

Key actions for AI ops automation:
- Contacts: create, get, update, search, list
- Companies: create, get, update, search
- Deals: create, get, update, search
- Notes/Engagements: create note on contact/deal
- Associations: link contact↔company, contact↔deal
"""

from __future__ import annotations

from anytool.specs.base import ActionSpec, ParamSpec


# ══════════════════════════════════════════════════════════════════════
#  CONTACTS
# ══════════════════════════════════════════════════════════════════════

HUBSPOT_CREATE_CONTACT = ActionSpec(
    name="hubspot_create_contact",
    app="hubspot",
    description=(
        "Create a new contact in HubSpot. "
        "Pass properties as key-value pairs: email, firstname, lastname, phone, company, etc."
    ),
    method="POST",
    path="/crm/v3/objects/contacts",
    content_type="application/json",
    params=[
        ParamSpec(name="email", type="string", required=True,
                  description="Contact email address"),
        ParamSpec(name="firstname", type="string", required=False,
                  description="First name"),
        ParamSpec(name="lastname", type="string", required=False,
                  description="Last name"),
        ParamSpec(name="phone", type="string", required=False,
                  description="Phone number"),
        ParamSpec(name="company", type="string", required=False,
                  description="Company name"),
        ParamSpec(name="jobtitle", type="string", required=False,
                  description="Job title"),
        ParamSpec(name="lifecyclestage", type="string", required=False,
                  description="Lifecycle stage: subscriber, lead, marketingqualifiedlead, salesqualifiedlead, opportunity, customer, evangelist, other"),
    ],
    request_transform="hubspot_properties",
    response_ids={"id": "contact_id"},
)

HUBSPOT_GET_CONTACT = ActionSpec(
    name="hubspot_get_contact",
    app="hubspot",
    description=(
        "Get a contact by ID. Returns all default properties. "
        "Specify extra properties to fetch with the properties param."
    ),
    method="GET",
    path="/crm/v3/objects/contacts/{contact_id}",
    params=[
        ParamSpec(name="contact_id", type="string", required=True, location="path",
                  description="HubSpot contact ID"),
        ParamSpec(name="properties", type="string", required=False, location="query",
                  description="Comma-separated property names to include"),
    ],
    response_ids={"id": "contact_id"},
)

HUBSPOT_UPDATE_CONTACT = ActionSpec(
    name="hubspot_update_contact",
    app="hubspot",
    description=(
        "Update a contact's properties. "
        "Pass any HubSpot contact property as a parameter."
    ),
    method="PATCH",
    path="/crm/v3/objects/contacts/{contact_id}",
    content_type="application/json",
    params=[
        ParamSpec(name="contact_id", type="string", required=True, location="path",
                  description="HubSpot contact ID"),
        ParamSpec(name="email", type="string", required=False,
                  description="Email address"),
        ParamSpec(name="firstname", type="string", required=False,
                  description="First name"),
        ParamSpec(name="lastname", type="string", required=False,
                  description="Last name"),
        ParamSpec(name="phone", type="string", required=False,
                  description="Phone number"),
        ParamSpec(name="company", type="string", required=False,
                  description="Company name"),
        ParamSpec(name="jobtitle", type="string", required=False,
                  description="Job title"),
        ParamSpec(name="lifecyclestage", type="string", required=False,
                  description="Lifecycle stage"),
    ],
    request_transform="hubspot_properties",
    response_ids={"id": "contact_id"},
)

HUBSPOT_SEARCH_CONTACTS = ActionSpec(
    name="hubspot_search_contacts",
    app="hubspot",
    description=(
        "Search contacts using filters. "
        "Supports filtering by any property. Returns up to 100 results."
    ),
    method="POST",
    path="/crm/v3/objects/contacts/search",
    content_type="application/json",
    params=[
        ParamSpec(name="query", type="string", required=False,
                  description="Full-text search query (searches across all text properties)"),
        ParamSpec(name="filter_property", type="string", required=False,
                  description="Property name to filter by (e.g. 'email', 'company')"),
        ParamSpec(name="filter_operator", type="string", required=False,
                  description="Operator: EQ, NEQ, LT, LTE, GT, GTE, CONTAINS_TOKEN, NOT_CONTAINS_TOKEN"),
        ParamSpec(name="filter_value", type="string", required=False,
                  description="Value to filter by"),
        ParamSpec(name="limit", type="integer", required=False,
                  description="Max results (default 10, max 100)"),
        ParamSpec(name="properties", type="list", required=False,
                  description="List of property names to return"),
    ],
    request_transform="hubspot_search",
)

HUBSPOT_LIST_CONTACTS = ActionSpec(
    name="hubspot_list_contacts",
    app="hubspot",
    description="List contacts with pagination. Returns up to 100 per page.",
    method="GET",
    path="/crm/v3/objects/contacts",
    params=[
        ParamSpec(name="limit", type="integer", required=False, location="query",
                  description="Max contacts to return (default 10, max 100)"),
        ParamSpec(name="after", type="string", required=False, location="query",
                  description="Pagination cursor from previous response"),
        ParamSpec(name="properties", type="string", required=False, location="query",
                  description="Comma-separated property names to include"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  COMPANIES
# ══════════════════════════════════════════════════════════════════════

HUBSPOT_CREATE_COMPANY = ActionSpec(
    name="hubspot_create_company",
    app="hubspot",
    description="Create a new company in HubSpot.",
    method="POST",
    path="/crm/v3/objects/companies",
    content_type="application/json",
    params=[
        ParamSpec(name="name", type="string", required=True,
                  description="Company name"),
        ParamSpec(name="domain", type="string", required=False,
                  description="Company website domain (e.g. 'acme.com')"),
        ParamSpec(name="industry", type="string", required=False,
                  description="Industry"),
        ParamSpec(name="phone", type="string", required=False,
                  description="Company phone"),
        ParamSpec(name="city", type="string", required=False,
                  description="City"),
        ParamSpec(name="state", type="string", required=False,
                  description="State/region"),
        ParamSpec(name="country", type="string", required=False,
                  description="Country"),
    ],
    request_transform="hubspot_properties",
    response_ids={"id": "company_id"},
)

HUBSPOT_GET_COMPANY = ActionSpec(
    name="hubspot_get_company",
    app="hubspot",
    description="Get a company by ID.",
    method="GET",
    path="/crm/v3/objects/companies/{company_id}",
    params=[
        ParamSpec(name="company_id", type="string", required=True, location="path",
                  description="HubSpot company ID"),
        ParamSpec(name="properties", type="string", required=False, location="query",
                  description="Comma-separated property names to include"),
    ],
    response_ids={"id": "company_id"},
)

HUBSPOT_SEARCH_COMPANIES = ActionSpec(
    name="hubspot_search_companies",
    app="hubspot",
    description="Search companies using filters or full-text query.",
    method="POST",
    path="/crm/v3/objects/companies/search",
    content_type="application/json",
    params=[
        ParamSpec(name="query", type="string", required=False,
                  description="Full-text search query"),
        ParamSpec(name="filter_property", type="string", required=False,
                  description="Property name to filter by (e.g. 'domain', 'name')"),
        ParamSpec(name="filter_operator", type="string", required=False,
                  description="Operator: EQ, NEQ, CONTAINS_TOKEN, etc."),
        ParamSpec(name="filter_value", type="string", required=False,
                  description="Value to filter by"),
        ParamSpec(name="limit", type="integer", required=False,
                  description="Max results (default 10, max 100)"),
        ParamSpec(name="properties", type="list", required=False,
                  description="Property names to return"),
    ],
    request_transform="hubspot_search",
)


# ══════════════════════════════════════════════════════════════════════
#  DEALS
# ══════════════════════════════════════════════════════════════════════

HUBSPOT_CREATE_DEAL = ActionSpec(
    name="hubspot_create_deal",
    app="hubspot",
    description=(
        "Create a new deal in HubSpot. "
        "dealstage values depend on your pipeline config."
    ),
    method="POST",
    path="/crm/v3/objects/deals",
    content_type="application/json",
    params=[
        ParamSpec(name="dealname", type="string", required=True,
                  description="Deal name"),
        ParamSpec(name="amount", type="string", required=False,
                  description="Deal amount"),
        ParamSpec(name="dealstage", type="string", required=False,
                  description="Pipeline stage ID (e.g. 'appointmentscheduled', 'qualifiedtobuy')"),
        ParamSpec(name="pipeline", type="string", required=False,
                  description="Pipeline ID (default pipeline if omitted)"),
        ParamSpec(name="closedate", type="string", required=False,
                  description="Expected close date (ISO 8601, e.g. '2024-12-31')"),
        ParamSpec(name="hubspot_owner_id", type="string", required=False,
                  description="Owner (HubSpot user) ID"),
    ],
    request_transform="hubspot_properties",
    response_ids={"id": "deal_id"},
)

HUBSPOT_GET_DEAL = ActionSpec(
    name="hubspot_get_deal",
    app="hubspot",
    description="Get a deal by ID.",
    method="GET",
    path="/crm/v3/objects/deals/{deal_id}",
    params=[
        ParamSpec(name="deal_id", type="string", required=True, location="path",
                  description="HubSpot deal ID"),
        ParamSpec(name="properties", type="string", required=False, location="query",
                  description="Comma-separated property names to include"),
    ],
    response_ids={"id": "deal_id"},
)

HUBSPOT_UPDATE_DEAL = ActionSpec(
    name="hubspot_update_deal",
    app="hubspot",
    description="Update a deal's properties (stage, amount, owner, etc.).",
    method="PATCH",
    path="/crm/v3/objects/deals/{deal_id}",
    content_type="application/json",
    params=[
        ParamSpec(name="deal_id", type="string", required=True, location="path",
                  description="HubSpot deal ID"),
        ParamSpec(name="dealname", type="string", required=False,
                  description="Deal name"),
        ParamSpec(name="amount", type="string", required=False,
                  description="Deal amount"),
        ParamSpec(name="dealstage", type="string", required=False,
                  description="Pipeline stage ID"),
        ParamSpec(name="closedate", type="string", required=False,
                  description="Expected close date"),
        ParamSpec(name="hubspot_owner_id", type="string", required=False,
                  description="Owner ID"),
    ],
    request_transform="hubspot_properties",
    response_ids={"id": "deal_id"},
)

HUBSPOT_SEARCH_DEALS = ActionSpec(
    name="hubspot_search_deals",
    app="hubspot",
    description="Search deals using filters or full-text query.",
    method="POST",
    path="/crm/v3/objects/deals/search",
    content_type="application/json",
    params=[
        ParamSpec(name="query", type="string", required=False,
                  description="Full-text search query"),
        ParamSpec(name="filter_property", type="string", required=False,
                  description="Property to filter (e.g. 'dealstage', 'amount')"),
        ParamSpec(name="filter_operator", type="string", required=False,
                  description="Operator: EQ, NEQ, LT, GT, CONTAINS_TOKEN, etc."),
        ParamSpec(name="filter_value", type="string", required=False,
                  description="Value to filter by"),
        ParamSpec(name="limit", type="integer", required=False,
                  description="Max results (default 10, max 100)"),
        ParamSpec(name="properties", type="list", required=False,
                  description="Property names to return"),
    ],
    request_transform="hubspot_search",
)


# ══════════════════════════════════════════════════════════════════════
#  NOTES / ENGAGEMENTS
# ══════════════════════════════════════════════════════════════════════

HUBSPOT_CREATE_NOTE = ActionSpec(
    name="hubspot_create_note",
    app="hubspot",
    description=(
        "Create a note and associate it with a contact, company, or deal. "
        "Use associations param to link to objects."
    ),
    method="POST",
    path="/crm/v3/objects/notes",
    content_type="application/json",
    params=[
        ParamSpec(name="body", type="string", required=True,
                  description="Note body text (HTML supported)"),
        ParamSpec(name="contact_id", type="string", required=False,
                  description="Contact ID to associate the note with"),
        ParamSpec(name="company_id", type="string", required=False,
                  description="Company ID to associate the note with"),
        ParamSpec(name="deal_id", type="string", required=False,
                  description="Deal ID to associate the note with"),
        ParamSpec(name="hubspot_owner_id", type="string", required=False,
                  description="Owner ID for the note"),
    ],
    request_transform="hubspot_note",
    response_ids={"id": "note_id"},
)


# ══════════════════════════════════════════════════════════════════════
#  ASSOCIATIONS
# ══════════════════════════════════════════════════════════════════════

HUBSPOT_ASSOCIATE = ActionSpec(
    name="hubspot_associate",
    app="hubspot",
    description=(
        "Create an association between two HubSpot objects. "
        "For example, link a contact to a company or a deal to a contact. "
        "from_type and to_type: 'contacts', 'companies', 'deals'."
    ),
    method="PUT",
    path="/crm/v3/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}/{association_type}",
    params=[
        ParamSpec(name="from_type", type="string", required=True, location="path",
                  description="Source object type: 'contacts', 'companies', 'deals'"),
        ParamSpec(name="from_id", type="string", required=True, location="path",
                  description="Source object ID"),
        ParamSpec(name="to_type", type="string", required=True, location="path",
                  description="Target object type: 'contacts', 'companies', 'deals'"),
        ParamSpec(name="to_id", type="string", required=True, location="path",
                  description="Target object ID"),
        ParamSpec(name="association_type", type="string", required=True, location="path",
                  description="Association type (e.g. 'contact_to_company', 'deal_to_contact')"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  OWNERS
# ══════════════════════════════════════════════════════════════════════

HUBSPOT_LIST_OWNERS = ActionSpec(
    name="hubspot_list_owners",
    app="hubspot",
    description="List all owners (users) in the HubSpot account. Useful for finding owner IDs for assignment.",
    method="GET",
    path="/crm/v3/owners",
    params=[
        ParamSpec(name="email", type="string", required=False, location="query",
                  description="Filter by owner email"),
        ParamSpec(name="limit", type="integer", required=False, location="query",
                  description="Max results (default 100)"),
        ParamSpec(name="after", type="string", required=False, location="query",
                  description="Pagination cursor"),
    ],
)


# ── Export ────────────────────────────────────────────────────────────

HUBSPOT_SPECS = [
    # Contacts
    HUBSPOT_CREATE_CONTACT,
    HUBSPOT_GET_CONTACT,
    HUBSPOT_UPDATE_CONTACT,
    HUBSPOT_SEARCH_CONTACTS,
    HUBSPOT_LIST_CONTACTS,
    # Companies
    HUBSPOT_CREATE_COMPANY,
    HUBSPOT_GET_COMPANY,
    HUBSPOT_SEARCH_COMPANIES,
    # Deals
    HUBSPOT_CREATE_DEAL,
    HUBSPOT_GET_DEAL,
    HUBSPOT_UPDATE_DEAL,
    HUBSPOT_SEARCH_DEALS,
    # Engagements
    HUBSPOT_CREATE_NOTE,
    # Associations
    HUBSPOT_ASSOCIATE,
    # Owners
    HUBSPOT_LIST_OWNERS,
]
