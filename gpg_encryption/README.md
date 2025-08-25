# GPG Encryption

"GPG Encryption" hook creates a GPG-encrypted document from any other document (uploaded to document relations API endpoint).

> [!IMPORTANT]
> Note that this function requires a special "professional services" third party library pack and won't work without the involvement of ProServ team. To enable it, please contact your account manager.

## Settings (`hook.settings`)

Example:

```json
{
  "source_document_key": "edi_export",
  "target_document_key": "edi_export_gpg_encrypted"
}
```

### Settings JSON schema (`hook.settings_schema`)

```json
{
  "type": "object",
  "properties": {
    "source_document_key": {
      "type": "string",
      "description": "A unique identifier (key) of the source document in document relations.",
      "examples": [
        "edi_export"
      ]
    },
    "target_document_key": {
      "type": "string",
      "description": "Under which key should the GPG-encrypted document be created in document relations.",
      "examples": [
        "edi_export_gpg_encrypted"
      ]
    }
  },
  "additionalProperties": false
}
```

## Secrets (`hook.secrets`)

```json
{
  "gpg_public_key": "__redacted__secret__"
}
```

### Secrets JSON schema (`hook.secrets_schema`)

```json
{
  "type": "object",
  "properties": {
    "gpg_public_key": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```
