from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models.annotation import Annotation
from app.models.annotation_file import AnnotationFile
from app.models.project import Project
from app.models.variant import Variant
from app.models.vcf_file import VCFFile
from app.services.annotation_service import (
    annotate_vcf,
    filter_variants,
    get_high_risk_variants,
    match_variants_to_annotations,
    parse_annotation_file,
    scientific_summary,
    validate_annotation_file,
)

TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/scientific_informatics"
)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


VALID_HEADER = (
    "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
    "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele"
)

VALID_ROW = (
    "123456\tSNV\tTP53\t7157\tTP53\tPathogenic\t12345\t2\t121746135\t121746135\tC\tT"
)


def create_annotation_file(
    tmp_path: Path,
    content: str,
) -> Path:
    file_path = tmp_path / "test_annotation.tsv"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_validate_valid_annotation_file(tmp_path):
    file_path = create_annotation_file(
        tmp_path,
        f"{VALID_HEADER}\n{VALID_ROW}\n",
    )

    validate_annotation_file(file_path)


def test_validate_invalid_header(tmp_path):
    content = f"#VariantID\tType\tName\tGeneID\tGeneSymbol\tWrongColumn\n{VALID_ROW}\n"

    file_path = create_annotation_file(tmp_path, content)

    with pytest.raises(ValueError, match="Invalid ClinVar annotation format"):
        validate_annotation_file(file_path)


def test_validate_no_valid_entries(tmp_path):
    file_path = create_annotation_file(
        tmp_path,
        f"{VALID_HEADER}\n",
    )

    with pytest.raises(
        ValueError,
        match="No valid annotation entries found",
    ):
        validate_annotation_file(file_path)


def test_validate_invalid_row_length(tmp_path):
    invalid_row = "123456\tSNV\tTP53"

    file_path = create_annotation_file(
        tmp_path,
        f"{VALID_HEADER}\n{invalid_row}\n",
    )

    with pytest.raises(
        ValueError,
        match="No valid annotation entries found",
    ):
        validate_annotation_file(file_path)


def test_parse_annotation_file(tmp_path):
    annotation_file = tmp_path / "clinvar.tsv"

    annotation_file.write_text(
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsnv\tTP53_variant\t7157\tTP53\tPathogenic\t"
        "rs123\t2\t121746135\t121746135\tC\tT\n"
        "2\tsnv\tEGFR_variant\t1956\tEGFR\tBenign\t"
        "rs456\t22\t6025\t6025\tG\tT\n",
        encoding="utf-8",
    )

    result = parse_annotation_file(annotation_file)

    assert result == [
        {
            "chrom": "2",
            "pos": 121746135,
            "ref": "C",
            "alt": "T",
            "gene": "TP53",
            "clinical_significance": "Pathogenic",
        },
        {
            "chrom": "22",
            "pos": 6025,
            "ref": "G",
            "alt": "T",
            "gene": "EGFR",
            "clinical_significance": "Benign",
        },
    ]


def test_match_variants_to_annotations():
    variants = [
        {
            "chrom": "2",
            "pos": 121746135,
            "ref": "C",
            "alt": "T",
        },
        {
            "chrom": "22",
            "pos": 6025,
            "ref": "G",
            "alt": "T",
        },
    ]

    annotations = [
        {
            "chrom": "2",
            "pos": 121746135,
            "ref": "C",
            "alt": "T",
            "gene": "TP53",
            "clinical_significance": "Pathogenic",
        },
        {
            "chrom": "22",
            "pos": 6025,
            "ref": "G",
            "alt": "T",
            "gene": "EGFR",
            "clinical_significance": "Benign",
        },
    ]

    result = match_variants_to_annotations(
        variants,
        annotations,
    )

    assert len(result) == 2

    assert result[0]["gene"] == "TP53"
    assert result[0]["clinical_significance"] == "Pathogenic"

    assert result[1]["gene"] == "EGFR"
    assert result[1]["clinical_significance"] == "Benign"


