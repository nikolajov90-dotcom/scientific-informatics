from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.project_service import get_project
from app.services.vcf_service import (
    create_variants,
    create_vcf_file,
    delete_vcf_file,
    get_vcf_file,
    get_vcf_files,
    parse_vcf,
    save_uploaded_vcf,
    validate_vcf,
    validate_vcf_extension,
)

router = APIRouter(
    prefix="/projects/{project_id}/vcf",
    tags=["vcf"],
)


@router.post("/")
async def upload_vcf(
    project_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    project = await get_project(db, project_id)

    try:
        validate_vcf_extension(file.filename)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    file_path = save_uploaded_vcf(file, file.filename)

    try:
        validate_vcf(file_path)
    except ValueError as error:
        Path(file_path).unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    vcf_file = await create_vcf_file(
        db=db,
        project_id=project.id,
        filename=file.filename,
    )

    variants = parse_vcf(file_path)

    await create_variants(
        db=db,
        vcf_file_id=vcf_file.id,
        variants=variants,
    )

    return {
        "project_id": project.id,
        "vcf_id": vcf_file.id,
        "filename": file.filename,
        "path": str(file_path),
    }


@router.get("/")
async def list_vcf_files(
    project_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await get_project(db, project_id)

    vcf_files = await get_vcf_files(
        db=db,
        project_id=project_id,
    )

    return [
        {
            "id": vcf_file.id,
            "filename": vcf_file.filename,
            "created_at": vcf_file.created_at,
        }
        for vcf_file in vcf_files
    ]


@router.get("/{vcf_id}")
async def get_vcf(
    project_id: int,
    vcf_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    vcf_file = await get_vcf_file(
        db=db,
        project_id=project_id,
        vcf_id=vcf_id,
    )

    return {
        "id": vcf_file.id,
        "filename": vcf_file.filename,
        "created_at": vcf_file.created_at,
        "variants": [
            {
                "id": variant.id,
                "chrom": variant.chrom,
                "pos": variant.pos,
                "ref": variant.ref,
                "alt": variant.alt,
                "qual": variant.qual,
                "filter": variant.filter,
                "af": variant.af,
            }
            for variant in vcf_file.variants
        ],
    }


@router.delete("/{vcf_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vcf(
    project_id: int,
    vcf_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await get_project(db, project_id)

    await delete_vcf_file(
        db=db,
        project_id=project_id,
        vcf_id=vcf_id,
    )
