import psycopg2
from dotenv import load_dotenv
import os
from fastapi import FastAPI, UploadFile, File, HTTPException,Form
from supabase import create_client, Client
from pydantic import BaseModel,ConfigDict
import uuid 
from typing import List,Optional
from datetime import date, time,datetime
import json
from fastapi.middleware.cors import CORSMiddleware
from photo_agent import router as photo_agent_router

# Load environment variables from .env
load_dotenv()

app = FastAPI()
app.include_router(photo_agent_router)

origins = [
    "http://localhost:5174",  # Your dev frontend from the error
    "http://localhost:5173",  # A common Vite default
    "http://localhost:3000",  # A common React default
    "http://localhost",
    "https://magicclaims-production.up.railway.app/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow specific origins
    allow_credentials=True,    # Allow cookies
    allow_methods=["*"],       # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],       # Allow all headers
)

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Fetch variables
USER = os.getenv("USER")
PASSWORD = os.getenv("supabase_password")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
DBNAME = os.getenv("DBNAME")



# Initialize Supabase client
try:
    supabase: Client = create_client(URL, KEY)
    print("Supabase client initialized.")
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    exit(1)

# Initialize FastAPI app


# This is the name of your bucket in Supabase Storage
BUCKET_NAME = "claims-media" 

# Pydantic model for updating the title
class PhotoUpdate(BaseModel):
    title: str

