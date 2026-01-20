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

from gitlab_client import GitLabClient
import config
from progress_reporter import ConsoleProgressReporter
from common_utils import (
    disable_ssl_warnings,
    ensure_output_dir,
    get_timestamp,
    export_dataframe_to_csv
)
from export_utils import AccessLevelMapper, create_default_client, create_export_argument_parser

# 抑制 SSL 警告
disable_ssl_warnings()


class GroupExporter:
    """群組資料匯出器"""
    
    def __init__(self, output_dir: str = "./output"):
        self.client = create_default_client()
        self.output_dir = ensure_output_dir(output_dir)
        self.progress = ConsoleProgressReporter()
    
    def fetch_all_groups(self):
        """獲取所有群組資料"""
        print("🔍 正在獲取所有群組...")
        
        all_groups = []
        all_subgroups = []
        all_projects = []
        all_permissions = []
        
        # 獲取所有頂層群組
        groups = self.client.get_groups()
        print(f"✓ 找到 {len(groups)} 個群組\n")
        
        for idx, group in enumerate(groups, 1):
            group_name = getattr(group, 'name', 'Unknown')
            self.progress.report_progress(idx, len(groups), f"處理群組: {group_name}")
            
            # 群組基本資訊
            group_info = {
                'group_id': getattr(group, 'id', None),
                'group_name': getattr(group, 'name', None),
                'group_path': getattr(group, 'path', None),
                'group_full_path': getattr(group, 'full_path', None),
                'description': getattr(group, 'description', ''),
                'visibility': getattr(group, 'visibility', None),
                'created_at': getattr(group, 'created_at', None),
                'web_url': getattr(group, 'web_url', None),
                'parent_id': getattr(group, 'parent_id', None),
            }
            all_groups.append(group_info)
            
            # 獲取子群組
            try:
                subgroups = self.client.get_group_subgroups(group.id)
                
                for subgroup in subgroups:
                    subgroup_info = {
                        'parent_group_id': group.id,
                        'parent_group_name': group.name,
                        'subgroup_id': getattr(subgroup, 'id', None),
                        'subgroup_name': getattr(subgroup, 'name', None),
                        'subgroup_path': getattr(subgroup, 'path', None),
                        'subgroup_full_path': getattr(subgroup, 'full_path', None),
                        'description': getattr(subgroup, 'description', ''),
                        'visibility': getattr(subgroup, 'visibility', None),
                        'web_url': getattr(subgroup, 'web_url', None),
                    }
                    all_subgroups.append(subgroup_info)
            except Exception:
                pass
            
            # 獲取群組專案
            try:
                projects = self.client.get_group_projects(group.id)
                
                for project in projects:
                    project_info = {
                        'group_id': group.id,
                        'group_name': group.name,
                        'project_id': getattr(project, 'id', None),
                        'project_name': getattr(project, 'name', None),
                        'project_path': getattr(project, 'path', None),
                        'description': getattr(project, 'description', ''),
                        'visibility': getattr(project, 'visibility', None),
                        'created_at': getattr(project, 'created_at', None),
                        'last_activity_at': getattr(project, 'last_activity_at', None),
                        'web_url': getattr(project, 'web_url', None),
                        'default_branch': getattr(project, 'default_branch', None),
                        'star_count': getattr(project, 'star_count', 0),
                        'forks_count': getattr(project, 'forks_count', 0),
                    }
                    all_projects.append(project_info)
            except Exception:
                pass
            
            # 獲取群組成員權限
            try:
                members = self.client.get_group_members(group.id)
                
                for member in members:
                    permission_info = {
                        'group_id': group.id,
                        'group_name': group.name,
                        'user_id': getattr(member, 'id', None),
                        'username': getattr(member, 'username', None),
                        'name': getattr(member, 'name', None),
                        'email': getattr(member, 'email', ''),
                        'state': getattr(member, 'state', None),
                        'access_level': getattr(member, 'access_level', None),
                        'access_level_name': AccessLevelMapper.get_level_name(getattr(member, 'access_level', None)),
                        'expires_at': getattr(member, 'expires_at', None),
                    }
                    all_permissions.append(permission_info)
            except Exception:
                pass
        
        return {
            'groups': all_groups,
            'subgroups': all_subgroups,
            'projects': all_projects,
            'permissions': all_permissions
        }
    

    def export_to_csv(self, data: dict):
        """匯出資料到 CSV"""
        timestamp = get_timestamp()
        
        # 匯出群組資料
        if data['groups']:
            filename = f"all-groups_{timestamp}"
            csv_path = export_dataframe_to_csv(
                pd.DataFrame(data['groups']),
                self.output_dir,
                filename
            )
            print(f"\n✅ 群組資料已匯出: {csv_path}")
            print(f"   共 {len(data['groups'])} 個群組")
        
        # 匯出子群組資料
        if data['subgroups']:
            filename = f"all-subgroups_{timestamp}"
            csv_path = export_dataframe_to_csv(
                pd.DataFrame(data['subgroups']),
                self.output_dir,
                filename
            )
            print(f"\n✅ 子群組資料已匯出: {csv_path}")
            print(f"   共 {len(data['subgroups'])} 個子群組")
        
        # 匯出專案資料
        if data['projects']:
            filename = f"all-group-projects_{timestamp}"
            csv_path = export_dataframe_to_csv(
                pd.DataFrame(data['projects']),
                self.output_dir,
                filename
            )
            print(f"\n✅ 專案資料已匯出: {csv_path}")
            print(f"   共 {len(data['projects'])} 個專案")
        
        # 匯出權限資料
        if data['permissions']:
            filename = f"all-group-permissions_{timestamp}"
            csv_path = export_dataframe_to_csv(
                pd.DataFrame(data['permissions']),
                self.output_dir,
                filename
            )
            print(f"\n✅ 權限資料已匯出: {csv_path}")
            print(f"   共 {len(data['permissions'])} 筆權限記錄")
        
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
        
        filename = f"all-groups-summary_{timestamp}"
        csv_path = export_dataframe_to_csv(
            pd.DataFrame([summary]),
            self.output_dir,
            filename
        )
        print(f"\n✅ 摘要報告已匯出: {csv_path}")


def main():
    """主程式"""
    parser = create_export_argument_parser(
        description='匯出所有 GitLab 群組資訊',
        epilog="""
使用範例:
    python export_all_groups.py
    python export_all_groups.py --output ./reports
    python export_all_groups.py --output /path/to/custom/dir
        """
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
