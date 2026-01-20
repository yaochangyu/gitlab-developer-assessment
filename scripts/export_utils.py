#!/usr/bin/env python3
"""
Export 工具模組 - 提供所有 export 腳本的共用功能

此模組集中管理：
- GitLab 權限等級轉換
- GitLab 客戶端初始化
- ArgumentParser 共用參數設定
"""

import argparse
from gitlab_client import GitLabClient
import config


class AccessLevelMapper:
    """GitLab 權限等級轉換工具"""
    
    # 權限等級對照表
    LEVELS = {
        10: 'Guest',
        20: 'Reporter',
        30: 'Developer',
        40: 'Maintainer',
        50: 'Owner'
    }
    
    @staticmethod
    def get_level_name(level: int) -> str:
        """
        轉換權限等級代碼為名稱
        
        Args:
            level: 權限等級代碼 (10/20/30/40/50)
        
        Returns:
            權限等級名稱 (Guest/Reporter/Developer/Maintainer/Owner)
        
        Examples:
            >>> AccessLevelMapper.get_level_name(30)
            'Developer'
            >>> AccessLevelMapper.get_level_name(50)
            'Owner'
            >>> AccessLevelMapper.get_level_name(999)
            'Unknown'
        """
        return AccessLevelMapper.LEVELS.get(level, 'Unknown')


def create_default_client() -> GitLabClient:
    """
    建立預設的 GitLab 客戶端
    
    使用 config.py 中的設定：
    - GITLAB_URL
    - GITLAB_TOKEN
    - SSL 驗證關閉
    
    Returns:
        已初始化的 GitLabClient 實例
    
    Examples:
        >>> client = create_default_client()
        >>> projects = client.get_projects()
    """
    return GitLabClient(
        gitlab_url=config.GITLAB_URL,
        private_token=config.GITLAB_TOKEN,
        ssl_verify=False
    )


def create_base_argument_parser(
    description: str,
    epilog: str = None
) -> argparse.ArgumentParser:
    """
    建立基礎的 ArgumentParser
    
    Args:
        description: 程式描述文字
        epilog: 使用範例文字（可選）
    
    Returns:
        已設定的 ArgumentParser 實例
    
    Examples:
        >>> parser = create_base_argument_parser('匯出工具', epilog='使用範例...')
        >>> parser.add_argument('--custom', help='自訂參數')
    """
    return argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )


def add_output_argument(parser: argparse.ArgumentParser, default: str = './output') -> None:
    """
    添加 --output 參數
    
    Args:
        parser: ArgumentParser 實例
        default: 預設輸出目錄路徑
    
    Examples:
        >>> parser = argparse.ArgumentParser()
        >>> add_output_argument(parser)
        >>> add_output_argument(parser, default='./reports')
    """
    parser.add_argument(
        '--output',
        type=str,
        default=default,
        help=f'輸出目錄路徑 (預設: {default})'
    )


def add_username_argument(parser: argparse.ArgumentParser) -> None:
    """
    添加 --username 參數（支援多個用戶）
    
    Args:
        parser: ArgumentParser 實例
    
    Examples:
        >>> parser = argparse.ArgumentParser()
        >>> add_username_argument(parser)
    """
    parser.add_argument(
        '--username',
        nargs='*',
        help='用戶名稱（可指定多個，用空格分隔）。不指定則分析所有用戶'
    )


def add_project_name_argument(parser: argparse.ArgumentParser) -> None:
    """
    添加 --project-name 參數（支援多個專案）
    
    Args:
        parser: ArgumentParser 實例
    
    Examples:
        >>> parser = argparse.ArgumentParser()
        >>> add_project_name_argument(parser)
    """
    parser.add_argument(
        '--project-name',
        nargs='*',
        dest='project_names',
        help='專案名稱（可指定多個，用空格分隔）。不指定則分析所有專案'
    )


def add_date_range_arguments(parser: argparse.ArgumentParser) -> None:
    """
    添加日期範圍參數（--start-date 和 --end-date）
    
    Args:
        parser: ArgumentParser 實例
    
    Examples:
        >>> parser = argparse.ArgumentParser()
        >>> add_date_range_arguments(parser)
    """
    parser.add_argument(
        '--start-date',
        help=f'開始日期 (YYYY-MM-DD)，預設使用 config.py 的 START_DATE'
    )
    parser.add_argument(
        '--end-date',
        help=f'結束日期 (YYYY-MM-DD)，預設使用 config.py 的 END_DATE'
    )


def create_export_argument_parser(
    description: str,
    epilog: str = None
) -> argparse.ArgumentParser:
    """
    建立 export 腳本的完整 ArgumentParser（包含 --output 參數）
    
    Args:
        description: 程式描述文字
        epilog: 使用範例文字（可選）
    
    Returns:
        已設定 --output 參數的 ArgumentParser 實例
    
    Examples:
        >>> parser = create_export_argument_parser('匯出所有專案', epilog='範例...')
        >>> args = parser.parse_args()
    """
    parser = create_base_argument_parser(description, epilog)
    add_output_argument(parser)
    return parser
