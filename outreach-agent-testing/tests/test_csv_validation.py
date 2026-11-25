import pytest
from app.csv_validation import CSVValidationError, validate_csv

HEADER = "name,email,company,industry\n"


def write(tmp_path, text, name="p.csv"):
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return f


def test_valid_csv(tmp_path):
    rows = validate_csv(write(tmp_path, HEADER + "A B,a@x.com,X,Tech\n"))
    assert rows[0]["company"] == "X"


def test_missing_file(tmp_path):
    with pytest.raises(CSVValidationError):
        validate_csv(tmp_path / "nope.csv")


def test_wrong_extension(tmp_path):
    with pytest.raises(CSVValidationError):
        validate_csv(write(tmp_path, "x", "p.txt"))


def test_missing_column(tmp_path):
    with pytest.raises(CSVValidationError, match="Missing columns"):
        validate_csv(write(tmp_path, "name,email\nA,a@x.com\n"))


def test_empty_file(tmp_path):
    with pytest.raises(CSVValidationError):
        validate_csv(write(tmp_path, ""))


def test_header_only(tmp_path):
    with pytest.raises(CSVValidationError, match="no data rows"):
        validate_csv(write(tmp_path, HEADER))


def test_blank_field(tmp_path):
    with pytest.raises(CSVValidationError, match="empty"):
        validate_csv(write(tmp_path, HEADER + "A,a@x.com,,Tech\n"))


def test_bad_email(tmp_path):
    with pytest.raises(CSVValidationError, match="invalid email"):
        validate_csv(write(tmp_path, HEADER + "A,not-an-email,X,Tech\n"))


def test_duplicate_email(tmp_path):
    text = HEADER + "A,a@x.com,X,Tech\nB,A@x.com,Y,Tech\n"
    with pytest.raises(CSVValidationError, match="duplicate"):
        validate_csv(write(tmp_path, text))


def test_binary_file(tmp_path):
    f = tmp_path / "bin.csv"
    f.write_bytes(b"\xff\xfe\x00\x81\x82")
    with pytest.raises(CSVValidationError):
        validate_csv(f)