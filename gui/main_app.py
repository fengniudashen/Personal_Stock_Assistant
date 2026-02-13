"""
VibeSing 高音觉醒 - GUI 主应用程序
全功能管道操作界面，覆盖所有 pipeline 步骤
"""
import sys
import os
import json
import threading
import logging
import queue
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 尝试加载项目配置
CONFIG_PATH = ROOT / 'config_advanced.yaml'
try:
    import yaml
    with open(CONFIG_PATH, encoding='utf-8') as f:
        CONFIG = yaml.safe_load(f)
except Exception:
    CONFIG = {}


# =============================================================================
#  日志重定向器：将 logging 输出到 GUI 文本框
# =============================================================================
class QueueHandler(logging.Handler):
    """将日志消息发送到队列，供 GUI 线程安全读取"""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            self.log_queue.put_nowait(self.format(record))
        except queue.Full:
            pass


# =============================================================================
#  主应用程序
# =============================================================================
class VibeSingApp(tk.Tk):
    """VibeSing 主应用窗口"""

    def __init__(self):
        super().__init__()
        self.title("VibeSing 高音觉醒 - 智能标注工作台 v2.0")
        self.geometry("1280x800")
        self.minsize(960, 600)

        # 配色方案
        self.colors = {
            'bg': '#f8fafc',
            'sidebar': '#1e293b',
            'sidebar_text': '#e2e8f0',
            'sidebar_active': '#3b82f6',
            'accent': '#3b82f6',
            'success': '#10b981',
            'warning': '#f59e0b',
            'danger': '#ef4444',
            'card_bg': '#ffffff',
            'text': '#1e293b',
            'text_muted': '#64748b',
        }

        self.configure(bg=self.colors['bg'])

        # 日志队列
        self.log_queue = queue.Queue(maxsize=500)
        self._setup_logging()

        # 运行状态
        self.running_task = None
        self.task_thread = None

        # 构建 UI
        self._build_ui()

        # 定时刷新日志
        self._poll_log_queue()

    def _setup_logging(self):
        """配置日志到队列"""
        handler = QueueHandler(self.log_queue)
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s',
                                                datefmt='%H:%M:%S'))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

    # =========================================================================
    #  UI 构建
    # =========================================================================
    def _build_ui(self):
        # 侧边栏
        self.sidebar = tk.Frame(self, bg=self.colors['sidebar'], width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # 主内容区
        self.main_area = tk.Frame(self, bg=self.colors['bg'])
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 内容面板容器
        self.content_frame = tk.Frame(self.main_area, bg=self.colors['bg'])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 0))

        # 日志面板
        self.log_frame = tk.LabelFrame(self.main_area, text=" 📋 运行日志 ",
                                        bg=self.colors['bg'], fg=self.colors['text'])
        self.log_frame.pack(fill=tk.X, padx=16, pady=(4, 8))

        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, height=8, wrap=tk.WORD,
            bg='#0f172a', fg='#a5f3fc', font=('Consolas', 9),
            insertbackground='white'
        )
        self.log_text.pack(fill=tk.X, padx=4, pady=4)

        # 构建侧边栏菜单
        self._build_sidebar()

        # 构建所有面板 (但不显示)
        self.panels = {}
        self._build_dashboard_panel()
        self._build_download_panel()
        self._build_extract_panel()
        self._build_separate_panel()
        self._build_slice_panel()
        self._build_asr_panel()
        self._build_features_panel()
        self._build_weak_labels_panel()
        self._build_embedding_panel()
        self._build_clustering_panel()
        self._build_active_learning_panel()
        self._build_human_review_panel()
        self._build_export_panel()
        self._build_label_studio_panel()
        self._build_training_panel()
        self._build_settings_panel()

        # 默认显示仪表盘
        self._show_panel('dashboard')

    def _build_sidebar(self):
        """构建侧边栏导航"""
        # Logo
        logo_frame = tk.Frame(self.sidebar, bg=self.colors['sidebar'])
        logo_frame.pack(fill=tk.X, padx=12, pady=(16, 8))
        tk.Label(logo_frame, text="🎤 VibeSing", font=('Segoe UI', 16, 'bold'),
                 bg=self.colors['sidebar'], fg='white').pack(anchor='w')
        tk.Label(logo_frame, text="高音觉醒 v2.0", font=('Segoe UI', 9),
                 bg=self.colors['sidebar'], fg=self.colors['text_muted']).pack(anchor='w')

        ttk.Separator(self.sidebar, orient='horizontal').pack(fill=tk.X, padx=12, pady=8)

        # 菜单项
        menu_items = [
            ('dashboard',      '📊 仪表盘'),
            ('sep1',           None),
            ('download',       '⬇️  数据下载'),
            ('extract',        '🎵 音频提取'),
            ('separate',       '🔊 人声分离'),
            ('slice',          '✂️  智能切片'),
            ('asr',            '💬 ASR识别'),
            ('features',       '📈 特征提取'),
            ('weak_labels',    '🏷️  弱标签融合'),
            ('embedding',      '🧬 嵌入计算'),
            ('clustering',     '🫧 聚类去重'),
            ('active_learning','🎯 主动学习'),
            ('human_review',   '🔍 人工审核'),
            ('sep2',           None),
            ('export',         '📦 数据导出'),
            ('label_studio',   '🏷️  Label Studio'),
            ('training',       '🧠 模型训练'),
            ('sep3',           None),
            ('settings',       '⚙️  系统设置'),
        ]

        self.menu_buttons = {}
        for key, text in menu_items:
            if text is None:
                ttk.Separator(self.sidebar, orient='horizontal').pack(fill=tk.X, padx=20, pady=4)
                continue

            btn = tk.Label(
                self.sidebar, text=text, font=('Segoe UI', 10),
                bg=self.colors['sidebar'], fg=self.colors['sidebar_text'],
                anchor='w', padx=16, pady=6, cursor='hand2'
            )
            btn.pack(fill=tk.X, padx=8, pady=1)
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg='#334155'))
            btn.bind('<Leave>', lambda e, b=btn, k=key: b.configure(
                bg=self.colors['sidebar_active'] if getattr(self, '_active_panel', '') == k
                else self.colors['sidebar']))
            btn.bind('<Button-1>', lambda e, k=key: self._show_panel(k))
            self.menu_buttons[key] = btn

    def _show_panel(self, panel_name: str):
        """切换显示面板"""
        # 隐藏所有
        for w in self.content_frame.winfo_children():
            w.pack_forget()

        # 显示目标
        if panel_name in self.panels:
            self.panels[panel_name].pack(fill=tk.BOTH, expand=True)

        # 更新侧边栏高亮
        self._active_panel = panel_name
        for key, btn in self.menu_buttons.items():
            if key == panel_name:
                btn.configure(bg=self.colors['sidebar_active'])
            else:
                btn.configure(bg=self.colors['sidebar'])

    # =========================================================================
    #  面板工厂方法
    # =========================================================================
    def _create_panel(self, name: str, title: str) -> tk.Frame:
        """创建并注册一个面板"""
        panel = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.panels[name] = panel

        # 标题
        header = tk.Frame(panel, bg=self.colors['bg'])
        header.pack(fill=tk.X, pady=(0, 12))
        tk.Label(header, text=title, font=('Segoe UI', 18, 'bold'),
                 bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.LEFT)

        return panel

    def _card(self, parent, title: str = '', padx=12, pady=8) -> tk.LabelFrame:
        """创建卡片容器"""
        card = tk.LabelFrame(parent, text=f" {title} " if title else '',
                              bg=self.colors['card_bg'], fg=self.colors['text'],
                              font=('Segoe UI', 10, 'bold'),
                              relief='groove', bd=1)
        card.pack(fill=tk.X, padx=padx, pady=pady)
        return card

    def _param_row(self, parent, label_text: str, default_value: str = '',
                    row: int = 0, width: int = 40) -> tk.Entry:
        """创建参数输入行"""
        tk.Label(parent, text=label_text, bg=self.colors['card_bg'],
                 fg=self.colors['text'], font=('Segoe UI', 9)).grid(
            row=row, column=0, sticky='w', padx=(8, 4), pady=3)
        entry = tk.Entry(parent, width=width, font=('Segoe UI', 9))
        entry.grid(row=row, column=1, sticky='w', padx=4, pady=3)
        entry.insert(0, default_value)
        return entry

    def _run_button(self, parent, text: str, command, color=None) -> tk.Button:
        """创建运行按钮"""
        if color is None:
            color = self.colors['accent']
        btn = tk.Button(parent, text=text, command=command,
                        bg=color, fg='white', font=('Segoe UI', 10, 'bold'),
                        relief='flat', padx=20, pady=6, cursor='hand2',
                        activebackground=color)
        btn.pack(pady=8, padx=8, anchor='w')
        return btn

    def _browse_dir(self, entry: tk.Entry):
        """目录浏览"""
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _browse_file(self, entry: tk.Entry, filetypes=None):
        """文件浏览"""
        if filetypes is None:
            filetypes = [("All files", "*.*")]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    # =========================================================================
    #  后台任务执行器
    # =========================================================================
    def _run_in_thread(self, func, *args, task_name: str = "任务"):
        """在后台线程中运行任务"""
        if self.task_thread and self.task_thread.is_alive():
            messagebox.showwarning("提示", f"当前有任务正在运行，请等待完成。")
            return

        def worker():
            self.running_task = task_name
            self._log_info(f"▶ 开始 {task_name}...")
            start = time.time()
            try:
                func(*args)
                elapsed = time.time() - start
                self._log_info(f"✅ {task_name} 完成 (耗时 {elapsed:.1f}s)")
            except Exception as e:
                self._log_error(f"❌ {task_name} 失败: {e}")
                import traceback
                self._log_error(traceback.format_exc())
            finally:
                self.running_task = None

        self.task_thread = threading.Thread(target=worker, daemon=True)
        self.task_thread.start()

    def _log_info(self, msg: str):
        logger.info(msg)

    def _log_error(self, msg: str):
        logger.error(msg)

    def _poll_log_queue(self):
        """定时从队列读取日志"""
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + '\n')
                self.log_text.see(tk.END)
            except queue.Empty:
                break
        self.after(100, self._poll_log_queue)

    # =========================================================================
    #  📊 仪表盘面板
    # =========================================================================
    def _build_dashboard_panel(self):
        panel = self._create_panel('dashboard', '📊 仪表盘')

        # 统计卡片
        stats_row = tk.Frame(panel, bg=self.colors['bg'])
        stats_row.pack(fill=tk.X, pady=(0, 12))

        self.stat_labels = {}
        stat_items = [
            ('total_clips', '总切片数', '0', self.colors['accent']),
            ('labeled', '已标注', '0', self.colors['success']),
            ('unlabeled', '未标注', '0', self.colors['warning']),
            ('need_review', '需复审', '0', self.colors['danger']),
        ]

        for key, title, default, color in stat_items:
            card = tk.Frame(stats_row, bg='white', relief='groove', bd=1, padx=16, pady=12)
            card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
            tk.Label(card, text=title, bg='white', fg=self.colors['text_muted'],
                     font=('Segoe UI', 9)).pack(anchor='w')
            lbl = tk.Label(card, text=default, bg='white', fg=color,
                           font=('Segoe UI', 22, 'bold'))
            lbl.pack(anchor='w')
            self.stat_labels[key] = lbl

        # 标签体系概览
        label_card = self._card(panel, '标签体系 v2')
        labels_info = tk.Frame(label_card, bg=self.colors['card_bg'])
        labels_info.pack(fill=tk.X, padx=8, pady=8)

        primary = CONFIG.get('labels', {}).get('primary', [])
        secondary = CONFIG.get('labels', {}).get('secondary', [])
        quality = CONFIG.get('labels', {}).get('quality_flags', [])

        tk.Label(labels_info, text=f"主标签(发声机制): {', '.join(primary)}",
                 bg=self.colors['card_bg'], fg=self.colors['text'],
                 font=('Segoe UI', 9), wraplength=900, justify='left').pack(anchor='w')
        tk.Label(labels_info, text=f"辅标签(共鸣色彩): {', '.join(secondary)}",
                 bg=self.colors['card_bg'], fg=self.colors['text_muted'],
                 font=('Segoe UI', 9), wraplength=900, justify='left').pack(anchor='w', pady=(2, 0))
        tk.Label(labels_info, text=f"质量旗标: {', '.join(quality)}",
                 bg=self.colors['card_bg'], fg=self.colors['text_muted'],
                 font=('Segoe UI', 9), wraplength=900, justify='left').pack(anchor='w', pady=(2, 0))

        # 快速操作
        quick_card = self._card(panel, '快速操作')
        btn_row = tk.Frame(quick_card, bg=self.colors['card_bg'])
        btn_row.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(btn_row, text="🔄 刷新统计", command=self._refresh_stats,
                  bg=self.colors['accent'], fg='white', relief='flat',
                  padx=12, pady=4, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="▶ 运行全部流水线", command=self._run_full_pipeline,
                  bg=self.colors['success'], fg='white', relief='flat',
                  padx=12, pady=4, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="📦 导出数据集", command=lambda: self._show_panel('export'),
                  bg=self.colors['warning'], fg='white', relief='flat',
                  padx=12, pady=4, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)

    def _refresh_stats(self):
        """刷新仪表盘统计"""
        clips_dir = Path(CONFIG.get('paths', {}).get('clips', 'data/clips'))
        clip_count = len(list(clips_dir.glob('*.wav'))) if clips_dir.exists() else 0
        self.stat_labels['total_clips'].config(text=str(clip_count))

        fused_path = Path('data/fused_labels.json')
        need_review = 0
        if fused_path.exists():
            with open(fused_path, encoding='utf-8') as f:
                fused = json.load(f)
            need_review = sum(1 for r in fused if r.get('needs_review'))

        labeled = Path('data/labeled_clips.txt')
        labeled_count = len(labeled.read_text().splitlines()) if labeled.exists() else 0

        self.stat_labels['labeled'].config(text=str(labeled_count))
        self.stat_labels['unlabeled'].config(text=str(clip_count - labeled_count))
        self.stat_labels['need_review'].config(text=str(need_review))

    def _run_full_pipeline(self):
        """运行完整流水线"""
        def task():
            from run_full_pipeline import main as run_pipeline
            run_pipeline()
        self._run_in_thread(task, task_name="完整流水线")

    # =========================================================================
    #  ⬇️ 数据下载面板
    # =========================================================================
    def _build_download_panel(self):
        panel = self._create_panel('download', '⬇️ 数据下载')

        # URL 输入
        url_card = self._card(panel, '添加下载源')
        url_inner = tk.Frame(url_card, bg=self.colors['card_bg'])
        url_inner.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(url_inner, text="URL / 搜索关键词:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', padx=4, pady=2)
        self.dl_url_entry = tk.Entry(url_inner, width=70, font=('Segoe UI', 9))
        self.dl_url_entry.grid(row=0, column=1, sticky='w', padx=4, pady=2)

        tk.Label(url_inner, text="平台:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', padx=4, pady=2)
        self.dl_platform = ttk.Combobox(url_inner, values=['bilibili', 'youtube', 'douyin', '通用URL'],
                                         state='readonly', width=20, font=('Segoe UI', 9))
        self.dl_platform.grid(row=1, column=1, sticky='w', padx=4, pady=2)
        self.dl_platform.set('bilibili')

        # 参数
        param_card = self._card(panel, '下载参数')
        param_inner = tk.Frame(param_card, bg=self.colors['card_bg'])
        param_inner.pack(fill=tk.X, padx=8, pady=8)

        self.dl_output = self._param_row(param_inner, "输出目录:",
                                          CONFIG.get('paths', {}).get('raw_videos', './data/raw_videos'), 0)
        self.dl_quality = self._param_row(param_inner, "音质:", "bestaudio", 1, 20)
        self.dl_rate = self._param_row(param_inner, "限速:", "1M", 2, 20)

        tk.Button(param_inner, text="📂 浏览", command=lambda: self._browse_dir(self.dl_output),
                  font=('Segoe UI', 8)).grid(row=0, column=2, padx=4)

        # 按钮
        btn_row = tk.Frame(panel, bg=self.colors['bg'])
        btn_row.pack(fill=tk.X, pady=4)
        self._run_button(btn_row, "⬇️ 开始下载", self._do_download)

    def _do_download(self):
        url = self.dl_url_entry.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入URL或关键词")
            return

        platform = self.dl_platform.get()
        output = self.dl_output.get()

        def task():
            from downloaders.bilibili import BilibiliDownloader
            from downloaders.youtube import YouTubeDownloader
            os.makedirs(output, exist_ok=True)

            if platform == 'bilibili':
                dl = BilibiliDownloader(output_dir=output)
            elif platform == 'youtube':
                dl = YouTubeDownloader(output_dir=output)
            else:
                dl = YouTubeDownloader(output_dir=output)  # yt-dlp 通用

            dl.download(url)

        self._run_in_thread(task, task_name=f"下载 [{platform}]")

    # =========================================================================
    #  🎵 音频提取面板
    # =========================================================================
    def _build_extract_panel(self):
        panel = self._create_panel('extract', '🎵 音频提取 (Step 1)')

        card = self._card(panel, '参数配置')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        self.ext_input = self._param_row(inner, "输入目录(视频):",
                                          CONFIG.get('paths', {}).get('raw_videos', './data/raw_videos'), 0)
        self.ext_output = self._param_row(inner, "输出目录(音频):",
                                           CONFIG.get('paths', {}).get('audio_raw', './data/raw_audios'), 1)
        self.ext_sr = self._param_row(inner, "采样率:",
                                       str(CONFIG.get('audio', {}).get('sample_rate', 44100)), 2, 15)

        tk.Button(inner, text="📂", command=lambda: self._browse_dir(self.ext_input),
                  font=('Segoe UI', 8)).grid(row=0, column=2, padx=4)
        tk.Button(inner, text="📂", command=lambda: self._browse_dir(self.ext_output),
                  font=('Segoe UI', 8)).grid(row=1, column=2, padx=4)

        self._run_button(panel, "🎵 提取音频", self._do_extract)

    def _do_extract(self):
        def task():
            from pipeline.step1_extract import AudioExtractor
            extractor = AudioExtractor(
                input_dir=self.ext_input.get(),
                output_dir=self.ext_output.get(),
                sample_rate=int(self.ext_sr.get())
            )
            extractor.run()
        self._run_in_thread(task, task_name="音频提取 Step1")

    # =========================================================================
    #  🔊 人声分离面板
    # =========================================================================
    def _build_separate_panel(self):
        panel = self._create_panel('separate', '🔊 人声分离 (Step 2)')

        card = self._card(panel, '参数配置')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        self.sep_input = self._param_row(inner, "输入目录:",
                                          CONFIG.get('paths', {}).get('audio_raw', './data/raw_audios'), 0)
        self.sep_output = self._param_row(inner, "输出目录:",
                                           CONFIG.get('paths', {}).get('audio_clean', './data/audio_clean'), 1)

        tk.Label(inner, text="方法:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=2, column=0, sticky='w', padx=(8, 4), pady=3)
        self.sep_method = ttk.Combobox(inner, values=['demucs (htdemucs)', 'UVR5', 'MDX-Net'],
                                        state='readonly', width=25, font=('Segoe UI', 9))
        self.sep_method.grid(row=2, column=1, sticky='w', padx=4, pady=3)
        self.sep_method.set('demucs (htdemucs)')

        self._run_button(panel, "🔊 开始分离", self._do_separate)

    def _do_separate(self):
        def task():
            from pipeline.step2_separate import VocalSeparator
            separator = VocalSeparator(CONFIG)
            input_dir = Path(self.sep_input.get())
            output_dir = Path(self.sep_output.get())
            separator.run(str(input_dir), str(output_dir))
        self._run_in_thread(task, task_name="人声分离 Step2")

    # =========================================================================
    #  ✂️ 智能切片面板
    # =========================================================================
    def _build_slice_panel(self):
        panel = self._create_panel('slice', '✂️ 智能切片 (Step 3)')

        card = self._card(panel, '切片参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        self.sli_input = self._param_row(inner, "输入目录:",
                                          CONFIG.get('paths', {}).get('audio_clean', './data/audio_clean'), 0)
        self.sli_output = self._param_row(inner, "输出目录:",
                                           CONFIG.get('paths', {}).get('clips', './data/clips'), 1)

        slicing_cfg = CONFIG.get('slicing', {})
        self.sli_target = self._param_row(inner, "目标时长(s):",
                                           str(slicing_cfg.get('target_duration', 4.0)), 2, 10)
        self.sli_min = self._param_row(inner, "最小时长(s):",
                                        str(slicing_cfg.get('min_duration', 2.5)), 3, 10)
        self.sli_max = self._param_row(inner, "最大时长(s):",
                                        str(slicing_cfg.get('max_duration', 6.0)), 4, 10)

        tk.Label(inner, text="切片方法:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=5, column=0, sticky='w', padx=(8, 4), pady=3)
        self.sli_method = ttk.Combobox(inner, values=['hybrid', 'vad', 'energy'],
                                        state='readonly', width=15, font=('Segoe UI', 9))
        self.sli_method.grid(row=5, column=1, sticky='w', padx=4, pady=3)
        self.sli_method.set(slicing_cfg.get('method', 'hybrid'))

        self._run_button(panel, "✂️ 开始切片", self._do_slice)

    def _do_slice(self):
        def task():
            from pipeline.step3_slice import HybridSlicer
            slicer = HybridSlicer(CONFIG)
            slicer.run(self.sli_input.get(), self.sli_output.get())
        self._run_in_thread(task, task_name="智能切片 Step3")

    # =========================================================================
    #  💬 ASR 识别面板
    # =========================================================================
    def _build_asr_panel(self):
        panel = self._create_panel('asr', '💬 ASR语音识别 (Step 4)')

        card = self._card(panel, 'ASR 参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        whisper_cfg = CONFIG.get('whisper', {})
        self.asr_clips = self._param_row(inner, "切片目录:",
                                          CONFIG.get('paths', {}).get('clips', './data/clips'), 0)

        tk.Label(inner, text="Whisper 模型:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', padx=(8, 4), pady=3)
        self.asr_model = ttk.Combobox(inner, values=['tiny', 'base', 'small', 'medium', 'large-v3'],
                                       state='readonly', width=15, font=('Segoe UI', 9))
        self.asr_model.grid(row=1, column=1, sticky='w', padx=4, pady=3)
        self.asr_model.set(whisper_cfg.get('model', 'large-v3'))

        tk.Label(inner, text="语言:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=2, column=0, sticky='w', padx=(8, 4), pady=3)
        self.asr_lang = ttk.Combobox(inner, values=['zh', 'en', 'ja', 'auto'],
                                      state='readonly', width=10, font=('Segoe UI', 9))
        self.asr_lang.grid(row=2, column=1, sticky='w', padx=4, pady=3)
        self.asr_lang.set(whisper_cfg.get('language', 'zh'))

        # 关键词映射预览
        kw_card = self._card(panel, '关键词映射 (自动从配置读取)')
        kw_text = tk.Text(kw_card, height=6, wrap=tk.WORD, font=('Consolas', 8),
                          bg='#f1f5f9', fg=self.colors['text'])
        kw_text.pack(fill=tk.X, padx=8, pady=8)
        keywords = CONFIG.get('keywords', {})
        for label, kws in keywords.items():
            kw_text.insert(tk.END, f"{label}: {', '.join(kws)}\n")
        kw_text.configure(state='disabled')

        self._run_button(panel, "💬 运行 ASR", self._do_asr)

    def _do_asr(self):
        def task():
            from pipeline.step4_asr import ASRAnnotator
            labeler = ASRAnnotator(CONFIG)
            labeler.run(self.asr_clips.get())
        self._run_in_thread(task, task_name="ASR识别 Step4")

    # =========================================================================
    #  📈 特征提取面板
    # =========================================================================
    def _build_features_panel(self):
        panel = self._create_panel('features', '📈 特征提取 (Step 5)')

        card = self._card(panel, '特征参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        self.feat_clips = self._param_row(inner, "切片目录:",
                                           CONFIG.get('paths', {}).get('clips', './data/clips'), 0)
        self.feat_output = self._param_row(inner, "输出目录:",
                                            CONFIG.get('paths', {}).get('features', './data/features'), 1)

        feat_cfg = CONFIG.get('features', {})
        self.feat_mel_n = self._param_row(inner, "Mel 频带数:",
                                           str(feat_cfg.get('mel', {}).get('n_mels', 128)), 2, 10)

        # 启发式特征开关
        heur_card = self._card(panel, '启发式特征')
        heur_inner = tk.Frame(heur_card, bg=self.colors['card_bg'])
        heur_inner.pack(fill=tk.X, padx=8, pady=8)

        hcfg = feat_cfg.get('heuristics', {})
        self.feat_h1h2 = tk.BooleanVar(value=hcfg.get('enable_h1h2', True))
        self.feat_tilt = tk.BooleanVar(value=hcfg.get('enable_spectral_tilt', True))
        self.feat_jitter = tk.BooleanVar(value=hcfg.get('enable_jitter', True))
        self.feat_shimmer = tk.BooleanVar(value=hcfg.get('enable_shimmer', True))
        self.feat_hnr = tk.BooleanVar(value=hcfg.get('enable_hnr', True))

        for i, (var, text) in enumerate([
            (self.feat_h1h2, 'H1-H2 声门特征'),
            (self.feat_tilt, 'Spectral Tilt'),
            (self.feat_jitter, 'Jitter 音高微扰'),
            (self.feat_shimmer, 'Shimmer 振幅微扰'),
            (self.feat_hnr, 'HNR 谐波噪声比'),
        ]):
            tk.Checkbutton(heur_inner, text=text, variable=var,
                           bg=self.colors['card_bg'], font=('Segoe UI', 9)).grid(
                row=i // 3, column=i % 3, sticky='w', padx=8, pady=2)

        self._run_button(panel, "📈 提取特征", self._do_features)

    def _do_features(self):
        def task():
            from pipeline.step5_features import FeatureExtractor
            extractor = FeatureExtractor(CONFIG)
            extractor.run(self.feat_clips.get(), self.feat_output.get())
        self._run_in_thread(task, task_name="特征提取 Step5")

    # =========================================================================
    #  🏷️ 弱标签融合面板
    # =========================================================================
    def _build_weak_labels_panel(self):
        panel = self._create_panel('weak_labels', '🏷️ 弱标签融合 (Step 6)')

        card = self._card(panel, '融合参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        ws_cfg = CONFIG.get('weak_supervision', {})
        self.wl_asr_w = self._param_row(inner, "ASR 权重:",
                                          str(ws_cfg.get('asr_weight', 0.4)), 0, 10)
        self.wl_heur_w = self._param_row(inner, "启发式权重:",
                                           str(ws_cfg.get('heuristic_weight', 0.2)), 1, 10)
        self.wl_model_w = self._param_row(inner, "模型权重:",
                                            str(ws_cfg.get('model_weight', 0.3)), 2, 10)
        self.wl_nb_w = self._param_row(inner, "近邻权重:",
                                         str(ws_cfg.get('neighbor_weight', 0.1)), 3, 10)
        self.wl_conf = self._param_row(inner, "置信度阈值:",
                                         str(ws_cfg.get('confidence_threshold', 0.7)), 4, 10)

        self._run_button(panel, "🏷️ 运行弱标签融合", self._do_weak_labels)

    def _do_weak_labels(self):
        def task():
            from pipeline.step6_weak_labels import main as run_step6
            run_step6()
        self._run_in_thread(task, task_name="弱标签融合 Step6")

    # =========================================================================
    #  🧬 嵌入计算面板
    # =========================================================================
    def _build_embedding_panel(self):
        panel = self._create_panel('embedding', '🧬 嵌入计算 (Step 7)')

        card = self._card(panel, '嵌入参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        emb_cfg = CONFIG.get('features', {}).get('embedding', {})
        self.emb_clips = self._param_row(inner, "切片目录:",
                                          CONFIG.get('paths', {}).get('clips', './data/clips'), 0)

        tk.Label(inner, text="嵌入模型:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', padx=(8, 4), pady=3)
        self.emb_model = ttk.Combobox(inner, values=['openl3', 'clap', 'hubert'],
                                       state='readonly', width=15, font=('Segoe UI', 9))
        self.emb_model.grid(row=1, column=1, sticky='w', padx=4, pady=3)
        self.emb_model.set(emb_cfg.get('model', 'openl3'))

        self.emb_dim = self._param_row(inner, "嵌入维度:",
                                        str(emb_cfg.get('embedding_size', 512)), 2, 10)

        self._run_button(panel, "🧬 计算嵌入", self._do_embedding)

    def _do_embedding(self):
        def task():
            from pipeline.step7_embedding import EmbeddingExtractor
            computer = EmbeddingExtractor(CONFIG)
            computer.run(self.emb_clips.get())
        self._run_in_thread(task, task_name="嵌入计算 Step7")

    # =========================================================================
    #  🫧 聚类去重面板
    # =========================================================================
    def _build_clustering_panel(self):
        panel = self._create_panel('clustering', '🫧 聚类与去重 (Step 8)')

        card = self._card(panel, '聚类参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        cl_cfg = CONFIG.get('clustering', {})
        tk.Label(inner, text="聚类方法:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', padx=(8, 4), pady=3)
        self.cl_method = ttk.Combobox(inner, values=['hdbscan', 'kmeans', 'agglomerative'],
                                       state='readonly', width=15, font=('Segoe UI', 9))
        self.cl_method.grid(row=0, column=1, sticky='w', padx=4, pady=3)
        self.cl_method.set(cl_cfg.get('method', 'hdbscan'))

        self.cl_min_cluster = self._param_row(inner, "最小簇大小:",
                                               str(cl_cfg.get('min_cluster_size', 3)), 1, 10)
        self.cl_dedup = self._param_row(inner, "去重阈值:",
                                         str(cl_cfg.get('dedup_threshold', 0.95)), 2, 10)

        self._run_button(panel, "🫧 运行聚类", self._do_clustering)

    def _do_clustering(self):
        def task():
            from pipeline.step8_clustering import AudioClusterer
            manager = AudioClusterer(CONFIG)
            manager.run()
        self._run_in_thread(task, task_name="聚类去重 Step8")

    # =========================================================================
    #  🎯 主动学习面板
    # =========================================================================
    def _build_active_learning_panel(self):
        panel = self._create_panel('active_learning', '🎯 主动学习 (Step 9)')

        card = self._card(panel, '主动学习参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        al_cfg = CONFIG.get('active_learning', {})

        tk.Label(inner, text="策略:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', padx=(8, 4), pady=3)
        self.al_strategy = ttk.Combobox(inner,
                                         values=['uncertainty', 'diversity', 'uncertainty_diversity'],
                                         state='readonly', width=25, font=('Segoe UI', 9))
        self.al_strategy.grid(row=0, column=1, sticky='w', padx=4, pady=3)
        self.al_strategy.set(al_cfg.get('strategy', 'uncertainty_diversity'))

        self.al_batch = self._param_row(inner, "批次大小:",
                                         str(al_cfg.get('batch_size', 50)), 1, 10)
        self.al_uncertainty_w = self._param_row(inner, "不确定性权重:",
                                                  str(al_cfg.get('uncertainty_weight', 0.7)), 2, 10)

        self._run_button(panel, "🎯 选择标注样本", self._do_active_learning)

    def _do_active_learning(self):
        def task():
            from pipeline.step9_active_learning import ActiveLearningScheduler
            learner = ActiveLearningScheduler(CONFIG)
            learner.run(batch_size=int(self.al_batch.get()))
        self._run_in_thread(task, task_name="主动学习 Step9")

    # =========================================================================
    #  � 人工审核面板 (Step 10)
    # =========================================================================
    def _build_human_review_panel(self):
        panel = self._create_panel('human_review', '🔍 人工审核 (Step 10)')

        # ------------- 工具栏 -------------
        toolbar = tk.Frame(panel, bg=self.colors['bg'])
        toolbar.pack(fill=tk.X, pady=(0, 4))

        tk.Button(toolbar, text="🔄 加载切片", command=self._review_load_clips,
                  bg=self.colors['accent'], fg='white', relief='flat',
                  padx=10, pady=3, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=2)

        tk.Label(toolbar, text="  筛选状态:", bg=self.colors['bg'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(8, 2))
        self.rv_status_filter = ttk.Combobox(
            toolbar, values=['全部', '⏳待审核', '✅已通过', '❌已拒绝'],
            state='readonly', width=10, font=('Segoe UI', 9))
        self.rv_status_filter.pack(side=tk.LEFT, padx=2)
        self.rv_status_filter.set('全部')
        self.rv_status_filter.bind('<<ComboboxSelected>>', lambda e: self._review_apply_filter())

        tk.Label(toolbar, text="  筛选标签:", bg=self.colors['bg'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(8, 2))
        primary_labels = CONFIG.get('labels', {}).get('primary', [])
        self.rv_label_filter = ttk.Combobox(
            toolbar, values=['全部'] + primary_labels,
            state='readonly', width=12, font=('Segoe UI', 9))
        self.rv_label_filter.pack(side=tk.LEFT, padx=2)
        self.rv_label_filter.set('全部')
        self.rv_label_filter.bind('<<ComboboxSelected>>', lambda e: self._review_apply_filter())

        # 批量操作
        tk.Button(toolbar, text="⚡ 高置信度自动通过", command=self._review_batch_approve,
                  bg='#059669', fg='white', relief='flat',
                  padx=8, pady=3, font=('Segoe UI', 8)).pack(side=tk.RIGHT, padx=2)
        tk.Button(toolbar, text="🗑️ 自动拒绝无效", command=self._review_batch_reject,
                  bg=self.colors['danger'], fg='white', relief='flat',
                  padx=8, pady=3, font=('Segoe UI', 8)).pack(side=tk.RIGHT, padx=2)

        # ------------- 统计栏 -------------
        stats_bar = tk.Frame(panel, bg='#e2e8f0', relief='groove', bd=1)
        stats_bar.pack(fill=tk.X, pady=(0, 4))

        self.rv_stats = {}
        for key, label, color in [
            ('total', '总计: 0', self.colors['text']),
            ('pending', '⏳待审: 0', self.colors['warning']),
            ('approved', '✅通过: 0', self.colors['success']),
            ('rejected', '❌拒绝: 0', self.colors['danger']),
            ('progress', '进度: 0%', self.colors['accent']),
        ]:
            lbl = tk.Label(stats_bar, text=label, bg='#e2e8f0', fg=color,
                           font=('Segoe UI', 9, 'bold'), padx=12, pady=4)
            lbl.pack(side=tk.LEFT)
            self.rv_stats[key] = lbl

        # ------------- 主体: 左列表 + 右详情 -------------
        body = tk.PanedWindow(panel, orient=tk.HORIZONTAL, bg=self.colors['bg'],
                               sashwidth=4, sashrelief='raised')
        body.pack(fill=tk.BOTH, expand=True)

        # ---- 左侧: 切片列表 ----
        list_frame = tk.Frame(body, bg=self.colors['card_bg'])
        body.add(list_frame, width=480, minsize=300)

        cols = ('idx', 'clip_id', 'label', 'conf', 'tags', 'status')
        self.rv_tree = ttk.Treeview(list_frame, columns=cols, show='headings',
                                     selectmode='browse', height=16)
        self.rv_tree.heading('idx', text='#')
        self.rv_tree.heading('clip_id', text='切片ID')
        self.rv_tree.heading('label', text='主标签')
        self.rv_tree.heading('conf', text='置信度')
        self.rv_tree.heading('tags', text='辅标签')
        self.rv_tree.heading('status', text='审核')

        self.rv_tree.column('idx', width=35, anchor='center')
        self.rv_tree.column('clip_id', width=160)
        self.rv_tree.column('label', width=80)
        self.rv_tree.column('conf', width=55, anchor='center')
        self.rv_tree.column('tags', width=100)
        self.rv_tree.column('status', width=55, anchor='center')

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                   command=self.rv_tree.yview)
        self.rv_tree.configure(yscrollcommand=scrollbar.set)

        self.rv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.rv_tree.bind('<<TreeviewSelect>>', self._review_on_select)

        # Treeview 样式 - 审核状态着色
        self.rv_tree.tag_configure('approved', background='#d1fae5')
        self.rv_tree.tag_configure('rejected', background='#fee2e2')
        self.rv_tree.tag_configure('pending', background='#ffffff')

        # ---- 右侧: 详情面板 ----
        detail_frame = tk.Frame(body, bg=self.colors['card_bg'])
        body.add(detail_frame, width=420, minsize=320)

        # 滚动容器
        detail_canvas = tk.Canvas(detail_frame, bg=self.colors['card_bg'],
                                   highlightthickness=0)
        detail_scroll = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL,
                                       command=detail_canvas.yview)
        self.rv_detail = tk.Frame(detail_canvas, bg=self.colors['card_bg'])
        self.rv_detail.bind('<Configure>',
                            lambda e: detail_canvas.configure(
                                scrollregion=detail_canvas.bbox('all')))
        detail_canvas.create_window((0, 0), window=self.rv_detail, anchor='nw')
        detail_canvas.configure(yscrollcommand=detail_scroll.set)
        detail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        d = self.rv_detail  # shortcut

        # -- 文件信息 + 播放器 --
        info_card = tk.LabelFrame(d, text=' 🎵 当前切片 ', bg=self.colors['card_bg'],
                                   fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                                   relief='groove', bd=1)
        info_card.pack(fill=tk.X, padx=6, pady=(6, 4))

        self.rv_clip_info = tk.Label(info_card, text="请先加载切片并选择一条",
                                      bg=self.colors['card_bg'], fg=self.colors['text_muted'],
                                      font=('Segoe UI', 9), wraplength=380, justify='left')
        self.rv_clip_info.pack(fill=tk.X, padx=8, pady=4)

        player_row = tk.Frame(info_card, bg=self.colors['card_bg'])
        player_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Button(player_row, text="▶ 播放", command=self._review_play,
                  bg='#6366f1', fg='white', relief='flat', padx=12, pady=2,
                  font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Button(player_row, text="⏹ 停止", command=self._review_stop,
                  bg='#64748b', fg='white', relief='flat', padx=12, pady=2,
                  font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=2)

        # -- 自动标签（只读展示） --
        auto_card = tk.LabelFrame(d, text=' 🤖 自动标签 ', bg=self.colors['card_bg'],
                                   fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                                   relief='groove', bd=1)
        auto_card.pack(fill=tk.X, padx=6, pady=4)

        self.rv_auto_label = tk.Label(auto_card, text="-",
                                       bg=self.colors['card_bg'], fg=self.colors['text'],
                                       font=('Consolas', 9), wraplength=380, justify='left')
        self.rv_auto_label.pack(fill=tk.X, padx=8, pady=6)

        # -- 修改标签区域 --
        edit_card = tk.LabelFrame(d, text=' ✏️ 修改标签 (可选)', bg=self.colors['card_bg'],
                                   fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                                   relief='groove', bd=1)
        edit_card.pack(fill=tk.X, padx=6, pady=4)

        # 主标签下拉
        plbl_row = tk.Frame(edit_card, bg=self.colors['card_bg'])
        plbl_row.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(plbl_row, text="主标签:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.rv_primary_combo = ttk.Combobox(
            plbl_row, values=primary_labels, state='readonly',
            width=14, font=('Segoe UI', 9))
        self.rv_primary_combo.pack(side=tk.LEFT, padx=8)

        # 辅标签复选框
        stag_lbl = tk.Label(edit_card, text="辅标签:", bg=self.colors['card_bg'],
                             font=('Segoe UI', 9))
        stag_lbl.pack(anchor='w', padx=8, pady=(4, 0))
        stag_frame = tk.Frame(edit_card, bg=self.colors['card_bg'])
        stag_frame.pack(fill=tk.X, padx=8, pady=2)
        secondary_labels = CONFIG.get('labels', {}).get('secondary', [])
        self.rv_secondary_vars = {}
        for i, tag in enumerate(secondary_labels):
            var = tk.BooleanVar(value=False)
            self.rv_secondary_vars[tag] = var
            tk.Checkbutton(stag_frame, text=tag, variable=var,
                           bg=self.colors['card_bg'], font=('Segoe UI', 8)).grid(
                row=i // 3, column=i % 3, sticky='w', padx=4, pady=1)

        # 质量旗标复选框
        qflag_lbl = tk.Label(edit_card, text="质量旗标:", bg=self.colors['card_bg'],
                              font=('Segoe UI', 9))
        qflag_lbl.pack(anchor='w', padx=8, pady=(4, 0))
        qflag_frame = tk.Frame(edit_card, bg=self.colors['card_bg'])
        qflag_frame.pack(fill=tk.X, padx=8, pady=2)
        quality_labels = CONFIG.get('labels', {}).get('quality_flags', [])
        self.rv_quality_vars = {}
        for i, flag in enumerate(quality_labels):
            var = tk.BooleanVar(value=False)
            self.rv_quality_vars[flag] = var
            tk.Checkbutton(qflag_frame, text=flag, variable=var,
                           bg=self.colors['card_bg'], font=('Segoe UI', 8)).grid(
                row=i // 3, column=i % 3, sticky='w', padx=4, pady=1)

        # -- 备注 --
        notes_row = tk.Frame(edit_card, bg=self.colors['card_bg'])
        notes_row.pack(fill=tk.X, padx=8, pady=(4, 6))
        tk.Label(notes_row, text="备注:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.rv_notes = tk.Entry(notes_row, width=36, font=('Segoe UI', 9))
        self.rv_notes.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        # -- 审核操作按钮 --
        action_card = tk.LabelFrame(d, text=' ⚡ 审核操作 ', bg=self.colors['card_bg'],
                                     fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                                     relief='groove', bd=1)
        action_card.pack(fill=tk.X, padx=6, pady=4)

        btn_row = tk.Frame(action_card, bg=self.colors['card_bg'])
        btn_row.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(btn_row, text="✅ 通过 (A)", command=self._review_approve,
                  bg=self.colors['success'], fg='white', relief='flat',
                  padx=16, pady=6, font=('Segoe UI', 10, 'bold'),
                  cursor='hand2').pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="❌ 拒绝 (R)", command=self._review_reject,
                  bg=self.colors['danger'], fg='white', relief='flat',
                  padx=16, pady=6, font=('Segoe UI', 10, 'bold'),
                  cursor='hand2').pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="⏭ 跳过 (S)", command=self._review_skip,
                  bg='#64748b', fg='white', relief='flat',
                  padx=16, pady=6, font=('Segoe UI', 10, 'bold'),
                  cursor='hand2').pack(side=tk.LEFT, padx=4)

        nav_row = tk.Frame(action_card, bg=self.colors['card_bg'])
        nav_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Button(nav_row, text="◀ 上一条", command=self._review_prev,
                  bg=self.colors['card_bg'], fg=self.colors['text'], relief='groove',
                  padx=10, pady=2, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(nav_row, text="下一条 ▶", command=self._review_next,
                  bg=self.colors['card_bg'], fg=self.colors['text'], relief='groove',
                  padx=10, pady=2, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)

        # 快捷键提示
        shortcut_label = tk.Label(action_card,
                                   text="快捷键: A=通过  R=拒绝  S=跳过  Space=播放  ← →=切换",
                                   bg=self.colors['card_bg'], fg=self.colors['text_muted'],
                                   font=('Segoe UI', 8))
        shortcut_label.pack(fill=tk.X, padx=8, pady=(0, 6))

        # ------------- 内部数据 -------------
        self._rv_clips = []       # 当前已加载的切片列表
        self._rv_index = -1       # 当前选中索引
        self._rv_manager = None   # HumanReviewManager 实例
        self._rv_playing = False  # 音频播放状态

        # ------------- 键盘快捷键 -------------
        self.bind('<Key>', self._review_on_key)

    # ----- 审核面板: 数据加载 -----
    def _review_get_manager(self):
        """延迟初始化 HumanReviewManager"""
        if self._rv_manager is None:
            from pipeline.step10_human_review import HumanReviewManager
            self._rv_manager = HumanReviewManager(CONFIG)
        return self._rv_manager

    def _review_load_clips(self):
        """加载切片到列表"""
        manager = self._review_get_manager()

        # 解析过滤条件
        status_map = {'全部': None, '⏳待审核': 'pending', '✅已通过': 'approved', '❌已拒绝': 'rejected'}
        status = status_map.get(self.rv_status_filter.get())
        label = self.rv_label_filter.get()
        if label == '全部':
            label = None

        self._rv_clips = manager.load_clips_for_review(
            status_filter=status, label_filter=label)

        self._review_populate_tree()
        self._review_update_stats()

        if self._rv_clips:
            self._rv_index = 0
            self.rv_tree.selection_set(self.rv_tree.get_children()[0])
        else:
            self._rv_index = -1

        self._log_info(f"🔍 已加载 {len(self._rv_clips)} 条切片用于审核")

    def _review_apply_filter(self):
        """切换筛选条件时重新加载"""
        if self._rv_manager is not None:
            self._review_load_clips()

    def _review_populate_tree(self):
        """填充 Treeview"""
        self.rv_tree.delete(*self.rv_tree.get_children())
        for i, clip in enumerate(self._rv_clips):
            status_str = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}.get(
                clip.get('review_status', 'pending'), '⏳')
            tags_str = ', '.join(clip.get('final_secondary_tags', [])[:3])
            conf = clip.get('confidence', 0)
            tag = clip.get('review_status', 'pending')

            self.rv_tree.insert('', tk.END, iid=str(i), values=(
                i + 1,
                clip.get('clip_id', ''),
                clip.get('suggested_label', '?'),
                f"{conf:.2f}",
                tags_str or '-',
                status_str,
            ), tags=(tag,))

    def _review_update_stats(self):
        """更新统计栏"""
        manager = self._review_get_manager()
        stats = manager.get_stats()
        self.rv_stats['total'].config(text=f"总计: {stats['total']}")
        self.rv_stats['pending'].config(text=f"⏳待审: {stats['pending']}")
        self.rv_stats['approved'].config(text=f"✅通过: {stats['approved']}")
        self.rv_stats['rejected'].config(text=f"❌拒绝: {stats['rejected']}")
        self.rv_stats['progress'].config(text=f"进度: {stats['progress_pct']:.1f}%")

    # ----- 审核面板: 选中 & 详情 -----
    def _review_on_select(self, event=None):
        """Treeview 选中事件"""
        sel = self.rv_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self._rv_index = idx
        self._review_show_detail(idx)

    def _review_show_detail(self, idx: int):
        """展示选中切片的详情"""
        if idx < 0 or idx >= len(self._rv_clips):
            return

        clip = self._rv_clips[idx]
        clip_id = clip.get('clip_id', '')
        conf = clip.get('confidence', 0)
        label = clip.get('suggested_label', '?')
        duration = clip.get('duration', clip.get('t1', 0))

        # 文件信息
        file_path = clip.get('file_path', '')
        if not file_path:
            clips_dir = Path(CONFIG.get('paths', {}).get('clips', 'data/clips'))
            file_path = str(clips_dir / f"{clip_id}.wav")
        exists = Path(file_path).exists() if file_path else False

        info_text = (
            f"📂 {clip_id}\n"
            f"路径: {file_path}\n"
            f"时长: {duration or '?'}s  |  文件{'存在 ✓' if exists else '不存在 ✗'}\n"
            f"冲突度: {clip.get('conflict_score', 0):.2f}  |  "
            f"来源数: {clip.get('source_count', 0)}  |  "
            f"需复审: {'是 ⚠️' if clip.get('needs_review') else '否'}"
        )
        self.rv_clip_info.config(text=info_text)

        # 自动标签展示
        top3 = clip.get('top3_labels', [])
        top3_text = '  '.join(f"{t['label']}({t['prob']:.2f})" for t in top3) if top3 else label
        secondary = clip.get('secondary_tags', {})
        if isinstance(secondary, dict):
            sec_text = ', '.join(f"{k}({v:.2f})" for k, v in secondary.items()) or '-'
        else:
            sec_text = ', '.join(secondary) if secondary else '-'
        qflags = clip.get('quality_flags', [])
        qflag_text = ', '.join(qflags) if qflags else '-'

        auto_text = (
            f"主标签: {label} (置信度 {conf:.3f})\n"
            f"Top3: {top3_text}\n"
            f"辅标签: {sec_text}\n"
            f"质量旗标: {qflag_text}"
        )
        self.rv_auto_label.config(text=auto_text)

        # 填充编辑区域（使用审核后的值或自动标签值）
        final_primary = clip.get('final_primary_label', label)
        self.rv_primary_combo.set(final_primary)

        # 辅标签复选框
        final_secondary = set(clip.get('final_secondary_tags', []))
        for tag, var in self.rv_secondary_vars.items():
            var.set(tag in final_secondary)

        # 质量旗标复选框
        final_quality = set(clip.get('final_quality_flags', []))
        for flag, var in self.rv_quality_vars.items():
            var.set(flag in final_quality)

        # 备注
        self.rv_notes.delete(0, tk.END)
        self.rv_notes.insert(0, clip.get('reviewer_notes', ''))

    # ----- 审核面板: 音频播放 -----
    def _review_get_current_path(self) -> str:
        """获取当前选中切片的文件路径"""
        if self._rv_index < 0 or self._rv_index >= len(self._rv_clips):
            return ''
        clip = self._rv_clips[self._rv_index]
        fp = clip.get('file_path', '')
        if not fp:
            clips_dir = Path(CONFIG.get('paths', {}).get('clips', 'data/clips'))
            fp = str(clips_dir / f"{clip.get('clip_id', '')}.wav")
        return fp

    def _review_play(self):
        """播放当前切片音频"""
        fp = self._review_get_current_path()
        if not fp or not Path(fp).exists():
            self._log_error(f"音频文件不存在: {fp}")
            return
        try:
            import winsound
            winsound.PlaySound(fp, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self._rv_playing = True
        except ImportError:
            # 非 Windows: 尝试 subprocess
            import subprocess
            try:
                subprocess.Popen(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', fp])
                self._rv_playing = True
            except FileNotFoundError:
                self._log_error("无法播放音频: 请安装 ffplay 或在 Windows 上运行")

    def _review_stop(self):
        """停止播放"""
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except ImportError:
            pass
        self._rv_playing = False

    # ----- 审核面板: 提交操作 -----
    def _review_collect_edits(self) -> dict:
        """收集当前的编辑数据"""
        primary = self.rv_primary_combo.get()
        secondary = [tag for tag, var in self.rv_secondary_vars.items() if var.get()]
        quality = [flag for flag, var in self.rv_quality_vars.items() if var.get()]
        notes = self.rv_notes.get().strip()
        return {
            'primary_label': primary,
            'secondary_tags': secondary,
            'quality_flags': quality,
            'notes': notes,
        }

    def _review_submit(self, status: str):
        """提交审核并自动前进到下一条"""
        if self._rv_index < 0 or self._rv_index >= len(self._rv_clips):
            messagebox.showinfo("提示", "请先选择一条切片")
            return

        clip = self._rv_clips[self._rv_index]
        clip_id = clip['clip_id']
        edits = self._review_collect_edits()

        manager = self._review_get_manager()
        manager.submit_review(
            clip_id=clip_id,
            status=status,
            primary_label=edits['primary_label'],
            secondary_tags=edits['secondary_tags'],
            quality_flags=edits['quality_flags'],
            notes=edits['notes'],
        )

        # 更新本地数据
        clip['review_status'] = status
        clip['final_primary_label'] = edits['primary_label']
        clip['final_secondary_tags'] = edits['secondary_tags']
        clip['final_quality_flags'] = edits['quality_flags']
        clip['reviewer_notes'] = edits['notes']

        # 更新 Treeview 行
        status_str = {'approved': '✅', 'rejected': '❌'}.get(status, '⏳')
        iid = str(self._rv_index)
        self.rv_tree.item(iid, values=(
            self._rv_index + 1,
            clip_id,
            edits['primary_label'],
            f"{clip.get('confidence', 0):.2f}",
            ', '.join(edits['secondary_tags'][:3]) or '-',
            status_str,
        ), tags=(status,))

        # 更新统计
        self._review_update_stats()

        # 停止播放 & 自动前进
        self._review_stop()
        self._review_next()

    def _review_approve(self):
        self._review_submit('approved')

    def _review_reject(self):
        self._review_submit('rejected')

    def _review_skip(self):
        """跳过 (不更改状态，只前进到下一条)"""
        self._review_stop()
        self._review_next()

    # ----- 审核面板: 导航 -----
    def _review_next(self):
        """前进到下一条"""
        children = self.rv_tree.get_children()
        if not children:
            return
        new_idx = min(self._rv_index + 1, len(children) - 1)
        self._rv_index = new_idx
        self.rv_tree.selection_set(str(new_idx))
        self.rv_tree.see(str(new_idx))

    def _review_prev(self):
        """返回上一条"""
        if self._rv_index <= 0:
            return
        new_idx = self._rv_index - 1
        self._rv_index = new_idx
        self.rv_tree.selection_set(str(new_idx))
        self.rv_tree.see(str(new_idx))

    # ----- 审核面板: 批量操作 -----
    def _review_batch_approve(self):
        """批量通过高置信度切片"""
        threshold = 0.92
        if not messagebox.askyesno("批量通过",
            f"将自动通过置信度 ≥ {threshold} 且无冲突的待审核切片。\n继续？"):
            return

        def task():
            manager = self._review_get_manager()
            count = manager.batch_approve_high_confidence(min_confidence=threshold)
            self._log_info(f"✅ 批量自动通过: {count} 条")

        self._run_in_thread(task, task_name="批量自动通过")
        # 延迟刷新列表
        self.after(2000, self._review_load_clips)

    def _review_batch_reject(self):
        """批量拒绝无效切片"""
        if not messagebox.askyesno("批量拒绝",
            "将自动拒绝标签为 Invalid 或有多项严重质量问题的切片。\n继续？"):
            return

        def task():
            manager = self._review_get_manager()
            count = manager.batch_reject_invalid()
            self._log_info(f"❌ 批量自动拒绝: {count} 条")

        self._run_in_thread(task, task_name="批量自动拒绝")
        self.after(2000, self._review_load_clips)

    # ----- 审核面板: 键盘快捷键 -----
    def _review_on_key(self, event):
        """全局键盘快捷键处理"""
        # 仅在审核面板激活时生效
        if getattr(self, '_active_panel', '') != 'human_review':
            return

        # 如果焦点在输入框（Entry/Text），不拦截字母键
        focused = self.focus_get()
        is_typing = isinstance(focused, (tk.Entry, tk.Text, ttk.Entry))

        key = event.keysym.lower()

        if key == 'space' and not is_typing:
            if self._rv_playing:
                self._review_stop()
            else:
                self._review_play()
            return 'break'

        if is_typing:
            return  # 输入框中不拦截字母

        if key == 'a':
            self._review_approve()
            return 'break'
        elif key == 'r':
            self._review_reject()
            return 'break'
        elif key == 's':
            self._review_skip()
            return 'break'
        elif key in ('right', 'down'):
            self._review_next()
            return 'break'
        elif key in ('left', 'up'):
            self._review_prev()
            return 'break'

    # ----- 导出面板: 审核状态提示 -----
    def _update_export_review_hint(self):
        """更新导出面板的审核状态提示文字"""
        try:
            from pipeline.step10_human_review import HumanReviewManager
            manager = HumanReviewManager(CONFIG)
            stats = manager.get_stats()
            hint = f"审核进度: {stats['approved']} 已通过 / {stats['total']} 总计 ({stats['progress_pct']:.0f}%)"
            self.exp_review_hint.config(text=hint)
        except Exception:
            self.exp_review_hint.config(text="（无法获取审核状态）")

    # =========================================================================
    #  �📦 数据导出面板
    # =========================================================================
    def _build_export_panel(self):
        panel = self._create_panel('export', '📦 数据导出')

        card = self._card(panel, '导出参数')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        self.exp_output = self._param_row(inner, "输出目录:", "data/export", 0)

        tk.Label(inner, text="格式:", bg=self.colors['card_bg'],
                 font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', padx=(8, 4), pady=3)
        self.exp_format = ttk.Combobox(inner, values=['json', 'csv', 'manifest'],
                                        state='readonly', width=15, font=('Segoe UI', 9))
        self.exp_format.grid(row=1, column=1, sticky='w', padx=4, pady=3)
        self.exp_format.set('json')

        self.exp_conf = self._param_row(inner, "最低置信度:", "0.6", 2, 10)
        self.exp_verified = tk.BooleanVar(value=False)
        tk.Checkbutton(inner, text="仅导出人工验证的", variable=self.exp_verified,
                       bg=self.colors['card_bg'], font=('Segoe UI', 9)).grid(
            row=3, column=1, sticky='w', padx=4, pady=3)

        self.exp_approved_only = tk.BooleanVar(value=True)
        tk.Checkbutton(inner, text="✅ 仅导出审核通过的切片 (推荐)", variable=self.exp_approved_only,
                       bg=self.colors['card_bg'], font=('Segoe UI', 9, 'bold'),
                       fg=self.colors['success']).grid(
            row=4, column=1, sticky='w', padx=4, pady=3)

        # 审核状态提示
        self.exp_review_hint = tk.Label(inner, text="",
                                         bg=self.colors['card_bg'], fg=self.colors['text_muted'],
                                         font=('Segoe UI', 8))
        self.exp_review_hint.grid(row=5, column=1, sticky='w', padx=4, pady=1)
        self._update_export_review_hint()

        self._run_button(panel, "📦 导出数据集", self._do_export)

    def _do_export(self):
        def task():
            if self.exp_approved_only.get():
                # 仅导出审核通过的切片
                from pipeline.step10_human_review import HumanReviewManager
                manager = HumanReviewManager(CONFIG)
                approved = manager.get_approved_clips()

                if not approved:
                    self._log_error("没有审核通过的切片可导出！请先在 [人工审核] 面板审核切片。")
                    return

                import json, csv
                from pathlib import Path
                output_dir = Path(self.exp_output.get())
                output_dir.mkdir(parents=True, exist_ok=True)
                fmt = self.exp_format.get()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                if fmt == 'json':
                    out_file = output_dir / f'dataset_approved_{timestamp}.json'
                    with open(out_file, 'w', encoding='utf-8') as f:
                        json.dump(approved, f, indent=2, ensure_ascii=False)
                elif fmt == 'csv':
                    out_file = output_dir / f'dataset_approved_{timestamp}.csv'
                    if approved:
                        with open(out_file, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=approved[0].keys())
                            writer.writeheader()
                            writer.writerows(approved)
                elif fmt == 'manifest':
                    out_file = output_dir / f'dataset_approved_{timestamp}.manifest'
                    with open(out_file, 'w', encoding='utf-8') as f:
                        for rec in approved:
                            entry = {
                                'audio_filepath': rec['file_path'],
                                'label': rec['primary_label'],
                                'secondary_tags': rec['secondary_tags'],
                                'quality_flags': rec['quality_flags'],
                                'duration': rec.get('duration') or 0,
                            }
                            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

                self._log_info(f"✅ 已导出 {len(approved)} 条审核通过切片 → {out_file}")
            else:
                from scripts.export_dataset import export_dataset
                export_dataset(
                    output_dir=self.exp_output.get(),
                    format=self.exp_format.get(),
                    min_confidence=float(self.exp_conf.get()),
                    only_verified=self.exp_verified.get()
                )
        self._run_in_thread(task, task_name="数据导出")

    # =========================================================================
    #  🏷️ Label Studio 面板
    # =========================================================================
    def _build_label_studio_panel(self):
        panel = self._create_panel('label_studio', '🏷️ Label Studio 集成')

        # 任务生成
        gen_card = self._card(panel, '生成标注任务')
        gen_inner = tk.Frame(gen_card, bg=self.colors['card_bg'])
        gen_inner.pack(fill=tk.X, padx=8, pady=8)

        self.ls_clips = self._param_row(gen_inner, "切片目录:", "data/clips", 0)
        self.ls_labels = self._param_row(gen_inner, "弱标签目录:", "data/labels", 1)
        self.ls_output = self._param_row(gen_inner, "输出文件:", "data/labelstudio_tasks.json", 2)
        self.ls_base_url = self._param_row(gen_inner, "音频Base URL:", "http://localhost:8000/audio", 3)

        self._run_button(gen_card, "📋 生成任务 JSON", self._do_gen_tasks)

        # Label Studio 连接
        conn_card = self._card(panel, 'Label Studio 连接')
        conn_inner = tk.Frame(conn_card, bg=self.colors['card_bg'])
        conn_inner.pack(fill=tk.X, padx=8, pady=8)

        ls_cfg = CONFIG.get('label_studio', {})
        self.ls_host = self._param_row(conn_inner, "LS 地址:",
                                        ls_cfg.get('host', 'http://localhost:8080'), 0)
        self.ls_api_key = self._param_row(conn_inner, "API Key:",
                                           ls_cfg.get('api_key', ''), 1)

        self._run_button(conn_card, "📤 导入到 Label Studio", self._do_import_ls)

    def _do_gen_tasks(self):
        def task():
            from scripts.prepare_labelstudio_tasks import prepare_tasks
            prepare_tasks(
                clips_dir=self.ls_clips.get(),
                labels_dir=self.ls_labels.get(),
                output_file=self.ls_output.get(),
                audio_base_url=self.ls_base_url.get()
            )
        self._run_in_thread(task, task_name="生成 Label Studio 任务")

    def _do_import_ls(self):
        def task():
            from scripts.import_to_labelstudio import import_to_labelstudio
            import_to_labelstudio(
                tasks_file=self.ls_output.get(),
            )
        self._run_in_thread(task, task_name="导入 Label Studio")

    # =========================================================================
    #  🧠 模型训练面板
    # =========================================================================
    def _build_training_panel(self):
        panel = self._create_panel('training', '🧠 模型训练')

        card = self._card(panel, '多任务模型训练')
        inner = tk.Frame(card, bg=self.colors['card_bg'])
        inner.pack(fill=tk.X, padx=8, pady=8)

        train_cfg = CONFIG.get('training', {})
        self.tr_epochs = self._param_row(inner, "Epochs:", "20", 0, 10)
        self.tr_batch = self._param_row(inner, "Batch Size:", "32", 1, 10)
        self.tr_lr = self._param_row(inner, "学习率:", "0.001", 2, 10)
        self.tr_p_weight = self._param_row(inner, "主标签损失权重:",
                                            str(train_cfg.get('primary_loss_weight', 0.7)), 3, 10)
        self.tr_s_weight = self._param_row(inner, "辅标签损失权重:",
                                            str(train_cfg.get('secondary_loss_weight', 0.2)), 4, 10)
        self.tr_q_weight = self._param_row(inner, "质量损失权重:",
                                            str(train_cfg.get('quality_loss_weight', 0.1)), 5, 10)

        # 模型架构信息
        arch_card = self._card(panel, '模型架构 (VibeSingMultiTaskModel)')
        arch_text = tk.Text(arch_card, height=5, wrap=tk.WORD, font=('Consolas', 8),
                            bg='#f1f5f9', fg=self.colors['text'])
        arch_text.pack(fill=tk.X, padx=8, pady=8)
        arch_text.insert(tk.END, "编码器: CNN (4×ConvBlock) → AdaptiveAvgPool → FC(512→256)\n")
        arch_text.insert(tk.END, f"主标签头: Linear(256→128→9) + softmax  [9类: {', '.join(CONFIG.get('labels', {}).get('primary', [])[:5])}...]\n")
        arch_text.insert(tk.END, f"辅标签头: Linear(256→64→10) + sigmoid  [10类: {', '.join(CONFIG.get('labels', {}).get('secondary', [])[:4])}...]\n")
        arch_text.insert(tk.END, f"质量旗标头: Linear(256→32→6) + sigmoid [6类: {', '.join(CONFIG.get('labels', {}).get('quality_flags', [])[:3])}...]\n")
        arch_text.insert(tk.END, "损失: 0.7×CE(primary) + 0.2×BCE(secondary) + 0.1×BCE(quality)\n")
        arch_text.configure(state='disabled')

        self._run_button(panel, "🧠 开始训练", self._do_train, color=self.colors['success'])

    def _do_train(self):
        def task():
            self._log_info("加载训练数据...")
            self._log_info(f"Epochs={self.tr_epochs.get()}, Batch={self.tr_batch.get()}, LR={self.tr_lr.get()}")
            self._log_info(f"损失权重: primary={self.tr_p_weight.get()}, secondary={self.tr_s_weight.get()}, quality={self.tr_q_weight.get()}")

            try:
                from models.multitask_model import VibeSingMultiTaskModel, train_epoch
                import torch

                model = VibeSingMultiTaskModel(
                    primary_class_weights=CONFIG.get('training', {}).get('primary_class_weights')
                )
                optimizer = torch.optim.Adam(model.parameters(), lr=float(self.tr_lr.get()))

                self._log_info(f"模型参数量: {sum(p.numel() for p in model.parameters()):,}")
                self._log_info("⚠️ 请确保已准备好训练数据集 (data/export/)")
                self._log_info("提示: 训练数据加载器需要根据实际数据格式实现")

            except Exception as e:
                self._log_error(f"模型初始化失败: {e}")

        self._run_in_thread(task, task_name="模型训练")

    # =========================================================================
    #  ⚙️ 系统设置面板
    # =========================================================================
    def _build_settings_panel(self):
        panel = self._create_panel('settings', '⚙️ 系统设置')

        # 路径配置
        paths_card = self._card(panel, '数据路径')
        paths_inner = tk.Frame(paths_card, bg=self.colors['card_bg'])
        paths_inner.pack(fill=tk.X, padx=8, pady=8)

        paths_cfg = CONFIG.get('paths', {})
        self.settings_paths = {}
        for i, (key, default) in enumerate([
            ('raw_videos', './data/raw_videos'),
            ('audio_raw', './data/raw_audios'),
            ('audio_clean', './data/audio_clean'),
            ('clips', './data/clips'),
            ('features', './data/features'),
            ('export', './data/export'),
        ]):
            entry = self._param_row(paths_inner, f"{key}:", paths_cfg.get(key, default), i)
            self.settings_paths[key] = entry
            tk.Button(paths_inner, text="📂", font=('Segoe UI', 8),
                      command=lambda e=entry: self._browse_dir(e)).grid(row=i, column=2, padx=4)

        # 数据库
        db_card = self._card(panel, '数据库')
        db_inner = tk.Frame(db_card, bg=self.colors['card_bg'])
        db_inner.pack(fill=tk.X, padx=8, pady=8)

        self.settings_db = self._param_row(db_inner, "连接字符串:",
                                            paths_cfg.get('metadata_db', 'sqlite:///./data/vibesing.db'), 0, 50)

        tk.Button(db_inner, text="🔄 重建数据库", command=self._rebuild_db,
                  bg=self.colors['danger'], fg='white', relief='flat',
                  padx=8, pady=2, font=('Segoe UI', 8)).grid(row=1, column=1, sticky='w', padx=4, pady=4)

        # API
        api_card = self._card(panel, 'API 服务')
        api_inner = tk.Frame(api_card, bg=self.colors['card_bg'])
        api_inner.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(api_inner, text="▶ 启动 FastAPI 服务", command=self._start_api,
                  bg=self.colors['success'], fg='white', relief='flat',
                  padx=12, pady=4, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(api_inner, text="📋 查看API文档", command=self._open_api_docs,
                  bg=self.colors['accent'], fg='white', relief='flat',
                  padx=12, pady=4, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)

    def _rebuild_db(self):
        if not messagebox.askyesno("确认", "重建数据库将清除所有数据。确定继续？"):
            return

        def task():
            from scripts.init_db import init_database
            init_database()
        self._run_in_thread(task, task_name="重建数据库")

    def _start_api(self):
        def task():
            import subprocess
            subprocess.Popen([sys.executable, '-m', 'uvicorn', 'api.main:app',
                              '--host', '0.0.0.0', '--port', '8000'],
                             cwd=str(ROOT))
            self._log_info("FastAPI 服务已启动: http://localhost:8000")
            self._log_info("API 文档: http://localhost:8000/docs")
        self._run_in_thread(task, task_name="启动 API")

    def _open_api_docs(self):
        import webbrowser
        webbrowser.open("http://localhost:8000/docs")


# =============================================================================
#  入口
# =============================================================================
def main():
    app = VibeSingApp()
    app.mainloop()


if __name__ == '__main__':
    main()
