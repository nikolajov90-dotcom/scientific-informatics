from pydantic import BaseModel


class AnnotationResponse(BaseModel):
    id: int
    variant_id: int
    gene: str | None
    clinical_significance: str | None
