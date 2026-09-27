import gzip
import shutil
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.variant import Variant
from app.models.vcf_file import VCFFile

UPLOAD_DIR = Path("uploads")


def open_vcf(file_path: str | Path):
    if str(file_path).endswith(".gz"):
        return gzip.open(file_path, "rt", encoding="utf-8")

    return open(file_path, "r", encoding="utf-8")


def parse_vcf(file_path: str | Path) -> list[dict]:
    variants = []

    with open_vcf(file_path) as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            columns = line.split("\t")

            if len(columns) < 8:
                raise ValueError("Invalid VCF record")

            chrom = columns[0]
            pos = int(columns[1])
            ref = columns[3]
            alt = columns[4]
            qual = None if columns[5] == "." else float(columns[5])
            filter_value = None if columns[6] == "." else columns[6]
            info = columns[7]

            af = None

            for field in info.split(";"):
                if field.startswith("AF="):
                    af = float(field.split("=", 1)[1])
                    break

            variants.append(
                {
                    "chrom": chrom,
                    "pos": pos,
                    "ref": ref,
                    "alt": alt,
                    "qual": qual,
                    "filter": filter_value,
                    "af": af,
                }
            )

    return variants


def validate_vcf(file_path: str | Path) -> None:
    has_fileformat = False
    has_column_header = False

    with open_vcf(file_path) as file:
        for line in file:
            line = line.strip()

            if line.startswith("##fileformat=VCF"):
                has_fileformat = True

            elif line.startswith("#CHROM"):
                has_column_header = True

    if not has_fileformat or not has_column_header:
        raise ValueError("Invalid VCF file")


def validate_vcf_extension(file_path: str | Path) -> None:
    file_path = str(file_path)

    if not file_path.endswith((".vcf", ".vcf.gz")):
        raise ValueError("Invalid VCF file extension")


def save_uploaded_vcf(file, filename: str) -> Path:
    UPLOAD_DIR.mkdir(exist_ok=True)

    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


async def create_vcf_file(
    db: AsyncSession,
    project_id: int,
    filename: str,
) -> VCFFile:
    vcf_file = VCFFile(
        project_id=project_id,
        filename=filename,
    )

    db.add(vcf_file)
    await db.commit()
    await db.refresh(vcf_file)

    return vcf_file


async def create_variants(
    db: AsyncSession,
    vcf_file_id: int,
    variants: list[dict],
) -> list[Variant]:
    variant_objects = [
        Variant(
            vcf_file_id=vcf_file_id,
            chrom=variant["chrom"],
            pos=variant["pos"],
            ref=variant["ref"],
            alt=variant["alt"],
            qual=variant["qual"],
            filter=variant["filter"],
            af=variant["af"],
        )
        for variant in variants
    ]

    db.add_all(variant_objects)
    await db.commit()

    return variant_objects


async def get_vcf_files(
    db: AsyncSession,
    project_id: int,
) -> list[VCFFile]:
    result = await db.execute(select(VCFFile).where(VCFFile.project_id == project_id))

    return list(result.scalars().all())


async def get_vcf_file(
    db: AsyncSession,
    project_id: int,
    vcf_id: int,
) -> VCFFile:
    result = await db.execute(
        select(VCFFile)
        .options(selectinload(VCFFile.variants))
        .where(
            VCFFile.id == vcf_id,
            VCFFile.project_id == project_id,
        )
    )

    vcf_file = result.scalar_one_or_none()

    if vcf_file is None:
        raise HTTPException(
            status_code=404,
            detail="VCF file not found",
        )

    return vcf_file


async def delete_vcf_file(
    db: AsyncSession,
    project_id: int,
    vcf_id: int,
) -> None:
    vcf_file = await get_vcf_file(
        db=db,
        project_id=project_id,
        vcf_id=vcf_id,
    )

    file_path = UPLOAD_DIR / vcf_file.filename

    await db.execute(delete(Variant).where(Variant.vcf_file_id == vcf_file.id))

    await db.delete(vcf_file)
    await db.commit()

    if file_path.exists():
        file_path.unlink()
