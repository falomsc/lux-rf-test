import pytest
from src.core.exceptions import ConfigError
from src.utils.config_loader import merge_configs, load_config


class TestLoadConfig:
    def test_load_config_file_not_exists(self):
        """测试配置文件不存在时抛出 ConfigError"""
        with pytest.raises(ConfigError) as exc_info:
            load_config("/path/to/nonexistent/config.yaml")

        assert "配置文件不存在" in str(exc_info.value)

    def test_load_config_valid_yaml(self, tmp_path):
        """测试正常读取有效的 YAML 配置文件"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "database:\n  host: localhost\n  port: 5432\n",
            encoding="utf-8"
        )

        result = load_config(str(config_file))

        assert result == {"database": {"host": "localhost", "port": 5432}}

    def test_load_config_empty_file(self, tmp_path):
        """测试空配置文件返回空字典"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")

        result = load_config(str(config_file))

        assert result == {}

    def test_load_config_yaml_with_only_comments(self, tmp_path):
        """测试只有注释的 YAML 文件返回空字典"""
        config_file = tmp_path / "comments.yaml"
        config_file.write_text("# This is a comment\n# Another comment\n", encoding="utf-8")

        result = load_config(str(config_file))

        assert result == {}

    def test_load_config_invalid_yaml(self, tmp_path):
        """测试无效 YAML 格式抛出 ConfigError"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(
            "invalid: yaml: content:\n  - broken",
            encoding="utf-8"
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "配置文件解析错误" in str(exc_info.value)

    def test_load_config_with_list(self, tmp_path):
        """测试包含列表的 YAML 配置"""
        config_file = tmp_path / "list_config.yaml"
        config_file.write_text(
            "servers:\n  - server1\n  - server2\n  - server3\n",
            encoding="utf-8"
        )

        result = load_config(str(config_file))

        assert result == {"servers": ["server1", "server2", "server3"]}

    def test_load_config_with_nested_structure(self, tmp_path):
        """测试嵌套结构的 YAML 配置"""
        config_file = tmp_path / "nested.yaml"
        config_content = """
app:
  name: my_app
  version: 1.0.0
  settings:
    debug: true
    log_level: INFO
"""
        config_file.write_text(config_content, encoding="utf-8")

        result = load_config(str(config_file))

        assert result["app"]["name"] == "my_app"
        assert result["app"]["settings"]["debug"] is True


class TestMergeConfigs:
    def test_merge_empty_configs(self):
        """测试合并空配置"""
        result = merge_configs()
        assert result == {}

    def test_merge_single_config(self):
        """测试合并单个配置"""
        config = {"key": "value"}
        result = merge_configs(config)
        assert result == {"key": "value"}

    def test_merge_two_configs(self):
        """测试合并两个配置"""
        config1 = {"a": 1}
        config2 = {"b": 2}

        result = merge_configs(config1, config2)

        assert result == {"a": 1, "b": 2}

    def test_merge_configs_with_override(self):
        """测试后面的配置覆盖前面的同名键"""
        config1 = {"key": "old_value", "other": "keep"}
        config2 = {"key": "new_value"}

        result = merge_configs(config1, config2)

        assert result == {"key": "new_value", "other": "keep"}

    def test_merge_multiple_configs(self):
        """测试合并多个配置"""
        config1 = {"a": 1}
        config2 = {"b": 2}
        config3 = {"c": 3}
        config4 = {"a": 10, "d": 4}

        result = merge_configs(config1, config2, config3, config4)

        assert result == {"a": 10, "b": 2, "c": 3, "d": 4}

    def test_merge_configs_does_not_deep_merge(self):
        """测试合并是浅合并，不是深度合并"""
        config1 = {"nested": {"a": 1, "b": 2}}
        config2 = {"nested": {"c": 3}}

        result = merge_configs(config1, config2)

        # 浅合并会完全替换 nested 的值
        assert result == {"nested": {"c": 3}}

    def test_merge_configs_original_not_modified(self):
        """测试合并不会修改原始配置"""
        config1 = {"a": 1}
        config2 = {"b": 2}

        merge_configs(config1, config2)

        assert config1 == {"a": 1}
        assert config2 == {"b": 2}