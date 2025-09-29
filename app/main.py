# --- Imports ---
import os
import uuid
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from openai import OpenAI # This should be the only AI library imported

# --- Environment Setup ---
load_dotenv()

# Set the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configure the OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("CRITICAL ERROR: OPENAI_API_KEY not found in .env file. Please check the file.")

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# --- FastAPI App Initialization ---
app = FastAPI(title="AI Compliance Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)


# --- AI Data Extraction Logic ---
def extract_invoice_data_with_openai(image_path: str) -> dict:
    """
    Performs OCR on an image, sends the text to the OpenAI API for extraction,
    and returns structured data.
    """
    try:
        # 1. Perform OCR using Tesseract
        image = Image.open(image_path)
        ocr_text = pytesseract.image_to_string(image)

        if not ocr_text.strip():
            return {"status": "Error", "error": "OCR failed: No text found.", "data": {}}

        # 2. Use OpenAI GPT model to extract structured data
        system_prompt = """
        You are an expert data extraction bot for Indian GST invoices. Your task is to analyze raw OCR text and respond ONLY with a valid JSON object containing the following fields: 'invoiceNumber', 'date' (in YYYY-MM-DD format), 'gstin', 'totalAmount', and 'gstAmount'. If a field is not found, its value must be "N/A".
        """
        
        user_prompt = f"Extract the required fields from this OCR text:\n---\n{ocr_text}\n---"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        return {"status": "Completed", "error": None, "data": extracted_data}

    except Exception as e:
        print(f"An error occurred in OpenAI extraction: {e}")
        return {"status": "Error", "error": str(e), "data": {}}


# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Compliance Assistant API!"}


@app.post("/api/upload-invoice/")
async def upload_invoice(invoice_file: UploadFile = File(...)):
    file_extension = os.path.splitext(invoice_file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(TEMP_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await invoice_file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    result = extract_invoice_data_with_openai(file_path)

    os.remove(file_path)
    return result

