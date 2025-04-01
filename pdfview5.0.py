from PyQt5.QtWidgets import (QMainWindow, QToolBar, QAction, QVBoxLayout, 
                           QWidget, QPushButton, QFileDialog, QLabel, 
                           QColorDialog, QComboBox, QInputDialog, QHBoxLayout, 
                           QSizePolicy, QTextEdit, QScrollArea, QStackedLayout)
from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF, QByteArray, QSize, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QImage, QPen, qRgba
import fitz  # PyMuPDF

class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        # 윈도우 프레임 제거
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # 최소 창 크기 설정 (툴바 버튼들이 모두 보일 수 있는 크기)
        self.setMinimumSize(600, 400)  # 적절한 최소 크기 설정
        
        self.current_page = 0
        self.pdf_document = None
        self.zoom_factor = 1.0
        self.current_tool = None
        self.drawing = False
        self.start_pos = None
        self.current_color = QColor(255, 0, 0)
        self.annotations = {}
        self.opacity = 1.0  # 불투명도 초기값 추가
        self.is_maximized = False  # 최대화 상태 추적을 위한 변수 추가
        self.page_cache = {}  # 페이지 캐시를 저장할 딕셔너리 추가
        self.preload_thread = None  # 프리로딩 쓰레드
        self.render_dpi = 300  # 고품질 렌더링을 위한 DPI 설정
        self.selected_annotation = None  # 선택된 주석 저장
        self.is_selecting = False  # 선택 모드 상태 저장
        
        # 흑백 테마 스타일시트 적용
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QToolBar {
                background-color: #2d2d2d;
                border: none;
                spacing: 3px;
                padding: 3px;
            }
            QToolBar QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 5px;
            }
            QToolBar QToolButton:hover {
                background-color: #ff6b6b;
            }
            QToolBar QToolButton:checked {
                background-color: #ff6b6b;
            }
            QLabel {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: none;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: none;
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox:hover {
                background-color: #404040;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #404040;
            }
        """)
        
        # 아이콘 초기화
        self.icons = self.init_icons()
        
        self.initUI()
    
    def create_icon(self, svg_data):
        if svg_data.startswith('data:image/svg+xml;base64,'):
            svg_data = svg_data[len('data:image/svg+xml;base64,'):]
        
        # Base64 디코딩
        import base64
        svg_text = base64.b64decode(svg_data).decode('utf-8')
        
        # stroke 색상을 흰색으로 변경
        svg_text = svg_text.replace('stroke="currentColor"', 'stroke="white"')
        
        # 다시 Base64 인코딩
        svg_data = base64.b64encode(svg_text.encode('utf-8')).decode('utf-8')
        
        byte_array = QByteArray.fromBase64(svg_data.encode())
        pixmap = QPixmap()
        pixmap.loadFromData(byte_array)
        return QIcon(pixmap)
    
    def init_icons(self):
        return {
            'FOLDER_OPEN': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWZvbGRlci1vcGVuIj48cGF0aCBkPSJtNiAxNCAxLjUtMi45QTIgMiAwIDAgMSA5LjI0IDEwSDIwYTIgMiAwIDAgMSAxLjk0IDIuNWwtMS41NCA2YTIgMiAwIDAgMS0xLjk1IDEuNUg0YTIgMiAwIDAgMS0yLTJWNWEyIDIgMCAwIDEgMi0yaDMuOWEyIDIgMCAwIDEgMS42OS45bC44MSAxLjJhMiAyIDAgMCAwIDEuNjcuOUgxOGEyIDIgMCAwIDEgMiAydjIiLz48L3N2Zz4="),
            'SAVE': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXNhdmUiPjxwYXRoIGQ9Ik0xNS4yIDNhMiAyIDAgMCAxIDEuNC42bDMuOCAzLjhhMiAyIDAgMCAxIC42IDEuNFYxOWEyIDIgMCAwIDEtMiAySDVhMiAyIDAgMCAxLTItMlY1YTIgMiAwIDAgMSAyLTJ6Ii8+PHBhdGggZD0iTTE3IDIxdi03YTEgMSAwIDAgMC0xLTFIOGExIDEgMCAwIDAtMSAxdjciLz48cGF0aCBkPSJNNyAzdjRhMSAxIDAgMCAwIDEgMWg3Ii8+PC9zdmc+"),
            'CHEVRON_LEFT': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWNoZXZyb24tbGVmdCI+PHBhdGggZD0ibTE1IDE4LTYtNiA2LTYiLz48L3N2Zz4="),
            'CHEVRON_RIGHT': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWNoZXZyb24tcmlnaHQiPjxwYXRoIGQ9Im05IDE4IDYtNi02LTYiLz48L3N2Zz4="),
            'SELECT': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLW1vdXNlLXBvaW50ZXItY2xpY2siPjxwYXRoIGQ9Ik0xNCA0LjEgMTIgNiIvPjxwYXRoIGQ9Im01LjEgOC0yLjktLjgiLz48cGF0aCBkPSJtNiAxMi0xLjkgMiIvPjxwYXRoIGQ9Ik03LjIgMi4yIDggNS4xIi8+PHBhdGggZD0iTTkuMDM3IDkuNjlhLjQ5OC40OTggMCAwIDEgLjY1My0uNjUzbDExIDQuNWEuNS41IDAgMCAxLS4wNzQuOTQ5bC00LjM0OSAxLjA0MWExIDEgMCAwIDAtLjc0LjczOWwtMS4wNCA0LjM1YS41LjUgMCAwIDEtLjk1LjA3NHoiLz48L3N2Zz4="),
            'SQUARE': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjMiIHdpZHRoPSIxOCIgaGVpZ2h0PSIxOCIgcng9IjIiIHJ5PSIyIi8+PC9zdmc+"),
            'ARROW_RIGHT': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSI1IiB5MT0iMTIiIHgyPSIxOSIgeTI9IjEyIi8+PHBvbHlsaW5lIHBvaW50cz0iMTIgNSAxOSAxMiAxMiAxOSIvPjwvc3ZnPg=="),
            'TYPE': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjQgNyAxMCA3IDE2IDcgMjAgNyIvPjxsaW5lIHgxPSIxMiIgeTE9IjciIHgyPSIxMiIgeTI9IjIwIi8+PC9zdmc+"),
            'PALETTE': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTIiIHI9IjEwIi8+PGNpcmNsZSBjeD0iMTIiIGN5PSI4IiByPSIxIi8+PGNpcmNsZSBjeD0iOCIgY3k9IjEyIiByPSIxIi8+PGNpcmNsZSBjeD0iMTYiIGN5PSIxMiIgcj0iMSIvPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTYiIHI9IjEiLz48L3N2Zz4="),
            'close': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXgiPjxwYXRoIGQ9Ik0xOCA2IDYgMTgiLz48cGF0aCBkPSJtNiA2IDEyIDEyIi8+PC9zdmc+"),
            'window-minimize': self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLW1pbnVzIj48cGF0aCBkPSJNNSAxMmgxNCIvPjwvc3ZnPg=="),
            'window-maximum' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLW1heGltaXplIj48cGF0aCBkPSJNOCAzSDVhMiAyIDAgMCAwLTIgMnYzIi8+PHBhdGggZD0iTTIxIDhWNWEyIDIgMCAwIDAtMi0yaC0zIi8+PHBhdGggZD0iTTMgMTZ2M2EyIDIgMCAwIDAgMiAyaDMiLz48cGF0aCBkPSJNMTYgMjFoM2EyIDIgMCAwIDAgMi0ydi0zIi8+PC9zdmc+"),
            'window-small' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXBpY3R1cmUtaW4tcGljdHVyZSI+PHBhdGggZD0iTTIgMTBoNlY0Ii8+PHBhdGggZD0ibTIgNCA2IDYiLz48cGF0aCBkPSJNMjEgMTBWN2EyIDIgMCAwIDAtMi0yaC03Ii8+PHBhdGggZD0iTTMgMTR2MmEyIDIgMCAwIDAgMiAyaDMiLz48cmVjdCB4PSIxMiIgeT0iMTQiIHdpZHRoPSIxMCIgaGVpZ2h0PSI3IiByeD0iMSIvPjwvc3ZnPg=="),
            'rotate-ccw' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXJvdGF0ZS1jY3ciPjxwYXRoIGQ9Ik0zIDEyYTkgOSAwIDEgMCA5LTkgOS43NSA5Ljc1IDAgMCAwLTYuNzQgMi43NEwzIDgiLz48cGF0aCBkPSJNMyAzdjVoNSIvPjwvc3ZnPg=="),
            'roatate-cc' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXJvdGF0ZS1jdyI+PHBhdGggZD0iTTIxIDEyYTkgOSAwIDEgMS05LTljMi41MiAwIDQuOTMgMSA2Ljc0IDIuNzRMMjEgOCIvPjxwYXRoIGQ9Ik0yMSAzdjVoLTUiLz48L3N2Zz4="),
            'right_arrow' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWNoZXZyb25zLXJpZ2h0Ij48cGF0aCBkPSJtNiAxNyA1LTUtNS01Ii8+PHBhdGggZD0ibTEzIDE3IDUtNS01LTUiLz48L3N2Zz4="),
            'left_arrow' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWNoZXZyb25zLWxlZnQiPjxwYXRoIGQ9Im0xMSAxNy01LTUgNS01Ii8+PHBhdGggZD0ibTE4IDE3LTUtNSA1LTUiLz48L3N2Zz4="),
            'square-split-horizontal':self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXNxdWFyZS1zcGxpdC1ob3Jpem9udGFsIj48cGF0aCBkPSJNOCAxOUg1Yy0xIDAtMi0xLTItMlY3YzAtMSAxLTIgMi0yaDMiLz48cGF0aCBkPSJNMTYgNWgzYzEgMCAyIDEgMiAydjEwYzAgMS0xIDItMiAyaC0zIi8+PGxpbmUgeDE9IjEyIiB4Mj0iMTIiIHkxPSI0IiB5Mj0iMjAiLz48L3N2Zz4="),
            'settings' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXNldHRpbmdzIj48cGF0aCBkPSJNMTIuMjIgMmgtLjQ0YTIgMiAwIDAgMC0yIDJ2LjE4YTIgMiAwIDAgMS0xIDEuNzNsLS40My4yNWEyIDIgMCAwIDEtMiAwbC0uMTUtLjA4YTIgMiAwIDAgMC0yLjczLjczbC0uMjIuMzhhMiAyIDAgMCAwIC43MyAyLjczbC4xNS4xYTIgMiAwIDAgMSAxIDEuNzJ2LjUxYTIgMiAwIDAgMS0xIDEuNzRsLS4xNS4wOWEyIDIgMCAwIDAtLjczIDIuNzNsLjIyLjM4YTIgMiAwIDAgMC0yLjczLS43M2wtLjE1LjA4YTIgMiAwIDAgMS0yIDBsLS40My0uMjVhMiAyIDAgMCAxLTEtMS43M1Y0YTIgMiAwIDAgMC0yLTJ6Ii8+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyIvPjwvc3ZnPg=="),
            'list' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWxpc3QiPjxwYXRoIGQ9Ik0zIDEyaC4wMSIvPjxwYXRoIGQ9Ik0zIDE4aC4wMSIvPjxwYXRoIGQ9Ik0zIDZoLjAxIi8+PHBhdGggZD0iTTggMTJoMTMiLz48cGF0aCBkPSJNOCAxOGgxMyIvPjxwYXRoIGQ9Ik04IDZoMTMiLz48L3N2Zz4="),#주석리스트
            'lock' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWxvY2sta2V5aG9sZSI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxNiIgcj0iMSIvPjxyZWN0IHg9IjMiIHk9IjEwIiB3aWR0aD0iMTgiIGhlaWdodD0iMTIiIHJ4PSIyIi8+PHBhdGggZD0iTTcgMTBWN2E1IDUgMCAwIDEgMTAgMHYzIi8+PC9zdmc+"),
            'unlock' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWxvY2sta2V5aG9sZS1vcGVuIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjE2IiByPSIxIi8+PHJlY3Qgd2lkdGg9IjE4IiBoZWlnaHQ9IjEyIiB4PSIzIiB5PSIxMCIgcng9IjIiLz48cGF0aCBkPSJNNyAxMFY3YTUgNSAwIDAgMSA5LjMzLTIuNSIvPjwvc3ZnPg=="),
            'bookmark' :self.create_icon("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWJvb2ttYXJrIj48cGF0aCBkPSJtMTkgMjEtNy00LTcgNFY1YTIgMiAwIDAgMSAyLTJoMTBhMiAyIDAgMCAxIDIgMnYxNnoiLz48L3N2Zz4="),
            
        }
        
    def initUI(self):
        # 전체 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 메인 툴바 생성
        main_toolbar = self.addToolBar('메인')
        main_toolbar.setMovable(False)

        # 왼쪽 그룹 (파일 및 페이지 이동)
        left_group = QWidget()
        left_layout = QHBoxLayout(left_group)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        file_open = QAction('', self)
        file_open.setIcon(self.icons['FOLDER_OPEN'])
        file_open.triggered.connect(self.openfile)
        
        file_save = QAction('', self)
        file_save.setIcon(self.icons['SAVE'])
        file_save.triggered.connect(self.savePDF)
        
        prev_page = QAction('', self)
        next_page = QAction('', self)
        prev_page.setIcon(self.icons['CHEVRON_LEFT'])
        next_page.setIcon(self.icons['CHEVRON_RIGHT'])
        prev_page.triggered.connect(self.prevPage)
        next_page.triggered.connect(self.nextPage)

        # 회전 버튼 추가
        rotate_ccw = QAction('', self)
        rotate_ccw.setIcon(self.icons['rotate-ccw'])
        rotate_ccw.triggered.connect(lambda: self.rotatePage(-90))
        
        rotate_cw = QAction('', self)
        rotate_cw.setIcon(self.icons['roatate-cc'])
        rotate_cw.triggered.connect(lambda: self.rotatePage(90))
        
        main_toolbar.addAction(file_open)
        main_toolbar.addAction(file_save)
        main_toolbar.addAction(prev_page)
        main_toolbar.addAction(next_page)
        main_toolbar.addAction(rotate_ccw)
        main_toolbar.addAction(rotate_cw)

        # 첫 번째 스페이서 (왼쪽 그룹과 중앙 그룹 사이)
        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_toolbar.addWidget(left_spacer)

        # 중앙 그룹 (주석 도구들)
        tools = [
            ('선택', 'SELECT'),
            ('사각형', 'SQUARE'),
            ('화살표', 'ARROW_RIGHT'),
            ('텍스트', 'TYPE')
        ]

        # 도구 선택을 위한 변수 추가
        self.selected_tool = None
        
        # 도구 액션들을 저장할 딕셔너리 추가
        self.tool_actions = {}
        
        for tool_name, icon_name in tools:
            tool_action = QAction('', self)
            tool_action.setIcon(self.icons[icon_name])
            tool_action.setCheckable(True)
            if tool_name == '선택':
                tool_action.setShortcut('Shift+S')  # 선택 도구 단축키 추가
            tool_action.triggered.connect(lambda checked, t=tool_name: self.setTool(t))
            self.tool_actions[tool_name] = tool_action
            main_toolbar.addAction(tool_action)

        # 색상 선택 액션
        color_action = QAction('', self)
        color_action.setIcon(self.icons['PALETTE'])
        color_action.triggered.connect(self.selectColor)
        main_toolbar.addAction(color_action)

        # 두 번째 스페이서 (중앙 그룹과 오른쪽 그룹 사이)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_toolbar.addWidget(right_spacer)

        # 오른쪽 그룹 (창 컨트롤)
        self.max_button = QAction('', self)  # self로 저장하여 나중에 접근 가능하도록 함
        self.max_button.setIcon(self.icons['window-maximum'])
        self.max_button.triggered.connect(self.toggleMaximized)
        
        min_button = QAction('', self)
        min_button.setIcon(self.icons['window-minimize'])
        min_button.triggered.connect(self.showMinimized)
        
        close_button = QAction('', self)
        close_button.setIcon(self.icons['close'])
        close_button.triggered.connect(self.close)

        main_toolbar.addAction(min_button)
        main_toolbar.addAction(self.max_button)  # 최대화 버튼 추가
        main_toolbar.addAction(close_button)

        # PDF 표시 영역
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.pdf_label)
        
        # 잠금 버튼
        self.lock_button = QPushButton()
        self.lock_button.setIcon(self.icons['unlock'])
        self.lock_button.setFixedSize(48, 48)
        self.lock_button.setIconSize(QSize(24, 24))
        self.lock_button.clicked.connect(self.toggleLock)
        self.lock_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                width: 48px;
                height: 48px;
                max-width: 48px;
                max-height: 48px;
                min-width: 48px;
                min-height: 48px;
                padding: 0px;
                margin: 0px 15px 15px 0px;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
                border-radius: 24px;
                width: 48px;
                height: 48px;
                max-width: 48px;
                max-height: 48px;
                min-width: 48px;
                min-height: 48px;
                padding: 0px;
                margin: 0px 15px 15px 0px;
            }
        """)
        # 버튼을 우측 최하단에 배치
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.lock_button)
        main_layout.addLayout(button_layout)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # 잠금 상태 변수 추가
        self.is_locked = False

    def setTool(self, tool):
        # 이전에 선택된 도구의 체크 상태 해제
        if self.selected_tool and self.selected_tool in self.tool_actions:
            self.tool_actions[self.selected_tool].setChecked(False)
        
        # 새로운 도구 선택
        self.selected_tool = tool
        if tool in self.tool_actions:
            self.tool_actions[tool].setChecked(True)
        self.current_tool = tool

    def openfile(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "파일 선택", 
            "", 
            "PDF files (*.pdf);;Markdown files (*.md);;All files (*.*)"
        )
        if file_name:
            file_extension = file_name.lower().split('.')[-1]
            
            if file_extension == 'pdf':
                self.pdf_document = fitz.open(file_name)
                self.current_page = 0
                self.showPage()
            elif file_extension == 'md':
                try:
                    with open(file_name, 'r', encoding='utf-8') as f:
                        md_content = f.read()
                        
                    # markdown 텍스트를 HTML로 변환
                    import markdown
                    html_content = markdown.markdown(md_content)
                    
                    # QTextEdit를 사용하여 HTML 표시
                    text_view = QTextEdit()
                    text_view.setReadOnly(True)
                    text_view.setHtml(html_content)
                    
                    # 스타일시트 적용
                    text_view.setStyleSheet("""
                        QTextEdit {
                            background-color: #1a1a1a;
                            color: #ffffff;
                            border: none;
                            padding: 10px;
                        }
                    """)
                    
                    # 텍스트뷰를 PDF 레이블 대신 표시
                    self.pdf_label.hide()
                    layout = self.centralWidget().layout()
                    layout.addWidget(text_view)
                    
                    # PDF 관련 변수 초기화
                    self.pdf_document = None
                    self.current_page = 0
                    
                except Exception as e:
                    print(f"MD 파일 열기 오류: {str(e)}")

    def preload_pages(self):
        """백그라운드에서 모든 페이지를 고품질로 미리 렌더링"""
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        def render_page(page_num):
            try:
                page = self.pdf_document[page_num]
                # 고품질 렌더링을 위한 매트릭스 설정
                zoom_matrix = fitz.Matrix(self.zoom_factor * self.render_dpi/72, 
                                        self.zoom_factor * self.render_dpi/72)
                
                # 고품질 렌더링 옵션 설정
                pix = page.get_pixmap(
                    matrix=zoom_matrix,
                    alpha=False,
                    colorspace=fitz.csRGB
                )
                
                # QImage 변환 시 품질 유지
                qimage = QImage(pix.samples, pix.width, pix.height,
                              pix.stride, QImage.Format_RGB888)
                
                # 투명도 효과 적용
                if self.opacity < 1.0:
                    transparent_image = QImage(pix.width, pix.height, 
                                            QImage.Format_ARGB32)
                    for y in range(pix.height):
                        for x in range(pix.width):
                            color = qimage.pixelColor(x, y)
                            if color.red() > 240 and color.green() > 240 and color.blue() > 240:
                                color.setAlpha(int(self.opacity * 255))
                            transparent_image.setPixelColor(x, y, color)
                    qimage = transparent_image

                pixmap = QPixmap.fromImage(qimage)
                self.page_cache[page_num] = pixmap
                
            except Exception as e:
                print(f"페이지 {page_num} 렌더링 중 오류: {str(e)}")

        def preload_worker():
            with ThreadPoolExecutor(max_workers=2) as executor:  # 작업자 수 제한
                executor.map(render_page, range(len(self.pdf_document)))

        # 기존 쓰레드가 실행 중이면 중단
        if self.preload_thread and self.preload_thread.is_alive():
            return

        # 새로운 쓰레드에서 프리로딩 시작
        self.preload_thread = threading.Thread(target=preload_worker)
        self.preload_thread.daemon = True
        self.preload_thread.start()

    def showPage(self):
        if self.pdf_document is None:
            return
        
        try:
            # 캐시된 페이지가 있는지 확인
            if self.current_page in self.page_cache:
                pixmap = self.page_cache[self.current_page]
            else:
                # 페이지 새로 렌더링
                page = self.pdf_document[self.current_page]
                zoom_matrix = fitz.Matrix(self.zoom_factor * self.render_dpi/72, 
                                        self.zoom_factor * self.render_dpi/72)
                
                pix = page.get_pixmap(
                    matrix=zoom_matrix,
                    alpha=False,
                    colorspace=fitz.csRGB
                )
                
                qimage = QImage(pix.samples, pix.width, pix.height,
                              pix.stride, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)
                self.page_cache[self.current_page] = pixmap

            # 고품질 스케일링 적용
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * self.zoom_factor),
                int(pixmap.height() * self.zoom_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # 부드러운 스케일링 적용
            )

            # 투명도 적용을 위한 새 QPixmap 생성
            if self.opacity < 1.0:
                transparent_pixmap = QPixmap(pixmap.size())
                transparent_pixmap.fill(Qt.transparent)
                painter = QPainter(transparent_pixmap)
                painter.setOpacity(self.opacity)
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                pixmap = transparent_pixmap

            # 화면 크기에 맞게 조정
            screen = QApplication.primaryScreen()
            screen_size = screen.availableGeometry()
            toolbar = self.findChild(QToolBar)
            toolbar_height = toolbar.height() if toolbar else 0
            
            scaled_pixmap = pixmap.scaled(
                screen_size.width(),
                screen_size.height() - toolbar_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # 주석 그리기
            if self.current_page in self.annotations:
                painter = QPainter(scaled_pixmap)
                scale_factor_x = scaled_pixmap.width() / pixmap.width()
                scale_factor_y = scaled_pixmap.height() / pixmap.height()
                
                for i, ann in enumerate(self.annotations[self.current_page]):
                    # 선택된 주석은 다른 색으로 표시
                    if self.selected_annotation and self.selected_annotation[0] == self.current_page and self.selected_annotation[1] == i:
                        pen = QPen(QColor(255, 255, 0))  # 노란색으로 선택 표시
                        pen.setWidth(3)
                    else:
                        pen = QPen(ann['color'])
                        pen.setWidth(2)
                    painter.setPen(pen)
                    
                    start = QPointF(ann['start'].x() * scale_factor_x, 
                              ann['start'].y() * scale_factor_y)
                    end = QPointF(ann['end'].x() * scale_factor_x, 
                            ann['end'].y() * scale_factor_y)
                    
                    if ann['type'] == '사각형':
                        painter.drawRect(QRectF(start, end))
                    elif ann['type'] == '화살표':
                        painter.drawLine(start, end)
                    elif ann['type'] == '텍스트':
                        painter.drawText(start, ann['text'])
                painter.end()

            # PDF를 레이블에 표시
            self.pdf_label.setPixmap(scaled_pixmap)
            self.pdf_label.setMinimumSize(scaled_pixmap.width(), scaled_pixmap.height())
            
            # 창 크기 및 위치 조정
            if not self.is_maximized:
                window_width = scaled_pixmap.width()
                window_height = scaled_pixmap.height() + toolbar_height
                if self.pdf_label.pixmap() is None:
                    x = (screen_size.width() - window_width) // 2
                    y = (screen_size.height() - window_height) // 2
                    self.setGeometry(x, y, window_width, window_height)
                else:
                    current_geometry = self.geometry()  # 현재 창 위치 저장
                    self.resize(window_width, window_height)
                    self.move(current_geometry.x(), current_geometry.y())
            
            if self.is_maximized:
                self.showMaximized()

        except Exception as e:
            print(f"페이지 표시 중 오류 발생: {str(e)}")

    def prevPage(self):
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.showPage()

    def nextPage(self):
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.showPage()
            

    def addAnnotation(self):
        # 주석 추가 기능 구현
        # TODO: 주석 추가 대화상자 표시 및 저장 기능 구현
        pass

    def wheelEvent(self, event):
        # 잠금 상태에서는 Shift + 휠(투명도 조절)만 허용
        if self.is_locked:
            if event.modifiers() == Qt.ShiftModifier:
                self.wheelEvent_opacity(event)
            return
        
        # 잠금 해제 상태에서는 모든 기능 허용
        if event.modifiers() == Qt.ControlModifier and self.pdf_document:
            self.wheelEvent_zoom(event)
        elif event.modifiers() == Qt.ShiftModifier:
            self.wheelEvent_opacity(event)
        else:
            if self.pdf_document:
                delta = event.angleDelta().y()
                if delta > 0 and self.current_page > 0:
                    self.prevPage()
                elif delta < 0 and self.current_page < len(self.pdf_document) - 1:
                    self.nextPage()

    def wheelEvent_zoom(self, event):
        # 현재 레이블과 픽맵의 크기 가져오기
        label_rect = self.pdf_label.rect()
        current_pixmap = self.pdf_label.pixmap()
        if not current_pixmap:
            return

        # 마우스 위치를 레이블 좌표계로 변환
        mouse_pos = self.pdf_label.mapFrom(self, event.pos())
        
        # PDF 영역 내에 마우스가 있는지 확인
        is_mouse_over_pdf = self.pdf_label.rect().contains(mouse_pos)
        
        # 마우스 위치의 상대적 비율 계산 (0~1 사이)
        if is_mouse_over_pdf:
            rel_x = mouse_pos.x() / label_rect.width()
            rel_y = mouse_pos.y() / label_rect.height()
        else:
            # PDF 영역 밖이면 중앙 기준
            rel_x = 0.5
            rel_y = 0.5

        # 확대/축소 계산
        delta = event.angleDelta().y()
        zoom_change = 1.2 if delta > 0 else 0.8
        new_zoom = max(0.1, min(5.0, self.zoom_factor * zoom_change))

        if new_zoom != self.zoom_factor:
            self.zoom_factor = new_zoom
            
            # 캐시된 원본 이미지 사용
            if self.current_page in self.page_cache:
                self._update_zoomed_page(rel_x, rel_y, event.pos())
            else:
                self.showPage()

    def wheelEvent_opacity(self, event):
        delta = event.angleDelta().y()
        old_opacity = self.opacity
        
        if delta > 0:
            self.opacity = min(1.0, self.opacity + 0.1)
        else:
            self.opacity = max(0.1, self.opacity - 0.1)
        
        if old_opacity != self.opacity:
            # 창 자체의 투명도 설정
            self.setWindowOpacity(self.opacity)
            
            # 현재 표시된 pixmap 가져오기
            current_pixmap = self.pdf_label.pixmap()
            if current_pixmap:
                # 현재 pixmap의 크기를 그대로 유지하면서 투명도만 적용
                transparent_pixmap = QPixmap(current_pixmap.size())
                transparent_pixmap.fill(Qt.transparent)
                
                painter = QPainter(transparent_pixmap)
                painter.setOpacity(1.0)  # PDF 내용은 완전 불투명하게 유지
                painter.drawPixmap(0, 0, current_pixmap)
                
                # 주석 다시 그리기 (현재 크기 유지)
                if self.current_page in self.annotations:
                    for ann in self.annotations[self.current_page]:
                        pen = QPen(ann['color'])
                        pen.setWidth(2)
                        painter.setPen(pen)
                        
                        # 현재 표시된 크기 기준으로 주석 위치 계산
                        scale_factor_x = current_pixmap.width() / self.page_cache[self.current_page].width()
                        scale_factor_y = current_pixmap.height() / self.page_cache[self.current_page].height()
                        
                        start = QPointF(ann['start'].x() * scale_factor_x,
                                      ann['start'].y() * scale_factor_y)
                        end = QPointF(ann['end'].x() * scale_factor_x,
                                    ann['end'].y() * scale_factor_y)
                        
                        if ann['type'] == '사각형':
                            painter.drawRect(QRectF(start, end))
                        elif ann['type'] == '화살표':
                            painter.drawLine(start, end)
                        elif ann['type'] == '텍스트':
                            painter.drawText(start, ann['text'])
                
                painter.end()
                
                # 현재 크기 그대로 pixmap 설정
                self.pdf_label.setPixmap(transparent_pixmap)

    def _update_zoomed_page(self, rel_x, rel_y, mouse_pos):
        original_pixmap = self.page_cache[self.current_page]
        
        # 새로운 크기 계산
        new_width = int(original_pixmap.width() * self.zoom_factor)
        new_height = int(original_pixmap.height() * self.zoom_factor)
        
        # 스케일 조정
        scaled_pixmap = original_pixmap.scaled(
            new_width,
            new_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # 투명도 적용
        if self.opacity < 1.0:
            transparent_pixmap = QPixmap(scaled_pixmap.size())
            transparent_pixmap.fill(Qt.transparent)
            painter = QPainter(transparent_pixmap)
            painter.setOpacity(self.opacity)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()
            scaled_pixmap = transparent_pixmap

        # 주석 다시 그리기
        if self.current_page in self.annotations:
            painter = QPainter(scaled_pixmap)
            for ann in self.annotations[self.current_page]:
                pen = QPen(ann['color'])
                pen.setWidth(2)
                painter.setPen(pen)
                
                start = QPointF(ann['start'].x() * self.zoom_factor,
                              ann['start'].y() * self.zoom_factor)
                end = QPointF(ann['end'].x() * self.zoom_factor,
                           ann['end'].y() * self.zoom_factor)
                
                if ann['type'] == '사각형':
                    painter.drawRect(QRectF(start, end))
                elif ann['type'] == '화살표':
                    painter.drawLine(start, end)
                elif ann['type'] == '텍스트':
                    painter.drawText(start, ann['text'])
            painter.end()

        # 새로운 스크롤 위치 계산
        scroll_area = self.pdf_label.parent()
        if isinstance(scroll_area, QScrollArea):
            # 새로운 스크롤 위치 계산
            new_x = int(rel_x * scaled_pixmap.width() - mouse_pos.x())
            new_y = int(rel_y * scaled_pixmap.height() - mouse_pos.y())
            
            # 스크롤바 이동
            scroll_area.horizontalScrollBar().setValue(new_x)
            scroll_area.verticalScrollBar().setValue(new_y)

        self.pdf_label.setPixmap(scaled_pixmap)

    def updatePageWithOpacity(self, original_pixmap):
        """투명도만 업데이트하여 페이지를 빠르게 다시 그리는 메서드"""
        if not original_pixmap:
            return
        
        # 화면 크기에 맞게 조정
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        toolbar = self.findChild(QToolBar)
        toolbar_height = toolbar.height() if toolbar else 0
        
        # 원본 비율 유지하면서 화면에 맞게 스케일링
        scaled_pixmap = original_pixmap.scaled(
            screen_size.width(),
            screen_size.height() - toolbar_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # 현재 줌 팩터 적용
        scaled_pixmap = scaled_pixmap.scaled(
            int(scaled_pixmap.width() * self.zoom_factor),
            int(scaled_pixmap.height() * self.zoom_factor),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        if self.opacity < 1.0:
            # 투명도 적용을 위한 새 QPixmap 생성
            transparent_pixmap = QPixmap(scaled_pixmap.size())
            transparent_pixmap.fill(Qt.transparent)
            painter = QPainter(transparent_pixmap)
            painter.setOpacity(self.opacity)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()
            scaled_pixmap = transparent_pixmap
        
        # 주석 다시 그리기
        if self.current_page in self.annotations:
            painter = QPainter(scaled_pixmap)
            scale_factor_x = scaled_pixmap.width() / original_pixmap.width()
            scale_factor_y = scaled_pixmap.height() / original_pixmap.height()
            
            for ann in self.annotations[self.current_page]:
                pen = QPen(ann['color'])
                pen.setWidth(2)
                painter.setPen(pen)
                
                start = QPointF(ann['start'].x() * scale_factor_x,
                              ann['start'].y() * scale_factor_y)
                end = QPointF(ann['end'].x() * scale_factor_x,
                           ann['end'].y() * scale_factor_y)
                
                if ann['type'] == '사각형':
                    painter.drawRect(QRectF(start, end))
                elif ann['type'] == '화살표':
                    painter.drawLine(start, end)
                elif ann['type'] == '텍스트':
                    painter.drawText(start, ann['text'])
            painter.end()
        
        self.pdf_label.setPixmap(scaled_pixmap)

    def mousePressEvent(self, event):
        if self.is_locked:
            # 관통 기능 활성화
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton:
            if self.current_tool == '선택' and self.current_page in self.annotations:
                # 클릭한 위치의 상대 좌표 계산
                click_pos = self.pdf_label.mapFrom(self, event.pos())
                scale_factor_x = self.pdf_label.pixmap().width() / self.page_cache[self.current_page].width()
                scale_factor_y = self.pdf_label.pixmap().height() / self.page_cache[self.current_page].height()
                
                # 주석 선택 검사
                for i, ann in enumerate(self.annotations[self.current_page]):
                    start = QPointF(ann['start'].x() * scale_factor_x, ann['start'].y() * scale_factor_y)
                    end = QPointF(ann['end'].x() * scale_factor_x, ann['end'].y() * scale_factor_y)
                    
                    # 주석 영역 계산
                    rect = QRectF(min(start.x(), end.x()), min(start.y(), end.y()),
                                abs(end.x() - start.x()), abs(end.y() - start.y()))
                    
                    if rect.contains(click_pos):
                        self.selected_annotation = (self.current_page, i)
                        self.is_selecting = True
                        self.showPage()  # 선택 표시를 위해 페이지 다시 그리기
                        return
                
                # 빈 공간 클릭 시 선택 해제
                self.selected_annotation = None
                self.is_selecting = False
                self.showPage()
            else:
                self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.is_locked:
            # 관통 기능 활성화
            super().mouseReleaseEvent(event)
            return
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            end_pos = event.pos()
            
            tool = self.tool_combo.currentText()
            if tool != '선택':
                annotation = {
                    'type': tool,
                    'start': self.start_pos,
                    'end': end_pos,
                    'color': self.current_color,
                    'text': ''
                }

                if tool == '텍스트':
                    text, ok = QInputDialog.getText(self, '텍스트 입력', '내용:')
                    if ok:
                        annotation['text'] = text

                if self.current_page not in self.annotations:
                    self.annotations[self.current_page] = []
                self.annotations[self.current_page].append(annotation)
                self.showPage()

    def mouseMoveEvent(self, event):
        if self.is_locked:
            return
        if not self.is_maximized and event.buttons() == Qt.LeftButton:  # 최대화 상태가 아닐 때만 이동 가능
            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def fitToView(self):
        if self.pdf_document is None:
            return
        # 현재 레이블 크기에 맞추기
        self.zoom_factor = 1.0
        self.showPage()

    def selectColor(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color

    def savePDF(self):
        if self.pdf_document is None:
            return
        
        file_name, _ = QFileDialog.getSaveFileName(self, "PDF 저장", "", "PDF files (*.pdf)")
        if file_name:
            try:
                # 현재 주석이 있는 페이지들만 처리
                for page_num in self.annotations.keys():
                    page = self.pdf_document[page_num]
                    
                    # 페이지의 모든 주석을 처리
                    for ann in self.annotations[page_num]:
                        if ann['type'] == '사각형':
                            page.draw_rect([ann['start'].x(), ann['start'].y(), 
                                          ann['end'].x(), ann['end'].y()],
                                         color=ann['color'].getRgb()[:3])
                        elif ann['type'] == '화살표':
                            page.draw_line([ann['start'].x(), ann['start'].y(), 
                                          ann['end'].x(), ann['end'].y()],
                                         color=ann['color'].getRgb()[:3])
                        elif ann['type'] == '텍스트':
                            page.insert_text([ann['start'].x(), ann['start'].y()],
                                           ann['text'],
                                           color=ann['color'].getRgb()[:3])
                
                # 변경된 PDF 저장
                self.pdf_document.save(file_name)
                
            except Exception as e:
                print(f"PDF 저장 중 오류 발생: {str(e)}")

    def toggleMaximized(self):
        if self.is_maximized:
            self.showNormal()
            self.is_maximized = False
            self.max_button.setIcon(self.icons['window-maximum'])
            self.setMouseTracking(True)  # 마우스 추적 활성화
        else:
            self.showMaximized()
            self.is_maximized = True
            self.max_button.setIcon(self.icons['window-small'])  # 아이콘 변경
            self.setMouseTracking(False)  # 마우스 추적 비활성화

    def rotatePage(self, angle):
        """PDF 페이지를 회전시키는 메서드"""
        if self.pdf_document is None:
            return
        
        try:
            # 현재 페이지 가져오기
            page = self.pdf_document[self.current_page]
            
            # 현재 회전 각도 가져오기
            current_rotation = page.rotation
            
            # 새로운 회전 각도 계산 (360도 범위 내로 유지)
            new_rotation = (current_rotation + angle) % 360
            
            # 페이지 회전 적용
            page.set_rotation(new_rotation)
            
            # 화면 업데이트
            self.showPage()
            
        except Exception as e:
            print(f"페이지 회전 중 오류 발생: {str(e)}")

    def keyPressEvent(self, event):
        # 잠금 상태에서는 모든 키 입력 무시
        if self.is_locked:
            return
        if self.pdf_document is None and not (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_O):
            return
        
        # Ctrl + 단축키 처리
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_S:  # Ctrl + S
                self.savePDF()
            elif event.key() == Qt.Key_O:  # Ctrl + O
                self.openfile()
            
        # Ctrl + Shift + 단축키 처리
        elif event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            if event.key() == Qt.Key_Equal or event.key() == Qt.Key_Plus:  # Ctrl + Shift + +
                self.rotatePage(90)
            elif event.key() == Qt.Key_Minus:  # Ctrl + Shift + -
                self.rotatePage(-90)
            
        # 페이지 이동 키 처리
        elif event.key() in [Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown]:
            if self.current_page < len(self.pdf_document) - 1:
                self.current_page += 1
                self.showPage()
            
        elif event.key() in [Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp]:
            if self.current_page > 0:
                self.current_page -= 1
                self.showPage()
            
        # Delete 키로 선택된 주석 삭제
        if event.key() == Qt.Key_Delete and self.selected_annotation:
            page_num, ann_idx = self.selected_annotation
            if page_num in self.annotations and 0 <= ann_idx < len(self.annotations[page_num]):
                del self.annotations[page_num][ann_idx]
                self.selected_annotation = None
                self.showPage()
        
        # Enter 키로 선택된 주석 편집
        elif event.key() == Qt.Key_Return and self.selected_annotation:
            page_num, ann_idx = self.selected_annotation
            if page_num in self.annotations and 0 <= ann_idx < len(self.annotations[page_num]):
                ann = self.annotations[page_num][ann_idx]
                if ann['type'] == '텍스트':
                    text, ok = QInputDialog.getText(self, '텍스트 편집', '내용:', 
                                                  text=ann['text'])
                    if ok:
                        ann['text'] = text
                        self.showPage()
                
                # 색상 변경 (Ctrl+Enter)
                if event.modifiers() == Qt.ControlModifier:
                    color = QColorDialog.getColor(ann['color'])
                    if color.isValid():
                        ann['color'] = color
                        self.showPage()
        
        event.accept()

    def toggleLock(self):
        self.is_locked = not self.is_locked
        toolbar = self.findChild(QToolBar)
        current_pos = self.pos()  # 현재 창 위치 저장
        current_size = self.size()
        
        if self.is_locked:
            # 잠금 상태로 변경
            self.lock_button.setIcon(self.icons['lock'])
            
            # 툴바 높이 계산 및 숨기기
            toolbar_height = toolbar.height() if toolbar else 0
            if toolbar:
                toolbar.setVisible(False)
            
            # 창 크기 조정 (툴바 높이만큼 줄임)
            self.resize(current_size.width(), current_size.height() - toolbar_height)
            
            # 관통 기능 먼저 활성화
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            
            # 투명도 설정
            self.opacity = 0.7
            self.setWindowOpacity(self.opacity)
            
            # 마지막으로 윈도우 플래그 설정
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            
        else:
            # 잠금 해제 상태로 변경
            self.lock_button.setIcon(self.icons['unlock'])
            
            # 관통 기능 먼저 비활성화
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            
            # 툴바 높이 계산 및 표시
            toolbar_height = toolbar.height() if toolbar else 0
            if toolbar:
                toolbar.setVisible(True)
            
            # 창 크기 조정 (툴바 높이만큼 늘림)
            self.resize(current_size.width(), current_size.height() + toolbar_height)
            
            # 투명도 초기화
            self.opacity = 1.0
            self.setWindowOpacity(self.opacity)
            
            # 마지막으로 윈도우 플래그 설정
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        
        # 변경사항 적용을 위해 show() 호출하고 원래 위치로 복원
        self.show()
        self.move(current_pos)

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec_())
