import logging
from dataclasses import dataclass
from io import BytesIO

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token


@dataclass
class Configuration:
    """Holds extension configuration"""

    export_reference_key: str


class ConfigurationError(Exception):
    """Raised when extension configuration is invalid"""

    def __init__(self, message: str) -> None:
        super().__init__(f"Configuration Error: {message}")


@dataclass
class PageData:
    """Holds single page image, size and OCR data"""

    content: BytesIO
    size: tuple[int, int]
    ocr_data: list[dict]


def rossum_hook_request_handler(payload: dict) -> dict:
    """Handles the hook request"""
    client = get_rossum_client(payload)
    config = Configuration(**payload["settings"])

    pages = build_page_data_list(client, payload["annotation"])

    pdf_buffer = create_ocr_overlay_pdf(pages)
    logging.info("PDF with OCR overlay created in memory.")

    existing_relation_id = find_document_relation(
        client, config.export_reference_key, payload["annotation"]["id"]
    )

    if existing_relation_id:
        logging.info("Existing document relation found.")
        handle_existing_relation(
            client,
            existing_relation_id,
            pdf_buffer,
            payload["annotation"]["id"],
        )
    else:
        document_url = upload_document_to_rossum(
            client, pdf_buffer, payload["annotation"]["id"]
        )
        logging.info(f"Document uploaded to Rossum: {document_url}")

        relation_url = create_document_relation(
            client,
            config.export_reference_key,
            payload["annotation"]["url"],
            document_url,
        )
        logging.info(f"Document relation created: {relation_url}")

    return {"messages": []}


def get_rossum_client(payload: dict) -> SyncRossumAPIClient:
    """Creates and returns Rossum API client"""
    token = payload.get("rossum_authorization_token")
    if not token:
        raise ConfigurationError("Missing token owner of extension")

    return SyncRossumAPIClient(
        base_url=payload["base_url"] + "/api/v1", credentials=Token(token)
    )


def build_page_data_list(
    client: SyncRossumAPIClient, annotation: dict
) -> list[PageData]:
    """Builds a list of PageData objects for each page"""

    # Helper for chunking
    def chunked_ranges(n, chunk_size=20):
        return [
            list(range(i, min(i + chunk_size, n + 1)))
            for i in range(1, n + 1, chunk_size)
        ]

    chunks = chunked_ranges(len(annotation["pages"]))

    # Fetch OCR data
    ocr_data_pages = []

    for chunk in chunks:
        page_nums = ",".join(str(i) for i in chunk)
        ocr_data_response = client.internal_client.request_json(
            "GET",
            annotation["url"] + "/page_data",
            params={"granularity": "lines", "page_numbers": page_nums},
        )
        ocr_data_pages.extend(
            [c.get("items", []) for c in ocr_data_response.get("results", [])]
        )

    # Sanity check
    assert len(annotation["pages"]) == len(ocr_data_pages), (
        f"Page count mismatch: OCR data has {len(ocr_data_pages)} pages, "
        f"but annotation has {len(annotation['pages'])} pages"
    )

    pages = []
    for i, url in enumerate(annotation["pages"]):
        content = BytesIO(
            client.internal_client.request("GET", f"{url}/content").content
        )

        page_info = client.internal_client.request_json("GET", url)
        size = (page_info["width"], page_info["height"])

        ocr_data = ocr_data_pages[i]

        pages.append(PageData(content, size, ocr_data))

    return pages


def create_ocr_overlay_pdf(
    pages: list[PageData],
    font_name: str = "Helvetica",
    base_font_size: int = 10,
    vertical_adjustment_factor: float = 0.2,
) -> BytesIO:
    """Creates and returns a PDF with invisible OCR overlays"""
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer)

    for page in pages:
        c.setPageSize(page.size)

        width, height = page.size

        # Draw the page image as background
        image_reader = ImageReader(page.content)
        c.drawImage(image_reader, 0, 0, width=width, height=height)

        # Set fill color to black and transparent text for overlays
        c.setFillColorRGB(0, 0, 0)
        c.setFillAlpha(0)

        # Overlay each OCR text item
        for item in page.ocr_data:
            x0, y0, x1, y1 = item["position"]
            text = item["text"]

            # Skip empty text to avoid issues
            if not text.strip():
                continue

            # Calculate the width and height of the OCR bounding box
            box_width = x1 - x0
            box_height = y1 - y0

            # Set the font
            c.setFont(font_name, base_font_size)

            # Calculate the widht of the text to scale horizontally
            text_width = c.stringWidth(text, font_name, base_font_size)

            # Determine scaling factors
            x_scale = box_width / text_width if text_width else 1
            y_scale = box_height / base_font_size

            # Rossum coordinates have y=0 at the bottom, adjust baselines
            y_baseline = height - y1

            # Small vertical adjustment to center the text vertically
            vertical_adjustment = base_font_size * vertical_adjustment_factor

            # Save graphics state
            c.saveState()

            # Apply transformations
            c.translate(x0, y_baseline)
            c.scale(x_scale, y_scale)

            # Draw the text
            c.drawString(0, vertical_adjustment, text)

            # Restore graphics state
            c.restoreState()

        c.showPage()  # Finish the page

    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer


def find_document_relation(
    client: SyncRossumAPIClient, relation_key: str, annotation_id: int
) -> int | None:
    """Finds a document relation based on key and annotation"""
    params = {"key": relation_key, "annotation": annotation_id}
    results = client.internal_client.request_json(
        "GET", "document_relations", params=params
    ).get("results", [])
    return results[0]["id"] if results else None


def delete_document(client: SyncRossumAPIClient, document_url: str) -> None:
    """Deletes document in Rossum"""
    client.internal_client.request_json("DELETE", document_url)


def upload_document_to_rossum(
    client: SyncRossumAPIClient, pdf_bytes: BytesIO, annotation_id: int
) -> str:
    """Uploads PDF to Rossum and returns URL"""
    files = {
        "content": (f"{annotation_id}.pdf", pdf_bytes, "application/pdf"),
    }
    document = client.internal_client.request_json("POST", "documents", files=files)
    return document["url"]


def update_document_relation(
    client: SyncRossumAPIClient, relation_id: int, document_url: str
) -> str:
    """Updates existing document relation with new document URL"""
    data = {"documents": [document_url]}
    response = client.update_part_document_relation(relation_id, data)
    return response.url


def handle_existing_relation(
    client: SyncRossumAPIClient,
    relation_id: int,
    pdf_buffer: BytesIO,
    annotation_id: int,
) -> None:
    """Handles existing document relation: deletes and re-uploads document"""
    relation = client.retrieve_document_relation(relation_id)

    if relation.documents:
        delete_document(client, relation.documents[0])
        logging.info("Deleted existing document in relation.")

    # Upload the new document
    document_url = upload_document_to_rossum(client, pdf_buffer, annotation_id)
    logging.info(f"New document uploaded to Rossum: {document_url}")

    # Update the relation with the new document
    relation_url = update_document_relation(client, relation.id, document_url)
    logging.info(f"Document relation updated: {relation_url}")


def create_document_relation(
    client: SyncRossumAPIClient,
    export_reference_key: str,
    annotation_url: str,
    document_url: str,
) -> str:
    """Creates Document Relation object in Rossum"""
    data = {
        "type": "export",
        "key": export_reference_key,
        "annotation": annotation_url,
        "documents": [document_url],
    }

    response = client.create_new_document_relation(data)
    return response.url
