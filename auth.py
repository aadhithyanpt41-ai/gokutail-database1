import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from models import Chapter, Content, Page, ReadingProgress, User
from schemas import (
    ChapterCreate,
    ChapterPublic,
    ContentCreate,
    ContentPublic,
    ContentUpdate,
    CreatorPublic,
    CreatorSummary,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserPublic,
    UserUpdate,
)
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
        role=user.role,
        created_at=user.created_at,
        content_count=content_count,
        follower_count=0,
        total_views=0,
    )


def _creator_response(db: Session, user: User) -> CreatorPublic:
    private_user = _user_response(db, user)
    return CreatorPublic(**private_user.model_dump(exclude={"email"}))


def _creator_summary(user: User | None) -> CreatorSummary | None:
    if user is None:
        return None
    return CreatorSummary(
        id=user.id,
        username=user.username,
        name=user.name,
        avatar_url=user.avatar_url,
        creator_title=user.creator_title,
    )


def _content_response(db: Session, content: Content) -> ContentPublic:
    creator = db.get(User, content.owner_id)
    chapter_count = db.scalar(select(func.count(Chapter.id)).where(Chapter.content_id == content.id)) or 0
    first_chapter_id = db.scalar(
        select(Chapter.id).where(Chapter.content_id == content.id).order_by(Chapter.number.asc(), Chapter.created_at.asc()).limit(1)
    )
    return ContentPublic(
        id=content.id,
        owner_id=content.owner_id,
        title=content.title,
        content_type=content.content_type,
        description=content.description,
        cover_url=content.cover_url,
        genre=content.genre,
        tags=content.tags,
        language=content.language,
        age_rating=content.age_rating,
        view_count=content.view_count,
        status=content.status,
        created_at=content.created_at,
        chapter_count=chapter_count,
        first_chapter_id=first_chapter_id,
        creator=_creator_summary(creator),
    )


def _chapter_response(db: Session, chapter: Chapter) -> ChapterPublic:
    page_count = db.scalar(select(func.count(Page.id)).where(Page.chapter_id == chapter.id)) or 0
    return ChapterPublic(
        id=chapter.id,
        content_id=chapter.content_id,
        number=chapter.number,
        title=chapter.title,
        source_lang=chapter.source_lang,
        target_lang=chapter.target_lang,
        status=chapter.status,
        created_at=chapter.created_at,
        page_count=page_count,
    )


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
    contents = db.scalars(
        select(Content)
        .where(Content.owner_id == user.id, Content.status == "published")
        .order_by(Content.created_at.desc())
    ).all()
    return [_content_response(db, content) for content in contents]


@router.get("/content/mine", response_model=list[ContentPublic])
def my_content(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contents = db.scalars(
        select(Content).where(Content.owner_id == current_user.id).order_by(Content.created_at.desc())
    ).all()
    return [_content_response(db, content) for content in contents]


@router.post("/content", response_model=ContentPublic, status_code=status.HTTP_201_CREATED)
def create_content(payload: ContentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content = Content(owner_id=current_user.id, **payload.model_dump())
    db.add(content)
    db.commit()
    db.refresh(content)
    return _content_response(db, content)


@router.put("/content/{content_id}", response_model=ContentPublic)
def update_content(
    content_id: int,
    payload: ContentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = db.get(Content, content_id)
    if content is None or content.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(content, field, value)

    db.commit()
    db.refresh(content)
    return _content_response(db, content)


@router.delete("/content/{content_id}")
def delete_content(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = db.get(Content, content_id)
    if content is None or content.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    chapter_ids = db.scalars(select(Chapter.id).where(Chapter.content_id == content.id)).all()
    if chapter_ids:
        db.execute(delete(ReadingProgress).where(ReadingProgress.chapter_id.in_(chapter_ids)))
        db.execute(delete(Page).where(Page.chapter_id.in_(chapter_ids)))
        db.execute(delete(Chapter).where(Chapter.id.in_(chapter_ids)))
    db.delete(content)
    db.commit()
    return {"status": "deleted"}


@router.get("/content/{content_id}/chapters", response_model=list[ChapterPublic])
def my_content_chapters(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = db.get(Content, content_id)
    if content is None or content.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    chapters = db.scalars(
        select(Chapter).where(Chapter.content_id == content_id).order_by(Chapter.number.asc(), Chapter.created_at.asc())
    ).all()
    return [_chapter_response(db, chapter) for chapter in chapters]


@router.post("/content/{content_id}/chapters", response_model=ChapterPublic, status_code=status.HTTP_201_CREATED)
def create_chapter(
    content_id: int,
    payload: ChapterCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = db.get(Content, content_id)
    if content is None or content.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    chapter = Chapter(
        content_id=content_id,
        number=payload.number,
        title=payload.title,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        status=payload.status,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    for index, image_url in enumerate(payload.page_urls, start=1):
        db.add(Page(chapter_id=chapter.id, page_order=index, image_url=image_url))
    db.commit()
    db.refresh(chapter)
    return _chapter_response(db, chapter)


@router.post("/logout")
def logout():
    return {"status": "ok"}
