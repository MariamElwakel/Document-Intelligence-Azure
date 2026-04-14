# Azure Document Intelligence Streamlit App

This project is a Streamlit-based interface for working with Azure Document Intelligence. It lets you upload documents, run Azure prebuilt models, inspect structured extraction results, and create a labeled dataset to train a custom model.

The app currently supports:

- OCR / Read
- Layout Analysis
- General Documents with key-value extraction
- Invoice extraction
- Receipt extraction
- Custom model labeling, export, upload, training, and testing

## Features

- Upload PDF and image-based documents from a simple web UI
- Run Azure prebuilt models and inspect the extracted output
- View both raw JSON and structured tables in the app
- Extract invoice fields such as invoice ID, dates, totals, vendor, customer, and line items
- Extract receipt fields such as merchant info, transaction date, totals, and purchased items
- Analyze layout elements including text lines, paragraphs, tables, figures, and selection marks
- Build a labeled dataset for a custom model using bounding-box annotation
- Upload training assets to Azure Blob Storage and trigger custom model training

## Tech Stack

- Python
- Streamlit
- Azure Document Intelligence SDK
- Azure Blob Storage SDK
- Pillow
- pdf2image
- streamlit-drawable-canvas

## Project Structure

```text
.
|-- app.py                     # Main Streamlit entry point
|-- config.py                  # Azure client creation
|-- ocr_model.py               # OCR / Read model integration
|-- layout_model.py            # Layout model integration
|-- general_document_model.py  # General document extraction with key-value pairs
|-- invoice_model.py           # Prebuilt invoice extraction
|-- receipt_model.py           # Prebuilt receipt extraction
|-- output_format.py           # Streamlit rendering helpers for results
|-- custom_model.py            # Custom model workflow: label, export, upload, train, test
|-- label_document.py          # Bounding-box labeling UI
|-- ocr_crop.py                # OCR on cropped label regions
|-- requirements.txt           # Python dependencies
|-- README.md                  # Project documentation
|-- sample_invoice.pdf
|-- test.pdf
|-- tst.pdf
```

## How It Works

### 1. Prebuilt model flows

The main app in `app.py` exposes a model selector in Streamlit. Based on the selected option, it calls one of the analysis handlers:

- `OCR / Read` uses Azure `prebuilt-read`
- `Layout Analysis` uses Azure `prebuilt-layout`
- `General Documents` uses Azure layout analysis with `KEY_VALUE_PAIRS`
- `Invoices` uses Azure `prebuilt-invoice`
- `Receipts` uses Azure `prebuilt-receipt`

Each handler:

1. Accepts an uploaded file
2. Sends the file bytes to Azure Document Intelligence
3. Converts the Azure SDK response into a structured Python dictionary
4. Renders results in Streamlit as raw JSON plus a friendlier structured view

### 2. Custom model workflow

The custom model flow in `custom_model.py` provides a guided training pipeline inside the app:

1. Upload exactly 5 training files
2. Define the fields you want to extract
3. Draw bounding boxes to label regions on each document
4. Run OCR on each selected crop to capture the label text
5. Export Azure-compatible `fields.json` and `*.labels.json` files
6. Upload source images and generated OCR JSON files to Azure Blob Storage
7. Generate a SAS URL for the training container
8. Trigger model training through `DocumentIntelligenceAdministrationClient`
9. Test the trained custom model on a new file

## Requirements

- Python 3.10+ recommended
- An Azure Document Intelligence resource
- An Azure Blob Storage account and container access for the custom model workflow
- Poppler installed if you want reliable PDF-to-image conversion through `pdf2image`

## Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Document-Intelligence-Azure
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root.

### Required for all app modes

```env
ENDPOINT=your_azure_document_intelligence_endpoint
KEY=your_azure_document_intelligence_key
```

### Also required for the custom model workflow

```env
CONNECTION_STRING=your_azure_blob_storage_connection_string
AZURE_STORAGE_KEY=your_azure_storage_account_key
```

These variables are used in:

- `config.py` for the main `DocumentIntelligenceClient`
- `ocr_crop.py` for OCR on cropped label regions
- `custom_model.py` for Blob Storage upload and custom model training

## Running the App

Start the Streamlit app with:

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in your terminal, usually:

```text
http://localhost:8501
```

