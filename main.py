import sys
import os
import ctypes
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QObject, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QKeyEvent, QIcon, QPixmap, QMouseEvent, QCursor
from PyQt5.QtWidgets import (QApplication, QWidget, QLineEdit, QLabel, 
                            QVBoxLayout, QGraphicsOpacityEffect, QDesktopWidget,
                            QSystemTrayIcon, QMenu, QAction, QMessageBox, QHBoxLayout,
                            QPushButton, QSpacerItem, QSizePolicy)
import threading
import time
import logging
from command_helper import execute_command
from logging.handlers import RotatingFileHandler
import tempfile
import os

# 放到系统临时目录下，避免污染项目目录
log_path = os.path.join(tempfile.gettempdir(), 'smart_assistant.log')

# 日志轮转：最多 3 个文件，每个最多 2MB
file_handler = RotatingFileHandler(
    log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8'
)

logging.basicConfig(
    level=logging.INFO,  # 改成INFO，别用DEBUG了
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('SmartAssistant')

class FloatingBall(QWidget):
    """桌面浮动球，可拖动，点击显示搜索框"""
    clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        # 设置无边框、置顶、透明背景
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 窗口尺寸
        self.ball_size = 60
        self.setFixedSize(self.ball_size, self.ball_size)
        
        # 初始位置 - 屏幕右下角
        screen = QDesktopWidget().screenGeometry()
        self.move(screen.width() - self.ball_size - 20, screen.height() - self.ball_size - 80)
        
        # 鼠标跟踪
        self.dragging = False
        self.drag_position = QPoint()
        
        # 浮动动画
        self.float_animation = QPropertyAnimation(self, b"pos")
        self.float_animation.setDuration(2000)
        self.float_animation.setLoopCount(-1)  # 无限循环
        self.float_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 启动浮动动画
        self.start_float_animation()
        
        # 显示球体
        self.show()
        logger.info("浮动球已创建")

    def start_float_animation(self):
        """启动浮动动画：平滑上下浮动"""
        start_pos = self.pos()
        mid_pos = QPoint(start_pos.x(), start_pos.y() - 10)
        end_pos = QPoint(start_pos.x(), start_pos.y())
        
        # 使用关键帧实现平滑来回
        self.float_animation.setStartValue(start_pos)
        self.float_animation.setKeyValueAt(0.5, mid_pos)
        self.float_animation.setEndValue(end_pos)
        
        # 反向动画
        self.float_animation.valueChanged.connect(self.on_animation_value_changed)
        self.float_animation.start()

    def on_animation_value_changed(self, value):
        """动画值改变时，设置新位置"""
        self.move(value)

    def paintEvent(self, event):
        """绘制浮动球"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.setBrush(QBrush(QColor(59, 130, 246, 220)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.rect())
        
        # 绘制搜索图标
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(15, 15, 30, 30)
        
        # 绘制放大镜把手
        painter.setPen(QPen(QColor(255, 255, 255), 3))
        painter.drawLine(35, 35, 45, 45)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
            # 停止浮动动画
            self.float_animation.stop()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if self.dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
            
            # 如果是点击而非拖动，则触发点击信号
            if (event.globalPos() - (self.frameGeometry().topLeft() + self.drag_position)).manhattanLength() < 5:
                self.clicked.emit()
            
            # 重新启动浮动动画
            self.start_float_animation()

class DesktopOverlay(QWidget):
    """搜索框组件"""
    # 定义信号
    hide_overlay_signal = pyqtSignal()
    update_result_signal = pyqtSignal(str)
    
    def __init__(self, floating_ball):
        super().__init__()
        self.floating_ball = floating_ball
        
        # 连接信号
        self.hide_overlay_signal.connect(self.hide_overlay)
        self.update_result_signal.connect(self.update_result)
        
        # 设置无边框、置顶、透明背景
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 窗口尺寸
        self.width = 600
        self.height = 140  # 增加高度以适应输入框
        self.setFixedSize(self.width, self.height)
        
        # 初始位置 - 屏幕中央
        self.center_on_screen()
        
        # 鼠标跟踪
        self.dragging = False
        self.drag_position = QPoint()
        
        # 初始隐藏
        self.hide()
        self.is_visible = False
        self.is_searching = False
        
        # 初始化UI
        self.init_ui()
        
        logger.info("搜索框组件已初始化")
    
    def center_on_screen(self):
        """将窗口置于屏幕中央"""
        screen = QDesktopWidget().screenGeometry()
        self.move((screen.width() - self.width) // 2, (screen.height() - self.height) // 2)

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 标题栏（用于拖动）
        title_bar = QWidget()
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel("智能搜索")
        title_label.setStyleSheet("color: white; font-weight: bold;")
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                color: #ff5555;
            }
        """)
        close_btn.clicked.connect(self.hide_overlay_signal.emit)
        
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_btn)
        
        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入问题，按Enter搜索...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 30, 200);
                border: 2px solid #3B82F6;
                border-radius: 15px;
                padding: 12px 15px;  /* 增加上下内边距 */
                color: white;
                font-size: 16px;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-height: 30px;
            }
            QLineEdit:focus {
                border-color: #8B5CF6;
            }
        """)
        self.search_input.returnPressed.connect(self.execute_search)
        
        # 结果标签
        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: rgba(20, 20, 20, 180);
                border-radius: 10px;
                padding: 10px;
                color: #E0E0E0;
                font-size: 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        self.result_label.setWordWrap(True)
        self.result_label.setMinimumHeight(40)
        
        # 添加到主布局
        main_layout.addWidget(title_bar)
        main_layout.addWidget(self.search_input)
        main_layout.addWidget(self.result_label)
        self.setLayout(main_layout)
        
        # 设置透明度
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件（用于拖动窗口）"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件（拖动窗口）"""
        if self.dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()

    def show_overlay(self):
        """显示搜索框（切换显示状态）"""
        if self.is_visible:
            self.hide_overlay_signal.emit()
        else:
            logger.info("显示搜索框")
            self.is_visible = True
            
            # 居中显示
            self.center_on_screen()
            
            self.show()
            self.raise_()  # 确保窗口在最前面
            self.activateWindow()  # 激活窗口
            self.search_input.setFocus()
            self.search_input.setText("")
            self.result_label.setText("")
            self.is_searching = False
            
            # 创建显示动画
            self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.animation.setDuration(300)
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(0.95)
            self.animation.setEasingCurve(QEasingCurve.OutCubic)
            self.animation.start()

    def hide_overlay(self):
        """隐藏搜索框"""
        if self.is_visible:
            logger.info("隐藏搜索框")
            # 创建隐藏动画
            self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.animation.setDuration(300)
            self.animation.setStartValue(0.95)
            self.animation.setEndValue(0.0)
            self.animation.setEasingCurve(QEasingCurve.OutCubic)
            self.animation.finished.connect(self.hide_completely)
            self.animation.start()

    def hide_completely(self):
        """完全隐藏窗口"""
        logger.info("搜索框已完全隐藏")
        self.is_visible = False
        self.hide()

    def update_result(self, text):
        """更新结果标签"""
        self.result_label.setText(text)
        self.is_searching = False
        logger.info(f"搜索结果已更新: {text[:50]}...")

    def execute_search(self):
        """执行搜索命令"""
        if self.is_searching:
            logger.warning("搜索正在进行中，忽略新搜索请求")
            return
            
        query = self.search_input.text().strip()
        if query:
            logger.info(f"开始搜索: {query}")
            self.is_searching = True
            
            # 显示正在搜索状态
            self.result_label.setText("🔍 正在搜索...")
            QApplication.processEvents()  # 立即更新UI
            
            # 在新线程中执行搜索
            threading.Thread(target=self.perform_search, args=(query,), daemon=True).start()

    def perform_search(self, query):
        """执行搜索的线程函数"""
        try:
            logger.debug(f"执行搜索: {query}")
            result = execute_command(query)
            logger.debug(f"搜索完成: {result[:50]}...")
            self.update_result_signal.emit(result)
        except Exception as e:
            logger.error(f"搜索错误: {str(e)}")
            self.update_result_signal.emit(f"⚠️ 搜索出错: {str(e)}")
        
        # 5秒后自动隐藏
        QTimer.singleShot(5000, self.hide_overlay_signal.emit)

    def keyPressEvent(self, event: QKeyEvent):
        # ESC键关闭窗口
        if event.key() == Qt.Key_Escape:
            logger.debug("按下ESC键，隐藏搜索框")
            self.hide_overlay_signal.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        # 绘制半透明背景和边框
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明背景
        painter.setBrush(QBrush(QColor(10, 10, 10, 200)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)
        
        # 绘制边框
        painter.setPen(QPen(QColor(59, 130, 246, 150), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

def setup_tray_icon(app):
    """设置系统托盘图标"""
    logger.info("设置系统托盘图标")
    
    # 创建系统托盘图标
    tray = QSystemTrayIcon()
    
    # 创建托盘图标
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 绘制圆形背景
    painter.setBrush(QBrush(QColor(59, 130, 246)))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, 32, 32)
    
    # 绘制搜索图标
    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.drawEllipse(10, 10, 12, 12)
    
    # 绘制放大镜把手
    painter.setPen(QPen(QColor(255, 255, 255), 2))
    painter.drawLine(18, 18, 25, 25)
    
    painter.end()
    
    tray.setIcon(QIcon(pixmap))
    
    # 创建托盘菜单
    menu = QMenu()
    
    # 退出操作
    exit_action = QAction("退出程序")
    exit_action.triggered.connect(app.quit)
    
    menu.addAction(exit_action)
    tray.setContextMenu(menu)
    
    # 显示托盘图标
    tray.show()
    
    logger.info("托盘图标设置完成")
    return tray

def main():
    try:
        logger.info("启动应用程序")
        
        # 启用高DPI支持
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setQuitOnLastWindowClosed(False)  # 防止关闭窗口时退出应用
        
        # 创建浮动球
        floating_ball = FloatingBall()
        
        # 创建搜索框
        overlay = DesktopOverlay(floating_ball)
        
        # 连接浮动球点击事件
        floating_ball.clicked.connect(overlay.show_overlay)
        
        # 设置系统托盘图标
        tray = setup_tray_icon(app)
        
        # 显示启动提示
        try:
            tray.showMessage("智能助手", 
                            "程序已在后台运行\n点击桌面浮动球进行搜索", 
                            QSystemTrayIcon.Information, 
                            3000)
        except Exception as e:
            logger.warning(f"无法显示托盘通知: {str(e)}")
        
        logger.info("应用程序启动成功")
        sys.exit(app.exec_())
    
    except Exception as e:
        logger.exception("主函数未处理异常")
        # 显示错误消息框
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("程序错误")
        msg.setText(f"程序启动失败:\n{str(e)}")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

if __name__ == "__main__":
    main()