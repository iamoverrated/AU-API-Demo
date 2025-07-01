from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List
import uvicorn
import os

app = FastAPI()

# Dummy MS Graph logic (replace with actual logic using MSAL and requests)
def create_admin_unit(au_name: str):
    return {"id": "fake-au-id", "name": au_name}

def create_group(group_name: str, au_id: str):
    return {"id": f"fake-group-id-{group_name.lower()}", "name": group_name, "au_id": au_id}

def create_app_registration(au_id: str):
    return {"client_id": "fake-client-id", "client_secret": "fake-client-secret", "au_id": au_id}

class ProvisionRequest(BaseModel):
    au_name: str
    groups: List[str]
    create_app_registration: bool = False

@app.post("/provision")
async def provision(request: Request, payload: ProvisionRequest):
    # Optional: API key check
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Step 1: Create Administrative Unit
    au = create_admin_unit(payload.au_name)

    # Step 2: Create Groups
    groups = []
    for group in payload.groups:
        groups.append(create_group(group, au["id"]))

    # Step 3: Optionally create App Registration
    app_reg = None
    if payload.create_app_registration:
        app_reg = create_app_registration(au["id"])

    return {
        "status": "success",
        "administrative_unit": au,
        "groups": groups,
        "app_registration": app_reg
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
