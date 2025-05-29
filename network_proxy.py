#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络代理模块 - 处理代理相关功能
"""

import threading
import socket
import requests
from tkinter import messagebox


class NetworkProxy:
    def __init__(self, app):
        self.app = app

    def get_proxy_config(self):
        """获取代理配置"""
        if not self.app.use_proxy.get():
            return None

        proxy_type = self.app.proxy_type_var.get()
        proxy_host = self.app.proxy_host_var.get().strip()
        proxy_port = self.app.proxy_port_var.get().strip()

        if not proxy_host or not proxy_port:
            return None

        try:
            port = int(proxy_port)
            if proxy_type == 'HTTP':
                return {
                    'proxy_type': 'http',
                    'addr': proxy_host,
                    'port': port
                }
            elif proxy_type == 'SOCKS5':
                return {
                    'proxy_type': 'socks5',
                    'addr': proxy_host,
                    'port': port
                }
        except ValueError:
            return None

        return None

    def test_proxy(self):
        """测试代理连接"""
        proxy_config = self.get_proxy_config()
        if not proxy_config:
            messagebox.showwarning("警告", "请先配置代理信息")
            return

        self.app.log_message(f"正在测试代理连接 {proxy_config['addr']}:{proxy_config['port']}...")
        threading.Thread(target=self._test_proxy_async, args=(proxy_config,)).start()

    def _test_proxy_async(self, proxy_config):
        """异步测试代理"""
        try:
            proxies = {}
            if proxy_config['proxy_type'] == 'http':
                proxies = {
                    'http': f"http://{proxy_config['addr']}:{proxy_config['port']}",
                    'https': f"http://{proxy_config['addr']}:{proxy_config['port']}"
                }
            elif proxy_config['proxy_type'] == 'socks5':
                proxies = {
                    'http': f"socks5://{proxy_config['addr']}:{proxy_config['port']}",
                    'https': f"socks5://{proxy_config['addr']}:{proxy_config['port']}"
                }

            response = requests.get('https://api.telegram.org', proxies=proxies, timeout=10)
            if response.status_code == 200:
                self.app.root.after(0, lambda: self.app.log_message("代理连接测试成功！"))
                self.app.root.after(0, lambda: messagebox.showinfo("成功", "代理连接测试成功！"))
            else:
                self.app.root.after(0, lambda: self.app.log_message(f"代理连接测试失败，状态码: {response.status_code}"))

        except Exception as e:
            error_msg = str(e)  # 捕获错误信息
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"代理连接测试失败: {msg}"))
            self.app.root.after(0, lambda msg=error_msg: messagebox.showerror("测试失败", f"代理连接测试失败:\n{msg}"))

    def scan_proxy_ports(self):
        """扫描常见的代理端口"""
        self.app.log_message("开始扫描常见代理端口...")
        threading.Thread(target=self._scan_proxy_ports_async).start()

    def _scan_proxy_ports_async(self):
        """异步扫描代理端口"""
        common_ports = [7890, 7891, 7892, 7893, 8080, 8081, 1080, 1081, 3128, 8888, 9090]
        working_ports = []

        self.app.root.after(0, lambda: self.app.log_message("=== 开始端口扫描 ==="))

        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()

                if result == 0:
                    self.app.root.after(0, lambda p=port: self.app.log_message(f"✓ 端口 {p} 开放"))

                    # 测试HTTP代理
                    try:
                        proxies = {
                            'http': f'http://127.0.0.1:{port}',
                            'https': f'http://127.0.0.1:{port}'
                        }
                        response = requests.get('https://api.telegram.org', proxies=proxies, timeout=5)
                        if response.status_code == 200:
                            working_ports.append(('HTTP', port))
                            self.app.root.after(0, lambda p=port: self.app.log_message(f"✓ 端口 {p} - HTTP代理可用"))
                    except:
                        pass

                    # 测试SOCKS5代理
                    try:
                        proxies = {
                            'http': f'socks5://127.0.0.1:{port}',
                            'https': f'socks5://127.0.0.1:{port}'
                        }
                        response = requests.get('https://api.telegram.org', proxies=proxies, timeout=5)
                        if response.status_code == 200:
                            working_ports.append(('SOCKS5', port))
                            self.app.root.after(0, lambda p=port: self.app.log_message(f"✓ 端口 {p} - SOCKS5代理可用"))
                    except:
                        pass

                else:
                    self.app.root.after(0, lambda p=port: self.app.log_message(f"✗ 端口 {p} 未开放"))

            except Exception as e:
                self.app.root.after(0, lambda p=port, err=str(e): self.app.log_message(f"✗ 端口 {p} 测试失败: {err}"))

        # 显示结果
        if working_ports:
            best_proxy = working_ports[0]
            self.app.root.after(0, lambda: self.app.log_message(f"=== 找到可用代理: {best_proxy[0]} 端口 {best_proxy[1]} ==="))

            # 自动设置最佳代理
            self.app.proxy_type_var.set(best_proxy[0])
            self.app.proxy_port_var.set(str(best_proxy[1]))

            proxy_list = ", ".join([f"{ptype}:{port}" for ptype, port in working_ports])
            self.app.root.after(0, lambda pl=proxy_list: messagebox.showinfo("扫描结果",
                                                                         f"找到可用代理:\n{pl}\n\n已自动设置为最佳配置"))
        else:
            self.app.root.after(0, lambda: self.app.log_message("=== 未找到可用的代理端口 ==="))
            self.app.root.after(0,
                            lambda: messagebox.showwarning("扫描结果", "未找到可用的代理端口\n请检查Clash是否正在运行"))

    def diagnose_network(self):
        """诊断网络连接"""
        self.app.log_message("开始网络诊断...")
        threading.Thread(target=self._diagnose_network_async).start()

    def _diagnose_network_async(self):
        """异步网络诊断"""
        try:
            self.app.root.after(0, lambda: self.app.log_message("=== 网络诊断开始 ==="))

            # 1. 测试基本网络连接
            try:
                response = requests.get('https://www.baidu.com', timeout=10)
                self.app.root.after(0, lambda: self.app.log_message("✓ 基本网络连接正常"))
            except:
                self.app.root.after(0, lambda: self.app.log_message("✗ 基本网络连接失败"))
                return

            # 2. 测试是否能直连Telegram
            telegram_urls = [
                'https://api.telegram.org',
                'https://web.telegram.org',
                'https://core.telegram.org'
            ]

            telegram_accessible = False
            for url in telegram_urls:
                try:
                    response = requests.get(url, timeout=10)
                    self.app.root.after(0, lambda u=url: self.app.log_message(f"✓ 可以访问 {u}"))
                    telegram_accessible = True
                except Exception as e:
                    self.app.root.after(0, lambda u=url, err=str(e): self.app.log_message(f"✗ 无法访问 {u}: {err}"))

            if telegram_accessible:
                self.app.root.after(0, lambda: self.app.log_message("✓ 部分Telegram服务可访问，但可能需要特定配置"))
            else:
                self.app.root.after(0, lambda: self.app.log_message("✗ 无法访问任何Telegram服务，必须使用代理"))

            # 3. 测试DNS解析
            try:
                telegram_ips = socket.gethostbyname_ex('api.telegram.org')[2]
                self.app.root.after(0, lambda ips=telegram_ips: self.app.log_message(f"✓ DNS解析成功: {ips}"))
            except Exception as e:
                error_msg = str(e)
                self.app.root.after(0, lambda err=error_msg: self.app.log_message(f"✗ DNS解析失败: {err}"))
                self.app.root.after(0, lambda: messagebox.showerror("DNS问题", "DNS解析失败，可能需要更换DNS或使用代理"))
                return

            # 4. 测试代理端口是否开放
            proxy_host = self.app.proxy_host_var.get().strip()
            proxy_port = self.app.proxy_port_var.get().strip()

            if proxy_host and proxy_port:
                try:
                    port = int(proxy_port)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((proxy_host, port))
                    sock.close()

                    if result == 0:
                        self.app.root.after(0, lambda: self.app.log_message(f"✓ 代理端口 {proxy_host}:{proxy_port} 可访问"))
                    else:
                        self.app.root.after(0, lambda: self.app.log_message(f"✗ 代理端口 {proxy_host}:{proxy_port} 无法访问"))
                        self.app.root.after(0, lambda: messagebox.showerror("代理问题",
                                                                        f"代理端口 {proxy_host}:{proxy_port} 无法访问\n请检查Clash是否运行，端口是否正确"))
                        return

                except ValueError:
                    self.app.root.after(0, lambda: self.app.log_message("✗ 代理端口格式错误"))
                    return

            # 5. 测试不同类型的代理
            proxy_types = ['HTTP', 'SOCKS5']
            working_configs = []

            for ptype in proxy_types:
                try:
                    if ptype == 'HTTP':
                        proxies = {
                            'http': f'http://{proxy_host}:{proxy_port}',
                            'https': f'http://{proxy_host}:{proxy_port}'
                        }
                    else:  # SOCKS5
                        proxies = {
                            'http': f'socks5://{proxy_host}:{proxy_port}',
                            'https': f'socks5://{proxy_host}:{proxy_port}'
                        }

                    response = requests.get('https://api.telegram.org', proxies=proxies, timeout=10)
                    if response.status_code == 200:
                        working_configs.append(ptype)
                        self.app.root.after(0, lambda t=ptype: self.app.log_message(f"✓ {t} 代理可以连接Telegram"))
                    else:
                        self.app.root.after(0, lambda t=ptype: self.app.log_message(f"✗ {t} 代理无法连接Telegram"))

                except Exception as e:
                    self.app.root.after(0, lambda t=ptype, err=str(e): self.app.log_message(f"✗ {t} 代理测试失败: {err}"))

            # 6. 给出建议
            if working_configs:
                best_config = working_configs[0]
                self.app.root.after(0, lambda: self.app.log_message(f"建议使用: {best_config} 代理"))
                self.app.root.after(0, lambda cfg=best_config: messagebox.showinfo("诊断结果", f"建议使用 {cfg} 代理类型"))

                # 自动设置为最佳配置
                self.app.proxy_type_var.set(best_config)
            else:
                self.app.root.after(0, lambda: self.app.log_message("所有代理配置都无法连接Telegram"))
                self.app.root.after(0, lambda: messagebox.showerror("诊断结果",
                                                                "所有代理配置都无法连接Telegram\n请检查Clash配置或尝试其他代理端口"))

            # 7. MTProto连接测试
            self.app.root.after(0, lambda: self.app.log_message("=== 开始MTProto连接测试 ==="))

            # 测试Telegram的MTProto端口
            telegram_servers = [
                ('149.154.167.50', 443),  # DC2
                ('149.154.175.53', 443),  # DC4
                ('91.108.56.130', 443),   # DC5
            ]

            mtproto_working = False
            for server, port in telegram_servers:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(10)
                    result = sock.connect_ex((server, port))
                    sock.close()

                    if result == 0:
                        self.app.root.after(0, lambda s=server: self.app.log_message(f"✓ MTProto服务器 {s}:443 可连接"))
                        mtproto_working = True
                    else:
                        self.app.root.after(0, lambda s=server: self.app.log_message(f"✗ MTProto服务器 {s}:443 无法连接"))

                except Exception as e:
                    self.app.root.after(0, lambda s=server, err=str(e): self.app.log_message(
                        f"✗ MTProto服务器 {s}:443 测试失败: {err}"))

            if not mtproto_working:
                self.app.root.after(0, lambda: self.app.log_message("所有MTProto服务器都无法直连"))
                self.app.root.after(0, lambda: messagebox.showwarning("MTProto问题",
                                                                  "MTProto协议被阻止\n必须使用代理连接Telegram"))
            else:
                self.app.root.after(0, lambda: self.app.log_message("MTProto连接正常，可能是Telethon配置问题"))

            self.app.root.after(0, lambda: self.app.log_message("=== 网络诊断完成 ==="))

        except Exception as e:
            self.app.root.after(0, lambda: self.app.log_message(f"网络诊断失败: {str(e)}"))