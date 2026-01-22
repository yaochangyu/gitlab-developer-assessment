"""
匯出所有 GitLab 使用者到 CSV 檔案

透過 GitLab API 取得所有使用者資訊，並輸出為 CSV 格式
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


def export_all_users(output_dir: str = "./output"):
    """匯出所有使用者到 CSV 檔案"""
    
    # 初始化 GitLab 客戶端
    print(f"連線到 GitLab: {GITLAB_URL}")
    client = create_default_client()
    progress = ConsoleProgressReporter()
    
    # 取得所有使用者（包含 email）
    print("正在取得所有使用者...")
    users = client.get_all_users(with_email=True)
    print(f"找到 {len(users)} 個使用者")
    
    # 準備輸出目錄
    output_path = ensure_output_dir(output_dir)
    
    # 收集所有使用者資料
    all_users = []
    
    for idx, user in enumerate(users, 1):
        try:
            # 處理身份提供者資訊
            identities = getattr(user, 'identities', [])
            identity_providers = ','.join([identity.get('provider', '') for identity in identities]) if identities else ''
            
            user_info = {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': getattr(user, 'email', ''),
                'public_email': getattr(user, 'public_email', ''),
                'state': getattr(user, 'state', ''),
                'locked': getattr(user, 'locked', False),
                'is_admin': getattr(user, 'is_admin', False),
                'is_auditor': getattr(user, 'is_auditor', False),
                'two_factor_enabled': getattr(user, 'two_factor_enabled', False),
                'external': getattr(user, 'external', False),
                'private_profile': getattr(user, 'private_profile', False),
                'avatar_url': getattr(user, 'avatar_url', ''),
                'web_url': getattr(user, 'web_url', ''),
                'created_at': getattr(user, 'created_at', ''),
                'confirmed_at': getattr(user, 'confirmed_at', ''),
                'last_sign_in_at': getattr(user, 'last_sign_in_at', ''),
                'current_sign_in_at': getattr(user, 'current_sign_in_at', ''),
                'last_activity_on': getattr(user, 'last_activity_on', ''),
                'projects_limit': getattr(user, 'projects_limit', 0),
                'can_create_group': getattr(user, 'can_create_group', False),
                'can_create_project': getattr(user, 'can_create_project', False),
                'bio': getattr(user, 'bio', ''),
                'location': getattr(user, 'location', ''),
                'organization': getattr(user, 'organization', ''),
                'job_title': getattr(user, 'job_title', ''),
                'linkedin': getattr(user, 'linkedin', ''),
                'twitter': getattr(user, 'twitter', ''),
                'discord': getattr(user, 'discord', ''),
                'github': getattr(user, 'github', ''),
                'website_url': getattr(user, 'website_url', ''),
                'namespace_id': getattr(user, 'namespace_id', ''),
                'current_sign_in_ip': getattr(user, 'current_sign_in_ip', ''),
                'last_sign_in_ip': getattr(user, 'last_sign_in_ip', ''),
                'identities_count': len(identities),
                'identity_providers': identity_providers
            }
            
            all_users.append(user_info)
            
            # 顯示進度
            progress.report_progress(idx, len(users), f"{user.username} ({user.name})")
            
        except Exception as e:
            print(f"\r  [錯誤] 無法處理使用者 {user.id}: {e}".ljust(120))
            continue
    
    # 匯出 CSV
    if all_users:
        timestamp = get_timestamp()
        filename = f"all-users_{timestamp}"
        csv_path = export_dataframe_to_csv(
            pd.DataFrame(all_users),
            output_path,
            filename
        )
        print(f"\n✅ 完成！匯出 {len(all_users)} 個使用者到 {csv_path}")
    else:
        print("\n⚠️  未找到任何使用者")


def main():
    """主程式"""
    parser = create_export_argument_parser(
        description='匯出所有 GitLab 使用者資訊',
        epilog="""
使用範例:
    python export_all_users.py
    python export_all_users.py --output ./reports
        """
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("GitLab 使用者資料匯出工具")
    print("=" * 70)
    print(f"📁 輸出目錄: {args.output}")
    print(f"🔗 GitLab URL: {GITLAB_URL}")
    print("=" * 70)
    
    start_time = time.time()
    
    try:
        export_all_users(output_dir=args.output)
        
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
    export_all_users()
