import streamlit as st
import json
import os
from dotenv import load_dotenv
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from pdf2image import convert_from_bytes
from io import BytesIO
from datetime import datetime, timedelta

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient, generate_container_sas, ContainerSasPermissions
from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient
from azure.ai.documentintelligence.models import BuildDocumentModelRequest, DocumentBuildMode
from ocr_crop import ocr_crop
from label_document import labelling
# -------------------------------
# Setup
# -------------------------------
load_dotenv()

st.set_page_config(layout="wide")
st.title("📄 Document Intelligence Trainer")

endpoint = os.getenv("OCR_ENDPOINT")
key = os.getenv("OCR_KEY")
connection_string = os.getenv("CONNECTION_STRING")
account_key = os.getenv("AZURE_STORAGE_KEY")

container_name = "training-data-for-your-custom-model"

client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
admin_client = DocumentIntelligenceAdministrationClient(endpoint, AzureKeyCredential(key))
blob_service_client = BlobServiceClient.from_connection_string(connection_string)



# -------------------------------
# Session State
# -------------------------------
for key_name, default in [
    ("fields", []),
    ("labels", {}),
    ("sas_url", None),
    ("file_png_map", {}),
]:
    if key_name not in st.session_state:
        st.session_state[key_name] = default

# -------------------------------
# Utils
# -------------------------------
def load_file(file):
    if file.type == "application/pdf":
        return convert_from_bytes(file.getvalue())[0]
    return Image.open(file)


def bbox_to_polygon_original(bbox, scale_x, scale_y, img_width, img_height):
    """Convert display-space bbox to original image pixel coordinates (flat list)."""
    x = (bbox["left"]  * scale_x) / img_width
    y = (bbox["top"]   * scale_y) / img_height
    w = (bbox["width"] * scale_x) / img_width
    h = (bbox["height"]* scale_y) / img_height
    return [x, y,  x+w, y,  x+w, y+h,  x, y+h]


def upload_blob(data, blob_name):
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
    except Exception:
        pass
    container_client.get_blob_client(blob_name).upload_blob(data, overwrite=True)


def build_ocr_json(result, png_name):
    """
    Convert a prebuilt-layout AnalyzeResult into the .ocr.json schema
    that Azure Document Intelligence training expects.
    File must be named exactly: <imagename>.ocr.json  (no extra .png)
    """
    def flat_polygon(pts):
        return list(pts) if pts else [] # return the polygon in list bec. it may be return as an object.
    
    pages = []
    for page in result.pages:
        words = []
        for word in (page.words or []):
            pts = word.polygon or []
            words.append({
                "content":    word.content,
                "polygon":    flat_polygon(word.polygon),
                "confidence": word.confidence,
                "span": {
                    "offset": word.span.offset,
                    "length": word.span.length
                }
            })

        lines = []
        for line in (page.lines or []):
            pts = line.polygon or []
            lines.append({
                "content": line.content,
                "polygon": flat_polygon(line.polygon),
                "spans":   [{"offset": s.offset, "length": s.length}
                            for s in (line.spans or [])]
            })

        pages.append({
            "pageNumber": page.page_number,
            "angle":      page.angle or 0,
            "width":      page.width,
            "height":     page.height,
            "unit":       page.unit or "pixel",
            "words":      words,
            "lines":      lines,
            "spans":      [{"offset": s.offset, "length": s.length}
                           for s in (page.spans or [])]
        })

    return {
        "status": "succeeded",
        "analyzeResult": {
            "apiVersion": "2023-07-31",
            "modelId":    "prebuilt-layout",
            "content":    result.content,
            "pages":      pages
        }
    }


# -------------------------------
# STEP 1: Upload Documents
# -------------------------------
st.header("1️⃣ Upload Documents")

uploaded_files = st.file_uploader(
    "Upload exactly 5 files",
    type=["png", "jpg", "jpeg", "pdf"],
    accept_multiple_files=True
)

if not uploaded_files or len(uploaded_files) != 5:
    st.warning("Upload exactly 5 files")
    st.stop()



# -------------------------------
# STEP 2: Define Fields
# -------------------------------

st.header("2️⃣ Define Fields")

new_field = st.text_input("Field name")
if st.button("Add Field"):
    if new_field and new_field not in st.session_state.fields:
        st.session_state.fields.append(new_field)

st.write(st.session_state.fields)

if not st.session_state.fields:
    st.stop()

# -------------------------------
# STEP 3: Label Documents
# -------------------------------
st.header("3️⃣ Label Documents")

labelling(uploaded_files)



# -------------------------------
# STEP 4: Export Labels
# -------------------------------
st.header("4️⃣ Export Labels")
""" Prepare Azure Storage Format"""

