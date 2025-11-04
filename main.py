import psycopg2
from dotenv import load_dotenv
import os
from fastapi import FastAPI, UploadFile, File, HTTPException,Form
from supabase import create_client, Client
from pydantic import BaseModel
import uuid 
from typing import List

# Load environment variables from .env
load_dotenv()

app = FastAPI()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Fetch variables
USER = os.getenv("USER")
PASSWORD = os.getenv("supabase_password")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
DBNAME = os.getenv("DBNAME")



# -----------------------------------

# Connect to the database
# try:
#     connection = psycopg2.connect(
#         user=USER,
#         password=PASSWORD,
#         host=HOST,
#         port=PORT,
#         dbname=DBNAME
#     )
#     print("Connection successful!")
    
#     # Create a cursor to execute SQL queries
#     cursor = connection.cursor()
    
#     # Example query
#     cursor.execute("SELECT NOW();")
#     result = cursor.fetchone()
#     print("Current Time:", result)

#     # Close the cursor and connection
#     cursor.close()
#     connection.close()
#     print("Connection closed.")

# except Exception as e:
#     print(f"Failed to connect: {e}")


# Initialize Supabase client
try:
    supabase: Client = create_client(URL, KEY)
    print("Supabase client initialized.")
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    exit(1)

# Initialize FastAPI app


# This is the name of your bucket in Supabase Storage
BUCKET_NAME = "photos" 

# Pydantic model for updating the title
class PhotoUpdate(BaseModel):
    title: str

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

  
@app.post("/claim_media/")
async def upload_multiple_media(
    claim_id: int = Form(...), 
    uploaded_by_user_id: int = Form(...),
    files: List[UploadFile] = File(...)  # <--- KEY CHANGE
):
    """Uploads multiple media files to storage and saves their
    metadata to the ClaimMedia table."""
    
    db_entries = []
    uploaded_storage_paths = []

    for file in files:
        try:
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
                "storage_path": file_path
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


### API 3: Update a Photo's Title
@app.put("/photos/{media_id}")
def update_photo_title(media_id: int,photo_update: UploadFile = File(...)):
    """Updates the 'title' of a photo in the database."""
    
    try:
        response = supabase.table("claim_media").update(
            {"title": photo_update.title}
        ).eq("media_id", media_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Photo not found.")
            
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


### API 4: Delete a Photo
@app.delete("/photos/{media_id}")
def delete_photo(media_id: int):
    """Deletes a photo from the DB and from Supabase Storage."""
    try:
        # 1. Find the photo in the DB to get its storage_path
        select_response = supabase.table("claim_media").select("storage_path").eq("media_id", media_id).execute()
        if not select_response.data:
            raise HTTPException(status_code=404, detail="Photo not found.")
        
        storage_path = select_response.data[0].get("storage_path")

        # 2. Delete the file from Supabase Storage
        if storage_path:
            supabase.storage.from_(BUCKET_NAME).remove([storage_path])

        # 3. Delete the record from the database
        delete_response = supabase.table("claim_media").delete().eq("media_id", media_id).execute()
        
        if not delete_response.data:
            raise HTTPException(status_code=404, detail="Failed to delete photo record.")

        return {"message": "Photo deleted successfully", "deleted_record": delete_response.data[0]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# doing this for trigger

