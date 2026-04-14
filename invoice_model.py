from config import get_client
from azure.ai.documentintelligence.models import AnalyzeResult

# =========================
# Field Extraction Helpers
# =========================

def get_string(fields, field_name):
    field = fields.get(field_name)
    return field.value_string if field and hasattr(field, "value_string") else None


def get_date(fields, field_name):
    field = fields.get(field_name)
    return str(field.value_date) if field and hasattr(field, "value_date") and field.value_date else None


def get_currency(fields, field_name):
    field = fields.get(field_name)
    if field and hasattr(field, "value_currency") and field.value_currency:
        return round(field.value_currency.amount, 2) if field.value_currency.amount is not None else None
    return None


def get_number(fields, field_name):
    field = fields.get(field_name)
    return field.value_number if field and hasattr(field, "value_number") else None


def get_confidence(fields, field_name):
    field = fields.get(field_name)
    return round(field.confidence, 4) if field and field.confidence is not None else None


def get_address(fields, field_name):
    field = fields.get(field_name)
    if not field:
        return None
    return getattr(field, "content", None).replace("\n", ", ")


# =========================
# Line Items Extraction
# =========================

def extract_items(fields):
    items = []
    items_field = fields.get("Items")

    if not (items_field and hasattr(items_field, "value_array") and items_field.value_array):
        return items

    for item in items_field.value_array:
        obj = item.value_object or {}

        desc        = obj.get("Description")
        qty         = obj.get("Quantity")
        unit_price  = obj.get("UnitPrice")
        amount      = obj.get("Amount")
        product_code = obj.get("ProductCode")

        items.append({
            "description": desc.value_string if desc and hasattr(desc, "value_string") else None,
            "quantity": qty.value_number if qty and hasattr(qty, "value_number") else None,
            "unit_price": (
                round(unit_price.value_currency.amount, 2)
                if unit_price and hasattr(unit_price, "value_currency") and unit_price.value_currency else None
            ),
            "amount": (
                round(amount.value_currency.amount, 2)
                if amount and hasattr(amount, "value_currency") and amount.value_currency else None
            ),
            "product_code": product_code.value_string if product_code and hasattr(product_code, "value_string") else None,
        })

    return items


# =========================
# Main Function
# =========================

def analyze_invoice(file_bytes: bytes) -> dict:
    """
    Send document bytes to Azure prebuilt-invoice and return structured invoice data.
    """

    if not file_bytes:
        raise ValueError("file_bytes must not be empty or None")

    client = get_client()

    result: AnalyzeResult = client.begin_analyze_document(
        "prebuilt-invoice",
        body=file_bytes,
        content_type="application/octet-stream",
    ).result()

    output = {
        "page_count": len(result.pages) if result.pages else 0,
        "invoices": [],
    }

    if not result.documents:
        return output

    # =========================
    # Process each invoice
    # =========================
    for idx, invoice in enumerate(result.documents):
        fields = invoice.fields or {}

        output["invoices"].append({
            "invoice_index": idx,
            "doc_type": invoice.doc_type,

            # Invoice Info
            "invoice_id": get_string(fields, "InvoiceId"),
            "invoice_id_confidence": get_confidence(fields, "InvoiceId"),

            "invoice_date": get_date(fields, "InvoiceDate"),
            "invoice_date_confidence": get_confidence(fields, "InvoiceDate"),

            "due_date": get_date(fields, "DueDate"),
            "due_date_confidence": get_confidence(fields, "DueDate"),

            # Vendor / Customer
            "vendor_name": get_string(fields, "VendorName"),
            "vendor_name_confidence": get_confidence(fields, "VendorName"),

            "vendor_address": get_address(fields, "VendorAddress"),
            "customer_name": get_string(fields, "CustomerName"),
            "customer_name_confidence": get_confidence(fields, "CustomerName"),

            "customer_address": get_address(fields, "CustomerAddress"),

            # Line Items
            "items": extract_items(fields),

            # Totals
            "subtotal": get_currency(fields, "SubTotal"),
            "subtotal_confidence": get_confidence(fields, "SubTotal"),

            "tax": get_currency(fields, "TotalTax"),
            "tax_confidence": get_confidence(fields, "TotalTax"),

            "total": get_currency(fields, "InvoiceTotal"),
            "total_confidence": get_confidence(fields, "InvoiceTotal"),

            "amount_due": get_currency(fields, "AmountDue"),
            "amount_due_confidence": get_confidence(fields, "AmountDue"),
        })

    return output