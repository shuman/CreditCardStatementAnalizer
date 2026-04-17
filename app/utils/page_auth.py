"""
Page authentication helper utilities.
Redirects unauthenticated users to login page.
"""
from typing import Optional
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User


async def require_login(request: Request, db: AsyncSession) -> Optional[User]:
    """
    Check if user is logged in via session.
    Redirects to /login if not authenticated.

    Args:
        request: The FastAPI request object
        db: Database session

    Returns:
        User object if authenticated, redirects to login otherwise
    """
    user_id = request.session.get("user_id")

    if not user_id:
        # Not logged in - redirect to login page
        return None

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        # Invalid session - clear and redirect
        request.session.clear()
        return None

    return user
