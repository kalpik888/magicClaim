# check_models.py

import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API Key
load_dotenv()
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Error: Could not configure API. Check your .env file. {e}")
    exit()

print("--- Listing all available models for your API key ---")

try:
    # Iterate and print all available models
    for m in genai.list_models():
        print(f"\nModel Name: {m.name}")
        print(f"  Supported Methods: {m.supported_generation_methods}")
        print(f"  Display Name: {m.display_name}")

except Exception as e:
    print(f"\n--- ERROR ---")
    print(f"Could not list models. This might be an API key or permission issue.")
    print(f"Error details: {e}")

print("\n--- Done ---")