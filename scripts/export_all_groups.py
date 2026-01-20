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
        """獲取所有群組資料（按群組分組）"""
        print("🔍 正在獲取所有群組...")
        
        # 獲取所有頂層群組
        groups = self.client.get_groups()
        print(f"✓ 找到 {len(groups)} 個群組\n")
        
        # 按群組組織資料
        groups_data = []
        
        for idx, group in enumerate(groups, 1):
            group_name = getattr(group, 'name', 'Unknown')
            group_path = getattr(group, 'path', 'unknown')
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
            
            # 收集該群組的所有資料
            group_data = {
                'group_path': group_path,
                'group_name': group_name,
                'groups': [group_info],
                'subgroups': [],
                'projects': [],
                'permissions': []
            }
            
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
                    group_data['subgroups'].append(subgroup_info)
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
                    group_data['projects'].append(project_info)
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
                    group_data['permissions'].append(permission_info)
            except Exception:
                pass
            
            groups_data.append(group_data)
        
        return groups_data
    

    def export_to_csv(self, groups_data: list):
        """匯出資料到 CSV（每個群組獨立目錄）"""
        total_groups = len(groups_data)
        total_subgroups = 0
        total_projects = 0
        total_permissions = 0
        
        for idx, group_data in enumerate(groups_data, 1):
            group_path = group_data['group_path']
            group_name = group_data['group_name']
            
            print(f"\n[{idx}/{total_groups}] 匯出群組: {group_name}")
            
            # 建立群組專屬目錄
            group_dir = Path(self.output_dir) / group_path
            group_dir.mkdir(parents=True, exist_ok=True)
            
            # 匯出群組資料
            if group_data['groups']:
                csv_path = export_dataframe_to_csv(
                    pd.DataFrame(group_data['groups']),
                    str(group_dir),
                    'groups'
                )
                print(f"  ✓ groups.csv")
            
            # 匯出子群組資料
            if group_data['subgroups']:
                csv_path = export_dataframe_to_csv(
                    pd.DataFrame(group_data['subgroups']),
                    str(group_dir),
                    'subgroups'
                )
                print(f"  ✓ subgroups.csv ({len(group_data['subgroups'])} 筆)")
                total_subgroups += len(group_data['subgroups'])
            
            # 匯出專案資料
            if group_data['projects']:
                csv_path = export_dataframe_to_csv(
                    pd.DataFrame(group_data['projects']),
                    str(group_dir),
                    'projects'
                )
                print(f"  ✓ projects.csv ({len(group_data['projects'])} 筆)")
                total_projects += len(group_data['projects'])
            
            # 匯出權限資料
            if group_data['permissions']:
                csv_path = export_dataframe_to_csv(
                    pd.DataFrame(group_data['permissions']),
                    str(group_dir),
                    'permissions'
                )
                print(f"  ✓ permissions.csv ({len(group_data['permissions'])} 筆)")
                total_permissions += len(group_data['permissions'])
            
            # 產生該群組的摘要報告
            self._generate_group_summary(group_data, group_dir)
        
        # 產生全域摘要
        print(f"\n" + "=" * 70)
        print(f"✅ 匯出完成")
        print(f"   共 {total_groups} 個群組")
        print(f"   共 {total_subgroups} 個子群組")
        print(f"   共 {total_projects} 個專案")
        print(f"   共 {total_permissions} 筆權限記錄")
    
    def _generate_group_summary(self, group_data: dict, group_dir: Path):
        """產生群組摘要報告"""
        summary = {
            '群組名稱': group_data['group_name'],
            '子群組數': len(group_data['subgroups']),
            '專案數': len(group_data['projects']),
            '權限記錄數': len(group_data['permissions']),
        }
        
        # 計算各權限等級統計
        if group_data['permissions']:
            df_perm = pd.DataFrame(group_data['permissions'])
            access_stats = df_perm['access_level_name'].value_counts().to_dict()
            summary.update({f'{k} 數量': v for k, v in access_stats.items()})
        
        csv_path = export_dataframe_to_csv(
            pd.DataFrame([summary]),
            str(group_dir),
            'summary'
        )
        print(f"  ✓ summary.csv")


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
