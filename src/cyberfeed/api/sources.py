"""Sources API: CRUD, trigger collection, OPML import/export."""

import uuid

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response as RawResponse
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_current_user, get_db, require_role
from cyberfeed.collectors.registry import CollectorRegistry
from cyberfeed.core.exceptions import NotFoundError, ValidationError
from cyberfeed.models.source import Source
from cyberfeed.models.user import User
from cyberfeed.schemas.source import SourceCreate, SourceRead, SourceUpdate
from cyberfeed.services.collector_service import CollectorService
from cyberfeed.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"])
source_service = SourceService()
collector_service = CollectorService()


@router.get("")
async def list_sources(
    platform: str | None = None,
    is_active: bool | None = None,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sources = await source_service.get_all(db, platform=platform, is_active=is_active)
    return {
        "sources": [
            {
                **SourceRead.model_validate(s).model_dump(),
                "config": source_service.get_masked_config(s),
            }
            for s in sources
        ]
    }


@router.get("/platforms")
async def list_platforms(
    _user: User = Depends(get_current_user),
) -> dict:
    return {"platforms": CollectorRegistry.available_platforms()}


@router.post("")
async def create_source(
    body: SourceCreate,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Validate config with collector
    try:
        collector = CollectorRegistry.get(body.platform)
    except KeyError:
        raise ValidationError(f"Unknown platform: {body.platform}") from None

    is_valid, error = await collector.validate_config(body.config)
    if not is_valid:
        raise ValidationError(f"Invalid config: {error}")

    source = await source_service.create(
        db, body.name, body.platform, body.config, body.collect_interval_min
    )
    return {
        **SourceRead.model_validate(source).model_dump(),
        "config": source_service.get_masked_config(source),
    }


@router.patch("/{source_id}")
async def update_source(
    source_id: uuid.UUID,
    body: SourceUpdate,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await source_service.get_by_id(db, source_id)
    if not source:
        raise NotFoundError("Source")

    updates = body.model_dump(exclude_unset=True)
    source = await source_service.update(db, source, **updates)
    return {
        **SourceRead.model_validate(source).model_dump(),
        "config": source_service.get_masked_config(source),
    }


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: uuid.UUID,
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await source_service.delete(db, source_id)
    if not deleted:
        raise NotFoundError("Source")


@router.post("/{source_id}/collect")
async def trigger_collection(
    source_id: uuid.UUID,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await source_service.get_by_id(db, source_id)
    if not source:
        raise NotFoundError("Source")

    result = await collector_service.collect_source(db, source)
    return {
        "collected_count": result.new_count,
        "duplicate_count": result.duplicate_count,
        "errors": result.errors,
    }


@router.post("/import-opml")
async def import_opml(
    file: UploadFile,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import RSS sources from an OPML file."""
    if not file.filename or not file.filename.endswith((".opml", ".xml")):
        raise ValidationError("File must be .opml or .xml")

    content = await file.read()
    if len(content) > 1_000_000:  # 1MB limit
        raise ValidationError("File too large (max 1MB)")

    try:
        tree = etree.fromstring(content)
    except etree.XMLSyntaxError as e:
        raise ValidationError(f"Invalid XML: {e}") from None

    outlines = tree.xpath("//outline[@xmlUrl]")
    imported = 0
    skipped = 0

    for outline in outlines:
        xml_url = outline.get("xmlUrl", "").strip()
        title = outline.get("title") or outline.get("text") or xml_url
        if not xml_url:
            skipped += 1
            continue

        # Check for duplicate URL
        existing = await db.execute(select(Source).where(Source.config_json.contains(xml_url)))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        source = await source_service.create(db, title, "rss", {"url": xml_url}, 30)
        if source:
            imported += 1
        else:
            skipped += 1

    return {"imported": imported, "skipped": skipped}


@router.get("/export-opml")
async def export_opml(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RawResponse:
    """Export RSS sources as OPML file."""
    result = await db.execute(select(Source).where(Source.platform == "rss").order_by(Source.name))
    sources = result.scalars().all()

    root = etree.Element("opml", version="2.0")
    head = etree.SubElement(root, "head")
    title_el = etree.SubElement(head, "title")
    title_el.text = "CyberFeed RSS Sources"
    body = etree.SubElement(root, "body")

    for source in sources:
        config = source_service.get_decrypted_config(source)
        url = config.get("url", "")
        etree.SubElement(
            body,
            "outline",
            type="rss",
            text=source.name,
            title=source.name,
            xmlUrl=url,
        )

    xml_bytes = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    return RawResponse(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=cyberfeed-sources.opml"},
    )
