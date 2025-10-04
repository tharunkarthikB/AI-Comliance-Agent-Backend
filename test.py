import sys
import pytesseract
from PIL import Image

# --- Configuration ---
# This is the path we need to verify.
# Make sure it points to your tesseract.exe file.
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def run_ocr_test(image_path):
    """
    A simple, direct test to check if Tesseract is working correctly.
    """
    print("--- Starting Tesseract OCR Test ---")
    try:
        # 1. Set the Tesseract command path
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        print(f"Set Tesseract Path to: {TESSERACT_PATH}")

        # 2. Try to open the image
        print(f"Attempting to open image: {image_path}")
        image = Image.open(image_path)
        print("Image opened successfully.")

        # 3. Run Tesseract
        print("Running OCR...")
        extracted_text = pytesseract.image_to_string(image)
        print("OCR process finished.")

        # 4. Print the result
        if extracted_text and extracted_text.strip():
            print("\n--- OCR SUCCESS ---")
            print("Extracted Text:")
            print("-----------------")
            print(extracted_text)
            print("-----------------")
        else:
            print("\n--- OCR WARNING ---")
            print("The process ran, but no text was found in the image.")

    except FileNotFoundError:
        print("\n--- !!! CRITICAL ERROR !!! ---")
        print(f"TESSERACT NOT FOUND at the specified path: '{TESSERACT_PATH}'")
        print("Please verify that the tesseract.exe file exists at this exact location.")

    except Exception as e:
        print("\n--- !!! AN UNEXPECTED ERROR OCCURRED !!! ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ocr.py <path_to_your_image_file>")
        sys.exit(1)
    
    image_to_test = sys.argv[1]
    run_ocr_test(image_to_test)
