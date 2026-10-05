from pydantic import BaseModel


class QualityStats(BaseModel):
    mean: float | None
    median: float | None
    min: float | None
    max: float | None


class GeneCount(BaseModel):
    gene: str
    count: int


class ScientificSummaryResponse(BaseModel):
    total_variants: int
    quality_stats: QualityStats
    af_distribution: dict[str, int]
    top_genes: list[GeneCount]
    clinical_significance: dict[str, int]
