from pydantic import BaseModel


class VariantResponse(BaseModel):
    id: int
    vcf_file_id: int
    chrom: str
    pos: int
    ref: str
    alt: str
    qual: float | None
    filter: str | None
    af: float | None
    gene: str | None
    clinical_significance: str | None
