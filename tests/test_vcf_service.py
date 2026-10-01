import gzip

import pytest

from app.services.vcf_service import parse_vcf, validate_vcf, validate_vcf_extension


def test_parse_vcf(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5
"""

    vcf_file = tmp_path / "test.vcf"

    with open(vcf_file, "w", encoding="utf-8") as file:
        file.write(vcf_content)

    variants = parse_vcf(vcf_file)

    assert variants == [
        {
            "chrom": "2",
            "pos": 121746135,
            "ref": "C",
            "alt": "T",
            "qual": 100.0,
            "filter": "PASS",
            "af": 0.5,
        }
    ]


def test_parse_vcf_edge_cases(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t100\t.\tA\tG\t.\t.\tDP=30
2\t200\t.\tC\tT\t50\tPASS\tAF=0.25
2\t300\t.\tG\tA\t99\tPASS\tAF=0.75
"""

    vcf_file = tmp_path / "edge_cases.vcf"

    with open(vcf_file, "w", encoding="utf-8") as file:
        file.write(vcf_content)

    variants = parse_vcf(vcf_file)

    assert variants[0]["qual"] is None
    assert variants[0]["filter"] is None
    assert variants[0]["af"] is None

    assert variants[1]["af"] == 0.25
    assert variants[2]["af"] == 0.75


def test_parse_vcf_uses_info_af(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
##INFO=<ID=AF,Number=A,Type=Float,Description="Allele Frequency">
##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele Frequency">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5\tGT:AF\t0/1:0.9
"""

    vcf_file = tmp_path / "info_af.vcf"

    with open(vcf_file, "w", encoding="utf-8") as file:
        file.write(vcf_content)

    variants = parse_vcf(vcf_file)

    assert variants[0]["af"] == 0.5


def test_validate_vcf(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5
"""

    vcf_file = tmp_path / "valid.vcf"

    with open(vcf_file, "w", encoding="utf-8") as file:
        file.write(vcf_content)

    validate_vcf(vcf_file)


def test_validate_invalid_vcf(tmp_path):
    invalid_content = """This is not a VCF file.
"""

    invalid_file = tmp_path / "invalid.vcf"

    with open(invalid_file, "w", encoding="utf-8") as file:
        file.write(invalid_content)

    try:
        validate_vcf(invalid_file)
    except ValueError as error:
        assert str(error) == "Invalid VCF file"
    else:
        raise AssertionError("Expected ValueError")


def test_validate_vcf_missing_column_header(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
"""

    vcf_file = tmp_path / "missing_header.vcf"

    with open(vcf_file, "w", encoding="utf-8") as file:
        file.write(vcf_content)

    try:
        validate_vcf(vcf_file)
    except ValueError as error:
        assert str(error) == "Invalid VCF file"
    else:
        raise AssertionError("Expected ValueError")


def test_parse_vcf_invalid_record(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC
"""

    vcf_file = tmp_path / "invalid_record.vcf"

    with open(vcf_file, "w", encoding="utf-8") as file:
        file.write(vcf_content)

    try:
        parse_vcf(vcf_file)
    except ValueError as error:
        assert str(error) == "Invalid VCF record"
    else:
        raise AssertionError("Expected ValueError")


def test_parse_vcf_gz(tmp_path):
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\t.\tA\tG\t50\tPASS\tAF=0.25
"""

    file_path = tmp_path / "test.vcf.gz"

    with gzip.open(file_path, "wt", encoding="utf-8") as file:
        file.write(vcf_content)

    variants = parse_vcf(file_path)

    assert len(variants) == 1
    assert variants[0]["chrom"] == "1"
    assert variants[0]["pos"] == 100
    assert variants[0]["ref"] == "A"
    assert variants[0]["alt"] == "G"
    assert variants[0]["af"] == 0.25


def test_validate_vcf_extension():
    validate_vcf_extension("test.vcf")
    validate_vcf_extension("test.vcf.gz")

    with pytest.raises(ValueError):
        validate_vcf_extension("test.txt")

    with pytest.raises(ValueError):
        validate_vcf_extension("test.vcf.zip")
