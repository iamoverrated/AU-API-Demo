from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List
import uvicorn
import os

app = FastAPI()

# Dummy logic (replace with actual MS Graph logic)
def create_admin_unit(au_name: str, admin_upn: str):
    return {"id": "fake-au-id", "name": au_name, "admins": [admin_upn]}

def create_group(group_name: str, au_id: str, owner_upn: str):
    full_name = f"AUG_{group_name}"
    return {"id": f"fake-group-id-{group_name.lower()}", "name": full_name, "au_id": au_id, "owners": [owner_upn]}

def create_app_registration(au_id: str):
    return {"client_id": "fake-client-id", "client_secret": "fake-client-secret", "au_id": au_id}

def remove_group_from_au(group_id: str):
    return {"status": "removed_from_au", "group_id": group_id}

def add_group_to_au(group_id: str, au_id: str):
    return {"status": "added_to_au", "group_id": group_id, "au_id": au_id}

def add_members_to_group(group_id: str, members: List[str]):
    return {"group_id": group_id, "added_members": members}

def add_admin_to_au(au_id: str, admin_upn: str):
    return {"au_id": au_id, "admin": admin_upn}

def is_user_admin_of_au(user_upn: str, au_id: str):
    # Dummy check — replace with actual lookup
    dummy_admins = {"fake-au-id": ["admin@domain.com"]}
    return user_upn in dummy_admins.get(au_id, [])

def list_tools():
    return [
        "provision_tenant_unit",
        "remove_group_from_au",
        "add_group_to_au",
        "add_members_to_group",
        "add_admin_to_au",
        "list_tools"
    ]

class ProvisionRequest(BaseModel):
    au_name: str
    groups: List[str]
    create_app_registration: bool = False
    user_upn: str

class RemoveGroupRequest(BaseModel):
    group_id: str
    au_id: str
    user_upn: str

class AddGroupRequest(BaseModel):
    group_id: str
    au_id: str
    user_upn: str

class AddMembersRequest(BaseModel):
    group_id: str
    members: List[str]
    user_upn: str

class AddAdminRequest(BaseModel):
    au_id: str
    admin_upn: str
    user_upn: str

@app.post("/provision")
async def provision(request: Request, payload: ProvisionRequest):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    au = create_admin_unit(payload.au_name, payload.user_upn)
    groups = [create_group(group, au["id"], payload.user_upn) for group in payload.groups]
    app_reg = create_app_registration(au["id"]) if payload.create_app_registration else None

    return {
        "status": "success",
        "requested_by": payload.user_upn,
        "administrative_unit": au,
        "groups": groups,
        "app_registration": app_reg
    }

@app.post("/remove_group")
async def remove_group_handler(request: Request, payload: RemoveGroupRequest):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if not is_user_admin_of_au(payload.user_upn, payload.au_id):
        raise HTTPException(status_code=403, detail="User is not an admin of the specified AU")

    result = remove_group_from_au(payload.group_id)
    result["requested_by"] = payload.user_upn
    return result

@app.post("/add_group")
async def add_group_handler(request: Request, payload: AddGroupRequest):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if not is_user_admin_of_au(payload.user_upn, payload.au_id):
        raise HTTPException(status_code=403, detail="User is not an admin of the specified AU")

    result = add_group_to_au(payload.group_id, payload.au_id)
    result["requested_by"] = payload.user_upn
    return result

@app.post("/add_members")
async def add_members_handler(request: Request, payload: AddMembersRequest):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    result = add_members_to_group(payload.group_id, payload.members)
    result["requested_by"] = payload.user_upn
    return result

@app.post("/add_admin")
async def add_admin_handler(request: Request, payload: AddAdminRequest):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    result = add_admin_to_au(payload.au_id, payload.admin_upn)
    result["requested_by"] = payload.user_upn
    return result

@app.get("/list_tools")
async def list_tools_handler(request: Request):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return {"available_tools": list_tools()}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)