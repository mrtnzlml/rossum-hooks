# Searchable PDF

"Searchable PDF" hook creates a searchable PDF (PDF with an invisible text layer) from any supported input format.

> [!IMPORTANT]
> Note that this function requires a special "professional services" third party library pack and won't work without the involvement of ProServ team. To enable it, please contact your account manager.

## Settings (`hook.settings`)

Example:

```json
{
  "export_reference_key": "export_searchable_pdf"
}
```

### Settings JSON schema (`hook.settings_schema`)

```json
{
  "type": "object",
  "properties": {
    "export_reference_key": {
      "type": "string",
      "description": "Under which key should the searchable PDF document be created in document relations.",
      "examples": [
        "export_searchable_pdf"
      ]
    }
  },
  "additionalProperties": false
}
```

## Secrets (`hook.secrets`)

_none_

### Secrets JSON schema (`hook.secrets_schema`)

```json
{
  "type": "object",
  "additionalProperties": {
    "type": "string"
  }
}
```