## Supported Inputs

The app accepts these document formats in most flows:

- PDF
- JPG / JPEG
- PNG
- TIFF
- BMP

The custom model uploader currently accepts:

- PDF
- PNG
- JPG / JPEG

## Output Overview

### OCR / Read

Returns document pages, words, lines, styles, and related reading output in a structure compatible with the layout renderer.

### Layout Analysis

Returns:

- Full extracted content
- Handwritten style detection
- Page metadata
- Words and lines
- Selection marks
- Paragraphs
- Tables
- Figures

### General Documents

Returns:

- Key-value pairs
- Full text
- Page-level line data
- Paragraphs
- Tables

### Invoices

Returns structured invoice data such as:

- Invoice ID
- Invoice date
- Due date
- Vendor name and address
- Customer name and address
- Subtotal
- Tax
- Total
- Amount due
- Line items with quantity, unit price, amount, and product code

### Receipts

Returns structured receipt data such as:

- Receipt type
- Country or region
- Merchant name, address, and phone
- Transaction date and time
- Subtotal
- Tax
- Tip
- Total
- Purchased items

## Main Files Explained

### `app.py`

The Streamlit entry point. It defines the UI, file uploaders, handler functions, and model selection menu.

### `config.py`

Loads credentials from `.env` and creates the shared `DocumentIntelligenceClient`.

### `layout_model.py`

Calls Azure `prebuilt-layout` and transforms the result into a structured dictionary with pages, paragraphs, tables, figures, styles, and selection marks.

### `ocr_model.py`

Calls Azure `prebuilt-read` and formats the OCR response for rendering in the same UI style as layout results.

### `general_document_model.py`

Runs layout analysis with key-value pair extraction enabled and returns page content, text, paragraphs, and tables.

### `invoice_model.py`

Runs `prebuilt-invoice` and extracts invoice-specific business fields and line items.

### `receipt_model.py`

Runs `prebuilt-receipt` and extracts receipt-specific business fields and line items.

### `output_format.py`

Contains Streamlit rendering helpers that show:

- summary metrics
- raw JSON responses
- structured dataframes for paragraphs, tables, invoices, and receipts

### `custom_model.py`

Implements the custom model workflow from upload to training and testing. It also creates Azure-compatible OCR and label files for training.

### `label_document.py`

Provides the annotation UI using `streamlit-drawable-canvas`.

### `ocr_crop.py`

Crops a labeled region from the image, resizes if needed, and runs OCR on that crop to capture field text.

## Example Usage

### Run invoice extraction

1. Start the app with `streamlit run app.py`
2. Select `Invoices`
3. Upload an invoice PDF or image
4. Review the extracted totals, vendor info, and line items

### Run receipt extraction

1. Select `Receipts`
2. Upload a receipt image or PDF
3. Review merchant details, transaction info, and item totals

### Train a custom model

1. Select `Custom Model`
2. Upload 5 sample files
3. Define your field names
4. Draw labels for the fields on each document
5. Export labels
6. Upload training assets to Azure
7. Train with a chosen model ID
8. Test the trained model on a new document

## Notes and Limitations

- The custom model flow currently expects exactly 5 uploaded training files.
- The Azure Blob container name is hardcoded in `custom_model.py` as `training-data-for-your-custom-model`.
- PDF rendering for labeling uses only the first page when converting from bytes.
- The project includes sample and test PDFs, but it does not currently include automated tests.
- A local `labels` directory is created during custom label export.
- Azure credentials must be valid or analysis requests will fail.

## Troubleshooting

### Streamlit app does not start

- Make sure the virtual environment is activated
- Make sure dependencies from `requirements.txt` are installed
- Confirm you are running `streamlit run app.py` from the project root

### Azure request fails

- Check that `ENDPOINT` and `KEY` are correct in `.env`
- Confirm the Azure resource is active and supports Document Intelligence
- Verify the uploaded file format is supported

### Custom model upload or training fails

- Check `CONNECTION_STRING` and `AZURE_STORAGE_KEY`
- Confirm the storage account allows container access
- Make sure label export was completed before upload
- Ensure a SAS URL was generated before training

### PDF conversion issues

- Install Poppler and ensure it is available on your system path if `pdf2image` fails


## License

TEAM
