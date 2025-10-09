# app.py
import os
import uuid
import json
import traceback
import requests
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from openai import OpenAI

# --- Load environment variables ---
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")
FRONTEND_URL = "https://ai-compliance-agent-6x5opqcnt-tks-projects-c34b12e1.vercel.app"

if not OPENAI_API_KEY:
    raise ValueError("CRITICAL: OPENAI_API_KEY is missing.")
if not OCR_SPACE_API_KEY:
    raise ValueError("CRITICAL: OCR_SPACE_API_KEY is missing.")

client = OpenAI(api_key=OPENAI_API_KEY)

# --- FastAPI app setup ---
app = FastAPI(title="AI Compliance Assistant API")

origins = [
    "http://localhost:5173",
    FRONTEND_URL,  # Your Vercel frontend (no slash)
]

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
    try:
        # --- Step 1: Read file bytes ---
        file_bytes = await invoice_file.read()
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")

        # --- Step 2: Send to OCR.Space ---
        ocr_response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": (invoice_file.filename, file_bytes)},
            data={"apikey": OCR_SPACE_API_KEY, "language": "eng"},
            timeout=60
        )
        ocr_response.raise_for_status()
        ocr_json = ocr_response.json()

        if ocr_json.get("IsErroredOnProcessing"):
            raise ValueError(f"OCR.Space error: {ocr_json.get('ErrorMessage')}")

        parsed_text = (
            ocr_json.get("ParsedResults", [{}])[0].get("ParsedText", "").strip()
        )
        if not parsed_text:
            raise ValueError("OCR returned no text.")

        # --- Step 3: Extract using OpenAI ---
        system_prompt = (
            "You are an expert data extraction bot for Indian GST invoices. "
            "Respond ONLY with a JSON object containing: "
            "'invoiceNumber', 'date' (YYYY-MM-DD), 'gstin', 'totalAmount', 'gstAmount'. "
            "If any field is missing, set it as 'N/A'."
        )
        user_prompt = f"OCR text:\n{parsed_text}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw_output = response.choices[0].message.content
        extracted = json.loads(raw_output)

        # Ensure all keys exist
        for key in ["invoiceNumber", "date", "gstin", "totalAmount", "gstAmount"]:
            extracted.setdefault(key, "N/A")

        return {"status": "Completed", "data": extracted}

    except Exception as e:
        return {
            "status": "Error",
            "error": str(e),
            "trace": traceback.format_exc(),
            "data": {},
        }
