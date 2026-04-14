from config import get_client

# Field extraction helpers

def get_string(fields, field_name):
    """extracts a text value from fields"""

    field = fields.get(field_name)
    return field.value_string if field and hasattr(field, "value_string") else None


def get_date(fields, field_name):
    """extracts a date (like 2024-01-01)"""

    field = fields.get(field_name)

    # If date exists → convert it to string
    return str(field.value_date) if field and hasattr(field, "value_date") and field.value_date else None


def get_time(fields, field_name):
    """"extracts a time (like 12:45)"""

    field = fields.get(field_name)
    # If proper time exists → return it
    if field and hasattr(field, "value_time") and field.value_time:
        return str(field.value_time)
    
    # If not → fallback to raw text
    return getattr(field, "content", None)


def get_currency(fields, field_name):
    """"extracts money values like total, tax, etc."""
    field = fields.get(field_name)

    # If currency exists → return amount rounded to 2 decimals
    if field and hasattr(field, "value_currency") and field.value_currency:
        return round(field.value_currency.amount, 2) if field.value_currency.amount is not None else None
    return None


def get_confidence(fields, field_name):
    """"returns how confident Azure is about the extracted value"""

    field = fields.get(field_name)
    # Return confidence (0 → 1), rounded
    return round(field.confidence, 4) if field and field.confidence is not None else None


def get_address(fields, field_name):
    """extracts address in a clean format"""
    field = fields.get(field_name)
    if not field:
        return None
    return getattr(field, "content", None).replace("\n", ", ")


def get_phone(fields, field_name):
    """extracts phone number"""

    field = fields.get(field_name)
    if not field:
        return None
    
    # Prefer readable format (like 010-123-4567)
    return (getattr(field, "content", None)
            or getattr(field, "value_phone_number", None)
            or getattr(field, "value_string", None))


def extract_items(fields):
    """"extracts the list of purchased items"""

    items = []
    items_field = fields.get("Items")
    if not (items_field and hasattr(items_field, "value_array") and items_field.value_array):
        return items

    # Get each property of each item (description, quantity, price, total_price)
    for item in items_field.value_array:

        obj         = item.value_object or {}
        desc        = obj.get("Description")
        qty         = obj.get("Quantity")
        price       = obj.get("Price")
        total_price = obj.get("TotalPrice")

        items.append({
            "description": desc.value_string if desc and hasattr(desc, "value_string") else None,
            "quantity":    qty.value_number  if qty  and hasattr(qty,  "value_number")  else None,
            "price": (
                round(price.value_currency.amount, 2)
                if price and hasattr(price, "value_currency") and price.value_currency else None
            ),
            "total_price": (
                round(total_price.value_currency.amount, 2)
                if total_price and hasattr(total_price, "value_currency") and total_price.value_currency else None
            ),
        })
    return items



def analyze_receipt(file_bytes: bytes):
    """
    Send document bytes to Azure prebuilt-receipt and return a structured dict
    containing all extracted receipt fields across all receipts in the document.
    """
    
    client = get_client()
    result = client.begin_analyze_document(
        "prebuilt-receipt",
        body=file_bytes,
        content_type="application/octet-stream",
    ).result()

    output = {
        "page_count": len(result.pages) if result.pages else 0,
        "receipts": [],
    }

    if not result.documents:
        return output

    # Process each detected receipt in the document
    for idx, receipt in enumerate(result.documents):
        fields = receipt.fields or {}

        output["receipts"].append({
            "receipt_index":    idx,
            "doc_type":         receipt.doc_type,
            "receipt_type":     get_string(fields, "ReceiptType"),
            "country_region":   (
                fields["CountryRegion"].value_country_region
                if "CountryRegion" in fields and hasattr(fields["CountryRegion"], "value_country_region")
                else None
            ),
            # Merchant info
            "merchant_name":              get_string(fields, "MerchantName"),
            "merchant_name_confidence":   get_confidence(fields, "MerchantName"),
            "merchant_address":           get_address(fields, "MerchantAddress"),
            "merchant_phone":             get_phone(fields, "MerchantPhoneNumber"),
            # Transaction info
            "transaction_date":            get_date(fields, "TransactionDate"),
            "transaction_time":            get_time(fields, "TransactionTime"),
            "transaction_date_confidence": get_confidence(fields, "TransactionDate"),
            # Line items
            "items": extract_items(fields),
            # Totals
            "subtotal":            get_currency(fields, "Subtotal"),
            "subtotal_confidence": get_confidence(fields, "Subtotal"),
            "tax":                 get_currency(fields, "TotalTax"),
            "tax_confidence":      get_confidence(fields, "TotalTax"),
            "tip":                 get_currency(fields, "Tip"),
            "tip_confidence":      get_confidence(fields, "Tip"),
            "total":               get_currency(fields, "Total"),
            "total_confidence":    get_confidence(fields, "Total"),
        })

    return output