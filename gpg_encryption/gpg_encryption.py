import os
from dataclasses import dataclass
from typing import Literal

import gnupg
import httpx

# Constants
POST_DOCUMENT_URL = "{base_url}/api/v1/documents"
DELETE_DOCUMENT_URL = "{base_url}/api/v1/documents/{id}"

GET_DOCUMENT_RELATION_URL = "{base_url}/api/v1/document_relations?annotation={annotation_id}&key={key}"
POST_DOCUMENT_RELATION_URL = "{base_url}/api/v1/document_relations"
PATCH_DOCUMENT_RELATION_URL = "{base_url}/api/v1/document_relations/{id}"


@dataclass
class Settings:
    source_document_key: str
    target_document_key: str


@dataclass
class Secrets:
    gpg_public_key: str


def get_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def request_single_url(url: str, auth_token: str, type_: Literal["file", "json"]):
    with httpx.Client() as client:
        response = client.get(url, headers=get_auth_headers(auth_token), follow_redirects=True)
        response.raise_for_status()
        return response.content if type_ == "file" else response.json()


def request_paginated_url(url: str, auth_token: str):
    results = []
    with httpx.Client() as client:
        while url:
            response = client.get(url, headers=get_auth_headers(auth_token))
            response.raise_for_status()
            data = response.json()
            results.extend(data["results"])
            url = data["pagination"]["next"]
    return results


def encrypt_document(content: bytes, public_key: str) -> str:
    gnupg_home = "/tmp/.gnupg"  # in a serverless function, gnupg directory must be in tmp
    os.makedirs(gnupg_home, exist_ok=True)

    gpg = gnupg.GPG(gnupghome=gnupg_home)
    gpg.encoding = "utf-8"
    imported_key = gpg.import_keys(public_key)

    # getting recipient from the public key
    recipients = imported_key.fingerprints
    encrypted = gpg.encrypt(content, recipients)

    if not encrypted.ok:
        raise ValueError(f"Encryption failed: {encrypted.status}\n{encrypted.stderr}")

    return encrypted.data


def upload_encrypted_document(base_url: str, token: str, filename: str, content: bytes) -> str:
    url = POST_DOCUMENT_URL.format(base_url=base_url)
    with httpx.Client() as client:
        response = client.post(
            url, headers=get_auth_headers(token), files={"content": (filename, content, "application/pgp-encrypted")}
        )
        response.raise_for_status()
        new_document_url = response.json().get("url")
        if not new_document_url:
            raise ValueError("No new document url returned after upload.")

        return new_document_url


def handle_new_document_relation(
    base_url: str, token: str, annotation: dict, new_encrypted_document_url: str, settings: Settings
):
    def create_new_document_relation(key: str):
        with httpx.Client() as client:
            response = client.post(
                POST_DOCUMENT_RELATION_URL.format(base_url=base_url),
                headers=get_auth_headers(token) | {"Content-Type": "application/json"},
                json={
                    "type": "export",
                    "key": key,
                    "annotation": annotation["url"],
                    "documents": [new_encrypted_document_url],
                },
            )
            response.raise_for_status()

    def update_existing_document_relation(existing_document_relation_id):
        with httpx.Client() as client:
            response = client.patch(
                PATCH_DOCUMENT_RELATION_URL.format(base_url=base_url, id=existing_document_relation_id),
                headers=get_auth_headers(token) | {"Content-Type": "application/json"},
                json={"documents": [new_encrypted_document_url]},
            )
            response.raise_for_status()

    def delete_previous_encrypted_documents(document_urls: list[str]):
        for document_url in document_urls:
            document_id = document_url.split("/")[-1]
            with httpx.Client() as client:
                response = client.delete(
                    DELETE_DOCUMENT_URL.format(base_url=base_url, id=document_id), headers=get_auth_headers(token)
                )
                response.raise_for_status()

    document_relations_url = GET_DOCUMENT_RELATION_URL.format(
        base_url=base_url, annotation_id=annotation["id"], key=settings.target_document_key
    )

    existing_document_relations = request_paginated_url(document_relations_url, token)
    if existing_document_relations:
        existing_document_relation = existing_document_relations[0]
        update_existing_document_relation(existing_document_relation["id"])
        delete_previous_encrypted_documents(existing_document_relation["documents"])
    else:
        create_new_document_relation(settings.target_document_key)


def rossum_hook_request_handler(payload: dict) -> dict:
    settings = Settings(**payload["settings"])
    secrets = Secrets(**payload["secrets"])
    token = payload["rossum_authorization_token"]
    base_url = payload["base_url"]
    annotation = payload["annotation"]

    document_relations_url = GET_DOCUMENT_RELATION_URL.format(
        base_url=base_url, annotation_id=annotation["id"], key=settings.source_document_key
    )

    document_relations = request_paginated_url(document_relations_url, token)
    if not document_relations:
        raise ValueError(
            f"No document relations for annotation {annotation['id']} with key {settings.source_document_key} found."
        )

    # relying on only one document_relation with the source key for annotation and only one document in the document_relation
    source_document_url = document_relations[0]["documents"][0]
    source_content_url = f"{source_document_url}/content"
    source_content = request_single_url(source_content_url, token, type_="file")

    encrypted_content = encrypt_document(source_content, secrets.gpg_public_key)

    source_document_id = source_document_url.split("/")[-1]
    target_filename = f"{source_document_id}_encrypted.gpg"

    new_document_url = upload_encrypted_document(base_url, token, target_filename, encrypted_content)

    if not new_document_url:
        raise ValueError("No new document url returned after upload.")

    handle_new_document_relation(base_url, token, annotation, new_document_url, settings)

    return {
        "messages": [
            {
                "id": payload.get("annotation", {}).get("id", None),
                "type": "info",
                "content": "Process completed successfully.",
            }
        ]
    }
