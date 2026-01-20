#!/usr/bin/env python3
"""
匯出所有 GitLab 群組資訊

此腳本會匯出所有可存取的 GitLab 群組資料，包含：
- 群組基本資訊
- 子群組列表
- 群組內專案列表
- 群組成員權限

使用方式：
    python export_all_groups.py                    # 匯出到 ./output
    python export_all_groups.py --output ./reports # 指定輸出目錄
"""

import argparse
import sys
import os
from pathlib import Path
import pandas as pd
import time

# 加入當前目錄到 Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitlab_client import GitLabClient
import config


class GroupExporter:
    """群組資料匯出器"""
    
    def __init__(self, output_dir: str = "./output"):
        self.client = GitLabClient(
            gitlab_url=config.GITLAB_URL,
            private_token=config.GITLAB_TOKEN,
            ssl_verify=False
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_all_groups(self):
        """獲取所有群組資料"""
        print("🔍 正在獲取所有群組...")
        
        all_groups = []
        all_subgroups = []
        all_projects = []
        all_permissions = []
        
        # 獲取所有頂層群組
        groups = self.client.get_groups()
        print(f"✓ 找到 {len(groups)} 個群組")
        
        for idx, group in enumerate(groups, 1):
            print(f"\n[{idx}/{len(groups)}] 處理群組: {group.get('name', 'Unknown')}")
            
            # 群組基本資訊
            group_info = {
                'group_id': group.get('id'),
                'group_name': group.get('name'),
                'group_path': group.get('path'),
                'group_full_path': group.get('full_path'),
                'description': group.get('description', ''),
                'visibility': group.get('visibility'),
                'created_at': group.get('created_at'),
                'web_url': group.get('web_url'),
                'parent_id': group.get('parent_id'),
            }
            all_groups.append(group_info)
            
            # 獲取子群組
            try:
                subgroups = self.client.get_subgroups(group['id'])
                print(f"  ├─ 子群組: {len(subgroups)} 個")
                
                for subgroup in subgroups:
                    subgroup_info = {
                        'parent_group_id': group['id'],
                        'parent_group_name': group['name'],
                        'subgroup_id': subgroup.get('id'),
                        'subgroup_name': subgroup.get('name'),
                        'subgroup_path': subgroup.get('path'),
                        'subgroup_full_path': subgroup.get('full_path'),
                        'description': subgroup.get('description', ''),
                        'visibility': subgroup.get('visibility'),
                        'web_url': subgroup.get('web_url'),
                    }
                    all_subgroups.append(subgroup_info)
            except Exception as e:
                print(f"  ├─ ⚠️  無法獲取子群組: {e}")
            
            # 獲取群組專案
            try:
                projects = self.client.get_group_projects(group['id'])
                print(f"  ├─ 專案: {len(projects)} 個")
                
                for project in projects:
                    project_info = {
                        'group_id': group['id'],
                        'group_name': group['name'],
                        'project_id': project.get('id'),
                        'project_name': project.get('name'),
                        'project_path': project.get('path'),
                        'description': project.get('description', ''),
                        'visibility': project.get('visibility'),
                        'created_at': project.get('created_at'),
                        'last_activity_at': project.get('last_activity_at'),
                        'web_url': project.get('web_url'),
                        'default_branch': project.get('default_branch'),
                        'star_count': project.get('star_count', 0),
                        'forks_count': project.get('forks_count', 0),
                    }
                    all_projects.append(project_info)
            except Exception as e:
                print(f"  ├─ ⚠️  無法獲取專案列表: {e}")
            
            # 獲取群組成員權限
            try:
                members = self.client.get_group_members(group['id'])
                print(f"  └─ 成員: {len(members)} 位")
                
                for member in members:
                    permission_info = {
                        'group_id': group['id'],
                        'group_name': group['name'],
                        'user_id': member.get('id'),
                        'username': member.get('username'),
                        'name': member.get('name'),
                        'email': member.get('email', ''),
                        'state': member.get('state'),
                        'access_level': member.get('access_level'),
                        'access_level_name': self._get_access_level_name(member.get('access_level')),
                        'expires_at': member.get('expires_at'),
                    }
                    all_permissions.append(permission_info)
            except Exception as e:
                print(f"  └─ ⚠️  無法獲取成員列表: {e}")
        
        return {
            'groups': all_groups,
            'subgroups': all_subgroups,
            'projects': all_projects,
            'permissions': all_permissions
        }
    
    def _get_access_level_name(self, level: int) -> str:
        """轉換權限等級代碼為名稱"""
        levels = {
            10: 'Guest',
            20: 'Reporter',
            30: 'Developer',
            40: 'Maintainer',
            50: 'Owner'
        }
        return levels.get(level, 'Unknown')
    
    def export_to_csv(self, data: dict):
        """匯出資料到 CSV"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 匯出群組資料
        if data['groups']:
            df_groups = pd.DataFrame(data['groups'])
            filename = self.output_dir / f"all-groups_{timestamp}.csv"
            df_groups.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 群組資料已匯出: {filename}")
            print(f"   共 {len(df_groups)} 個群組")
        
        # 匯出子群組資料
        if data['subgroups']:
            df_subgroups = pd.DataFrame(data['subgroups'])
            filename = self.output_dir / f"all-subgroups_{timestamp}.csv"
            df_subgroups.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 子群組資料已匯出: {filename}")
            print(f"   共 {len(df_subgroups)} 個子群組")
        
        # 匯出專案資料
        if data['projects']:
            df_projects = pd.DataFrame(data['projects'])
            filename = self.output_dir / f"all-group-projects_{timestamp}.csv"
            df_projects.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 專案資料已匯出: {filename}")
            print(f"   共 {len(df_projects)} 個專案")
        
        # 匯出權限資料
        if data['permissions']:
            df_permissions = pd.DataFrame(data['permissions'])
            filename = self.output_dir / f"all-group-permissions_{timestamp}.csv"
            df_permissions.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 權限資料已匯出: {filename}")
            print(f"   共 {len(df_permissions)} 筆權限記錄")
        
        # 產生摘要報告
        self._generate_summary(data, timestamp)
    
    def _generate_summary(self, data: dict, timestamp: str):
        """產生摘要報告"""
        summary = {
            '總群組數': len(data['groups']),
            '總子群組數': len(data['subgroups']),
            '總專案數': len(data['projects']),
            '總權限記錄數': len(data['permissions']),
        }
        
        # 計算各權限等級統計
        if data['permissions']:
            df_perm = pd.DataFrame(data['permissions'])
            access_stats = df_perm['access_level_name'].value_counts().to_dict()
            summary.update({f'{k} 數量': v for k, v in access_stats.items()})
        
        df_summary = pd.DataFrame([summary])
        filename = self.output_dir / f"all-groups-summary_{timestamp}.csv"
        df_summary.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n✅ 摘要報告已匯出: {filename}")


def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description='匯出所有 GitLab 群組資訊',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
    python export_all_groups.py
    python export_all_groups.py --output ./reports
    python export_all_groups.py --output /path/to/custom/dir
        """
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=os.path.join(os.getcwd(), 'output'),
        help='輸出目錄路徑 (預設: ./output)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("GitLab 群組資料匯出工具")
    print("=" * 70)
    print(f"📁 輸出目錄: {args.output}")
    print(f"🔗 GitLab URL: {config.GITLAB_URL}")
    print("=" * 70)
    
    start_time = time.time()
    
    try:
        exporter = GroupExporter(output_dir=args.output)
        data = exporter.fetch_all_groups()
        exporter.export_to_csv(data)
        
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
    main()
