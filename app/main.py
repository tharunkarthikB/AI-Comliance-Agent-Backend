# app.py  -- Vercel-compatible variant (uses OCR.Space instead of pytesseract)
import os
import uuid
import json
import traceback
import requests
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

if not OPENAI_API_KEY:
    raise ValueError("CRITICAL: OPENAI_API_KEY environment variable not set.")
if not OCR_SPACE_API_KEY:
    raise ValueError("CRITICAL: OCR_SPACE_API_KEY environment variable not set.")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="AI Compliance Assistant API (OCR.Space variant)")

# IMPORTANT: FRONTEND_URL must not contain a trailing slash
origins = [FRONTEND_URL, "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/api/upload-invoice/")
async def upload_invoice(invoice_file: UploadFile = File(...)):
    """
    Receives an invoice image, sends it to OCR.Space for OCR,
    then calls OpenAI to extract the desired fields and returns JSON.
    """
    try:
        # Read uploaded file bytes
        file_bytes = await invoice_file.read()
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")

        # 1) Send file to OCR.Space
        files = {
            "file": (invoice_file.filename, file_bytes, invoice_file.content_type or "application/octet-stream")
        }
        data = {
            "apikey": OCR_SPACE_API_KEY,
            "language": "eng",
            "isOverlayRequired": False
        }

        ocr_resp = requests.post("https://api.ocr.space/parse/image", files=files, data=data, timeout=60)
        ocr_resp.raise_for_status()
        ocr_json = ocr_resp.json()

        if ocr_json.get("IsErroredOnProcessing"):
            err_msg = ocr_json.get("ErrorMessage") or ocr_json.get("ErrorDetails") or "Unknown OCR.Space error"
            raise ValueError(f"OCR.Space error: {err_msg}")

        parsed = ocr_json.get("ParsedResults")
        if not parsed or not parsed[0].get("ParsedText"):
            raise ValueError("OCR returned empty text.")

        ocr_text = parsed[0]["ParsedText"].strip()
        if not ocr_text:
            raise ValueError("OCR parsed text is empty.")

        # 2) Ask OpenAI to extract required fields (returns JSON)
        system_prompt = (
            "You are an expert data extraction bot for Indian GST invoices. "
            "Respond ONLY with a valid JSON object containing exactly these keys: "
            "'invoiceNumber', 'date' (YYYY-MM-DD if available, else 'N/A'), 'gstin', 'totalAmount', 'gstAmount'. "
            "If a field is not found, set it to 'N/A'. Do NOT include any extra text."
        )
        user_prompt = f"Extract the required fields from this OCR text:\n---\n{ocr_text}\n---"

        # Use the same OpenAI client pattern as your original code.
        # If your OpenAI SDK does not accept `response_format`, remove that and parse content manually.
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )

        # The SDK may give a dict or a string; handle both.
        raw = response.choices[0].message.content
        if isinstance(raw, dict):
            extracted = raw
        else:
            s = str(raw).strip()
            # try to find JSON substring
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_text = s[start:end+1]
            else:
                json_text = s
            extracted = json.loads(json_text)

        # Ensure required keys exist (fill with 'N/A' if missing)
        for k in ("invoiceNumber", "date", "gstin", "totalAmount", "gstAmount"):
            if k not in extracted:
                extracted[k] = "N/A"

        return {"status": "Completed", "error": None, "data": extracted}

    except Exception as e:
        tb = traceback.format_exc()
        return {
            "status": "Error",
            "error": f"Error Message: {str(e)}\n\nFull Traceback:\n{tb}",
            "data": {}
        }