@pytest.mark.asyncio
async def test_annotate_vcf(db_session, tmp_path):
    project = Project(
        name="Test project",
        description="Annotation test",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    vcf_file = VCFFile(
        project_id=project.id,
        filename="test.vcf",
    )
    db_session.add(vcf_file)
    await db_session.commit()
    await db_session.refresh(vcf_file)

    variant = Variant(
        vcf_file_id=vcf_file.id,
        chrom="2",
        pos=121746135,
        ref="C",
        alt="T",
        qual=100.0,
        filter="PASS",
        af=0.5,
    )
    db_session.add(variant)
    await db_session.commit()

    annotation_file = AnnotationFile(
        project_id=project.id,
        filename="clinvar.tsv",
    )
    db_session.add(annotation_file)
    await db_session.commit()

    annotation_path = Path("uploads") / "clinvar.tsv"
    annotation_path.parent.mkdir(exist_ok=True)

    annotation_path.write_text(
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsnv\tTP53_variant\t7157\tTP53\tPathogenic\t"
        "rs123\t2\t121746135\t121746135\tC\tT\n",
        encoding="utf-8",
    )

    result = await annotate_vcf(
        db=db_session,
        vcf_id=vcf_file.id,
    )

    assert len(result) == 1
    assert result[0].variant_id == variant.id
    assert result[0].gene == "TP53"
    assert result[0].clinical_significance == "Pathogenic"


@pytest.mark.asyncio
async def test_filter_variants(db_session):
    project = Project(
        name="Filter test project",
        description="Variant filtering test",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    vcf_file = VCFFile(
        project_id=project.id,
        filename="filter_test.vcf",
    )
    db_session.add(vcf_file)
    await db_session.commit()
    await db_session.refresh(vcf_file)

    variants = [
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="2",
            pos=121746135,
            ref="C",
            alt="T",
            qual=100.0,
            filter="PASS",
            af=0.5,
        ),
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="22",
            pos=6025,
            ref="G",
            alt="T",
            qual=80.0,
            filter="PASS",
            af=0.05,
        ),
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="22",
            pos=5090,
            ref="G",
            alt="GCCT",
            qual=200.0,
            filter="PASS",
            af=0.2,
        ),
    ]

    db_session.add_all(variants)
    await db_session.commit()

    db_session.add_all(
        [
            Annotation(
                variant_id=variants[0].id,
                gene="TP53",
                clinical_significance="Pathogenic",
            ),
            Annotation(
                variant_id=variants[1].id,
                gene="EGFR",
                clinical_significance="Benign",
            ),
            Annotation(
                variant_id=variants[2].id,
                gene="BRCA1",
                clinical_significance="Likely_pathogenic",
            ),
        ]
    )
    await db_session.commit()

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        min_quality=100,
    )

    assert len(result) == 2
    assert result[0].id == variants[0].id
    assert result[1].id == variants[2].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        min_af=0.1,
    )

    assert len(result) == 2
    assert result[0].id == variants[0].id
    assert result[1].id == variants[2].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        min_quality=100,
        min_af=0.3,
    )

    assert len(result) == 1
    assert result[0].id == variants[0].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        chrom="22",
    )

    assert len(result) == 2
    assert result[0].id == variants[1].id
    assert result[1].id == variants[2].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        gene="BRCA1",
    )

    assert len(result) == 1
    assert result[0].id == variants[2].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        significance="Pathogenic",
    )

    assert len(result) == 1
    assert result[0].id == variants[0].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        max_quality=100,
    )

    assert len(result) == 2
    assert result[0].id == variants[0].id
    assert result[1].id == variants[1].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        max_af=0.2,
    )

    assert len(result) == 2
    assert result[0].id == variants[1].id
    assert result[1].id == variants[2].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        max_quality=100,
    )

    assert len(result) == 2
    assert result[0].id == variants[0].id
    assert result[1].id == variants[1].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        max_af=0.2,
    )

    assert len(result) == 2
    assert result[0].id == variants[1].id
    assert result[1].id == variants[2].id

    result = await filter_variants(
        db=db_session,
        vcf_id=vcf_file.id,
        limit=1,
        offset=1,
    )

    assert len(result) == 1
    assert result[0].id == variants[1].id


