from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models import Chapter, Content, Page, ReadingProgress, User
from schemas import (
    AdminOverview,
    ChapterPagesResponse,
    ChapterPublic,
    ContentPublic,
    CreatorSummary,
    PagePublic,
    ProgressPublic,
    ProgressUpdate,
)
from security import get_current_user
from session import get_db

router = APIRouter()


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
    chapter_count = db.scalar(
        select(func.count(Chapter.id)).where(Chapter.content_id == content.id, Chapter.status == "published")
    ) or 0
    first_chapter_id = db.scalar(
        select(Chapter.id)
        .where(Chapter.content_id == content.id, Chapter.status == "published")
        .order_by(Chapter.number.asc(), Chapter.created_at.asc())
        .limit(1)
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


@router.get("/catalog", response_model=list[ContentPublic])
def catalog(
    q: str | None = None,
    content_type: str | None = None,
    genre: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(Content).where(Content.status == "published")
    if q:
        needle = f"%{q.strip()}%"
        query = query.where(or_(Content.title.ilike(needle), Content.description.ilike(needle), Content.tags.ilike(needle)))
    if content_type and content_type != "all":
        query = query.where(Content.content_type == content_type)
    if genre and genre != "all":
        query = query.where(Content.genre == genre)

    contents = db.scalars(query.order_by(Content.created_at.desc())).all()
    return [_content_response(db, content) for content in contents]


@router.get("/content/{content_id}", response_model=ContentPublic)
def content_detail(content_id: int, db: Session = Depends(get_db)):
    content = db.get(Content, content_id)
    if content is None or content.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")
    return _content_response(db, content)


@router.get("/content/{content_id}/chapters", response_model=list[ChapterPublic])
def content_chapters(content_id: int, db: Session = Depends(get_db)):
    content = db.get(Content, content_id)
    if content is None or content.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    chapters = db.scalars(
        select(Chapter)
        .where(Chapter.content_id == content_id, Chapter.status == "published")
        .order_by(Chapter.number.asc(), Chapter.created_at.asc())
    ).all()
    return [_chapter_response(db, chapter) for chapter in chapters]


@router.get("/chapters/{chapter_id}/pages", response_model=ChapterPagesResponse)
def chapter_pages(chapter_id: int, db: Session = Depends(get_db)):
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    content = db.get(Content, chapter.content_id)
    if content is None or content.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    pages = db.scalars(select(Page).where(Page.chapter_id == chapter.id).order_by(Page.page_order.asc())).all()
    if not pages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This chapter has no pages yet")

    content.view_count += 1
    db.commit()
    db.refresh(content)

    previous_chapter_id = db.scalar(
        select(Chapter.id)
        .where(Chapter.content_id == content.id, Chapter.status == "published", Chapter.number < chapter.number)
        .order_by(Chapter.number.desc())
        .limit(1)
    )
    next_chapter_id = db.scalar(
        select(Chapter.id)
        .where(Chapter.content_id == content.id, Chapter.status == "published", Chapter.number > chapter.number)
        .order_by(Chapter.number.asc())
        .limit(1)
    )

    return ChapterPagesResponse(
        content=_content_response(db, content),
        chapter=_chapter_response(db, chapter),
        pages=[
            PagePublic(id=page.id, order=page.page_order, image_url=page.image_url, caption=page.caption)
            for page in pages
        ],
        previous_chapter_id=previous_chapter_id,
        next_chapter_id=next_chapter_id,
    )


@router.post("/chapters/{chapter_id}/progress", response_model=ProgressPublic)
def save_progress(
    chapter_id: int,
    payload: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    progress = db.scalar(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.chapter_id == chapter_id,
        )
    )
    if progress is None:
        progress = ReadingProgress(
            user_id=current_user.id,
            chapter_id=chapter_id,
            page_number=payload.page_number,
            completed=payload.completed,
        )
        db.add(progress)
    else:
        progress.page_number = payload.page_number
        progress.completed = payload.completed

    db.commit()
    db.refresh(progress)
    return ProgressPublic(
        chapter_id=progress.chapter_id,
        page_number=progress.page_number,
        completed=progress.completed,
        updated_at=progress.updated_at,
    )


@router.get("/me/progress", response_model=list[ProgressPublic])
def my_progress(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == current_user.id)
        .order_by(ReadingProgress.updated_at.desc())
    ).all()
    return [
        ProgressPublic(
            chapter_id=row.chapter_id,
            page_number=row.page_number,
            completed=row.completed,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/admin/overview", response_model=AdminOverview)
def admin_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    users = db.scalar(select(func.count(User.id))) or 0
    published_works = db.scalar(select(func.count(Content.id)).where(Content.status == "published")) or 0
    draft_works = db.scalar(select(func.count(Content.id)).where(Content.status == "draft")) or 0
    chapters = db.scalar(select(func.count(Chapter.id))) or 0
    pages = db.scalar(select(func.count(Page.id))) or 0
    total_views = db.scalar(select(func.coalesce(func.sum(Content.view_count), 0))) or 0
    recent_users = db.scalars(select(User).order_by(User.created_at.desc()).limit(6)).all()
    recent_content = db.scalars(select(Content).order_by(Content.created_at.desc()).limit(8)).all()

    from auth import _user_response

    return AdminOverview(
        users=users,
        published_works=published_works,
        draft_works=draft_works,
        chapters=chapters,
        pages=pages,
        total_views=total_views,
        recent_users=[_user_response(db, user) for user in recent_users],
        recent_content=[_content_response(db, content) for content in recent_content],
    )
