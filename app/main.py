# --- Imports ---
import os
import sys
import uuid
import json
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from openai import OpenAI

# --- Environment Setup ---
load_dotenv()

# The Windows-specific Tesseract path has been removed.
# The Dockerfile handles the Tesseract installation on the live server.

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("CRITICAL ERROR: OPENAI_API_KEY not found in .env file.")
client = OpenAI(api_key=OPENAI_API_KEY)

# --- FastAPI App Initialization ---
app = FastAPI(title="AI Compliance Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)


# --- API Endpoint with Enhanced Error Return ---
@app.post("/api/upload-invoice/")
async def upload_invoice(invoice_file: UploadFile = File(...)):
    file_path = None
    try:
        # Step 1: Save the temporary file
        file_extension = os.path.splitext(invoice_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(TEMP_DIR, unique_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await invoice_file.read())

        # Step 2: Perform OCR
        image = Image.open(file_path)
        ocr_text = pytesseract.image_to_string(image)
        if not ocr_text.strip():
            raise ValueError("OCR failed: No text was extracted from the image.")

        # Step 3: Call OpenAI API
        system_prompt = "You are an expert data extraction bot for Indian GST invoices. Respond ONLY with a valid JSON object containing: 'invoiceNumber', 'date' (YYYY-MM-DD), 'gstin', 'totalAmount', 'gstAmount'. If a field is not found, its value must be 'N/A'."
        user_prompt = f"Extract the required fields from this OCR text:\n---\n{ocr_text}\n---"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        extracted_data = json.loads(response.choices[0].message.content)
        return {"status": "Completed", "error": None, "data": extracted_data}

    except Exception as e:
        # Send the full error traceback to the frontend
        full_traceback = traceback.format_exc()
        print(f"ERROR: {full_traceback}") 
        sys.stdout.flush()
        return {
            "status": "Error",
            "error": f"Error Message: {str(e)}\n\nFull Traceback:\n{full_traceback}",
            "data": {}
        }

    finally:
        # Final Step: Clean up the temporary file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
