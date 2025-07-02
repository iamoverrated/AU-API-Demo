from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List
import uvicorn
import os
from msal import ConfidentialClientApplication
import requests

app = FastAPI()

# MSAL setup
def get_access_token():
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]

    app = ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" in result:
        return result["access_token"]
    else:
        raise HTTPException(status_code=500, detail="Failed to acquire access token")

# MS Graph: Check if AU already exists

def find_existing_admin_unit(au_name: str):
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"https://graph.microsoft.com/v1.0/directory/administrativeUnits?$filter=displayName eq '{au_name}'",
        headers=headers
    )
    if response.status_code == 200:
        results = response.json().get("value", [])
        if results:
            return results[0]
    return None

# MS Graph: Create Administrative Unit
def create_admin_unit(au_name: str, admin_upn: str):
    existing = find_existing_admin_unit(au_name)
    if existing:
        return existing

    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "displayName": au_name,
        "description": f"AU managed by {admin_upn}",
        "visibility": "Public"
    }
    response = requests.post(
        "https://graph.microsoft.com/v1.0/directory/administrativeUnits",
        headers=headers,
        json=data
    )
    if response.status_code != 201:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()

# MS Graph: Create Group
def create_group(group_name: str, au_id: str, owner_upn: str):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    group_data = {
        "displayName": f"AUG_{group_name}",
        "mailEnabled": False,
        "mailNickname": f"aug_{group_name.lower()}",
        "securityEnabled": True,
        "owners@odata.bind": [
            f"https://graph.microsoft.com/v1.0/users/{owner_upn}"
        ]
    }
    response = requests.post(
        "https://graph.microsoft.com/v1.0/groups",
        headers=headers,
        json=group_data
    )
    if response.status_code != 201:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    group = response.json()

    # Add group to AU
    au_bind_url = f"https://graph.microsoft.com/v1.0/directory/administrativeUnits/{au_id}/members/$ref"
    bind_data = {
        "@odata.id": f"https://graph.microsoft.com/v1.0/groups/{group['id']}"
    }
    bind_response = requests.post(au_bind_url, headers=headers, json=bind_data)
    if bind_response.status_code != 204:
        raise HTTPException(status_code=bind_response.status_code, detail=bind_response.json())

    return group

def create_app_registration(au_id: str):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Create App Registration
    app_data = {
        "displayName": f"AppReg-AU-{au_id}",
        "signInAudience": "AzureADMyOrg"
    }
    app_response = requests.post(
        "https://graph.microsoft.com/v1.0/applications",
        headers=headers,
        json=app_data
    )
    if app_response.status_code != 201:
        raise HTTPException(status_code=app_response.status_code, detail=app_response.json())
    app = app_response.json()

    # Create Client Secret
    secret_data = {
        "passwordCredential": {
            "displayName": "DefaultSecret"
        }
    }
    secret_response = requests.post(
        f"https://graph.microsoft.com/v1.0/applications/{app['id']}/addPassword",
        headers=headers,
        json=secret_data
    )
    if secret_response.status_code != 200:
        raise HTTPException(status_code=secret_response.status_code, detail=secret_response.json())
    secret = secret_response.json()

    # Create Service Principal
    sp_data = {"appId": app["appId"]}
    sp_response = requests.post(
        "https://graph.microsoft.com/v1.0/servicePrincipals",
        headers=headers,
        json=sp_data
    )
    if sp_response.status_code != 201:
        raise HTTPException(status_code=sp_response.status_code, detail=sp_response.json())
    sp = sp_response.json()

    # Assign AU-scoped Role to SP (Admin)
    role_assignment = {
        "principalId": sp["id"],
        "resourceScope": f"/directory/administrativeUnits/{au_id}",
        "roleDefinitionId": "fe930be7-5e62-47db-91af-98c3a49a38b1"  # Directory Writers role
    }
    ra_response = requests.post(
        "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments",
        headers=headers,
        json=role_assignment
    )
    if ra_response.status_code not in (200, 201):
        raise HTTPException(status_code=ra_response.status_code, detail=ra_response.json())

    return {
        "app_display_name": app["displayName"],
        "app_id": app["appId"],
        "client_id": app["id"],
        "service_principal_id": sp["id"],
        "au_id": au_id
    }

# Check if user is admin
def is_user_admin_of_au(user_upn: str, au_id: str):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(
        f"https://graph.microsoft.com/v1.0/directory/administrativeUnits/{au_id}/scopedRoleMembers",
        headers=headers
    )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    members = response.json().get("value", [])
    return any(
        member.get("principal", {}).get("userPrincipalName", "").lower() == user_upn.lower()
        for member in members
    )


# Dummy placeholder for Graph Logic (to be implemented)
def remove_group_from_au(group_id: str):
    return {"status": "removed_from_au", "group_id": group_id}

def add_group_to_au(group_id: str, au_id: str):
    return {"status": "added_to_au", "group_id": group_id, "au_id": au_id}

def add_members_to_group(group_id: str, members: List[str]):
    return {"group_id": group_id, "added_members": members}

def add_admin_to_au(au_id: str, admin_upn: str):
    return {"au_id": au_id, "admin": admin_upn}

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

    access_token = get_access_token()  # MSAL token (not yet used in dummy functions)

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

    if not is_user_admin_of_au(payload.user_upn, "fake-au-id"):
        raise HTTPException(status_code=403, detail="User is not an admin of the specified AU")

    result = add_members_to_group(payload.group_id, payload.members)
    result["requested_by"] = payload.user_upn
    return result

@app.post("/add_admin")
async def add_admin_handler(request: Request, payload: AddAdminRequest):
    api_key = request.headers.get("Authorization")
    expected_key = os.getenv("API_KEY", "Bearer test123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if not is_user_admin_of_au(payload.user_upn, payload.au_id):
        raise HTTPException(status_code=403, detail="User is not an admin of the specified AU")

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