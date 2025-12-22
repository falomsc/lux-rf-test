import json
from pathlib import Path

from src.reporters.base_reporter import BaseReporter
from src.utils.logger import get_logger

logger = get_logger()


class GNSSReporter(BaseReporter):
    """GNSS 测试报告生成器"""
    # TODO 更新 excel 和 dashboard 方法
    def __init__(self, output_dir: str):
        super().__init__(output_dir)
        self._output_path = Path(output_dir)
        self._output_path.mkdir(parents=True, exist_ok=True)

    def generate_json_report(
            self,
            results: dict[str, list[dict]],
            filename: str = "gnss_results"
    ) -> str:
        """
        json 格式
        :param results:
        :param filename:
        :return:
        """
        total_path = self._output_path / f"{filename}.json"
        with open(total_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"已生成 JSON 报告: {total_path}")

        # 为每个测试用例生成单独的 jsonl 文件
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
        excel 格式
        :param results:
        :param filename:
        :return:
        """
        pass

    def generate_dashboard_report(
            self,
            results: dict[str, list[dict]],
            filename: str = "gnss_results"
    ) -> str:
        """
        excel 格式
        :param results:
        :param filename:
        :return:
        """
        pass

    def generate(self, results: dict[str, list[dict]], formats: list[str] = None) -> list[str]:
        """
        生成报告

        :param results:
        :param formats:
        :return:
        """
        output_files = []

        if 'json' in formats:
            path = self.generate_json_report(results)
            if path:
                output_files.append(path)

        if 'xlsx' in formats:
            path = self.generate_excel_report(results)
            if path:
                output_files.append(path)

        if 'dashboard' in formats:
            path = self.generate_excel_report(results)
            if path:
                output_files.append(path)

        return output_files
