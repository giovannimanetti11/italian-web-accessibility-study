from pathlib import Path

import pytest

from scripts.prepare_tranco_frame import encode_frame, filter_tranco_it


def test_preserves_original_ranks_and_it_suffix(tmp_path: Path):
    source = tmp_path / "full.csv"
    source.write_text("1,alpha.com\n35, ALFA.IT \n71,beta.it\n88,gamma.org\n")
    assert filter_tranco_it(source) == [(35, "alfa.it"), (71, "beta.it")]
    assert encode_frame(filter_tranco_it(source)) == b"35,alfa.it\n71,beta.it\n"


def test_duplicate_it_domain_rejected(tmp_path: Path):
    source = tmp_path / "duplicates.csv"
    source.write_text("1,alpha.it\n2,ALPHA.IT\n")
    with pytest.raises(ValueError, match="Duplicate"):
        filter_tranco_it(source)
