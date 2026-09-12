"""Signing in, and signing out.

Each route parses the request, calls one service function, and renders or
redirects. Nothing here queries (Principle I, done-gate 4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from app import development
from app.database import Db, get_session
from app.dependencies import SESSION_COOKIE, current_account
from app.rendering import render
from app.security import (
    CSRF_COOKIE,
    client_key,
    csrf_protect,
    is_secure_request,
    rate_limit_exceeded,
)
from app.services import auth_service
from app.services.email_service import EmailDeliveryFailed

router = APIRouter(tags=["auth"])

TOO_MANY = "Too many attempts. Wait a few minutes and try again."


@router.get("/login")
def login_form(request: Request, db: Db = Depends(get_session)):
    # A *valid* session sends them to the dashboard. A stale cookie must not:
    # `/` would bounce it straight back here, and the two would loop forever.
    if auth_service.session_is_valid(db, request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    response = render(request, "auth/login.html")
    if request.cookies.get(SESSION_COOKIE):
        response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.post("/login", dependencies=[Depends(csrf_protect)])
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Db = Depends(get_session),
):
    if rate_limit_exceeded(f"login:{client_key(request)}"):
        return render(request, "auth/login.html", {"message": TOO_MANY, "email": email}, 429)

    try:
        await auth_service.start_login(db, email, password)
    except (auth_service.InvalidCredentials, auth_service.InactiveAccount):
        return render(
            request,
            "auth/login.html",
            {"message": "That email address and password did not match.", "email": email},
            status.HTTP_401_UNAUTHORIZED,
        )
    except EmailDeliveryFailed:
        # The code exists and was printed to the server console, so it is
        # reachable even when the mail provider refuses. Carry the failure to
        # the code page rather than stopping here: the person is told plainly
        # (FR-020), and can still finish signing in if they have the code.
        return RedirectResponse(
            f"/login/verify?email={email}&mail=failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        f"/login/verify?email={email}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/login/verify")
def verify_form(request: Request, email: str = "", mail: str = ""):
    context: dict = {"email": email}
    if mail == "failed":
        context["message"] = (
            "The code could not be emailed. It was still issued, so enter it if you "
            "have it another way. Otherwise sign in again once mail is working."
        )
        context["message_kind"] = "warning"

    # development-only: None in production, and the template shows nothing.
    # Deleting app/development.py and this line removes the feature entirely.
    context["development_code"] = development.code_for(email)

    return render(request, "auth/verify.html", context)


@router.post("/login/verify", dependencies=[Depends(csrf_protect)])
def verify_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    db: Db = Depends(get_session),
):
    if rate_limit_exceeded(f"verify:{client_key(request)}"):
        return render(request, "auth/verify.html", {"message": TOO_MANY, "email": email}, 429)

    try:
        row = auth_service.verify_code(
            db,
            email,
            code,
            ip=client_key(request),
            user_agent=request.headers.get("user-agent"),
        )
    except auth_service.CodeExpired:
        return render(
            request,
            "auth/verify.html",
            {"message": "That code has expired. Sign in again to get a new one.", "email": email},
            status.HTTP_401_UNAUTHORIZED,
        )
    except (auth_service.CodeInvalid, auth_service.InactiveAccount):
        return render(
            request,
            "auth/verify.html",
            {"message": "That code is not correct.", "email": email},
            status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        row.id,
        httponly=True,
        secure=is_secure_request(request),
        samesite="lax",
        path="/",
        expires=int((row.expires_at - row.created_at).total_seconds()),
    )
    return response


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(
    request: Request,
    db: Db = Depends(get_session),
    account=Depends(current_account),
):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        auth_service.sign_out(db, token)

    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response