class ClaimCreate(BaseModel):
    policy_id: str
    customer_id: str
    date_of_incident: date
    incident_time: time
    incident_location: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ClaimResponse(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    date_of_incident: date
    incident_time: time
    incident_location: str
    description: Optional[str] = None

class ClaimUpdate(BaseModel):
    policy_id: Optional[str] = None
    customer_id: Optional[str] = None
    date_of_incident: Optional[date] = None
    incident_time: Optional[time] = None
    incident_location: Optional[str] = None
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
# --- 2. The 4 API Endpoints ---

### API 1: View (Read) All Photos
@app.get("/claim_media")
def get_all_media():
    """Fetches all media records from the claim_media table."""
    try:
        response = supabase.table("claim_media").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/claims/media/{media_id}")
def get_media_for_claim(media_id : int):
    """Fetches all media records for a specific claim_id."""
    try:
        # This is how you filter by a foreign key
        response = supabase.table("claim_media").select("*").eq("media_id", media_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/claims/{customer_id}")
def get_media_for_claim(customer_id : str):
    try:
        response = supabase.table("claim").select("*").eq("customer_id", customer_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/claim/{claim_id}")
def get_media_for_claim(claim_id : str):
    try:
        policy_id_res = supabase.table("claim").select("policy_id").eq("claim_id", claim_id).execute()
        policy_id = None
        if(policy_id_res.data):
            policy_id = policy_id_res.data[0]['policy_id']

        car_id_res = supabase.table("policy").select("car_id").eq("policy_id", policy_id).execute()
        car_id = None
        if(car_id_res.data):
            car_id = car_id_res.data[0]['car_id']
        
        cust_id_res = supabase.table("claim").select("customer_id").eq("claim_id", claim_id).execute()
        cust_id=None
        if(cust_id_res.data):
            cust_id = cust_id_res.data[0]['customer_id']

        shop_id_res = cust_id_res = supabase.table("claim").select("repair_shop_id_done").eq("claim_id", claim_id).execute()
        shop_id=None
        if(shop_id_res.data):
            shop_id = shop_id_res.data[0]['repair_shop_id_done']
        
        pol_no = supabase.table("policy").select("policy_number").eq("policy_id", policy_id).execute()

        shop_response = supabase.table("repair_shop").select("*").eq("repair_shop_id", shop_id).execute()
        cust_response = supabase.table("customer").select("*").eq("customer_id", cust_id).execute()
        car_response = supabase.table("car").select("*").eq("car_id", car_id).execute()
        claim_response = supabase.table("claim").select("*").eq("claim_id", claim_id).execute()
        media_response = supabase.table("claim_media").select("*").eq("claim_id", claim_id).execute()
        return claim_response.data + media_response.data + car_response.data + cust_response.data + shop_response.data + pol_no.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@app.get("/claim_car/{customer_id}")
def get_media_for_claim(customer_id : str):
    try:
        claim_response = supabase.table("claim").select("*").eq("customer_id", customer_id).execute()
        car_response = supabase.table("car").select("*").eq("customer_id", customer_id).execute()
        return claim_response.data + car_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/claims", response_model=ClaimResponse)
def create_claim(claim_data: ClaimCreate):
    try:
        # 1. Generate ID
        new_claim_id = f"CL-{uuid.uuid4()}"

        new_claim_data = claim_data.model_dump(mode='json')
        # ------------------------------------
        
        new_claim_data["claim_id"] = new_claim_id

        response = supabase.table("claim").insert(new_claim_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create claim.")
            
        # --- THIS IS THE FIX for the RETURN ---
        # We parse the data from Supabase (which also has date objects)
        # into our Pydantic model, which knows how to serialize it.
        return ClaimResponse(**response.data[0])
        # ------------------------------------
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

  
@app.post("/claim_media/")
async def upload_multiple_media(
    claim_id: str = Form(...), 
    uploaded_by_user_id: int = Form(...),
    files: List[UploadFile] = File(...),
    descriptions: List[str] = Form(...)
):
    #descriptions = ["","desp1"]
    db_entries = []
    uploaded_storage_paths = []
    

    for index, file in enumerate(files):
        try:
            description = descriptions[index]
            
            # 1. Create a unique path for each file
            file_extension = os.path.splitext(file.filename)[1]
            file_path = f"claims/{uuid.uuid4()}{file_extension}"
            
            # 2. Read file content
            file_content = await file.read()
            
            # 3. Upload file to Supabase Storage
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            # 4. Add file metadata to our list for the bulk DB insert
            db_entries.append({
                "claim_id": claim_id,
                "uploaded_by_user_id": uploaded_by_user_id,
                "storage_path": file_path,
                "description": description
            })
            # Keep track of uploaded files for potential rollback
            uploaded_storage_paths.append(file_path)

        except Exception as e:
            # If any file fails to upload, stop and roll back
            # by deleting the files we've already uploaded.
            if uploaded_storage_paths:
                supabase.storage.from_(BUCKET_NAME).remove(uploaded_storage_paths)
            raise HTTPException(
                status_code=500, 
                detail=f"Error uploading file {file.filename}: {str(e)}"
            )

    # 5. After all files are in storage, do ONE bulk insert to the DB
    if not db_entries:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    try:
        # This is much faster than inserting one by one!
        response = supabase.table("claim_media").insert(db_entries).execute()

        try:
            supabase.table("claim").update({"status": "active"}).eq("claim_id", claim_id).execute()
        except Exception as e:
            # If this update fails, it's not a critical error.
            # The photos are still saved. We just log it.
            print(f"WARNING: Failed to update claim {claim_id} status to 'active': {e}")

        return response.data
    
    except Exception as e:
        # If the DB insert fails, we must roll back and delete
        # the orphaned files from storage.
        if uploaded_storage_paths:
            supabase.storage.from_(BUCKET_NAME).remove(uploaded_storage_paths)
        raise HTTPException(
            status_code=500, 
            detail=f"Error saving file metadata to database: {str(e)}"
        )
    
@app.post("/claim/full_submission")
async def create_claim_and_upload_media(
    # --- MODIFIED SECTION: Claim data as individual fields ---
    policy_id: str = Form(...),
    customer_id: str = Form(...),
    date_of_incident: date = Form(...),
    incident_time: time = Form(...),
    incident_location: str = Form(...),
    description: Optional[str] = Form(None),
    
    # --- Unchanged media/user fields ---
    uploaded_by_user_id: int = Form(...),
    files: List[UploadFile] = File(...),
    descriptions: List[str] = Form(...),
):
    """
    Creates a new claim AND uploads media in a single transaction.
    - Claim data is sent as individual form fields.
    - A claim is only created if at least one file is provided.
    """
    
    # --- 1. Validate Inputs (Unchanged) ---
    if not files:
        raise HTTPException(status_code=400, detail="A claim must include at least one photo.")
    
    if len(descriptions) == 1 and "," in descriptions[0]:
            descriptions = [d.strip() for d in descriptions[0].split(",")]
    
    # Note: I'm keeping your original file/description count check commented out,
    # but you'll need to fix the logic for accessing descriptions[index]
    # in section 3 if this check remains commented out.
    # if len(files) != len(descriptions):
    #     raise HTTPException(
    #         status_code=400, 
    #         detail=f"File count ({len(files)}) and description count ({len(descriptions)}) do not match."
    #     )

    # --- 2. Collect and Validate Claim Data ---
    try:
        # Collect data from Form fields into a dictionary
        claim_data_dict = {
            "policy_id": policy_id,
            "customer_id": customer_id,
            "date_of_incident": date_of_incident,
            "incident_time": incident_time,
            "incident_location": incident_location,
            "description": description
        }
        
        # Validate the dictionary using our Pydantic model
        # FastAPI/Pydantic handle type conversion (e.g., str to date)
        claim_data = ClaimCreate(**claim_data_dict)
        
    except Exception as e: # Catches Pydantic validation errors
        raise HTTPException(status_code=422, detail=f"Invalid claim data: {str(e)}")

    # --- 3. Process All Files (Upload to Storage) (Unchanged) ---
    new_claim_id = f"CL-{uuid.uuid4()}"
    uploaded_storage_paths = []
    db_media_entries = []

    for index, file in enumerate(files):
        try:
            # IMPORTANT: This will fail if len(files) != len(descriptions)
            desc_text = descriptions[index] if index < len(descriptions) else None
            description = desc_text if desc_text else None
            
            file_extension = os.path.splitext(file.filename)[1]
            file_path = f"claims/{new_claim_id}/{uuid.uuid4()}{file_extension}"
            
            file_content = await file.read()
            
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            uploaded_storage_paths.append(file_path)
            db_media_entries.append({
                "claim_id": new_claim_id,
                "uploaded_by_user_id": uploaded_by_user_id,
                "storage_path": file_path,
                "description": description
            })
            
        except Exception as e:
            # --- ROLLBACK FILES ---
            if uploaded_storage_paths:
                supabase.storage.from_(BUCKET_NAME).remove(uploaded_storage_paths)
            raise HTTPException(
                status_code=500, 
                detail=f"Error uploading file {file.filename}: {str(e)}"
            )

    # --- 4. Save to Database (Claim + Media) (Unchanged) ---
    try:
        # 1. Create the main claim record
        #    We use the 'claim_data' model from Step 2
        claim_record = claim_data.model_dump(mode='json') # Use 'json' mode for dates
        claim_record["claim_id"] = new_claim_id
        
        claim_response = supabase.table("claim").insert(claim_record).execute()
        if not claim_response.data:
            raise Exception("Failed to insert claim record.")

        # 2. Create the media records
        media_response = supabase.table("claim_media").insert(db_media_entries).execute()
        if not media_response.data:
            raise Exception("Failed to insert media records.")
        
        return {
            "claim": claim_response.data[0],
            "media": media_response.data
        }
    
    except Exception as e:
        # --- CRITICAL ROLLBACK ---
        print(f"Database error, rolling back storage: {e}")
        if uploaded_storage_paths:
            supabase.storage.from_(BUCKET_NAME).remove(uploaded_storage_paths)
        raise HTTPException(
            status_code=500, 
            detail=f"Error saving to database: {str(e)}"
        )

### API 3: Update a Photo's Title

@app.put("/claim/full_submission/{claim_id}")
async def update_claim_and_media(
    claim_id: str,
    
    # Data for the claim text fields (NOW INDIVIDUAL)
    policy_id: Optional[str] = Form(None),
    customer_id: Optional[str] = Form(None),
    date_of_incident: Optional[date] = Form(None),
    incident_time: Optional[time] = Form(None),
    incident_location: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    
    # Who is making this edit?
    edited_by_user_id: int = Form(...), 
    
    # Optional: New files to ADD
    new_files: List[UploadFile] = File([]),
    new_descriptions: List[str] = Form([]),
    
    # Optional: List of existing media_ids to DELETE
    #, 
):
    """
    Updates an existing claim, adds new media, and deletes old media.
    - Claim data is sent as individual form fields.
    - 'media_to_delete_json' must be a stringified JSON list of media_id strings.
    """
    
    # --- 1. Validate Claim Exists ---
    try:
        existing_claim = supabase.table("claim").select("claim_id").eq("claim_id", claim_id).execute()
        if not existing_claim.data:
            raise HTTPException(status_code=404, detail="Claim not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking claim: {str(e)}")

    # --- 2. Parse and Validate Inputs ---
    
    # --- MODIFIED SECTION ---
    # Build a dictionary from the individual form fields
    claim_data_dict = {
        "policy_id": policy_id,
        "customer_id": customer_id,
        "date_of_incident": date_of_incident,
        "incident_time": incident_time,
        "incident_location": incident_location,
        "description": description
    }
    
    # Filter out any 'None' values. 
    # This leaves us with only the fields the user wants to update.
    filtered_claim_data = {k: v for k, v in claim_data_dict.items() if v is not None}

    # Validate the data that *was* provided using our Pydantic model
    try:
        claim_update_model = ClaimUpdate(**filtered_claim_data)
        claim_record = claim_update_model.model_dump(mode='json', exclude_unset=True)
    except Exception as e: # Catches Pydantic validation errors
        raise HTTPException(status_code=422, detail=f"Invalid claim data: {str(e)}")
    # --- END MODIFIED SECTION ---

    # Parse the list of media IDs to delete
    # try:
    #     media_ids_to_delete = json.loads(media_to_delete_json)
    #     if not isinstance(media_ids_to_delete, list):
    #         raise ValueError("media_to_delete_json must be a JSON list.")
    # except Exception as e:
    #     raise HTTPException(status_code=400, detail=f"Invalid JSON for media_to_delete_json: {str(e)}")

    # (This logic remains the same)
    if len(new_descriptions) == 1 and "," in new_descriptions[0]:
        new_descriptions = [d.strip() for d in new_descriptions[0].split(",")]

    if len(new_files) != len(new_descriptions):
        raise HTTPException(
            status_code=400, 
            detail="New file count and new description count must match."
        )

    # --- 3. Process New File Uploads (if any) ---
    # (This section is unchanged)
    newly_uploaded_storage_paths = []
    db_media_entries_to_add = []

    for index, file in enumerate(new_files):
        try:
            desc_text = new_descriptions[index]
            description = desc_text if desc_text else None
            
            file_extension = os.path.splitext(file.filename)[1]
            # This is the internal path, used for uploading and deleting
            file_path = f"claims/{claim_id}/{uuid.uuid4()}{file_extension}" 
            
            file_content = await file.read()
            
            # --- START FIX ---

            # 1. Upload the file and CAPTURE the response
            upload_res = supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": file.content_type}
            )

            # 2. Check for an upload error (like in your first snippet)
            #    Note: Supabase-py returns a dict on error, not an exception
            if hasattr(upload_res, "error") and upload_res.error:
                 raise Exception(f"Upload failed: {upload_res.error.message}")

            # 3. Get the public URL
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            
            # --- END FIX ---

            # Add path to this list (for rollbacks)
            newly_uploaded_storage_paths.append(file_path)
            
            # Add the PUBLIC URL to the database
            db_media_entries_to_add.append({
                "claim_id": claim_id,
                "uploaded_by_user_id": edited_by_user_id,
                "storage_path": public_url,  # <--- Use the public_url here
                "description": description
            })
            
        except Exception as e:
            # --- ROLLBACK FILES ---
            if newly_uploaded_storage_paths:
                supabase.storage.from_(BUCKET_NAME).remove(newly_uploaded_storage_paths)
            raise HTTPException(
                status_code=500, 
                detail=f"Error uploading file {file.filename}: {str(e)}"
            )

    # --- 4. Get Storage Paths for Media to Delete ---
    # (This section is unchanged)
    # storage_paths_to_delete = []
    # if media_ids_to_delete:
    #     try:
    #         media_records = supabase.table("claim_media").select("media_id", "storage_path") \
    #             .in_("media_id", media_ids_to_delete).execute()
            
    #         storage_paths_to_delete = [m['storage_path'] for m in media_records.data]
    #     except Exception as e:
    #         print(f"Warning: Could not fetch storage paths for media to delete: {str(e)}")


    # --- 5. Save All Changes to Database ---
    try:
        # --- MODIFIED SECTION ---
        # 1. Update the main claim record
        #    We use the 'filtered_claim_data' dict we created in section 2.
        #    FastAPI has already validated and converted the data types.
        #claim_record = filtered_claim_data 
        
        claim_response = None
        if claim_record: # Only update if there's data to update
            claim_response = supabase.table("claim").update(claim_record) \
                .eq("claim_id", claim_id).execute()
        # --- END MODIFIED SECTION ---

        # 2. Delete old media records from DB
        # deleted_media_response = None
        # if media_ids_to_delete:
        #     deleted_media_response = supabase.table("claim_media").delete() \
        #         .in_("media_id", media_ids_to_delete).execute()

        # 3. Create the new media records in DB
        added_media_response = None
        if db_media_entries_to_add:
            added_media_response = supabase.table("claim_media").insert(db_media_entries_to_add).execute()

        # --- 6. (On Success) Delete Old Files from Storage ---
        # (This logic is unchanged)
        # if storage_paths_to_delete:
        #     try:
        #         supabase.storage.from_(BUCKET_NAME).remove(storage_paths_to_delete)
        #     except Exception as e:
        #         print(f"Warning: DB delete succeeded, but failed to remove files from storage: {str(e)}")

        return {
            "message": "Claim updated successfully.",
            "updated_claim": claim_response.data[0] if claim_response and claim_response.data else "No text fields updated.",
            "added_media": added_media_response.data if added_media_response and added_media_response.data else [],
            #"deleted_media_count": len(deleted_media_response.data) if deleted_media_response and deleted_media_response.data else 0
        }
    
    except Exception as e:
        # (Rollback logic is unchanged)
        print(f"Database error, rolling back storage: {e}")
        if newly_uploaded_storage_paths:
            supabase.storage.from_(BUCKET_NAME).remove(newly_uploaded_storage_paths)
        
        raise HTTPException(
            status_code=500, 
            detail=f"Error saving to database: {str(e)}"
        )

@app.put("/description/{media_id}")
def update_photo_title(media_id: int,desc: str):
    """Updates the 'title' of a photo in the database."""
    
    try:
        response = supabase.table("claim_media").update(
            {"description": desc}
        ).eq("media_id", media_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Photo not found.")
            
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


### API 4: Delete a Photo
@app.delete("/photos/{media_id}")
def delete_photo(media_id: int):
    """
    Deletes a photo from the DB and Storage,
    but only if it's not the last photo for the claim.
    """
    try:
        # --- 1. Find the photo AND its claim_id ---
        # We need the claim_id to perform the count
        select_response = supabase.table("claim_media") \
            .select("storage_path, claim_id") \
            .eq("media_id", media_id) \
            .maybe_single() \
            .execute()

        if not select_response.data:
            raise HTTPException(status_code=404, detail="Photo not found.")
        
        storage_url = select_response.data.get("storage_path")
        claim_id = select_response.data.get("claim_id")

        if not claim_id:
             raise HTTPException(status_code=500, detail="Database integrity error: Photo is not linked to a claim.")

        # --- 2. NEW: Check if this is the last photo ---
        count_response = supabase.table("claim_media") \
            .select("media_id", count='exact') \
            .eq("claim_id", claim_id) \
            .execute()

        if count_response.count <= 1:
            # This is the last photo. Block the deletion.
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete the last photo. A claim must have at least one photo."
            )

        # --- 3. FIXED: Delete the file from Supabase Storage ---
        if storage_url:
            try:
                # We MUST parse the internal path from the full URL
                internal_path = storage_url.split(f"{BUCKET_NAME}/", 1)[1]
                supabase.storage.from_(BUCKET_NAME).remove([internal_path])
            except Exception as e:
                # Log this, but don't stop the DB delete.
                print(f"Warning: Failed to delete file from storage: {str(e)}")

        # --- 4. Delete the record from the database ---
        delete_response = supabase.table("claim_media").delete().eq("media_id", media_id).execute()
        
        if not delete_response.data:
            # This shouldn't happen if step 1 passed, but it's good to check
            raise HTTPException(status_code=404, detail="Failed to delete photo record.")

        return {"message": "Photo deleted successfully", "deleted_record": delete_response.data[0]}
    
    except HTTPException as e:
        # Re-raise HTTPException so FastAPI shows the correct status code
        raise e
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=str(e))

