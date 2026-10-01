from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.annotation_service import (
    create_annotation_file,
    delete_annotation_file,
    get_annotation_files,
    save_uploaded_annotation,
    validate_annotation_file,
)
from app.services.project_service import get_project

router = APIRouter(
    prefix="/projects/{project_id}/annotation",
    tags=["annotation"],
)


@router.post("/")
async def upload_annotation(
    project_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    project = await get_project(db, project_id)

    file_path = save_uploaded_annotation(
        file,
        file.filename,
    )

    try:
        validate_annotation_file(file_path)
    except ValueError as error:
        file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    annotation_file = await create_annotation_file(
        db=db,
        project_id=project.id,
        filename=file.filename,
    )

    return {
        "project_id": project.id,
        "annotation_id": annotation_file.id,
        "filename": annotation_file.filename,
        "path": str(file_path),
    }


@router.get("/")
async def list_annotation_files(
    project_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await get_project(db, project_id)

    annotation_files = await get_annotation_files(
        db=db,
        project_id=project_id,
    )

    return [
        {
            "id": annotation_file.id,
            "filename": annotation_file.filename,
            "created_at": annotation_file.created_at,
        }
        for annotation_file in annotation_files
    ]


@router.delete(
    "/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_annotation(
    project_id: int,
    annotation_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await get_project(db, project_id)

    await delete_annotation_file(
        db=db,
        project_id=project_id,
        annotation_id=annotation_id,
    )
