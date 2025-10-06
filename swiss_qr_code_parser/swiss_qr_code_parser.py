from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from txscript import TxScript


@dataclass
class ParsedQrData:
    """
    Represents data parsed from a Swiss QR-bill (Version 2.x).
    Fields match the official specification for data contained within the QR code.
    """

    # Header
    header: Optional[str] = None
    version: Optional[str] = None
    coding: Optional[str] = None

    # Creditor Information (Payable to)
    creditor_iban: Optional[str] = None
    creditor_address_type: Optional[str] = None
    creditor_name: Optional[str] = None
    creditor_street: Optional[str] = None  # For 'K' type, this holds Address Line 1
    creditor_house_no: Optional[str] = None
    creditor_postcode: Optional[str] = None
    creditor_city: Optional[str] = None  # For 'K' type, this holds Address Line 2
    creditor_country: Optional[str] = None

    # Ultimate Creditor Information (Optional)
    ultimate_creditor_address_type: Optional[str] = None
    ultimate_creditor_name: Optional[str] = None
    ultimate_creditor_street: Optional[str] = None
    ultimate_creditor_house_no: Optional[str] = None
    ultimate_creditor_postcode: Optional[str] = None
    ultimate_creditor_city: Optional[str] = None
    ultimate_creditor_country: Optional[str] = None

    # Payment Information
    amount: Optional[str] = None
    currency: Optional[str] = None

    # Debtor Information (Payable by)
    debtor_address_type: Optional[str] = None
    debtor_name: Optional[str] = None
    debtor_street: Optional[str] = None
    debtor_house_no: Optional[str] = None
    debtor_postcode: Optional[str] = None
    debtor_city: Optional[str] = None
    debtor_country: Optional[str] = None

    # Reference
    reference_type: Optional[str] = None
    reference: Optional[str] = None

    # Additional Information
    unstructured_message: Optional[str] = None
    bill_information: Optional[str] = None

    # Trailer
    trailer: Optional[str] = None


@dataclass
class Settings:
    extracted_data_mapping: ParsedQrData  # using the same class for settings because the keys must match
    qr_code_datapoint: str  # where to find the QR code text in the document fields


def from_dict(cls, data: Dict[str, Any]):
    """Recursively convert a dict into a dataclass."""
    if not is_dataclass(cls):
        return data  # not a dataclass, just return the value
    fieldtypes = {f.name: f.type for f in fields(cls)}
    return cls(**{key: from_dict(fieldtypes[key], value) for key, value in data.items() if key in fieldtypes})


def parse_qr_text(raw_data: str) -> ParsedQrData | None:
    """
    Returns a ParsedQrData object containing the parsed fields from the Swiss QR-bill text.
    Compatible with version 2.x of the specification.
    """

    def _parse_address_block(lines: List[str], start_index: int) -> Tuple[Dict[str, str], int]:
        address_data = {}
        if not lines[start_index].strip():
            return {}, 7  # Skip 7 empty lines for an unused block

        address_type = lines[start_index]
        address_data["type"] = address_type

        if address_type == "S":
            address_data["name"] = lines[start_index + 1]
            address_data["street"] = lines[start_index + 2]
            address_data["house_no"] = lines[start_index + 3]
            address_data["postcode"] = lines[start_index + 4]
            address_data["city"] = lines[start_index + 5]
            address_data["country"] = lines[start_index + 6]
            return address_data, 7
        elif address_type == "K":
            # Note: 'K' type has combined address lines. We map them to the most
            # relevant fields in the dataclass for convenience.
            address_data["name"] = lines[start_index + 1]
            address_data["street"] = lines[start_index + 2]  # Address Line 1
            address_data["city"] = lines[start_index + 3]  # Address Line 2
            return address_data, 4
        else:
            raise ValueError(f"Unknown address type '{address_type}'")

    lines = raw_data.strip().splitlines()
    result = ParsedQrData()
    i = 0

    # --- Header ---
    result.header, result.version, result.coding = lines[i : i + 3]
    i += 3

    # --- Creditor Info ---
    result.creditor_iban = lines[i]
    i += 1
    addr, consumed = _parse_address_block(lines, i)
    result.creditor_address_type = addr.get("type")
    result.creditor_name = addr.get("name")
    result.creditor_street = addr.get("street")
    result.creditor_house_no = addr.get("house_no")
    result.creditor_postcode = addr.get("postcode")
    result.creditor_city = addr.get("city")
    result.creditor_country = addr.get("country")
    i += consumed

    # --- Ultimate Creditor Info ---
    addr, consumed = _parse_address_block(lines, i)
    result.ultimate_creditor_address_type = addr.get("type")
    result.ultimate_creditor_name = addr.get("name")
    result.ultimate_creditor_street = addr.get("street")
    result.ultimate_creditor_house_no = addr.get("house_no")
    result.ultimate_creditor_postcode = addr.get("postcode")
    result.ultimate_creditor_city = addr.get("city")
    result.ultimate_creditor_country = addr.get("country")
    i += consumed

    # --- Payment Amount ---
    result.amount, result.currency = lines[i : i + 2]
    i += 2

    # --- Debtor Info ---
    addr, consumed = _parse_address_block(lines, i)
    result.debtor_address_type = addr.get("type")
    result.debtor_name = addr.get("name")
    result.debtor_street = addr.get("street")
    result.debtor_house_no = addr.get("house_no")
    result.debtor_postcode = addr.get("postcode")
    result.debtor_city = addr.get("city")
    result.debtor_country = addr.get("country")
    i += consumed

    # --- Reference ---
    result.reference_type, result.reference = lines[i : i + 2]
    i += 2

    # --- Additional Information ---
    add_info = lines[i]
    # Check if it's structured bill information or an unstructured message
    if add_info.startswith("//S1/"):
        result.bill_information = add_info
    else:
        result.unstructured_message = add_info
    i += 1

    # --- Trailer ---
    result.trailer = lines[i]

    return result


class RossumClient:
    def __init__(self, payload: dict) -> None:
        self.base_url = payload["base_url"]
        self.auth_token = payload["rossum_authorization_token"]
        self.headers = self._build_headers()

    def _build_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.auth_token}"}

    def call(self, method: str, endpoint: str, **kwargs) -> dict:
        if endpoint.startswith("https://"):
            url = endpoint
        else:
            url = f"{self.base_url}/api/v1/{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()


def rossum_hook_request_handler(payload) -> dict | None:
    if payload["event"] != "annotation_content":
        if not payload["rossum_authorization_token"]:
            raise ValueError("Rossum authorization token is required for event different than annotation_content")
        # fool the txscript that its dealing with supported event
        rossum_client = RossumClient(payload)
        content = rossum_client.call("GET", payload["annotation"]["content"], timeout=20)["content"]
        payload["annotation"]["content"] = content
        payload["event"] = "annotation_content"
    t = TxScript.from_payload(payload)

    settings = from_dict(Settings, payload.get("settings", {}))

    qr_code_field = getattr(t.field, settings.qr_code_datapoint, None)
    if qr_code_field:

        try:
            qr_data = parse_qr_text(qr_code_field)
        except Exception as e:
            return {
                "automation_blockers": [
                    {"id": qr_code_field.id, "content": f"Failed to parse Swiss QR code data ({e})"}
                ]
            }

        for swiss_field_name, configured_datapoint_name in asdict(settings.extracted_data_mapping).items():
            if not configured_datapoint_name:
                continue
            value = getattr(qr_data, swiss_field_name)
            setattr(t.field, configured_datapoint_name, value)

    response = t.hook_response()
    return response
