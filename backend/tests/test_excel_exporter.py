"""Tests for Excel exporter"""
import pytest
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from app.domain.models import InstagramPost, PostType, AuditResult, PostAuditStatus
from app.exporters.excel_exporter import ExcelExporter


@pytest.fixture
def sample_audit_result():
    """Create a sample audit result"""
    posts = [
        InstagramPost(
            shortcode="POST001",
            username="master",
            caption="Found everywhere 🎉",
            post_type=PostType.PHOTO,
            published_at=datetime(2026, 9, 1),
            permalink="https://www.instagram.com/p/POST001/",
            is_video=False,
        ),
        InstagramPost(
            shortcode="POST002",
            username="master",
            caption="Missing in one account",
            post_type=PostType.VIDEO,
            published_at=datetime(2026, 9, 2),
            permalink="https://www.instagram.com/p/POST002/",
            is_video=True,
        ),
        InstagramPost(
            shortcode="POST003",
            username="master",
            caption="Missing in multiple 🚀",
            post_type=PostType.CAROUSEL,
            published_at=datetime(2026, 9, 3),
            permalink="https://www.instagram.com/p/POST003/",
            is_video=False,
        ),
    ]

    posts_status = [
        PostAuditStatus(
            master_post=posts[0],
            account_status={"account_a": "found", "account_b": "found"},
            missing_in=[],
            review_in=[],
        ),
        PostAuditStatus(
            master_post=posts[1],
            account_status={"account_a": "found", "account_b": "review"},
            missing_in=[],
            review_in=["account_b"],
        ),
        PostAuditStatus(
            master_post=posts[2],
            account_status={"account_a": "missing", "account_b": "missing"},
            missing_in=["account_a", "account_b"],
            review_in=[],
        ),
    ]

    return AuditResult(
        master_account="master",
        compared_accounts=["account_a", "account_b"],
        posts_status=posts_status,
        total_master_posts=3,
        found_in_all=1,
        with_missing=1,
        with_review=1,
        missing_count_by_account={"account_a": 1, "account_b": 0},
        review_count_by_account={"account_a": 0, "account_b": 1},
        timestamp=datetime.now(),
    )


def test_excel_export_creates_file(sample_audit_result, tmp_path):
    """Test that export creates an Excel file"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    assert result_path.exists()
    assert result_path.suffix == ".xlsx"


def test_excel_has_all_sheets(sample_audit_result, tmp_path):
    """Test that Excel has all required sheets"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    assert "1_ESCANEO" in wb.sheetnames
    assert "2_FALTANTES" in wb.sheetnames
    assert "3_REVISAR" in wb.sheetnames


def test_escaneo_sheet_has_correct_rows(sample_audit_result, tmp_path):
    """Test that ESCANEO sheet has all posts"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["1_ESCANEO"]

    # Header + 3 posts
    assert ws.max_row == 4


def test_faltantes_sheet_has_only_missing(sample_audit_result, tmp_path):
    """Test that FALTANTES sheet has only posts with missing accounts"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["2_FALTANTES"]

    # Header + 1 post (POST003 has missing accounts)
    assert ws.max_row == 2


def test_revisar_sheet_has_only_review(sample_audit_result, tmp_path):
    """Test that REVISAR sheet has only posts with review accounts"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["3_REVISAR"]

    # Header + 1 post (POST002 has review accounts)
    assert ws.max_row == 2


def test_excel_preserves_unicode(sample_audit_result, tmp_path):
    """Test that Excel preserves Unicode and emojis"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["1_ESCANEO"]

    # Check if emoji is preserved in captions
    found_emoji = False
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[2] and "🎉" in str(row[2]):
            found_emoji = True
            break

    assert found_emoji


def test_excel_has_hyperlinks(sample_audit_result, tmp_path):
    """Test that Excel has hyperlinks for URLs"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["1_ESCANEO"]

    # Check column B (LINK COLOMBIA) for hyperlinks
    found_hyperlink = False
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=2):
        for cell in row:
            if cell.hyperlink:
                found_hyperlink = True
                break

    assert found_hyperlink


def test_excel_headers_are_bold(sample_audit_result, tmp_path):
    """Test that headers are formatted bold"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["1_ESCANEO"]

    header_row = ws[1]
    for cell in header_row:
        if cell.value:
            assert cell.font.bold is True


def test_missing_accounts_in_faltantes_column(sample_audit_result, tmp_path):
    """Test that FALTA EN and REVISAR EN columns show correct accounts"""
    exporter = ExcelExporter()
    result_path = exporter.export(sample_audit_result, str(tmp_path))

    wb = load_workbook(result_path)
    ws = wb["1_ESCANEO"]

    # Find FALTA EN column (second to last column, before REVISAR EN)
    falta_col = ws.max_column - 1
    revisar_col = ws.max_column

    # Check POST002 row (should have "account_b" in REVISAR EN, nothing in FALTA EN)
    falta_en_post2 = ws.cell(row=3, column=falta_col).value
    revisar_en_post2 = ws.cell(row=3, column=revisar_col).value
    assert (falta_en_post2 is None or falta_en_post2 == "")
    assert revisar_en_post2 is not None and "account_b" in revisar_en_post2

    # Check POST003 row (should have both accounts in FALTA EN)
    falta_en_post3 = ws.cell(row=4, column=falta_col).value
    assert falta_en_post3 is not None and "account_a" in falta_en_post3
    assert "account_b" in falta_en_post3
