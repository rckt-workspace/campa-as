"""Excel exporter for Instagram content audit results"""
from pathlib import Path
from datetime import datetime
from html import unescape
import re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from app.domain.models import AuditResult, PostType


def clean_caption_for_export(caption: str) -> str:
    """Clean caption for Excel export: unescape, remove metadata, preserve emojis"""
    if not caption:
        return ""

    caption = unescape(caption)

    pattern = r"^\d+\s+likes?,\s+\d+\s+comments?\s*-\s*\w+\s+(?:on|el)\s+\w+\s+\d+,\s+\d+:\s*"
    caption = re.sub(pattern, "", caption, flags=re.IGNORECASE)

    caption = caption.strip()

    return caption


def get_post_type_label(post_type: PostType) -> str:
    """Convert post type enum to human readable label"""
    mapping = {
        PostType.PHOTO: "Post",
        PostType.VIDEO: "Video",
        PostType.REEL: "Reel",
        PostType.CAROUSEL: "Carrusel",
        PostType.STORY: "Historia",
    }
    return mapping.get(post_type, post_type.value)


class ExcelExporter:
    """Export audit results to Excel format with professional styling"""

    def __init__(self, filename: str = "NewBody_Auditoria_Contenido.xlsx"):
        self.filename = filename
        self.account_labels = {}

    def export(
        self,
        audit_result: AuditResult,
        output_dir: str = "data/exports",
        account_labels: dict = None,
    ) -> Path:
        """Export audit result to Excel file"""
        self.account_labels = account_labels or {}

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"NewBody_Auditoria_Contenido_{timestamp}.xlsx"
        file_path = output_path / filename

        workbook = Workbook()
        workbook.remove(workbook.active)

        self._create_escaneo_sheet(workbook, audit_result)
        self._create_parrilla_sheet(workbook, audit_result)
        self._create_revisar_sheet(workbook, audit_result)

        workbook.save(file_path)
        return file_path

    def _get_account_label(self, account: str) -> str:
        """Get human-readable label for account, fallback to username"""
        return self.account_labels.get(account, account)

    def _create_escaneo_sheet(self, workbook: Workbook, audit_result: AuditResult) -> None:
        """Create ESCANEO sheet with all posts and account status grid"""
        ws = workbook.create_sheet("1_ESCANEO", 0)

        headers = ["FECHA", "PUBLICACIÓN", "CAPTION", "TIPO"]

        for account in audit_result.compared_accounts:
            label = self._get_account_label(account)
            headers.append(label)

        headers.extend(["FALTA EN", "REVISAR EN"])

        ws.append(headers)

        self._format_header(ws)
        self._set_column_widths_escaneo(ws, len(audit_result.compared_accounts))

        for post_status in audit_result.posts_status:
            master = post_status.master_post
            row = [
                master.published_at.strftime("%d/%m/%Y"),
                "Ver publicación",
                clean_caption_for_export(master.caption),
                get_post_type_label(master.post_type),
            ]

            for account in audit_result.compared_accounts:
                match_detail = post_status.account_matches.get(account)
                if match_detail and match_detail.status.value == "found":
                    row.append("✓ MATCH CONFIRMADO")
                elif match_detail and match_detail.status.value == "review":
                    row.append("⚠ REVISAR CANDIDATO")
                else:
                    row.append("✕ NO ENCONTRADO")

            missing_labels = [self._get_account_label(acc) for acc in post_status.missing_in]
            row.append(" · ".join(missing_labels) if missing_labels else "")

            review_labels = [self._get_account_label(acc) for acc in post_status.review_in]
            row.append(" · ".join(review_labels) if review_labels else "")

            ws.append(row)
            excel_row = ws.max_row

            ws.cell(excel_row, 2).hyperlink = master.permalink
            ws.cell(excel_row, 2).font = Font(color="0563C1", underline="single")

            for col_idx, account in enumerate(audit_result.compared_accounts, 5):
                match_detail = post_status.account_matches.get(account)
                if match_detail and match_detail.candidate_permalink:
                    ws.cell(excel_row, col_idx).hyperlink = match_detail.candidate_permalink
                    ws.cell(excel_row, col_idx).font = Font(color="0563C1", underline="single")

        self._format_data_rows_escaneo(ws, audit_result.compared_accounts)

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
        ws.sheet_view.showGridLines = False

    def _create_parrilla_sheet(self, workbook: Workbook, audit_result: AuditResult) -> None:
        """Create PARRILLA sheet with one row per post and columns per account"""
        ws = workbook.create_sheet("2_PARRILLA", 1)

        headers = ["FECHA"]
        for account in audit_result.compared_accounts:
            headers.append(self._get_account_label(account))

        ws.append(headers)
        self._format_header(ws)

        for post_status in audit_result.posts_status:
            master = post_status.master_post
            row = [master.published_at.strftime("%d/%m/%Y")]

            for account in audit_result.compared_accounts:
                match_detail = post_status.account_matches.get(account)

                if match_detail and match_detail.status.value == "found":
                    row.append("YA ESTÁ")
                elif match_detail and match_detail.status.value == "review":
                    row.append("REVISAR CANDIDATO")
                else:
                    row.append("PUBLICAR")

            ws.append(row)
            excel_row = ws.max_row

            for col_idx, account in enumerate(audit_result.compared_accounts, 2):
                match_detail = post_status.account_matches.get(account)
                cell = ws.cell(excel_row, col_idx)

                if cell.value == "PUBLICAR":
                    cell.hyperlink = master.permalink
                    cell.fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
                    cell.font = Font(color="C62828", bold=True)
                elif cell.value == "YA ESTÁ" and match_detail and match_detail.candidate_permalink:
                    cell.hyperlink = match_detail.candidate_permalink
                    cell.fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
                    cell.font = Font(color="2E7D32", bold=True)
                elif cell.value == "REVISAR CANDIDATO" and match_detail and match_detail.candidate_permalink:
                    cell.hyperlink = match_detail.candidate_permalink
                    cell.fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
                    cell.font = Font(color="E65100", bold=True)

                cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.column_dimensions["A"].width = 14
        for i, account in enumerate(audit_result.compared_accounts, 2):
            ws.column_dimensions[get_column_letter(i)].width = 25

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
        ws.sheet_view.showGridLines = False

    def _create_revisar_sheet(self, workbook: Workbook, audit_result: AuditResult) -> None:
        """Create REVISAR sheet with details on posts requiring review"""
        ws = workbook.create_sheet("3_REVISAR", 2)

        headers = [
            "FECHA", "PUBLICACIÓN COLOMBIA", "CAPTION", "TIPO", "CUENTA",
            "RESULTADO", "CANDIDATO", "SIMILITUD TOTAL", "SIMILITUD VISUAL",
            "SIMILITUD CAPTION", "TIPO COINCIDE", "ACCIÓN"
        ]
        ws.append(headers)
        self._format_header(ws)

        for post_status in audit_result.posts_status:
            master = post_status.master_post

            for account in post_status.review_in:
                match_detail = post_status.account_matches.get(account)
                if not match_detail:
                    continue

                row = [
                    master.published_at.strftime("%d/%m/%Y"),
                    "Ver original",
                    clean_caption_for_export(master.caption),
                    get_post_type_label(master.post_type),
                    self._get_account_label(account),
                    "REVISAR CANDIDATO",
                    "Ver candidato",
                    f"{int(match_detail.score * 100)}%",
                    f"{int((match_detail.visual_similarity or 0) * 100)}%" if match_detail.visual_similarity else "N/A",
                    f"{int(match_detail.caption_similarity * 100)}%",
                    "Sí" if match_detail.type_match else "No",
                    "Validar si corresponde al mismo contenido",
                ]
                ws.append(row)
                excel_row = ws.max_row

                ws.cell(excel_row, 2).hyperlink = master.permalink
                ws.cell(excel_row, 2).font = Font(color="0563C1", underline="single")

                if match_detail.candidate_permalink:
                    ws.cell(excel_row, 7).hyperlink = match_detail.candidate_permalink
                ws.cell(excel_row, 7).font = Font(color="0563C1", underline="single")

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 35
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 18
        ws.column_dimensions["G"].width = 18
        ws.column_dimensions["H"].width = 15
        ws.column_dimensions["I"].width = 15
        ws.column_dimensions["J"].width = 15
        ws.column_dimensions["K"].width = 12
        ws.column_dimensions["L"].width = 30

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            ws.row_dimensions[row[0].row].height = 50
            row[2].alignment = Alignment(wrap_text=True, vertical="top")

        yellow_fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
        yellow_font = Font(color="E65100", bold=True)

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=6, max_col=6):
            for cell in row:
                cell.fill = yellow_fill
                cell.font = yellow_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
        ws.sheet_view.showGridLines = False

    def _format_header(self, ws) -> None:
        """Format header row with professional styling"""
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )
            cell.border = Border(
                bottom=Side(style="thin", color="E4E7EC"),
            )

    def _set_column_widths_escaneo(self, ws, num_accounts: int) -> None:
        """Set column widths for ESCANEO sheet"""
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 58
        ws.column_dimensions["D"].width = 12

        for i in range(num_accounts):
            col_letter = get_column_letter(5 + i)
            ws.column_dimensions[col_letter].width = 18

        ws.column_dimensions[get_column_letter(5 + num_accounts)].width = 25
        ws.column_dimensions[get_column_letter(6 + num_accounts)].width = 25

    def _set_column_widths_parrilla(self, ws) -> None:
        """Set column widths for PARRILLA and REVISAR sheets"""
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 58
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 25
        ws.column_dimensions["F"].width = 12

    def _format_data_rows_escaneo(self, ws, accounts: list) -> None:
        """Format data rows in ESCANEO sheet with colors and wrapping"""
        green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
        green_font = Font(color="2E7D32", bold=True)

        yellow_fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
        yellow_font = Font(color="E65100", bold=True)

        red_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
        red_font = Font(color="C62828", bold=True)

        status_col_start = 5

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), 1):
            ws.row_dimensions[row_idx + 1].height = 65

            row[2].alignment = Alignment(wrap_text=True, vertical="top")

            for col_idx, cell in enumerate(row):
                if col_idx >= status_col_start - 1 and col_idx < status_col_start - 1 + len(accounts):
                    if cell.value == "ESTÁ":
                        cell.fill = green_fill
                        cell.font = green_font
                    elif cell.value == "REVISAR":
                        cell.fill = yellow_fill
                        cell.font = yellow_font
                    elif cell.value == "FALTA":
                        cell.fill = red_fill
                        cell.font = red_font

                    cell.alignment = Alignment(horizontal="center", vertical="center")

    def _format_data_rows_parrilla(self, ws) -> None:
        """Format data rows in PARRILLA sheet"""
        red_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
        red_font = Font(color="C62828", bold=True)

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), 1):
            ws.row_dimensions[row_idx + 1].height = 65

            row[2].alignment = Alignment(wrap_text=True, vertical="top")

            if row[5].value == "FALTA":
                row[5].fill = red_fill
                row[5].font = red_font
                row[5].alignment = Alignment(horizontal="center", vertical="center")

    def _format_data_rows_revisar(self, ws) -> None:
        """Format data rows in REVISAR sheet"""
        yellow_fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
        yellow_font = Font(color="E65100", bold=True)

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), 1):
            ws.row_dimensions[row_idx + 1].height = 65

            row[2].alignment = Alignment(wrap_text=True, vertical="top")

            if row[5].value == "REVISAR":
                row[5].fill = yellow_fill
                row[5].font = yellow_font
                row[5].alignment = Alignment(horizontal="center", vertical="center")
