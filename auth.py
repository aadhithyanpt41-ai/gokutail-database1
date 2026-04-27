import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Content, User
from schemas import ContentCreate, ContentPublic, CreatorPublic, TokenResponse, UserCreate, UserLogin, UserPublic, UserUpdate
from security import create_access_token, get_current_user, hash_password, verify_password
from session import get_db

router = APIRouter()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:30] or "creator"


def _unique_username(db: Session, base: str) -> str:
    username = _slugify(base)
    if len(username) < 3:
        username = f"{username}_creator"

    candidate = username[:30]
    index = 2
    while db.scalar(select(User).where(User.username == candidate)):
        suffix = f"_{index}"
        candidate = f"{username[:30 - len(suffix)]}{suffix}"
        index += 1
    return candidate


def _user_response(db: Session, user: User) -> UserPublic:
    content_count = db.scalar(
        select(func.count(Content.id)).where(Content.owner_id == user.id, Content.status == "published")
    ) or 0
    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        name=user.name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        website=user.website,
        location=user.location,
        creator_title=user.creator_title,
        created_at=user.created_at,
        content_count=content_count,
        follower_count=0,
        total_views=0,
    )


def _creator_response(db: Session, user: User) -> CreatorPublic:
    private_user = _user_response(db, user)
    return CreatorPublic(**private_user.model_dump(exclude={"email"}))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    username = payload.username or _unique_username(db, payload.name or payload.email.split("@")[0])
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")

    user = User(
        email=payload.email,
        username=username,
        name=payload.name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=_user_response(db, user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=_user_response(db, user))


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _user_response(db, current_user)


@router.put("/me", response_model=UserPublic)
def update_me(payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updates = payload.model_dump(exclude_unset=True)
    username = updates.pop("username", None)
    if username is not None and username != current_user.username:
        existing_user = db.scalar(select(User).where(User.username == username, User.id != current_user.id))
        if existing_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")
        current_user.username = username

    for field, value in updates.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return _user_response(db, current_user)


@router.get("/creators/{username}", response_model=CreatorPublic)
def public_creator(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username.lower(), User.is_active == True))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found")
    return _creator_response(db, user)


@router.get("/creators/{username}/contents", response_model=list[ContentPublic])
def public_creator_contents(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username.lower(), User.is_active == True))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found")
    return db.scalars(
        select(Content)
        .where(Content.owner_id == user.id, Content.status == "published")
        .order_by(Content.created_at.desc())
    ).all()


@router.get("/content/mine", response_model=list[ContentPublic])
def my_content(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Content).where(Content.owner_id == current_user.id).order_by(Content.created_at.desc())).all()


@router.post("/content", response_model=ContentPublic, status_code=status.HTTP_201_CREATED)
def create_content(payload: ContentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content = Content(owner_id=current_user.id, **payload.model_dump())
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


@router.post("/logout")
def logout():
    return {"status": "ok"}
