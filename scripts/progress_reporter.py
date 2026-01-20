"""
進度報告器模組

提供統一的進度條顯示功能，供所有 CLI 工具共用
"""

from abc import ABC, abstractmethod


# ==================== 抽象介面 ====================

class IProgressReporter(ABC):
    """進度報告介面"""
    
    @abstractmethod
    def report_start(self, message: str) -> None:
        """報告開始訊息"""
        pass
    
    @abstractmethod
    def report_progress(self, current: int, total: int, message: str = "") -> None:
        """報告進度"""
        pass
    
    @abstractmethod
    def report_complete(self, message: str) -> None:
        """報告完成訊息"""
        pass
    
    @abstractmethod
    def report_warning(self, message: str) -> None:
        """報告警告訊息"""
        pass


# ==================== 實作類別 ====================

class ConsoleProgressReporter(IProgressReporter):
    """終端機進度報告器"""
    
    def report_start(self, message: str) -> None:
        """報告開始訊息"""
        print(f"\n🔄 {message}")
    
    def report_progress(self, current: int, total: int, message: str = "") -> None:
        """報告進度"""
        percentage = (current / total * 100) if total > 0 else 0
        bar_length = 30
        filled_length = int(bar_length * current // total) if total > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        progress_msg = f"  [{bar}] {current}/{total} ({percentage:.1f}%)"
        if message:
            progress_msg += f" - {message}"
        
        # 清空整行後再輸出，避免文字殘留
        terminal_width = 120  # 假設終端寬度，可根據需要調整
        padded_msg = progress_msg.ljust(terminal_width)
        print(f"\r{padded_msg}", end='', flush=True)
        
        if current >= total:
            print()  # 完成時換行
    
    def report_complete(self, message: str) -> None:
        """報告完成訊息"""
        print(f"✓ {message}")
    
    def report_warning(self, message: str) -> None:
        """報告警告訊息"""
        print(f"⚠️  {message}")


class SilentProgressReporter(IProgressReporter):
    """靜默進度報告器（不輸出任何訊息）"""
    
    def report_start(self, message: str) -> None:
        pass
    
    def report_progress(self, current: int, total: int, message: str = "") -> None:
        pass
    
    def report_complete(self, message: str) -> None:
        pass
    
    def report_warning(self, message: str) -> None:
        pass


# ==================== 便利函數 ====================

def create_progress_bar(current: int, total: int, message: str = "", bar_length: int = 30) -> str:
    """
    建立進度條字串（不直接輸出）
    
    Args:
        current: 當前進度
        total: 總數
        message: 附加訊息
        bar_length: 進度條長度
        
    Returns:
        格式化的進度條字串
    """
    percentage = (current / total * 100) if total > 0 else 0
    filled_length = int(bar_length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    progress_msg = f"  [{bar}] {current}/{total} ({percentage:.1f}%)"
    if message:
        progress_msg += f" - {message}"
    
    return progress_msg


def print_progress(current: int, total: int, message: str = "", terminal_width: int = 120) -> None:
    """
    直接打印進度條（便利函數）
    
    Args:
        current: 當前進度
        total: 總數
        message: 附加訊息
        terminal_width: 終端寬度
    """
    progress_msg = create_progress_bar(current, total, message)
    padded_msg = progress_msg.ljust(terminal_width)
    print(f"\r{padded_msg}", end='', flush=True)
    
    if current >= total:
        print()  # 完成時換行
