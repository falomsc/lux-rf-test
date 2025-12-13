"""
GNSS 测试报告生成模块
支持 JSON 和 Excel 格式
"""

import json
import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from src.reporters.base_reporter import BaseReporter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GNSSReporter(BaseReporter):
    """GNSS 测试报告生成器"""

    # 样式定义
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    CENTER_ALIGN = Alignment(horizontal="center", vertical="center")
    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    def __init__(self, output_dir: str):
        """
        初始化报告生成器

        Args:
            output_dir: 输出目录
        """
        super().__init__(output_dir)
        self._output_path = Path(output_dir)
        self._output_path.mkdir(parents=True, exist_ok=True)

    def generate_json_report(
        self,
        results: dict[str, list[dict]],
        filename: str = "gnss_results"
    ) -> str:
        """
        生成 JSON 格式报告

        Args:
            results: 测试结果
            filename: 文件名（不含扩展名）

        Returns:
            报告文件路径
        """
        # 生成汇总 JSON
        total_path = self._output_path / f"{filename}.json"
        with open(total_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"已生成 JSON 报告: {total_path}")

        # 为每个测试用例生成单独的 JSONL 文件
        for case_name, gnss_infos in results.items():
            case_path = self._output_path / f"{case_name}.jsonl"
            with open(case_path, 'w', encoding='utf-8') as f:
                for info in gnss_infos:
                    f.write(json.dumps(info, ensure_ascii=False) + '\n')

        return str(total_path)

    def generate_excel_report(
        self,
        results: dict[str, list[dict]],
        filename: str = "gnss_results"
    ) -> str:
        """
        生成 Excel 格式报告

        Args:
            results: 测试结果
            filename: 文件名（不含扩展名）

        Returns:
            报告文件路径
        """
        if not results:
            logger.warning("没有测试结果，无法生成 Excel 报告")
            return ""

        wb = Workbook()
        wb.remove(wb.active)  # 移除默认 sheet

        # 获取表头
        headers = self._generate_headers(results)

        for sheet_name, records in results.items():
            if not records:
                continue

            ws = wb.create_sheet(sheet_name[:31])  # Excel sheet 名称限制

            # 写入表头
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.fill = self.HEADER_FILL
                cell.font = self.HEADER_FONT
                cell.alignment = self.CENTER_ALIGN
                cell.border = self.THIN_BORDER

            # 写入数据
            for row_idx, record in enumerate(records, start=2):
                values = self._flatten_record(record)
                for col_idx, val in enumerate(values, 1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.alignment = self.CENTER_ALIGN
                    cell.border = self.THIN_BORDER

            # 自动调整列宽
            self._auto_adjust_column_width(ws)

        # 添加汇总 sheet
        self._add_summary_sheet(wb, results)

        output_path = self._output_path / f"{filename}.xlsx"
        wb.save(str(output_path))
        logger.info(f"已生成 Excel 报告: {output_path}")

        return str(output_path)

    def _generate_headers(self, results: dict[str, list[dict]]) -> list[str]:
        """生成表头"""
        headers = []
        # 获取第一条记录作为模板
        sample = None
        for records in results.values():
            if records:
                sample = records[0]
                break

        if not sample:
            return headers

        for key in sample.keys():
            if key == 'overall':
                headers.append('overall_top4_cn')
                for i in range(1, 5):
                    headers.append(f'overall_sat{i}')
            elif re.search(r'_gsv$', key):
                headers.append(f'{key}_top4_cn')
                for i in range(1, 5):
                    headers.append(f'{key}_sat{i}')
            else:
                headers.append(key)

        return headers

    def _flatten_record(self, record: dict) -> list[Any]:
        """将记录扁平化为值列表"""
        values = []

        for key, value in record.items():
            if key == 'overall' or re.search(r'_gsv$', key):
                if isinstance(value, dict):
                    values.append(value.get('top4_cn', ''))
                    sats = value.get('sats', [])
                    for i in range(4):
                        if i < len(sats):
                            sat = sats[i]
                            sat_str = f"{sat.get('prn', '')}: {sat.get('snr', '')}"
                            if 'constellation' in sat:
                                sat_str += f" ({sat['constellation']})"
                            values.append(sat_str)
                        else:
                            values.append('')
                else:
                    values.extend([''] * 5)
            else:
                values.append(value)

        return values

    def _auto_adjust_column_width(self, ws) -> None:
        """自动调整列宽"""
        for column_cells in ws.columns:
            max_length = 0
            column = column_cells[0].column_letter

            for cell in column_cells:
                try:
                    cell_length = len(str(cell.value)) if cell.value else 0
                    max_length = max(max_length, cell_length)
                except:
                    pass

            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width

    def _add_summary_sheet(self, wb: Workbook, results: dict[str, list[dict]]) -> None:
        """添加汇总 sheet"""
        ws = wb.create_sheet("Summary", 0)

        headers = ['Test Case', 'Records', 'Avg Overall Top4 CN',
                   'Avg GPS Top4 CN', 'Avg BDS Top4 CN',
                   'Avg GAL Top4 CN', 'Avg GLN Top4 CN']

        # 写入表头
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = self.CENTER_ALIGN
            cell.border = self.THIN_BORDER

        # 计算并写入汇总数据
        row = 2
        for case_name, records in results.items():
            if not records:
                continue

            ws.cell(row=row, column=1, value=case_name)
            ws.cell(row=row, column=2, value=len(records))

            # 计算各星座平均 top4 cn
            for col, key in enumerate(['overall', 'gps_gsv', 'bds_gsv', 'gal_gsv', 'gln_gsv'], 3):
                cn_values = []
                for rec in records:
                    gsv_info = rec.get(key, {})
                    if isinstance(gsv_info, dict):
                        top4_cn = gsv_info.get('top4_cn')
                        if top4_cn is not None:
                            cn_values.append(top4_cn)

                if cn_values:
                    avg = round(sum(cn_values) / len(cn_values), 2)
                    ws.cell(row=row, column=col, value=avg)

            row += 1

        self._auto_adjust_column_width(ws)

    def generate(self, results: dict[str, list[dict]], formats: list[str] = None) -> list[str]:
        """
        生成报告

        Args:
            results: 测试结果
            formats: 报告格式列表 ['json', 'xlsx']

        Returns:
            生成的报告文件路径列表
        """
        formats = formats or ['json', 'xlsx']
        output_files = []

        if 'json' in formats:
            path = self.generate_json_report(results)
            if path:
                output_files.append(path)

        if 'xlsx' in formats:
            path = self.generate_excel_report(results)
            if path:
                output_files.append(path)

        return output_files