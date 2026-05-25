# Contributing to anytool

Thanks for helping! The easiest way to contribute is adding specs for new apps.

## Adding a New App

### Option 1: Generate from OpenAPI

If the app has a public OpenAPI spec:

```bash
# List available operations
python scripts/spec_builder.py openapi https://api.example.com/openapi.json --app myapp --list

# Generate specific actions
python scripts/spec_builder.py openapi https://api.example.com/openapi.json \
  --app myapp --actions "createItem,getItem,listItems"

# Validate
python scripts/spec_builder.py validate
```

### Option 2: Generate from Google Discovery

```bash
python scripts/spec_builder.py google calendar --all
```

### Option 3: Write YAML manually

Create `registry/myapp/action_name.yaml`:

```yaml
name: myapp_create_item
app: myapp
version: "1"
description: |
  Create a new item. Provide a name (required) and optional description.
method: POST
path: /v1/items
base_url: https://api.myapp.com
auth:
  type: bearer
  header: "Authorization: Bearer {access_token}"
request:
  content_type: application/json
  body_schema:
    type: object
    required: [name]
    properties:
      name:
        type: string
        description: The item name.
      description:
        type: string
        description: Optional description.
response:
  success_codes: [200, 201]
  body_schema:
    type: object
    properties:
      id:
        type: string
        description: The created item ID.
tags: [myapp, productivity]
examples:
  - name: Create a basic item
    request:
      name: "My item"
    response:
      id: "item_abc123"
```

### Validate before submitting

```bash
python scripts/spec_builder.py validate
```

This checks:
- Required fields present (name, app, method, path, base_url)
- Valid HTTPS base_url
- All path `{placeholders}` are resolvable (in body_schema or inject_from_metadata)
- Valid HTTP method
- Auth section present

### Spec Quality Checklist

- [ ] `description` is clear and tells the LLM when to use this action
- [ ] `body_schema` has `required` fields marked
- [ ] Path params (e.g. `{issueId}`) are in `body_schema.properties`
- [ ] At least one `example` with realistic request/response
- [ ] `tags` include the app name

### Submit a PR

1. Fork the repo
2. Create a branch: `git checkout -b add-myapp-specs`
3. Add your specs to `registry/myapp/`
4. Run `python scripts/spec_builder.py validate`
5. Submit PR

## Code Contributions

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Reporting Issues

Open a GitHub issue with:
- Which action/app
- What you sent (request body)
- What happened vs what you expected
- Error message if any
