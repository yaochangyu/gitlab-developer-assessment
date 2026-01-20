"""
共用工具函數

提供所有 CLI 工具共用的基礎功能
"""

import os
import urllib3
from pathlib import Path
from typing import Union
from datetime import datetime
import pandas as pd


# ==================== SSL 設定 ====================

def disable_ssl_warnings():
    """抑制 SSL 不安全連線警告（用於 self-signed certificates）"""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==================== 目錄管理 ====================

def ensure_output_dir(output_dir: Union[str, Path]) -> Path:
    """
    確保輸出目錄存在
    
    Args:
        output_dir: 輸出目錄路徑（字串或 Path 物件）
        
    Returns:
        Path 物件
    """
    output_path = Path(output_dir) if isinstance(output_dir, str) else output_dir
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


# ==================== 時間戳 ====================

def get_timestamp(format: str = "%Y%m%d_%H%M%S") -> str:
    """
    取得當前時間戳
    
    Args:
        format: 時間格式字串（預設: YYYYMMDD_HHMMSS）
        
    Returns:
        格式化的時間戳字串
    """
    return datetime.now().strftime(format)


def get_datetime_string(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    取得當前日期時間字串（用於顯示）
    
    Args:
        format: 時間格式字串（預設: YYYY-MM-DD HH:MM:SS）
        
    Returns:
        格式化的日期時間字串
    """
    return datetime.now().strftime(format)


# ==================== CSV 匯出 ====================

def export_dataframe_to_csv(
    df: pd.DataFrame,
    output_dir: Union[str, Path],
    filename: str,
    encoding: str = 'utf-8-sig',
    index: bool = False
) -> Path:
    """
    匯出 DataFrame 到 CSV 檔案
    
    Args:
        df: pandas DataFrame
        output_dir: 輸出目錄
        filename: 檔案名稱（不含 .csv 副檔名）
        encoding: 編碼格式（預設: utf-8-sig，Excel 相容）
        index: 是否包含索引欄位
        
    Returns:
        輸出檔案的完整路徑
    """
    output_path = ensure_output_dir(output_dir)
    
    # 確保檔名有 .csv 副檔名
    if not filename.endswith('.csv'):
        filename = f"{filename}.csv"
    
    csv_path = output_path / filename
    df.to_csv(csv_path, index=index, encoding=encoding)
    
    return csv_path


def export_dict_list_to_csv(
    data: list,
    output_dir: Union[str, Path],
    filename: str,
    fieldnames: list = None,
    encoding: str = 'utf-8-sig'
) -> Path:
    """
    匯出字典列表到 CSV 檔案
    
    Args:
        data: 字典列表
        output_dir: 輸出目錄
        filename: 檔案名稱（不含 .csv 副檔名）
        fieldnames: CSV 欄位名稱（若為 None，自動從第一筆資料取得）
        encoding: 編碼格式（預設: utf-8-sig，Excel 相容）
        
    Returns:
        輸出檔案的完整路徑
    """
    if not data:
        raise ValueError("資料為空，無法匯出 CSV")
    
    # 轉換為 DataFrame 後匯出
    df = pd.DataFrame(data)
    
    # 如果有指定欄位順序，重新排列
    if fieldnames:
        # 只保留存在的欄位
        fieldnames = [f for f in fieldnames if f in df.columns]
        df = df[fieldnames]
    
    return export_dataframe_to_csv(df, output_dir, filename, encoding)


# ==================== 安全存取物件屬性 ====================

def safe_getattr(obj, attr: str, default=None):
    """
    安全地取得物件屬性（避免 AttributeError）
    
    Args:
        obj: 物件
        attr: 屬性名稱
        default: 預設值（屬性不存在時返回）
        
    Returns:
        屬性值或預設值
    """
    return getattr(obj, attr, default)


def extract_attrs(obj, attr_mapping: dict) -> dict:
    """
    批次提取物件屬性到字典
    
    Args:
        obj: 物件
        attr_mapping: 屬性對映 {欄位名稱: (屬性名稱, 預設值)}
        
    Returns:
        提取的屬性字典
        
    Example:
        >>> mapping = {
        ...     'id': ('id', None),
        ...     'name': ('name', ''),
        ...     'email': ('email', '')
        ... }
        >>> extract_attrs(user, mapping)
        {'id': 123, 'name': 'Alice', 'email': 'alice@example.com'}
    """
    result = {}
    for field_name, (attr_name, default_value) in attr_mapping.items():
        result[field_name] = safe_getattr(obj, attr_name, default_value)
    return result


# ==================== 檔案命名工具 ====================

def create_timestamped_filename(base_name: str, extension: str = 'csv') -> str:
    """
    建立帶時間戳的檔案名稱
    
    Args:
        base_name: 基礎檔名
        extension: 副檔名（不含點號）
        
    Returns:
        帶時間戳的檔案名稱
        
    Example:
        >>> create_timestamped_filename('export', 'csv')
        'export_20240120_143022.csv'
    """
    timestamp = get_timestamp()
    return f"{base_name}_{timestamp}.{extension}"


# ==================== 資料驗證 ====================

def is_valid_date(date_string: str, format: str = "%Y-%m-%d") -> bool:
    """
    驗證日期字串格式
    
    Args:
        date_string: 日期字串
        format: 日期格式（預設: YYYY-MM-DD）
        
    Returns:
        是否為有效日期
    """
    try:
        datetime.strptime(date_string, format)
        return True
    except (ValueError, TypeError):
        return False


def parse_date(date_string: str, format: str = "%Y-%m-%d") -> datetime:
    """
    解析日期字串
    
    Args:
        date_string: 日期字串
        format: 日期格式（預設: YYYY-MM-DD）
        
    Returns:
        datetime 物件
        
    Raises:
        ValueError: 日期格式無效
    """
    return datetime.strptime(date_string, format)


# ==================== 簡化的統計函數 ====================

def calculate_percentage(part: int, total: int, decimal_places: int = 1) -> float:
    """
    計算百分比
    
    Args:
        part: 部分數量
        total: 總數
        decimal_places: 小數位數
        
    Returns:
        百分比（0-100）
    """
    if total == 0:
        return 0.0
    return round((part / total) * 100, decimal_places)
