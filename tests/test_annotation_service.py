from pathlib import Path

import pytest

from app.services.annotation_service import validate_annotation_file

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
