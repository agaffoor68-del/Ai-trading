"""
Phase 2: Admin Endpoints

Protected by Admin role dependency.
Endpoints for user management and subscription control.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_admin, require_active_subscription, get_db
from app.core.database import SessionLocal
from app.core.models import User, Subscription, UserRole, SubscriptionPlan

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/users")
async def list_all_users(
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    """
    List all users with their subscription details.
    Admin only.
    """
    users = (
        db.query(User)
        .options(joinedload(User.subscription))
        .order_by(User.created_at.desc())
        .all()
    )

    result = []
    for user in users:
        sub = user.subscription
        result.append({
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "subscription": {
                "plan_type": sub.plan_type.value if sub else None,
                "start_date": sub.start_date.isoformat() if sub and sub.start_date else None,
                "end_date": sub.end_date.isoformat() if sub and sub.end_date else None,
                "is_active": sub.is_active if sub else False,
            } if sub else None,
        })

    return {"users": result, "total": len(result)}


@router.post("/subscribe")
async def grant_subscription(
    user_id: int,
    plan_type: str = "Basic",
    days: int = 30,
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    """
    Give a user a subscription for X days (default 30 days).
    Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not active",
        )

    # Validate plan type
    try:
        plan_enum = SubscriptionPlan(plan_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan type. Must be one of: {[p.value for p in SubscriptionPlan]}",
        )

    now = datetime.now(IST)
    end_date = now + timedelta(days=days)

    # Check if user already has a subscription
    existing_sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()

    if existing_sub:
        existing_sub.plan_type = plan_enum
        existing_sub.start_date = now
        existing_sub.end_date = end_date
        existing_sub.is_active = True
        existing_sub.updated_at = now
    else:
        new_sub = Subscription(
            user_id=user_id,
            plan_type=plan_enum,
            start_date=now,
            end_date=end_date,
            is_active=True,
        )
        db.add(new_sub)

    db.commit()

    logger.info(
        f"Admin {admin_user.email} granted {plan_type} subscription for {days} days "
        f"to user {user.email} (id={user_id})"
    )

    return {
        "message": f"{plan_type} subscription granted for {days} days",
        "user_id": user_id,
        "email": user.email,
        "plan_type": plan_enum.value,
        "end_date": end_date.isoformat(),
    }


@router.delete("/revoke/{user_id}")
async def revoke_access(
    user_id: int,
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    """
    Revoke a user's access immediately by deactivating their account and subscription.
    Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke admin access",
        )

    # Deactivate user
    user.is_active = False
    user.updated_at = datetime.now(IST)

    # Deactivate subscription if exists
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if sub:
        sub.is_active = False
        sub.end_date = datetime.now(IST)
        sub.updated_at = datetime.now(IST)

    db.commit()

    logger.warning(
        f"Admin {admin_user.email} revoked access for user {user.email} (id={user_id})"
    )

    return {
        "message": f"Access revoked for user {user.email}",
        "user_id": user_id,
        "is_active": False,
    }


@router.get("/stats")
async def get_admin_stats(
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db_session),
):
    """
    Get platform statistics for admin dashboard.
    Admin only.
    """
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.role == UserRole.ADMIN).count()
    regular_users = db.query(User).filter(User.role == UserRole.USER).count()

    total_subscriptions = db.query(Subscription).count()
    active_subscriptions = db.query(Subscription).filter(Subscription.is_active == True).count()

    now = datetime.now(IST)
    expired_subscriptions = (
        db.query(Subscription)
        .filter(Subscription.is_active == True)
        .filter(Subscription.end_date < now)
        .count()
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "regular_users": regular_users,
        "total_subscriptions": total_subscriptions,
        "active_subscriptions": active_subscriptions,
        "expired_subscriptions": expired_subscriptions,
    }