if st.button("Export Azure Labels"):
    os.makedirs("labels", exist_ok=True)

    # fields.json — uploaded to container ROOT, not inside a subfolder
    fields_json = {
        "fields": [
            {"fieldKey": f, "fieldType": "string", "fieldFormat": "not-specified"}
            for f in st.session_state.fields
        ],
        "definitions": {}
    }
    with open("labels/fields.json", "w") as fh:
        json.dump(fields_json, fh, indent=2)

    # <imagename>.labels.json — one per document
    for file_name, field_data in st.session_state.labels.items():
        png_name = st.session_state.file_png_map.get(
            file_name, file_name.rsplit(".", 1)[0] + ".png"
        )

        label_entries = []
        for field_name, annotations in field_data.items():
            values = []
            for ann in annotations:
                polygon = bbox_to_polygon_original(ann, ann["scale_x"], ann["scale_y"], ann["img_width"], ann["img_height"])
                values.append({
                    "page": 1,
                    "text": ann["ocr_text"],
                    "boundingBoxes": [polygon]
                })
            label_entries.append({"label": field_name, "value": values})

        labels_output = {
            "$schema": "https://schema.cognitiveservices.azure.com/formrecognizer/2021-03-01/labels.json",
            "document": png_name,
            "labels":   label_entries
        }

        # ✅ Correct name: <imagename>.labels.json  NOT <imagename>.png.labels.json
        label_filename = png_name.rsplit(".", 1)[0] + ".labels.json"
        with open(f"labels/{label_filename}", "w") as fh:
            json.dump(labels_output, fh, indent=2)

    st.success("Labels exported ✅")

# -------------------------------
# STEP 5: Upload to Azure + Generate OCR
# -------------------------------

st.header("5️⃣ Upload to Azure")

if st.button("Upload & Generate SAS"):
    total = len(uploaded_files)
    progress = st.progress(0, text="Uploading Files...")

    for i, file in enumerate(uploaded_files):
        png_name = st.session_state.file_png_map[file.name]
        progress.progress(i / total, text=f"Uploading {png_name}...")

        # Convert to PNG bytes
        img = (convert_from_bytes(file.getvalue())[0]
               if file.type == "application/pdf"
               else Image.open(file))
        buf = BytesIO()
        img.save(buf, format="PNG")
        binary = buf.getvalue()

        # Upload image
        upload_blob(binary, png_name)

        # Run layout OCR and upload <imagename>.ocr.json
        progress.progress(i / total, text=f"Running OCR for {png_name}...")
        ocr_poller = client.begin_analyze_document(
            "prebuilt-layout",
            body=binary,
            content_type=file.type
        )
        ocr_result = ocr_poller.result()
        ocr_json = build_ocr_json(ocr_result, png_name)

        # ✅ Correct name: <imagename>.ocr.json  NOT <imagename>.png.ocr.json
        ocr_blob_name = png_name.rsplit(".", 1)[0] + ".ocr.json"
        upload_blob(json.dumps(ocr_json, indent=2).encode("utf-8"), ocr_blob_name)

    # Upload fields.json to container ROOT
    progress.progress(0.9, text="Uploading label files...")
    if os.path.exists("labels/fields.json"):
        with open("labels/fields.json", "rb") as fh:
            upload_blob(fh.read(), "fields.json")

    # Upload .labels.json files (same level as images, not in a subfolder)
    for label_file in os.listdir("labels"):
        if label_file.endswith(".labels.json"):
            with open(f"labels/{label_file}", "rb") as fh:
                upload_blob(fh.read(), label_file)

    # Generate SAS URL
    sas_token = generate_container_sas(
        account_name=blob_service_client.account_name,
        container_name=container_name,
        account_key=account_key,
        permission=ContainerSasPermissions(read=True, list=True),
        expiry=datetime.utcnow() + timedelta(hours=2)
    )
    st.session_state.sas_url = (
        f"https://{blob_service_client.account_name}.blob.core.windows.net"
        f"/{container_name}?{sas_token}"
    )

    progress.progress(1.0, text="Done!")
    st.success("Uploaded ✅")
    st.code(st.session_state.sas_url)

# -------------------------------
# STEP 6: Train Model
# -------------------------------
st.header("6️⃣ Train Model")

model_id = st.text_input("Model ID")

if st.button("Train"):
    if not st.session_state.sas_url:
        st.error("Run Step 5 first")
        st.stop()
    if not model_id:
        st.error("Enter a Model ID")
        st.stop()

    with st.spinner("Training... this may take several minutes"):
        poller = admin_client.begin_build_document_model(
            BuildDocumentModelRequest(
                model_id=model_id,
                build_mode=DocumentBuildMode.TEMPLATE,
                azure_blob_source={"containerUrl": st.session_state.sas_url, "prefix": ""}
            )
        )
        model = poller.result()

    st.success(f"Model trained: {model.model_id} ✅")

# -------------------------------
# STEP 7: Test Model
# -------------------------------
st.header("7️⃣ Test Model")

test_file = st.file_uploader("Test file", key="test_uploader")

if st.button("Test"):
    if not test_file:
        st.warning("Upload a test file first")
        st.stop()
    if not model_id:
        st.warning("Enter the Model ID above")
        st.stop()

    with st.spinner("Analyzing..."):
        poller = client.begin_analyze_document(
            model_id=model_id,
            body=test_file.read(),
            content_type="application/octet-stream"
        )
        result = poller.result()

    output = {}
    for doc in result.documents:
        for name, field in doc.fields.items():
            # value_string for strings; fall back to content for other types
            output[name] = field.value_string if field.value_string is not None else field.content

    st.json(output)