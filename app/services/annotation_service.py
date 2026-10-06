import shutil
from collections import Counter
from pathlib import Path
from statistics import mean, median

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.annotation import Annotation
from app.models.annotation_file import AnnotationFile
from app.models.variant import Variant
from app.models.vcf_file import VCFFile

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


def parse_annotation_file(file_path: str | Path) -> list[dict]:
    annotations = []

    with open(file_path, "r", encoding="utf-8") as file:
        file.readline()

        for line in file:
            line = line.strip()

            if not line:
                continue

            values = line.split("\t")

            if len(values) != len(EXPECTED_COLUMNS_12):
                continue

            annotations.append(
                {
                    "chrom": values[7],
                    "pos": int(values[8]),
                    "ref": values[10],
                    "alt": values[11],
                    "gene": values[4],
                    "clinical_significance": values[5],
                }
            )

    return annotations


def match_variants_to_annotations(
    variants: list[dict],
    annotations: list[dict],
) -> list[dict]:
    matches = []

    for variant in variants:
        for annotation in annotations:
            if (
                variant["chrom"] == annotation["chrom"]
                and variant["pos"] == annotation["pos"]
                and variant["ref"] == annotation["ref"]
                and variant["alt"] == annotation["alt"]
            ):
                matches.append(
                    {
                        "variant": variant,
                        "gene": annotation["gene"],
                        "clinical_significance": annotation["clinical_significance"],
                    }
                )

    return matches


async def annotate_vcf(
    db: AsyncSession,
    vcf_id: int,
) -> list[Annotation]:
    result = await db.execute(
        select(VCFFile)
        .options(selectinload(VCFFile.variants))
        .where(VCFFile.id == vcf_id)
    )

    vcf_file = result.scalar_one_or_none()

    if vcf_file is None:
        raise HTTPException(
            status_code=404,
            detail="VCF file not found",
        )

    annotation_result = await db.execute(
        select(AnnotationFile).where(AnnotationFile.project_id == vcf_file.project_id)
    )

    annotation_file = annotation_result.scalars().first()

    if annotation_file is None:
        raise HTTPException(
            status_code=404,
            detail="Annotation file not found",
        )

    annotation_path = UPLOAD_DIR / annotation_file.filename

    annotations = parse_annotation_file(annotation_path)

    variants = [
        {
            "id": variant.id,
            "chrom": variant.chrom,
            "pos": variant.pos,
            "ref": variant.ref,
            "alt": variant.alt,
        }
        for variant in vcf_file.variants
    ]

    matches = match_variants_to_annotations(
        variants,
        annotations,
    )

    annotation_objects = [
        Annotation(
            variant_id=match["variant"]["id"],
            gene=match["gene"],
            clinical_significance=match["clinical_significance"],
        )
        for match in matches
    ]

    db.add_all(annotation_objects)
    await db.commit()

    return annotation_objects


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


async def filter_variants(
    db: AsyncSession,
    vcf_id: int,
    min_quality: float | None = None,
    max_quality: float | None = None,
    min_af: float | None = None,
    max_af: float | None = None,
    chrom: str | None = None,
    gene: str | None = None,
    significance: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Variant]:
    query = (
        select(Variant)
        .options(selectinload(Variant.annotation))
        .join(Annotation, isouter=True)
        .where(Variant.vcf_file_id == vcf_id)
    )

    if min_quality is not None:
        query = query.where(Variant.qual >= min_quality)

    if max_quality is not None:
        query = query.where(Variant.qual <= max_quality)

    if min_af is not None:
        query = query.where(Variant.af >= min_af)

    if max_af is not None:
        query = query.where(Variant.af <= max_af)

    if chrom is not None:
        query = query.where(Variant.chrom == chrom)

    if gene is not None:
        query = query.where(Annotation.gene == gene)

    if significance is not None:
        query = query.where(Annotation.clinical_significance == significance)

    query = query.order_by(Variant.id)
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)

    return list(result.scalars().all())


async def scientific_summary(
    db: AsyncSession,
    vcf_id: int,
) -> dict:
    query = (
        select(Variant)
        .options(selectinload(Variant.annotation))
        .where(Variant.vcf_file_id == vcf_id)
        .order_by(Variant.id)
    )

    result = await db.execute(query)
    variants = list(result.scalars().all())

    total_variants = len(variants)

    quality_values = [variant.qual for variant in variants if variant.qual is not None]

    quality_stats = {
        "mean": mean(quality_values) if quality_values else None,
        "median": median(quality_values) if quality_values else None,
        "min": min(quality_values) if quality_values else None,
        "max": max(quality_values) if quality_values else None,
    }

    af_distribution = {
        "0-0.01": 0,
        "0.01-0.05": 0,
        "0.05-0.1": 0,
        "0.1-0.5": 0,
        "0.5-1.0": 0,
    }

    for variant in variants:
        if variant.af is None:
            continue

        if variant.af < 0.01:
            af_distribution["0-0.01"] += 1
        elif variant.af < 0.05:
            af_distribution["0.01-0.05"] += 1
        elif variant.af < 0.1:
            af_distribution["0.05-0.1"] += 1
        elif variant.af < 0.5:
            af_distribution["0.1-0.5"] += 1
        else:
            af_distribution["0.5-1.0"] += 1

    gene_counts = Counter(
        variant.annotation.gene
        for variant in variants
        if variant.annotation and variant.annotation.gene
    )

    top_genes = [
        {"gene": gene, "count": count} for gene, count in gene_counts.most_common(10)
    ]

    significance_counts = Counter(
        variant.annotation.clinical_significance
        for variant in variants
        if variant.annotation and variant.annotation.clinical_significance
    )

    return {
        "total_variants": total_variants,
        "quality_stats": quality_stats,
        "af_distribution": af_distribution,
        "top_genes": top_genes,
        "clinical_significance": dict(significance_counts),
    }


async def get_high_risk_variants(
    db: AsyncSession,
    vcf_id: int,
    min_qual: float = 100,
    min_af: float = 0.1,
) -> list[Variant]:
    query = (
        select(Variant)
        .options(selectinload(Variant.annotation))
        .join(Annotation, isouter=True)
        .where(
            Variant.vcf_file_id == vcf_id,
            Variant.qual >= min_qual,
            Variant.af >= min_af,
            Annotation.clinical_significance.in_(["Pathogenic", "Likely_pathogenic"]),
        )
        .order_by(Variant.id)
    )

    result = await db.execute(query)
    return list(result.scalars().all())
