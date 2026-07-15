from fastapi import APIRouter, Depends, HTTPException, Request

from ...dependencies.auth import get_current_user_optional
from ...services.file_history_service import file_history_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/history")
async def get_profile_history(
    request: Request,
    current_user: dict | None = Depends(get_current_user_optional),
):
    resolved_user = current_user or {
        "id": request.headers.get("X-Airco-User-Id"),
        "email": request.headers.get("X-Airco-User-Email"),
        "name": request.headers.get("X-Airco-User-Name"),
        "given_name": request.headers.get("X-Airco-Given-Name"),
        "family_name": request.headers.get("X-Airco-Family-Name"),
        "preferred_username": request.headers.get("X-Airco-Preferred-Username"),
        "roles": [],
    }
    user_id = resolved_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    history = file_history_service.list_for_user(user_id)

    return {
        "user": {
            "id": resolved_user.get("id"),
            "email": resolved_user.get("email"),
            "name": resolved_user.get("name"),
            "given_name": resolved_user.get("given_name"),
            "family_name": resolved_user.get("family_name"),
            "preferred_username": resolved_user.get("preferred_username"),
            "roles": resolved_user.get("roles", []),
        },
        **history,
    }


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    request: Request,
    current_user: dict | None = Depends(get_current_user_optional),
):
    resolved_user = current_user or {
        "id": request.headers.get("X-Airco-User-Id"),
        "email": request.headers.get("X-Airco-User-Email"),
        "name": request.headers.get("X-Airco-User-Name"),
        "given_name": request.headers.get("X-Airco-Given-Name"),
        "family_name": request.headers.get("X-Airco-Family-Name"),
        "preferred_username": request.headers.get("X-Airco-Preferred-Username"),
        "roles": [],
    }
    user_id = resolved_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        success = file_history_service.delete_file(user_id, file_id)
        if not success:
            raise HTTPException(status_code=404, detail="File not found or access denied")
        
        return {"message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
