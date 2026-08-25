from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth as auth_lib
from app.config import get_settings
from app.database import get_db
from app.deps import create_session_cookie_value, get_current_user_optional
from app.models import User
from app.schemas import MeOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.get("/login")
async def login(db: AsyncSession = Depends(get_db)):
    """Redirects the user to VATSIM Connect to authorize this app. No password is ever seen by this app."""
    state = await auth_lib.create_oauth_state(db)
    return RedirectResponse(auth_lib.build_authorize_url(state))


@router.get("/callback")
async def callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    valid = await auth_lib.consume_oauth_state(db, state)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    token_data = await auth_lib.exchange_code_for_token(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="VATSIM Connect did not return an access token")

    userinfo = await auth_lib.fetch_userinfo(access_token)
    user = await auth_lib.get_or_create_user(db, userinfo)

    redirect = RedirectResponse(f"{settings.FRONTEND_BASE_URL}/")
    redirect.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=create_session_cookie_value(user.id),
        httponly=True,
        secure=settings.ENV != "development",
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return redirect


@router.post("/logout")
async def logout():
    resp = RedirectResponse(f"{settings.FRONTEND_BASE_URL}/", status_code=302)
    resp.delete_cookie(settings.SESSION_COOKIE_NAME)
    return resp


@router.get("/me", response_model=MeOut | None)
async def me(user: User | None = Depends(get_current_user_optional)):
    if user is None:
        return None
    return MeOut(vatsim_cid=user.vatsim_cid, full_name=user.full_name, email=user.email)
