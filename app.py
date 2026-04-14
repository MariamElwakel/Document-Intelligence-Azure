import streamlit as st

from layout_model import analyze_layout
from output_format import render_layout_results
from general_document_model import analyze_general
from ocr_model import analyze_ocr
from custom_model import custom_model_app

def file_uploader(label="Upload a document (PDF, JPEG, PNG, TIFF, BMP)"):
    """Single-file uploader used by most models."""

    return st.file_uploader(label, type=["pdf", "jpg", "jpeg", "png", "tiff", "bmp"])


def multi_file_uploader(min_files=5):
    """Multi-file uploader for Custom Model — enforces minimum."""

    files = st.file_uploader(
        f"Upload at least {min_files} documents",
        accept_multiple_files=True,
        type=["pdf", "jpg", "jpeg", "png", "tiff", "bmp"],
    )

    if files and len(files) < min_files:
        st.warning(f"Please upload at least {min_files} documents. You have {len(files)} so far.")
        return None
    return files



#  MODEL HANDLERS
def handle_layout():
    """
    Handler for Layout Analysis model
    """
    uploaded_file = file_uploader()
    if uploaded_file:

        with st.spinner("Analyzing layout…"):
            try:
                result = analyze_layout(uploaded_file.read())
                render_layout_results(result)
            except Exception as e:
                st.error("Analysis failed. Check your file format or Azure credentials.")
                st.exception(e)


def handle_general():
    """
    Handler for General Documents model
    """
    uploaded_file = file_uploader()
    if uploaded_file:
        with st.spinner("Analyzing General documents…"):
            try:
                files_bytes = uploaded_file.read()
                result = analyze_general(files_bytes)
                print("results are done")
                render_layout_results(result)
            except Exception as e:
                st.error("Analysis Failed.")
                st.exception(e)
  
            

def handle_ocr():
    """
    Handler for OCR / Read model
    """
    uploaded_file = file_uploader()
    if uploaded_file:
        with st.spinner("Analyzing OCR (Reading Document)…"):
            try:
                result = analyze_ocr(uploaded_file.read())
                render_layout_results(result)
            except Exception as e:
                st.error("Analysis failed. Check your file format or Azure credentials.")
                st.exception(e)


def handle_invoices():
    """
    Handler for Invoices model
    """
    st.info("Invoices model — not yet implemented.")
    uploaded_file = file_uploader()
    if uploaded_file:
        st.warning("Invoices model not yet implemented.")



def handle_receipts():
    """
    Handler for Receipts model"""
    st.info("Receipts model — not yet implemented.")
    uploaded_file = file_uploader()
    if uploaded_file:
        st.warning("Receipts model not yet implemented.")


def handle_custom():
    """
    Handler for Custom Model — expects multiple files for training.
    """
    custom_model_app()



OPTIONS = {
    "OCR / Read":        handle_ocr,
    "Layout Analysis":   handle_layout,
    "General Documents": handle_general,
    "Invoices":          handle_invoices,
    "Receipts":          handle_receipts,
    "Custom Model":      handle_custom,
}



def main():
    st.set_page_config(page_title="Azure Document Intelligence", layout="wide")
    st.title("Azure Document Intelligence")

    # Call the appropriate handler based on user selection
    option = st.selectbox("Select a processing model", list(OPTIONS.keys()))
    OPTIONS[option]() 


if __name__ == "__main__":
    main()