@pytest.mark.asyncio
async def test_scientific_summary(db_session):
    project = Project(
        name="Summary test project",
        description="Test project for scientific summary",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    vcf_file = VCFFile(
        project_id=project.id,
        filename="summary_test.vcf",
    )
    db_session.add(vcf_file)
    await db_session.commit()
    await db_session.refresh(vcf_file)

    variants = [
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="2",
            pos=121746135,
            ref="C",
            alt="T",
            qual=100,
            filter="PASS",
            af=0.5,
        ),
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="22",
            pos=6025,
            ref="G",
            alt="T",
            qual=80,
            filter="PASS",
            af=0.05,
        ),
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="22",
            pos=5090,
            ref="G",
            alt="GCCT",
            qual=200,
            filter="PASS",
            af=0.2,
        ),
    ]

    db_session.add_all(variants)
    await db_session.commit()

    for variant in variants:
        await db_session.refresh(variant)

    db_session.add_all(
        [
            Annotation(
                variant_id=variants[0].id,
                gene="TP53",
                clinical_significance="Pathogenic",
            ),
            Annotation(
                variant_id=variants[1].id,
                gene="EGFR",
                clinical_significance="Benign",
            ),
            Annotation(
                variant_id=variants[2].id,
                gene="BRCA1",
                clinical_significance="Likely_pathogenic",
            ),
        ]
    )
    await db_session.commit()

    result = await scientific_summary(
        db=db_session,
        vcf_id=vcf_file.id,
    )

    assert result["total_variants"] == 3

    assert result["quality_stats"]["mean"] == pytest.approx(126.67, rel=1e-2)
    assert result["quality_stats"]["median"] == 100
    assert result["quality_stats"]["min"] == 80
    assert result["quality_stats"]["max"] == 200

    assert result["af_distribution"]["0.05-0.1"] == 1
    assert result["af_distribution"]["0.1-0.5"] == 1
    assert result["af_distribution"]["0.5-1.0"] == 1

    assert result["top_genes"] == [
        {"gene": "TP53", "count": 1},
        {"gene": "EGFR", "count": 1},
        {"gene": "BRCA1", "count": 1},
    ]

    assert result["clinical_significance"] == {
        "Pathogenic": 1,
        "Benign": 1,
        "Likely_pathogenic": 1,
    }


@pytest.mark.asyncio
async def test_get_high_risk_variants(db_session):
    project = Project(
        name="High-risk test project",
        description="Test project for high-risk variants",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    vcf_file = VCFFile(
        project_id=project.id,
        filename="high_risk_test.vcf",
    )
    db_session.add(vcf_file)
    await db_session.commit()
    await db_session.refresh(vcf_file)

    variants = [
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="2",
            pos=121746135,
            ref="C",
            alt="T",
            qual=100,
            filter="PASS",
            af=0.5,
        ),
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="22",
            pos=6025,
            ref="G",
            alt="T",
            qual=80,
            filter="PASS",
            af=0.05,
        ),
        Variant(
            vcf_file_id=vcf_file.id,
            chrom="22",
            pos=5090,
            ref="G",
            alt="GCCT",
            qual=200,
            filter="PASS",
            af=0.2,
        ),
    ]

    db_session.add_all(variants)
    await db_session.commit()

    for variant in variants:
        await db_session.refresh(variant)

    db_session.add_all(
        [
            Annotation(
                variant_id=variants[0].id,
                gene="TP53",
                clinical_significance="Pathogenic",
            ),
            Annotation(
                variant_id=variants[1].id,
                gene="EGFR",
                clinical_significance="Benign",
            ),
            Annotation(
                variant_id=variants[2].id,
                gene="BRCA1",
                clinical_significance="Likely_pathogenic",
            ),
        ]
    )
    await db_session.commit()

    result = await get_high_risk_variants(
        db=db_session,
        vcf_id=vcf_file.id,
    )

    assert len(result) == 2
    assert result[0].id == variants[0].id
    assert result[1].id == variants[2].id

    assert result[0].annotation.gene == "TP53"
    assert result[0].annotation.clinical_significance == "Pathogenic"

    assert result[1].annotation.gene == "BRCA1"
    assert result[1].annotation.clinical_significance == "Likely_pathogenic"
