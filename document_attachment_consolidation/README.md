This Hook is designed to generate a searchable PDF from a confirmed annotation. When triggered, it gathers the source annotation and any attached child annotations, fetches their page images and OCR data, and compiles them into a single PDF with an invisible text overlay. This new PDF is then uploaded back as a document and linked to the original annotation.

-----

## Configuration

The hook requires a JSON object to be configured in the **Settings** field within the Rossum UI. This object must contain one mandatory key.

  * `export_reference_key` (string, **required**): This string acts as a unique identifier for the relationship between the original annotation and the generated searchable PDF.
      * When the hook runs, it looks for an existing "export" document_relation with this key.
    <!-- end list -->
      - If one **is not found**, it creates a new document_relation using this key.
      - If one **is found**, it updates that document_relation to point to the new PDF and **deletes the old PDF document**.

### Example Settings

```json
{
  "export_reference_key": "searchable_pdf_v1"
}
```