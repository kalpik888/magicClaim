# photo_agent.py

import os
import io
# 1. Use the correct, official library
import google.generativeai as genai
from fastapi import APIRouter, File, UploadFile, HTTPException
from typing import List
from PIL import Image
from dotenv import load_dotenv
from schemas import DamagedParts
from supabase import create_client, Client

# --- Setup & Configuration ---
load_dotenv()
try:
    # 2. Configure the library
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Error configuring Google AI Client: {e}")
    # Handle error appropriately

# 3. Initialize the model directly
# The 'pip install --upgrade' command from Step 1 ensures 
# this model name is now recognized.
model = genai.GenerativeModel('gemini-flash-latest')

try:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase: Client = create_client(url, key)
    print("Supabase client initialized for photo.")
except Exception as e:
    print(f"Error initializing Supabase client in photo: {e}")

# --- Create your ROUTER ---
router = APIRouter(
    prefix="/claim",
    tags=["Insurance Claims"]
)

# --- Helper Functions (no change) ---
def prepare_image(image_bytes: bytes) -> List[bytes]:
    try:
        return Image.open(io.BytesIO(image_bytes))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")
    
def fetch_claim_photos(claim_id: str) -> List[bytes]:
    """
    Fetches all photo files for a given claim_id from Supabase Storage.
    Returns a list of image bytes.
    """
    
    # --- IMPORTANT ASSUMPTIONS ---
    DB_TABLE = "claim_media"       # Table with file paths
    PATH_COLUMN = "storage_path"      # Column in 'claim_media' with the path
    STORAGE_BUCKET = "claims-media"  # Name of your Storage bucket
    # -----------------------------

    print(f"Fetching photo paths for claim_id: {claim_id}")
    try:
        # Step 1: Query the database for file paths
        response = supabase.table(DB_TABLE)\
                           .select(PATH_COLUMN)\
                           .eq("claim_id", claim_id)\
                           .execute()
        print(response.data)
        
        if not response.data:
            print(f"No photos found for claim_id: {claim_id}")
            return []

        # List of full URLs (e.g., "https://.../claims-media/path/to/file.jpg")
        full_urls = [item[PATH_COLUMN] for item in response.data]
        print(f"Found {len(full_urls)} photo URLs.")

        # Step 2: Download each file from Storage
        photo_bytes_list = []
        
        # This is the key to find the relative path
        path_delimiter = f"/{STORAGE_BUCKET}/" 
        
        for url in full_urls:
            try:
                # --- THE FIX ---
                # Split the URL to get the part *after* the bucket name
                # "https://.../claims-media/path/to/file.jpg" -> "path/to/file.jpg"
                relative_path = url.split(path_delimiter)[-1]
                
                print(f"Downloading relative path: {relative_path}")
                file_bytes = supabase.storage.from_(STORAGE_BUCKET).download(relative_path)
                photo_bytes_list.append(file_bytes)
                
            except Exception as e:
                print(f"Error downloading file {url}: {e}")
        
        return photo_bytes_list

    except Exception as e:
        print(f"Error querying Supabase: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch photo paths.")
    
@router.post("/analyze/{claim_id}", response_model=DamagedParts)
async def analyze_claim_from_supabase(claim_id: str):
    """
    Fetches claim images from Supabase, analyzes them with Gemini,
    and returns a consolidated damage report.
    """
    
    # Step 1: Fetch the raw photo bytes from Supabase
    photo_bytes_list = fetch_claim_photos(claim_id)
    
    if not photo_bytes_list:
        raise HTTPException(status_code=404, detail="No photos found for this claim ID.")

    print(f"Processing {len(photo_bytes_list)} images from Supabase for claim {claim_id}...")

    # Step 2: Convert bytes to PIL Images for Gemini
    pil_images = []
    for img_bytes in photo_bytes_list:
        pil_images.append(prepare_image(img_bytes))

    # Step 3: Build the prompt (same as before)
    prompt = [
        "You are an expert insurance adjuster...",
        "Analyze these images...",
        "Provide a consolidated list...",
        "Respond ONLY with JSON...",
        *pil_images,
    ]

    # Step 4: Call Gemini (same as before)
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": DamagedParts
            }
        )
        return DamagedParts.model_validate_json(response.text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

# --- Your Endpoint (using the original, correct syntax) ---
@router.post("/analyze", response_model=DamagedParts)
async def analyze_claim_images(files: List[UploadFile] = File(...)):
    """
    Upload multiple car images to get a consolidated damage report.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No images provided")

    print(f"Processing {len(files)} images...")

    pil_images = []
    for file in files:
        content = await file.read()
        pil_images.append(prepare_image(content))

    prompt = [
        "You are an expert insurance adjuster specializing in auto claims.",
        "Analyze these images, which are different angles of the SAME damaged vehicle.",
        "Identify all visibly damaged parts across all images.",
        "Provide a consolidated list of unique damaged part names and a brief summary.",
        "Respond ONLY with JSON matching the requested schema.",
        *pil_images,
    ]

    try:
        # 4. This is the correct way to call generate_content
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": DamagedParts
            }
        )
        return DamagedParts.model_validate_json(response.text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")