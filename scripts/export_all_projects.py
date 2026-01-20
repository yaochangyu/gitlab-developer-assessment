"""
匯出所有 GitLab 專案到 CSV 檔案

透過 GitLab API 取得所有專案資訊，並輸出為 CSV 格式
"""

import sys
import time
import pandas as pd

from gitlab_client import GitLabClient
from config import GITLAB_URL
from progress_reporter import ConsoleProgressReporter
from common_utils import (
    disable_ssl_warnings,
    ensure_output_dir,
    get_timestamp,
    export_dataframe_to_csv
)
from export_utils import create_default_client, create_export_argument_parser

# 抑制 SSL 警告
disable_ssl_warnings()


def export_all_projects(output_dir: str = "./output"):
    """匯出所有專案到 CSV 檔案"""
    
    # 初始化 GitLab 客戶端
    print(f"連線到 GitLab: {GITLAB_URL}")
    client = create_default_client()
    progress = ConsoleProgressReporter()
    
    # 取得所有專案
    print("正在取得所有專案...")
    projects = client.get_projects()
    print(f"找到 {len(projects)} 個專案")
    
    # 準備輸出目錄
    output_path = ensure_output_dir(output_dir)
    
    # 收集所有專案資料
    all_projects = []
    
    for idx, project in enumerate(projects, 1):
        # 取得完整專案資訊
        try:
            full_project = client.get_project(project.id)
            
            project_info = {
                'id': full_project.id,
                'name': full_project.name,
                'path': full_project.path,
                'path_with_namespace': full_project.path_with_namespace,
                'description': getattr(full_project, 'description', '') or '',
                'visibility': getattr(full_project, 'visibility', ''),
                'default_branch': getattr(full_project, 'default_branch', ''),
                'web_url': full_project.web_url,
                'ssh_url_to_repo': getattr(full_project, 'ssh_url_to_repo', ''),
                'http_url_to_repo': getattr(full_project, 'http_url_to_repo', ''),
                'namespace_id': full_project.namespace.get('id', ''),
                'namespace_name': full_project.namespace.get('name', ''),
                'namespace_path': full_project.namespace.get('path', ''),
                'namespace_kind': full_project.namespace.get('kind', ''),
                'created_at': getattr(full_project, 'created_at', ''),
                'last_activity_at': getattr(full_project, 'last_activity_at', ''),
                'archived': getattr(full_project, 'archived', False),
                'star_count': getattr(full_project, 'star_count', 0),
                'forks_count': getattr(full_project, 'forks_count', 0),
                'open_issues_count': getattr(full_project, 'open_issues_count', 0),
                'creator_id': getattr(full_project, 'creator_id', ''),
                'creator_name': ''
            }
            
            # 嘗試取得建立者名稱
            if hasattr(full_project, 'owner') and full_project.owner:
                project_info['creator_name'] = full_project.owner.get('name', '')
            
            all_projects.append(project_info)
            
            # 顯示進度
            progress.report_progress(idx, len(projects), full_project.path_with_namespace)
            
        except Exception as e:
            print(f"\r  [錯誤] 無法取得專案 {project.id}: {e}".ljust(120))
            continue
    
    # 匯出 CSV
    if all_projects:
        timestamp = get_timestamp()
        filename = f"all-projects_{timestamp}"
        csv_path = export_dataframe_to_csv(
            pd.DataFrame(all_projects),
            output_path,
            filename
        )
        print(f"\n✅ 完成！匯出 {len(all_projects)} 個專案到 {csv_path}")
    else:
        print("\n⚠️  未找到任何專案")


def main():
    """主程式"""
    parser = create_export_argument_parser(
        description='匯出所有 GitLab 專案資訊',
        epilog="""
使用範例:
    python export_all_projects.py
    python export_all_projects.py --output ./reports
        """
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("GitLab 專案資料匯出工具")
    print("=" * 70)
    print(f"📁 輸出目錄: {args.output}")
    print(f"🔗 GitLab URL: {GITLAB_URL}")
    print("=" * 70)
    
    start_time = time.time()
    
    try:
        export_all_projects(output_dir=args.output)
        
        elapsed_time = time.time() - start_time
        print("\n" + "=" * 70)
        print(f"✅ 完成！執行時間: {elapsed_time:.2f} 秒")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    export_all_projects()
