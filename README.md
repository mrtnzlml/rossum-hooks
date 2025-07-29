# 📄 Rossum Searchable PDF Generator

A **Rossum Custom Hook** that automatically converts image-based documents into fully searchable PDFs. This tool takes the OCR data from Rossum and layers it as invisible, selectable text over the original document image.

This means you get the best of both worlds: the **original visual fidelity** of the document and the power of **full-text search** and copy-pasting. 📜➡️🔍

## ✨ Features

- **Searchable & Selectable Text**: Turns flat images or non-searchable PDFs into fully interactive documents.
- **Preserves Original Layout**: The visual appearance of the document is completely unchanged.
- **Invisible Text Layer**: The OCR text is layered invisibly, providing a clean user experience.
- **Multi-Page Support**: Seamlessly processes documents of any length, fetching and combining all pages.
- **Idempotent**: If the hook runs again on the same document, it intelligently updates the existing searchable PDF instead of creating duplicates.
- **Configurable**: Easily set the key used for creating the document relation in Rossum.

## ⚙️ How It Works

The process is handled automatically by the hook in a few simple steps:

1. **Trigger**: The hook is activated by a pre-configured event in a Rossum queue (e.g., an annotation's status "Export").
1. **Fetch Data**: It fetches the image and the line-by-line OCR data for every page of the source document using the Rossum API.
1. **Generate PDF**: Using the `reportlab` library, it constructs a new PDF in memory. For each page, it:
    - Draws the original page image as the background.
    - Overlays the OCR text using an **invisible font**, precisely scaling and positioning it to match the location on the image.
1. **Upload & Link**: The newly generated searchable PDF is uploaded back to Rossum. A **Document Relation** is then created (or updated) to link this new PDF to the original annotation, making it easily accessible.

## 🚀 Setup and Usage

In the Rossum UI, navigate to "Extensions" and click "Create extension".

- Give it a descriptive name (e.g., "Searchable PDF Generator").
- Copy the code from `hook.py`
- Choose the trigger event. A good choice is "Export".
- In the JSON configuration section, add the following key. This defines how the generated document is linked back to the annotation.

```json
{
  "export_reference_key": "searchable_pdf"
}
```

### Usage

Once configured, the hook operates automatically in the background. When the trigger event occurs for a document:

- The hook will run and generate the searchable PDF.
- The new file will appear in the related documents (currently innaccessible via UI).

This newly generated file can be later used in Rossum's Export Pipelines, for example.