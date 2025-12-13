"""Excel报告生成器"""

import os
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from src.reporters.base_reporter import BaseReporter


class ExcelReporter(BaseReporter):
    """Excel报告生成器"""

    def __init__(self, output_dir: str = "output/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 样式定义
        self._header_font = Font(bold=True, color="FFFFFF")
        self._header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        self._pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        self._fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        self._border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

    def generate(self, data: list[dict[str, Any]], filename: str = None, **kwargs) -> str:
        """生成Excel报告"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"spurious_report_{timestamp}.xlsx"

        wb = Workbook()
        ws = wb.active
        ws.title = "Spurious Results"

        if not data:
            filepath = os.path.join(self.output_dir, filename)
            wb.save(filepath)
            return filepath

        # 写入表头
        headers = list(data[0].keys())
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = self._header_font
            cell.fill = self._header_fill
            cell.alignment = Alignment(horizontal="center")
            cell.border = self._border

        # 写入数据
        for row_idx, row_data in enumerate(data, 2):
            for col_idx, header in enumerate(headers, 1):
                value = row_data.get(header)
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = self._border
                cell.alignment = Alignment(horizontal="center")

                # Pass/Fail 颜色
                if header == "pass_fail":
                    if value is True:
                        cell.fill = self._pass_fill
                        cell.value = "PASS"
                    elif value is False:
                        cell.fill = self._fail_fill
                        cell.value = "FAIL"

        # 自动调整列宽
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 18

        # 保存
        filepath = os.path.join(self.output_dir, filename)
        wb.save(filepath)
        print(f"Excel report saved: {filepath}")
        return filepath