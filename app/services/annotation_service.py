import shutil
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation_file import AnnotationFile

UPLOAD_DIR = Path("uploads")

EXPECTED_COLUMNS_12 = [
    "#VariantID",
    "Type",
    "Name",
    "GeneID",
    "GeneSymbol",
    "ClinicalSignificance",
    "RS_dbSNP",
    "Chromosome",
    "Start",
    "Stop",
    "ReferenceAllele",
    "AlternateAllele",
]


def validate_annotation_file(file_path: str | Path) -> None:
    with open(file_path, "r", encoding="utf-8") as file:
        header = file.readline().strip()

        columns = header.split("\t")

        if columns != EXPECTED_COLUMNS_12:
            raise ValueError("Invalid ClinVar annotation format")

        valid_entries = 0

        for line in file:
            line = line.strip()

            if not line:
                continue

            values = line.split("\t")

            if len(values) != len(EXPECTED_COLUMNS_12):
                continue

            valid_entries += 1

        if valid_entries == 0:
            raise ValueError("No valid annotation entries found")


def save_uploaded_annotation(file, filename: str) -> Path:
    UPLOAD_DIR.mkdir(exist_ok=True)

    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


async def create_annotation_file(
    db: AsyncSession,
    project_id: int,
    filename: str,
) -> AnnotationFile:
    annotation_file = AnnotationFile(
        project_id=project_id,
        filename=filename,
    )

    db.add(annotation_file)
    await db.commit()
    await db.refresh(annotation_file)

    return annotation_file


async def get_annotation_files(
    db: AsyncSession,
    project_id: int,
) -> list[AnnotationFile]:
    result = await db.execute(
        select(AnnotationFile).where(AnnotationFile.project_id == project_id)
    )

    return list(result.scalars().all())


async def delete_annotation_file(
    db: AsyncSession,
    project_id: int,
    annotation_id: int,
) -> None:
    result = await db.execute(
        select(AnnotationFile).where(
            AnnotationFile.id == annotation_id,
            AnnotationFile.project_id == project_id,
        )
    )

    annotation_file = result.scalar_one_or_none()

    if annotation_file is None:
        raise HTTPException(
            status_code=404,
            detail="Annotation file not found",
        )

    file_path = UPLOAD_DIR / annotation_file.filename

    await db.delete(annotation_file)
    await db.commit()

    if file_path.exists():
        file_path.unlink()
