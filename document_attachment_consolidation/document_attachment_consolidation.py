import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

import requests
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


@dataclass
class Settings:
    export_reference_key: str


@dataclass
class PageData:
    """Holds single page image, size and OCR data"""

    content: BytesIO
    size: tuple[int, int]
    ocr_data: list[dict]


class HttpClient:
    # ------------------
    # Basic HTTP client
    # ------------------

    def __init__(self, payload: dict) -> None:
        self.base_url = payload["base_url"]
        self.auth_token = payload["rossum_authorization_token"]
        self.headers = self._build_headers()

    def _build_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.auth_token}"}

    def call(self, method: str, endpoint: str, binary=False, **kwargs) -> dict | bytes:
        if endpoint.startswith("https://"):
            url = endpoint
        else:
            url = f"{self.base_url}/api/v1/{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        if not binary:
            return response.json()
        else:
            return response.content


class ApiClient:
    def __init__(self, rossum) -> None:
        self.rossum: HttpClient = rossum
        self.api_url = f"{rossum.base_url}/api/v1/"

    # ------------------
    # Basic HTTP methods with pagination support
    # ------------------

    def get(self, endpoint: str, id_: str = None, query_params: dict = None):
        url = f"{self.api_url}{endpoint}"
        if id_ is not None:
            if "{id}" in endpoint:
                url = url.format(id=id_)
            else:
                url = f"{url}/{id_}"
        if query_params:
            url = f"{url}?{'&'.join(f'{k}={v}' for k, v in query_params.items())}"

        results = []
        while url:
            response = self.rossum.call("GET", url)
            if isinstance(response, dict) and "results" in response and "pagination" in response:
                results.extend(response.get("results", []))
                url = response.get("pagination", {}).get("next")
            else:
                return response
        return results

    def post(self, endpoint: str, **kwargs):
        url = f"{self.api_url}{endpoint}"
        results = []

        while url:
            response = self.rossum.call("POST", url, **kwargs)
            if isinstance(response, dict) and "results" in response and "pagination" in response:
                results.extend(response.get("results", []))
                url = response.get("pagination", {}).get("next")
            else:
                return response
        return results

    def patch(self, endpoint: str, id_: str, **kwargs):
        return self.rossum.call("PATCH", f"{self.api_url}{endpoint}/{id_}", **kwargs)

    def delete(self, endpoint: str, id_: str):
        return self.rossum.call("DELETE", f"{self.api_url}{endpoint}/{id_}", binary=True)

    # ------------------
    # Custom methods
    # ------------------

    def get_relations_parents_attachments(self, parent_id):
        return self.get("relations", query_params={"parent": parent_id, "type": "attachment"})

    def upload_document(self, filename, content):
        return self.post("documents", files={"content": (filename, content)})

    def create_or_update_relation(self, document, annotation, key):
        existing_relations = self.get("document_relations", query_params={"key": key, "annotation": annotation["id"]})
        if not existing_relations:
            new_relation = self.post(
                "document_relations",
                json={"documents": [document["url"]], "annotation": annotation["url"], "type": "export", "key": key},
            )
            logging.info(f"Creating new document relation {new_relation['id']}")

        else:
            existing_relation = existing_relations[0]
            new_relation = self.patch(
                "document_relations", id_=existing_relation["id"], json={"documents": [document["url"]]}
            )
            logging.info(f"Setting new document into existing document_relation {existing_relation['id']}")

            if existing_relation.get("documents"):
                old_document_id = existing_relation["documents"][0].split("/")[-1]
                self.delete("documents", id_=old_document_id)
                logging.info(f"Deleting old document {old_document_id}")

        return new_relation


def rossum_hook_request_handler(payload) -> dict | None:
    if not payload.get("rossum_authorization_token"):
        raise ValueError("No Rossum authorization token provided in the payload")

    if not (payload["event"] == "annotation_content" and payload["action"] in ["confirm", "export"]):
        logging.info(
            f"Skipping hook, it runs only on event == 'annotation_status' and action == 'confirm' or 'export'. "
            f"(Current event: {payload['event']}, current status: {payload['annotation']['status']})"
        )
        return {"messages": []}
    rossum_client = HttpClient(payload)
    api_client = ApiClient(rossum_client)
    settings = Settings(**payload["settings"])

    # adding the parent first
    annotations_to_process = {payload["annotation"]["url"]: payload["annotation"]}
    logging.info(f"Adding parent annotation {payload['annotation']['id']}")

    relations = api_client.get_relations_parents_attachments(payload["annotation"]["id"])
    for relation in relations:
        for annotation in relation["annotations"]:
            # appending the annotations from relations, duplicities are skipped (dict with url as key is used)
            id_ = annotation.split("/")[-1]
            annotations_to_process[annotation] = api_client.get("annotations", id_=id_)
            logging.info(f"Adding related annotation {id_} from relation {relation['id']}")

    page_data_list = build_page_data_list(api_client, annotations_to_process.values())
    pdf_bytes = create_ocr_overlay_pdf(page_data_list)

    document = api_client.upload_document(filename=f"{payload['annotation']['id']}.pdf", content=pdf_bytes)
    logging.info(f"Uploaded document {document['id']}")

    api_client.create_or_update_relation(document, payload["annotation"], settings.export_reference_key)

    return {"messages": []}


def build_page_data_list(client: ApiClient, annotations: Iterable[dict]) -> list[PageData]:
    """Builds a list of PageData objects for each page"""

    # Helper for chunking
    def chunked_ranges(n, chunk_size=20):
        return [list(range(i, min(i + chunk_size, n + 1))) for i in range(1, n + 1, chunk_size)]

    page_urls = []
    ocr_pages = []

    for annotation in annotations:
        current_ocr_pages = []
        chunks = chunked_ranges(len(annotation["pages"]))
        page_urls.extend(annotation["pages"])

        # Fetch OCR data

        for chunk in chunks:
            page_nums = ",".join(str(i) for i in chunk)
            ocr_data_response = client.get(
                "annotations/{id}/page_data",
                annotation["id"],
                query_params={"page_numbers": page_nums, "granularity": "lines"},
            )
            current_ocr_pages.extend([c.get("items", []) for c in ocr_data_response.get("results", [])])

        # Sanity check
        assert len(annotation["pages"]) == len(current_ocr_pages), (
            f"Page count mismatch for annotation {annotation['id']}: OCR data has {len(current_ocr_pages)} pages, "
            f"but the annotation has {len(annotation['pages'])} pages"
        )

        ocr_pages.extend(current_ocr_pages)

    pdf_pages = []
    for ocr_data, page_url in zip(ocr_pages, page_urls):
        content = BytesIO(client.rossum.call("GET", f"{page_url}/content", binary=True))

        page_info = client.rossum.call("GET", page_url)
        size = (page_info["width"], page_info["height"])

        pdf_pages.append(PageData(content, size, ocr_data))

    return pdf_pages


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
