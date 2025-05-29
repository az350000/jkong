#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块 - 处理配置文件的加载和保存
"""

import json
import os


class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config
            else:
                return {}
        except Exception as e:
            print(f"加载配置失败: {e}")
            return {}

    def save_config(self, config):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            raise Exception(f"保存配置失败: {e}")

    def get_default_config(self):
        """获取默认配置"""
        return {
            'api_id': '',
            'api_hash': '',
            'bot_token': '',
            'use_proxy': True,
            'proxy_host': '127.0.0.1',
            'proxy_port': '7890',
            'proxy_type': 'HTTP',
            'filter_username': False,
            'filter_links': False,
            'filter_buttons': False,
            'filter_media': False,
            'filter_forwarded': False,
            'filter_keywords': '',
            'target_keywords': '',
            'forward_to': '',
            'whitelist_groups': ''
        }