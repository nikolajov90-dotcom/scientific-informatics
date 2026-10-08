from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.annotation import AnnotationResponse
from app.schemas.summary import ScientificSummaryResponse
from app.schemas.variant import VariantResponse
from app.services.annotation_service import (
    annotate_vcf,
    create_af_significance_heatmap,
    filter_variants,
    get_high_risk_variants,
    scientific_summary,
)

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
)


@router.post(
    "/{vcf_id}/annotate",
    response_model=list[AnnotationResponse],
)
async def annotate_vcf_endpoint(
    vcf_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await annotate_vcf(
        db=db,
        vcf_id=vcf_id,
    )


@router.get(
    "/{vcf_id}/variants",
    response_model=list[VariantResponse],
)
async def get_variants(
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
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    variants = await filter_variants(
        db=db,
        vcf_id=vcf_id,
        min_quality=min_quality,
        max_quality=max_quality,
        min_af=min_af,
        max_af=max_af,
        chrom=chrom,
        gene=gene,
        significance=significance,
        limit=limit,
        offset=offset,
    )

    return [
        VariantResponse(
            id=variant.id,
            vcf_file_id=variant.vcf_file_id,
            chrom=variant.chrom,
            pos=variant.pos,
            ref=variant.ref,
            alt=variant.alt,
            qual=variant.qual,
            filter=variant.filter,
            af=variant.af,
            gene=variant.annotation.gene if variant.annotation else None,
            clinical_significance=(
                variant.annotation.clinical_significance if variant.annotation else None
            ),
        )
        for variant in variants
    ]


@router.get(
    "/{vcf_id}/summary",
    response_model=ScientificSummaryResponse,
)
async def get_scientific_summary(
    vcf_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await scientific_summary(
        db=db,
        vcf_id=vcf_id,
    )


@router.get(
    "/{vcf_id}/high-risk-variants",
    response_model=list[VariantResponse],
)
async def get_high_risk_variants_endpoint(
    vcf_id: int,
    min_qual: float = 100,
    min_af: float = 0.1,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    variants = await get_high_risk_variants(
        db=db,
        vcf_id=vcf_id,
        min_qual=min_qual,
        min_af=min_af,
    )

    return [
        VariantResponse(
            id=variant.id,
            vcf_file_id=variant.vcf_file_id,
            chrom=variant.chrom,
            pos=variant.pos,
            ref=variant.ref,
            alt=variant.alt,
            qual=variant.qual,
            filter=variant.filter,
            af=variant.af,
            gene=variant.annotation.gene if variant.annotation else None,
            clinical_significance=(
                variant.annotation.clinical_significance if variant.annotation else None
            ),
        )
        for variant in variants
    ]


@router.get(
    "/{vcf_id}/af-significance-heatmap",
)
async def get_af_significance_heatmap(
    vcf_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    heatmap = await create_af_significance_heatmap(
        db=db,
        vcf_id=vcf_id,
    )

    return StreamingResponse(
        heatmap,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f"attachment; filename=vcf_{vcf_id}_af_significance_heatmap.png"
            )
        },
    )
