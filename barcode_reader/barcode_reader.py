import json

from pydantic import BaseModel
from rossum_api import ElisAPIClientSync
from txscript import TxScript
from txscript.txscript import TxScriptAnnotationContent as Tx


class Configuration(BaseModel):
    barcodes_field_name: str


class ConfigurationError(Exception):
    """Raised when extension configuration is invalid"""

    def __init__(self, message: str) -> None:
        super().__init__(f"Configuration Error: {message}")


def rossum_hook_request_handler(payload: dict) -> dict:
    """Main entry point for hook"""
    t: Tx = TxScript.from_payload(payload)
    config = Configuration(**payload["settings"])

    client = ElisAPIClientSync(
        base_url=payload["base_url"] + "/api/v1",
        token=payload["rossum_authorization_token"],
    )

    action = payload.get("action")
    if action == "initialize":
        return handle_initialize(t, client, config, payload)

    return t.hook_response()


def assert_multivalue(t: Tx, schema_id: str) -> None:
    """Raises if field is missing or not multivalue"""
    field = getattr(t.field, schema_id, None)
    if field is None:
        raise ConfigurationError(f"Field '{schema_id}' is not present")
    if not hasattr(field, "all_values"):
        raise ConfigurationError(f"Field '{schema_id}' is not a multivalue")


def handle_initialize(
    t: Tx,
    client: ElisAPIClientSync,
    config: Configuration,
    payload: dict,
) -> dict:
    """Handles 'initialize' by running full-doc OCR and saving results"""
    ocr_data = get_full_ocr_data(client, payload["annotation"]["url"])
    create_initial_multivalue(t, config.barcodes_field_name, ocr_data)
    return t.hook_response()


def get_full_ocr_data(
    client: ElisAPIClientSync, annotation_url: str
) -> list[dict]:
    """Calls the full-document barcode OCR endpoint"""
    response = client.request_json(
        "GET",
        f"{annotation_url}/page_data",
        params={"granularity": "barcodes"},
    )
    return response.get("results", [])


def create_initial_multivalue(
    t: Tx, schema_id: str, ocr_data: list[dict]
) -> None:
    """Creates multivalue entries from OCR data"""
    assert_multivalue(t, schema_id)
    field = getattr(t.field, schema_id)
    field.all_values = []

    for page in ocr_data:
        page_number = page.get("page_number")
        for item in page.get("items", []):
            value = json.dumps({"text": item["text"], "type": item["type"]})
            field.all_values.append(value)
            field.all_values[-1].attr.page = page_number
            field.all_values[-1].attr.position = item.get("position")