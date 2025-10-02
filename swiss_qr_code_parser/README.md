## Swiss QR code parser

Hook which reads the data of a Swiss QR code, parses it and sets the values to selected datapoints

### Example config
```json
{
  "qr_code_datapoint": "swiss_qr_text",
  "extracted_data_mapping": {
    "creditor_iban": "iban_val",
    "reference": "reference_val",
    "unstructured_message": "additional_val"
  }
}
```


### Resulting datapoints
Example config, as shown above, will parse the qr code text from datapoint `swiss_qr_text` and set the following datapoints:
- `iban_val`: The creditor's IBAN from the QR code.
- `reference_val`: The reference number from the QR code.
- `additional_val`: The unstructured message from the QR code.


### Description of the config options
- `qr_code_datapoint`: The datapoint which contains the raw text data of the Swiss QR code.
- `extracted_data_mapping`: A mapping of the fields to extract from the QR code data to the corresponding datapoints. The keys are the fields in the QR code, and the values are the selected datapoint names.
- Supported fields to extract:
  - `header`: Header of the payment information (e.g., 'SPC').
  - `version`: Version of the QR code standard.
  - `coding`: Coding type used in the QR code.
  - `creditor_iban`: The creditor's IBAN.
  - `creditor_address_type`: Address type for the creditor ('S' or 'K').
  - `creditor_name`: The creditor's name.
  - `creditor_street`: The creditor's street address.
  - `creditor_house_no`: The creditor's house number.
  - `creditor_postcode`: The creditor's postal code.
  - `creditor_city`: The creditor's city.
  - `creditor_country`: The creditor's country.
  - `ultimate_creditor_address_type`: Address type for the ultimate creditor (optional).
  - `ultimate_creditor_name`: Name of the ultimate creditor (optional).
  - `ultimate_creditor_street`: Street of the ultimate creditor (optional).
  - `ultimate_creditor_house_no`: House number of the ultimate creditor (optional).
  - `ultimate_creditor_postcode`: Postal code of the ultimate creditor (optional).
  - `ultimate_creditor_city`: City of the ultimate creditor (optional).
  - `ultimate_creditor_country`: Country of the ultimate creditor (optional).
  - `amount`: Payment amount.
  - `currency`: Payment currency (e.g., 'CHF').
  - `debtor_address_type`: Address type for the debtor ('S' or 'K').
  - `debtor_name`: Name of the debtor.
  - `debtor_street`: Street of the debtor.
  - `debtor_house_no`: House number of the debtor.
  - `debtor_postcode`: Postal code of the debtor.
  - `debtor_city`: City of the debtor.
  - `debtor_country`: Country of the debtor.
  - `reference_type`: Type of reference (QRR / SCOR / NON).
  - `reference`: The reference number.
  - `unstructured_message`: Unstructured message for additional information.
  - `bill_information`: Structured bill information.
  - `trailer`: Trailer information from the QR code (e.g., 'EPD').