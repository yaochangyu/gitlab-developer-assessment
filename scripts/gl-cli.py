#!/usr/bin/env python3
"""
GitLab CLI - 開發者程式碼品質與技術水平分析工具

遵循 SOLID 原則設計：
- S: 單一職責 - 每個類別只負責一個功能
- O: 開放封閉 - 透過介面擴展，不修改現有程式碼
- L: 里氏替換 - 子類別可以替換父類別
- I: 介面隔離 - 細分介面，避免實作不需要的方法
- D: 依賴反轉 - 依賴抽象而非具體實作
"""

import argparse
import sys
import os
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
import signal
import time

from gitlab_client import GitLabClient
import config
from progress_reporter import IProgressReporter, ConsoleProgressReporter, SilentProgressReporter
from common_utils import disable_ssl_warnings, ensure_output_dir, export_dataframe_to_csv
from export_utils import AccessLevelMapper, create_default_client

# 抑制 SSL 警告
disable_ssl_warnings()


# ==================== 工具類別 ====================

# AccessLevelUtil 已移至 export_utils.AccessLevelMapper


# ==================== 抽象介面 (介面隔離原則) ====================

# IProgressReporter 已從 progress_reporter 模組導入

class IDataFetcher(ABC):
    """資料獲取介面"""
    
    @abstractmethod
    def fetch(self, **kwargs) -> Any:
        """獲取資料"""
        pass


class IDataProcessor(ABC):
    """資料處理介面"""
    
    @abstractmethod
    def process(self, data: Any) -> pd.DataFrame:
        """處理資料"""
        pass


class IDataExporter(ABC):
    """資料匯出介面"""
    
    @abstractmethod
    def export(self, df: pd.DataFrame, filename: str) -> None:
        """匯出資料"""
        pass


# ==================== 資料獲取器 (單一職責原則) ====================

class ProjectDataFetcher(IDataFetcher):
    """專案資料獲取器（包含授權資訊）"""
    
    def __init__(self, client: GitLabClient, progress_reporter: Optional[IProgressReporter] = None):
        self.client = client
        self.progress = progress_reporter or SilentProgressReporter()
    
    def fetch(self, project_name: Optional[str] = None, 
              group_id: Optional[int] = None,
              include_permissions: bool = True) -> Dict[str, Any]:
        """
        獲取專案資料（包含授權資訊）
        
        Args:
            project_name: 專案名稱 (可選)
            group_id: 群組 ID (可選)
            include_permissions: 是否包含授權資訊 (預設: True)
        
        Returns:
            包含專案列表和授權資訊的字典
        """
        self.progress.report_start("正在獲取專案列表...")
        projects = self.client.get_projects(group_id=group_id, search=project_name)
        self.progress.report_complete(f"找到 {len(projects)} 個專案")
        
        result = {
            'projects': projects,
            'permissions': []
        }
        
        # 如果需要包含授權資訊
        if include_permissions and projects:
            self.progress.report_start("正在獲取授權資訊...")
            for idx, project in enumerate(projects, 1):
                try:
                    self.progress.report_progress(idx, len(projects), project.name)
                    project_detail = self.client.get_project(project.id)
                    
                    # 獲取專案成員
                    members = project_detail.members.list(all=True)
                    
                    for member in members:
                        result['permissions'].append({
                            'project_id': project.id,
                            'project_name': project.name,
                            'member_type': 'User',
                            'member_id': member.id,
                            'member_name': member.name,
                            'member_username': member.username,
                            'member_email': getattr(member, 'email', ''),
                            'access_level': member.access_level,
                            'access_level_name': AccessLevelMapper.get_level_name(member.access_level)
                        })
                    
                    # 獲取群組成員（如果有共享給群組）
                    try:
                        shared_groups = project_detail.shared_with_groups
                        for group in shared_groups:
                            result['permissions'].append({
                                'project_id': project.id,
                                'project_name': project.name,
                                'member_type': 'Group',
                                'member_id': group['group_id'],
                                'member_name': group['group_name'],
                                'member_username': '',
                                'member_email': '',
                                'access_level': group['group_access_level'],
                                'access_level_name': AccessLevelMapper.get_level_name(group['group_access_level'])
                            })
                    except:
                        pass
                        
                except Exception as e:
                    self.progress.report_warning(f"無法獲取 {project.name} 的授權資訊: {e}")
                    continue
        
        return result


class ProjectPermissionFetcher(IDataFetcher):
    """專案授權資料獲取器"""
    
    def __init__(self, client: GitLabClient, progress_reporter: Optional[IProgressReporter] = None):
        self.client = client
        self.progress = progress_reporter or SilentProgressReporter()
    
    def fetch(self, project_name: Optional[str] = None,
              group_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        獲取專案授權資料
        
        Args:
            project_name: 專案名稱 (可選)
            group_id: 群組 ID (可選)
        
        Returns:
            授權資料列表
        """
        self.progress.report_start("正在獲取專案列表...")
        projects = self.client.get_projects(group_id=group_id, search=project_name)
        self.progress.report_complete(f"找到 {len(projects)} 個專案")
        
        permissions_data = []
        
        if projects:
            self.progress.report_start("正在獲取專案授權資訊...")
            for idx, project in enumerate(projects, 1):
                self.progress.report_progress(idx, len(projects), project.name)
                project_detail = self.client.get_project(project.id)
                
                # 獲取專案成員
                members = project_detail.members.list(all=True)
                
                for member in members:
                    permissions_data.append({
                        'project_id': project.id,
                        'project_name': project.name,
                        'member_type': 'User',
                        'member_id': member.id,
                        'member_name': member.name,
                        'member_username': member.username,
                        'member_email': getattr(member, 'email', ''),
                        'access_level': member.access_level,
                        'access_level_name': AccessLevelMapper.get_level_name(member.access_level)
                    })
                
                # 獲取群組成員（如果有共享給群組）
                try:
                    shared_groups = project_detail.shared_with_groups
                    for group in shared_groups:
                        permissions_data.append({
                            'project_id': project.id,
                            'project_name': project.name,
                            'member_type': 'Group',
                            'member_id': group['group_id'],
                            'member_name': group['group_name'],
                            'member_username': '',
                            'member_email': '',
                            'access_level': group['group_access_level'],
                            'access_level_name': AccessLevelMapper.get_level_name(group['group_access_level'])
                        })
                except:
                    pass
        
        return permissions_data


class UserDataFetcher(IDataFetcher):
    """使用者資料獲取器（支援快取）"""
    
    def __init__(self, client: GitLabClient, progress_reporter: Optional[IProgressReporter] = None):
        self.client = client
        self.progress = progress_reporter or SilentProgressReporter()
        self._projects_cache = {}  # 快取字典：key=(group_id, project_name), value=[projects]
    
    def fetch(self, username: Optional[str] = None,
              project_name: Optional[str] = None,
              start_date: Optional[str] = None,
              end_date: Optional[str] = None,
              group_id: Optional[int] = None,
              user_info: Optional[Any] = None) -> Dict[str, Any]:
        """
        獲取使用者資料
        
        Args:
            username: 使用者名稱 (可選)
            project_name: 專案名稱 (可選，篩選特定專案)
            start_date: 開始日期
            end_date: 結束日期
            group_id: 群組 ID (可選)
            user_info: 使用者資訊物件 (可選，用於精確匹配)
        
        Returns:
            使用者資料字典
        """
        # 建立快取鍵值
        cache_key = (group_id, project_name)
        
        # 檢查快取
        if cache_key in self._projects_cache:
            projects = self._projects_cache[cache_key]
            self.progress.report_complete(
                f"✓ 使用快取專案列表（{len(projects)} 個專案）"
            )
        else:
            self.progress.report_start("正在獲取專案列表...")
            projects = self.client.get_projects(group_id=group_id, search=project_name)
            self._projects_cache[cache_key] = projects
            self.progress.report_complete(f"找到 {len(projects)} 個專案（已快取）")
        
        # 檢查是否有找到專案
        if project_name and not projects:
            self.progress.report_warning(f"找不到名稱包含 '{project_name}' 的專案")
        
        user_data = {
            'commits': [],
            'code_changes': [],
            'merge_requests': [],
            'code_reviews': [],
            'permissions': [],
            'user_profile': [],  # 新增：使用者基本資訊
            'user_events': [],   # 新增：使用者事件
            'contributors': []   # 新增：貢獻者統計
        }
        
        # 準備匹配條件（使用 email 和 name 進行精確匹配）
        target_email = None
        target_name = None
        target_username = username
        
        if user_info:
            target_email = getattr(user_info, 'email', None)
            target_name = getattr(user_info, 'name', None)
            target_username = getattr(user_info, 'username', username)
            
            # 收集使用者基本資訊
            user_data['user_profile'].append({
                'user_id': user_info.id,
                'username': user_info.username,
                'name': user_info.name,
                'email': getattr(user_info, 'email', ''),
                'public_email': getattr(user_info, 'public_email', ''),
                'state': getattr(user_info, 'state', ''),
                'avatar_url': getattr(user_info, 'avatar_url', ''),
                'web_url': getattr(user_info, 'web_url', ''),
                'created_at': getattr(user_info, 'created_at', ''),
                'bio': getattr(user_info, 'bio', ''),
                'location': getattr(user_info, 'location', ''),
                'organization': getattr(user_info, 'organization', ''),
                'job_title': getattr(user_info, 'job_title', ''),
                'pronouns': getattr(user_info, 'pronouns', ''),
                'website_url': getattr(user_info, 'website_url', ''),
                'skype': getattr(user_info, 'skype', ''),
                'linkedin': getattr(user_info, 'linkedin', ''),
                'twitter': getattr(user_info, 'twitter', ''),
                'last_activity_on': getattr(user_info, 'last_activity_on', ''),
                'last_sign_in_at': getattr(user_info, 'last_sign_in_at', ''),
                'current_sign_in_at': getattr(user_info, 'current_sign_in_at', ''),
                'confirmed_at': getattr(user_info, 'confirmed_at', ''),
                'is_admin': getattr(user_info, 'is_admin', False),
                'can_create_group': getattr(user_info, 'can_create_group', False),
                'can_create_project': getattr(user_info, 'can_create_project', False),
                'projects_limit': getattr(user_info, 'projects_limit', 0),
                'two_factor_enabled': getattr(user_info, 'two_factor_enabled', False),
                'external': getattr(user_info, 'external', False),
                'private_profile': getattr(user_info, 'private_profile', False),
                'followers': getattr(user_info, 'followers', 0),
                'following': getattr(user_info, 'following', 0),
                'bot': getattr(user_info, 'bot', False),
                'note': getattr(user_info, 'note', ''),
                'namespace_id': getattr(user_info, 'namespace_id', '')
            })
            
            # 獲取使用者事件
            try:
                self.progress.report_start(f"正在獲取使用者事件...")
                user_obj = self.client.gl.users.get(user_info.id)
                events = user_obj.events.list(
                    after=start_date,
                    before=end_date,
                    all=True
                )
                
                # 建立專案 ID 集合（用於過濾事件）
                project_ids = {project.id for project in projects} if projects else set()
                
                filtered_count = 0
                for event in events:
                    event_project_id = getattr(event, 'project_id', None)
                    
                    # 如果有指定專案，只保留屬於這些專案的事件
                    if projects and event_project_id not in project_ids:
                        filtered_count += 1
                        continue
                    
                    user_data['user_events'].append({
                        'user_id': user_info.id,
                        'username': user_info.username,
                        'event_id': event.id,
                        'action_name': getattr(event, 'action_name', ''),
                        'target_type': getattr(event, 'target_type', ''),
                        'target_title': getattr(event, 'target_title', ''),
                        'created_at': event.created_at,
                        'author_username': getattr(event, 'author_username', ''),
                        'project_id': event_project_id or '',
                        'push_data': str(getattr(event, 'push_data', {}))
                    })
                
                total_events = len(events)
                kept_events = len(user_data['user_events'])
                if projects:
                    self.progress.report_complete(
                        f"找到 {total_events} 個使用者事件，保留 {kept_events} 個（過濾 {filtered_count} 個非專案事件）"
                    )
                else:
                    self.progress.report_complete(f"找到 {total_events} 個使用者事件")
            except Exception as e:
                self.progress.report_warning(f"Failed to get user events: {e}")
        
        if projects:
            self.progress.report_start(f"正在分析 {len(projects)} 個專案的使用者活動...")
        
        for idx, project in enumerate(projects, 1):
            self.progress.report_progress(idx, len(projects), project.name)
            
            # 獲取 commits
            commits = self.client.get_project_commits(
                project.id,
                since=start_date,
                until=end_date
            )
            
            # 過濾符合條件的 commits
            filtered_commits = []
            for commit in commits:
                # 改善匹配邏輯：使用 email 優先，其次 name，最後 username
                if username:
                    match = False
                    if target_email and commit.author_email == target_email:
                        match = True
                    elif target_name and commit.author_name == target_name:
                        match = True
                    elif commit.author_name == username:
                        match = True
                    
                    if not match:
                        continue
                
                filtered_commits.append(commit)
            
            # 處理過濾後的 commits（加入進度提示）
            if filtered_commits:
                self.progress.report_start(f"正在處理 {len(filtered_commits)} 個 commits...")
            
            # 定義處理單個 commit 的函數
            def process_commit(commit):
                try:
                    commit_detail = self.client.get_commit_detail(project.id, commit.id)
                    diff = self.client.get_commit_diff(project.id, commit.id)
                    
                    commit_info = {
                        'project_id': project.id,
                        'project_name': project.name,
                        'commit_id': commit.id,
                        'commit_short_id': commit.short_id,
                        'author_name': commit.author_name,
                        'author_email': commit.author_email,
                        'committed_date': commit.committed_date,
                        'title': commit.title,
                        'message': commit.message,
                        'stats': commit_detail.stats,
                        'diff': diff
                    }
                    
                    # 收集程式碼異動
                    code_changes = []
                    for file_diff in diff:
                        code_changes.append({
                            'project_id': project.id,
                            'project_name': project.name,
                            'commit_id': commit.id,
                            'author_name': commit.author_name,
                            'author_email': commit.author_email,
                            'file_path': file_diff.get('new_path') or file_diff.get('old_path'),
                            'old_path': file_diff.get('old_path'),
                            'new_path': file_diff.get('new_path'),
                            'new_file': file_diff.get('new_file'),
                            'renamed_file': file_diff.get('renamed_file'),
                            'deleted_file': file_diff.get('deleted_file'),
                            'diff': file_diff.get('diff', '')
                        })
                    
                    return (commit_info, code_changes, None)
                except Exception as e:
                    return (None, None, f"Failed to get commit detail for {commit.id}: {e}")
            
            # 使用並行處理提升效能
            max_workers = 10  # 可調整並行數量
            completed = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任務
                futures = {executor.submit(process_commit, commit): commit for commit in filtered_commits}
                
                # 處理完成的任務
                for future in as_completed(futures):
                    completed += 1
                    
                    # 每處理 10 個 commit 顯示一次進度
                    if completed % 10 == 0 or completed == len(filtered_commits):
                        self.progress.report_progress(completed, len(filtered_commits), f"處理 commit {completed}/{len(filtered_commits)}")
                    
                    commit_info, code_changes, error = future.result()
                    
                    if error:
                        print(f"Warning: {error}")
                        continue
                    
                    if commit_info:
                        user_data['commits'].append(commit_info)
                    
                    if code_changes:
                        user_data['code_changes'].extend(code_changes)
            
            # 獲取 Merge Requests
            mrs = self.client.get_project_merge_requests(
                project.id,
                updated_after=start_date,
                updated_before=end_date
            )
            
            # 過濾符合條件的 MRs
            filtered_mrs = []
            for mr in mrs:
                # 改善匹配邏輯：使用 username 匹配
                if username:
                    match = False
                    if target_username and mr.author['username'] == target_username:
                        match = True
                    elif mr.author['username'] == username:
                        match = True
                    
                    if not match:
                        continue
                
                filtered_mrs.append(mr)
            
            # 處理過濾後的 MRs（使用並行處理）
            if filtered_mrs:
                self.progress.report_start(f"正在處理 {len(filtered_mrs)} 個 Merge Requests...")
            
            # 定義處理單個 MR 的函數
            def process_mr(mr):
                try:
                    mr_detail = self.client.get_merge_request_detail(project.id, mr.iid)
                    discussions = self.client.get_merge_request_discussions(project.id, mr.iid)
                    
                    mr_info = {
                        'project_id': project.id,
                        'project_name': project.name,
                        'mr_iid': mr.iid,
                        'title': mr.title,
                        'state': mr.state,
                        'author': mr.author['username'],
                        'created_at': mr.created_at,
                        'updated_at': mr.updated_at,
                        'merged_at': getattr(mr, 'merged_at', None),
                        'source_branch': mr.source_branch,
                        'target_branch': mr.target_branch,
                        'upvotes': mr.upvotes,
                        'downvotes': mr.downvotes,
                        'discussion_count': len(discussions)
                    }
                    
                    # 分析 Code Review
                    code_reviews = []
                    for discussion in discussions:
                        for note in discussion.attributes.get('notes', []):
                            code_reviews.append({
                                'project_id': project.id,
                                'project_name': project.name,
                                'mr_iid': mr.iid,
                                'author': note.get('author', {}).get('username', ''),
                                'created_at': note.get('created_at', ''),
                                'body': note.get('body', ''),
                                'type': note.get('type', ''),
                                'resolvable': note.get('resolvable', False),
                                'resolved': note.get('resolved', False)
                            })
                    
                    return (mr_info, code_reviews, None)
                except Exception as e:
                    return (None, None, f"Failed to get MR detail for {mr.iid}: {e}")
            
            # 使用並行處理提升效能
            max_workers = 10  # 可調整並行數量
            mr_completed = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任務
                futures = {executor.submit(process_mr, mr): mr for mr in filtered_mrs}
                
                # 處理完成的任務
                for future in as_completed(futures):
                    mr_completed += 1
                    
                    # 每處理 10 個 MR 顯示一次進度
                    if mr_completed % 10 == 0 or mr_completed == len(filtered_mrs):
                        self.progress.report_progress(mr_completed, len(filtered_mrs), f"處理 MR {mr_completed}/{len(filtered_mrs)}")
                    
                    mr_info, code_reviews, error = future.result()
                    
                    if error:
                        print(f"Warning: {error}")
                        continue
                    
                    if mr_info:
                        user_data['merge_requests'].append(mr_info)
                    
                    if code_reviews:
                        user_data['code_reviews'].extend(code_reviews)
            
            # 獲取專案授權資訊和貢獻者統計
            try:
                project_detail = self.client.get_project(project.id)
                
                # 獲取成員資訊（加入超時保護）
                members = []
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(project_detail.members.list, all=True)
                        members = future.result(timeout=30)  # 30秒超時
                except FutureTimeoutError:
                    self.progress.report_warning(f"獲取專案 {project.name} 成員列表超時 (30秒)，跳過此項目")
                except Exception as e:
                    self.progress.report_warning(f"獲取專案 {project.name} 成員列表失敗: {e}")
                
                for member in members:
                    # 改善匹配邏輯：使用 username 匹配
                    if username:
                        match = False
                        if target_username and member.username == target_username:
                            match = True
                        elif member.username == username:
                            match = True
                        
                        if not match:
                            continue
                    
                    user_data['permissions'].append({
                        'project_id': project.id,
                        'project_name': project.name,
                        'member_type': 'User',
                        'member_id': member.id,
                        'member_name': member.name,
                        'member_username': member.username,
                        'member_email': getattr(member, 'email', ''),
                        'access_level': member.access_level,
                        'access_level_name': AccessLevelMapper.get_level_name(member.access_level),
                        'expires_at': getattr(member, 'expires_at', None)
                    })
                
                # 獲取專案貢獻者統計（加入超時保護）
                contributors = []
                try:
                    # 使用 ThreadPoolExecutor 加入超時機制
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(project_detail.repository_contributors)
                        contributors = future.result(timeout=30)  # 30秒超時
                except FutureTimeoutError:
                    self.progress.report_warning(f"獲取專案 {project.name} 貢獻者統計超時 (30秒)，跳過此項目")
                except Exception as e:
                    self.progress.report_warning(f"獲取專案 {project.name} 貢獻者統計失敗: {e}")
                
                for contributor in contributors:
                    # 如果指定了使用者，只獲取該使用者的統計
                    if username:
                        match = False
                        if target_email and contributor.get('email') == target_email:
                            match = True
                        elif target_name and contributor.get('name') == target_name:
                            match = True
                        elif contributor.get('name') == username:
                            match = True
                        
                        if not match:
                            continue
                    
                    user_data['contributors'].append({
                        'project_id': project.id,
                        'project_name': project.name,
                        'contributor_name': contributor.get('name', ''),
                        'contributor_email': contributor.get('email', ''),
                        'total_commits': contributor.get('commits', 0),
                        'total_additions': contributor.get('additions', 0),
                        'total_deletions': contributor.get('deletions', 0)
                    })
            except Exception as e:
                self.progress.report_warning(f"Failed to get project details/contributors for {project.name}: {e}")
        
        return user_data
    
    def clear_cache(self):
        """清除所有專案快取"""
        self._projects_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        取得快取統計資訊
        
        Returns:
            包含快取統計的字典
        """
        total_projects = sum(len(projects) for projects in self._projects_cache.values())
        return {
            'cached_queries': len(self._projects_cache),
            'total_cached_projects': total_projects
        }



class UserProjectsFetcher(IDataFetcher):
    """使用者專案列表獲取器"""
    
    def __init__(self, client: GitLabClient, progress_reporter: Optional[IProgressReporter] = None):
        self.client = client
        self.progress = progress_reporter or SilentProgressReporter()
    
    def fetch(self, username: Optional[str] = None, group_name: Optional[str] = None) -> Dict[str, Any]:
        """
        獲取使用者參與的專案列表
        
        Args:
            username: 使用者名稱 (可選)
            group_name: 群組名稱 (可選)
        
        Returns:
            使用者專案資料
        """
        # 如果有提供群組名稱，先轉換為群組 ID
        group_id = None
        if group_name:
            try:
                groups = self.client.get_groups(group_name=group_name)
                if groups:
                    group_id = groups[0].id
                    self.progress.report_complete(f"找到群組：{groups[0].name} (ID: {group_id})")
                else:
                    self.progress.report_warning(f"找不到群組 '{group_name}'，將查詢所有專案")
            except Exception as e:
                self.progress.report_warning(f"無法查詢群組: {e}")
        
        self.progress.report_start("正在獲取專案列表...")
        projects = self.client.get_projects(group_id=group_id)
        self.progress.report_complete(f"找到 {len(projects)} 個專案")
        
        user_projects = []
        
        # 驗證使用者是否存在
        user_info = None
        if username:
            try:
                users = self.client.gl.users.list(username=username)
                if users:
                    user_info = users[0]
                    self.progress.report_complete(f"找到使用者：{user_info.name} (@{user_info.username})")
            except Exception as e:
                self.progress.report_warning(f"無法驗證使用者: {e}")
        
        if projects:
            if username:
                self.progress.report_start(f"正在檢查 {len(projects)} 個專案，尋找使用者的參與專案...")
            else:
                self.progress.report_start(f"正在分析 {len(projects)} 個專案的成員資訊...")
        
        for idx, project in enumerate(projects, 1):
            # 只在找到使用者時才顯示進度，避免誤導
            if username:
                self.progress.report_progress(idx, len(projects), f"檢查中... 已找到 {len(user_projects)} 個")
            else:
                self.progress.report_progress(idx, len(projects), project.name)
            
            try:
                project_detail = self.client.get_project(project.id)
                # 使用 members_all 來包含繼承的權限（透過群組獲得的權限）
                members = project_detail.members_all.list(all=True)
                
                for member in members:
                    # 如果指定了使用者名稱，則過濾
                    if username:
                        if user_info and member.username != user_info.username:
                            continue
                        elif not user_info and member.username != username:
                            continue
                    
                    user_projects.append({
                        'user_id': member.id,
                        'username': member.username,
                        'name': member.name,
                        'email': getattr(member, 'email', ''),
                        'project_id': project.id,
                        'project_name': project.name,
                        'project_description': project.description or '',
                        'project_visibility': project.visibility,
                        'project_created_at': project.created_at,
                        'project_last_activity': project.last_activity_at,
                        'access_level': member.access_level,
                        'access_level_name': AccessLevelMapper.get_level_name(member.access_level),
                        'expires_at': getattr(member, 'expires_at', None)
                    })
            except Exception as e:
                self.progress.report_warning(f"Failed to get members for project {project.name}: {e}")
        
        return {'user_projects': user_projects}


class GroupDataFetcher(IDataFetcher):
    """群組資料獲取器（包含子群組、專案、授權資訊）"""
    
    def __init__(self, client: GitLabClient, progress_reporter: Optional[IProgressReporter] = None):
        self.client = client
        self.progress = progress_reporter or SilentProgressReporter()
    
    def fetch(self, group_name: Optional[str] = None) -> Dict[str, Any]:
        """
        獲取群組資料
        
        Args:
            group_name: 群組名稱 (可選，不填則取得全部)
        
        Returns:
            群組資料字典，包含群組資訊、子群組、專案、授權
        """
        self.progress.report_start("正在獲取群組列表...")
        groups = self.client.get_groups(group_name=group_name)
        self.progress.report_complete(f"找到 {len(groups)} 個群組")
        
        groups_data = []
        subgroups_data = []
        projects_data = []
        permissions_data = []
        
        if groups:
            self.progress.report_start(f"正在分析 {len(groups)} 個群組...")
        
        for idx, group in enumerate(groups, 1):
            try:
                self.progress.report_progress(idx, len(groups), group.name)
                
                # 取得完整群組資訊
                group_detail = self.client.get_group(group.id)
                
                # 群組基本資訊
                group_info = {
                    'group_id': group_detail.id,
                    'group_name': group_detail.name,
                    'group_path': group_detail.path,
                    'group_full_path': group_detail.full_path,
                    'description': getattr(group_detail, 'description', ''),
                    'visibility': getattr(group_detail, 'visibility', ''),
                    'created_at': getattr(group_detail, 'created_at', ''),
                    'web_url': getattr(group_detail, 'web_url', ''),
                    'parent_id': getattr(group_detail, 'parent_id', None),
                }
                
                # 取得群組成員
                members = self.client.get_group_members(group_detail.id)
                group_info['total_members'] = len(members)
                group_info['owners'] = len([m for m in members if m.access_level == 50])
                group_info['maintainers'] = len([m for m in members if m.access_level == 40])
                group_info['developers'] = len([m for m in members if m.access_level == 30])
                group_info['reporters'] = len([m for m in members if m.access_level == 20])
                group_info['guests'] = len([m for m in members if m.access_level == 10])
                
                # 群組成員授權資訊
                for member in members:
                    permissions_data.append({
                        'group_id': group_detail.id,
                        'group_name': group_detail.name,
                        'resource_type': 'Group',
                        'member_id': member.id,
                        'member_name': getattr(member, 'name', ''),
                        'member_username': member.username,
                        'member_email': getattr(member, 'email', ''),
                        'access_level': member.access_level,
                        'access_level_name': AccessLevelMapper.get_level_name(member.access_level),
                        'expires_at': getattr(member, 'expires_at', None)
                    })
                
                # 取得子群組
                try:
                    subgroups = self.client.get_group_subgroups(group_detail.id)
                    group_info['subgroups_count'] = len(subgroups)
                    
                    for subgroup in subgroups:
                        subgroups_data.append({
                            'parent_group_id': group_detail.id,
                            'parent_group_name': group_detail.name,
                            'subgroup_id': subgroup.id,
                            'subgroup_name': subgroup.name,
                            'subgroup_path': subgroup.path,
                            'subgroup_full_path': subgroup.full_path,
                            'description': getattr(subgroup, 'description', ''),
                            'visibility': getattr(subgroup, 'visibility', ''),
                            'web_url': getattr(subgroup, 'web_url', ''),
                        })
                except:
                    group_info['subgroups_count'] = 0
                
                # 取得群組專案
                try:
                    projects = self.client.get_group_projects(group_detail.id)
                    group_info['projects_count'] = len(projects)
                    
                    for project in projects:
                        project_info = {
                            'group_id': group_detail.id,
                            'group_name': group_detail.name,
                            'project_id': project.id,
                            'project_name': project.name,
                            'project_path': project.path,
                            'description': getattr(project, 'description', ''),
                            'visibility': getattr(project, 'visibility', ''),
                            'created_at': getattr(project, 'created_at', ''),
                            'last_activity_at': getattr(project, 'last_activity_at', ''),
                            'web_url': getattr(project, 'web_url', ''),
                        }
                        projects_data.append(project_info)
                        
                        # 取得專案成員授權
                        try:
                            project_detail = self.client.get_project(project.id)
                            project_members = project_detail.members.list(all=True)
                            
                            for member in project_members:
                                permissions_data.append({
                                    'group_id': group_detail.id,
                                    'group_name': group_detail.name,
                                    'resource_type': 'Project',
                                    'resource_id': project.id,
                                    'resource_name': project.name,
                                    'member_id': member.id,
                                    'member_name': getattr(member, 'name', ''),
                                    'member_username': member.username,
                                    'member_email': getattr(member, 'email', ''),
                                    'access_level': member.access_level,
                                    'access_level_name': AccessLevelMapper.get_level_name(member.access_level),
                                    'expires_at': getattr(member, 'expires_at', None)
                                })
                            
                            # 取得共享給群組的授權
                            shared_groups = getattr(project_detail, 'shared_with_groups', [])
                            for shared_group in shared_groups:
                                permissions_data.append({
                                    'group_id': group_detail.id,
                                    'group_name': group_detail.name,
                                    'resource_type': 'Project',
                                    'resource_id': project.id,
                                    'resource_name': project.name,
                                    'member_id': shared_group.get('group_id'),
                                    'member_name': shared_group.get('group_name'),
                                    'member_username': '',
                                    'member_email': '',
                                    'access_level': shared_group.get('group_access_level'),
                                    'access_level_name': AccessLevelMapper.get_level_name(shared_group.get('group_access_level')),
                                    'expires_at': shared_group.get('expires_at', None)
                                })
                        except Exception as e:
                            self.progress.report_warning(f"Failed to get permissions for project {project.name}: {e}")
                except:
                    group_info['projects_count'] = 0
                
                groups_data.append(group_info)
                
            except Exception as e:
                self.progress.report_warning(f"Failed to fetch group {group.name}: {e}")
        
        return {
            'groups': groups_data,
            'subgroups': subgroups_data,
            'projects': projects_data,
            'permissions': permissions_data
        }


# ==================== 資料處理器 (單一職責原則) ====================

class ProjectDataProcessor(IDataProcessor):
    """專案資料處理器（包含授權統計）"""
    
    def process(self, data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """
        處理專案資料和授權資訊
        
        Args:
            data: 包含 'projects' 和 'permissions' 的字典
        
        Returns:
            包含 'projects' 和 'permissions' DataFrame 的字典
        """
        projects = data.get('projects', [])
        permissions = data.get('permissions', [])
        
        result = {}
        
        # 處理專案基本資料
        projects_data = []
        for project in projects:
            # 計算該專案的授權統計
            project_perms = [p for p in permissions if p['project_id'] == project.id]
            user_count = len([p for p in project_perms if p['member_type'] == 'User'])
            group_count = len([p for p in project_perms if p['member_type'] == 'Group'])
            
            # 統計各權限等級的人數
            owner_count = len([p for p in project_perms if p['access_level'] == 50])
            maintainer_count = len([p for p in project_perms if p['access_level'] == 40])
            developer_count = len([p for p in project_perms if p['access_level'] == 30])
            reporter_count = len([p for p in project_perms if p['access_level'] == 20])
            guest_count = len([p for p in project_perms if p['access_level'] == 10])
            
            projects_data.append({
                'project_id': project.id,
                'project_name': project.name,
                'description': getattr(project, 'description', ''),
                'visibility': getattr(project, 'visibility', ''),
                'created_at': getattr(project, 'created_at', ''),
                'last_activity_at': getattr(project, 'last_activity_at', ''),
                'default_branch': getattr(project, 'default_branch', ''),
                'ssh_url': getattr(project, 'ssh_url_to_repo', ''),
                'http_url': getattr(project, 'http_url_to_repo', ''),
                'web_url': getattr(project, 'web_url', ''),
                'star_count': getattr(project, 'star_count', 0),
                'forks_count': getattr(project, 'forks_count', 0),
                'open_issues_count': getattr(project, 'open_issues_count', 0),
                # 新增授權統計欄位
                'total_members': user_count + group_count,
                'user_members': user_count,
                'group_members': group_count,
                'owners': owner_count,
                'maintainers': maintainer_count,
                'developers': developer_count,
                'reporters': reporter_count,
                'guests': guest_count,
            })
        
        result['projects'] = pd.DataFrame(projects_data)
        
        # 處理授權詳細資料
        if permissions:
            result['permissions'] = pd.DataFrame(permissions)
        else:
            result['permissions'] = pd.DataFrame()
        
        return result


class ProjectPermissionProcessor(IDataProcessor):
    """專案授權資料處理器"""
    
    def process(self, permissions: List[Dict[str, Any]]) -> pd.DataFrame:
        """處理授權資料"""
        return pd.DataFrame(permissions)


class UserDataProcessor(IDataProcessor):
    """使用者資料處理器"""
    
    def process(self, user_data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """處理使用者資料"""
        result = {}
        
        # 處理使用者基本資訊
        if user_data.get('user_profile'):
            result['user_profile'] = pd.DataFrame(user_data['user_profile'])
        else:
            result['user_profile'] = pd.DataFrame()
        
        # 處理使用者事件
        if user_data.get('user_events'):
            result['user_events'] = pd.DataFrame(user_data['user_events'])
        else:
            result['user_events'] = pd.DataFrame()
        
        # 處理貢獻者統計
        if user_data.get('contributors'):
            result['contributors'] = pd.DataFrame(user_data['contributors'])
        else:
            result['contributors'] = pd.DataFrame()
        
        # 處理 commits
        if user_data['commits']:
            commits_df = pd.DataFrame([{
                'project_id': c['project_id'],
                'project_name': c['project_name'],
                'commit_id': c['commit_id'],
                'commit_short_id': c['commit_short_id'],
                'author_name': c['author_name'],
                'author_email': c['author_email'],
                'committed_date': c['committed_date'],
                'title': c['title'],
                'additions': c['stats'].get('additions', 0),
                'deletions': c['stats'].get('deletions', 0),
                'total': c['stats'].get('total', 0),
            } for c in user_data['commits']])
            result['commits'] = commits_df
        else:
            result['commits'] = pd.DataFrame()
        
        # 處理程式碼異動
        if user_data['code_changes']:
            result['code_changes'] = pd.DataFrame(user_data['code_changes'])
        else:
            result['code_changes'] = pd.DataFrame()
        
        # 處理 Merge Requests
        if user_data['merge_requests']:
            result['merge_requests'] = pd.DataFrame(user_data['merge_requests'])
        else:
            result['merge_requests'] = pd.DataFrame()
        
        # 處理 Code Reviews
        if user_data['code_reviews']:
            result['code_reviews'] = pd.DataFrame(user_data['code_reviews'])
        else:
            result['code_reviews'] = pd.DataFrame()
        
        # 處理授權資訊
        if user_data.get('permissions'):
            result['permissions'] = pd.DataFrame(user_data['permissions'])
        else:
            result['permissions'] = pd.DataFrame()
        
        # 產生統計資料（包含授權統計）
        result['statistics'] = self._generate_statistics(result)
        
        return result
    
    def _generate_statistics(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """產生統計資料（包含授權統計、貢獻者統計和事件統計）"""
        stats = []
        
        commits_df = data.get('commits', pd.DataFrame())
        mrs_df = data.get('merge_requests', pd.DataFrame())
        reviews_df = data.get('code_reviews', pd.DataFrame())
        changes_df = data.get('code_changes', pd.DataFrame())
        permissions_df = data.get('permissions', pd.DataFrame())
        contributors_df = data.get('contributors', pd.DataFrame())
        events_df = data.get('user_events', pd.DataFrame())
        
        if not commits_df.empty:
            # 按作者統計
            for author in commits_df['author_name'].unique():
                author_commits = commits_df[commits_df['author_name'] == author]
                author_mrs = mrs_df[mrs_df['author'] == author] if not mrs_df.empty else pd.DataFrame()
                
                # 獲取該作者的授權統計
                author_email = author_commits.iloc[0]['author_email']
                author_perms = permissions_df
                if not permissions_df.empty:
                    # 優先使用 email 匹配，其次使用 username 和 name
                    author_perms = permissions_df[
                        (permissions_df['member_email'] == author_email) |  # Email 優先
                        (permissions_df['member_username'] == author) |
                        (permissions_df['member_name'] == author)
                    ]
                
                # 統計授權資訊
                total_projects_with_access = len(author_perms) if not author_perms.empty else 0
                owner_projects = len(author_perms[author_perms['access_level'] == 50]) if not author_perms.empty else 0
                maintainer_projects = len(author_perms[author_perms['access_level'] == 40]) if not author_perms.empty else 0
                developer_projects = len(author_perms[author_perms['access_level'] == 30]) if not author_perms.empty else 0
                reporter_projects = len(author_perms[author_perms['access_level'] == 20]) if not author_perms.empty else 0
                guest_projects = len(author_perms[author_perms['access_level'] == 10]) if not author_perms.empty else 0
                
                # 從貢獻者統計取得總計（如果有的話）
                contributor_stats = contributors_df
                if not contributors_df.empty:
                    contributor_stats = contributors_df[
                        (contributors_df['contributor_email'] == author_email) |
                        (contributors_df['contributor_name'] == author)
                    ]
                
                total_contrib_commits = contributor_stats['total_commits'].sum() if not contributor_stats.empty else 0
                total_contrib_additions = contributor_stats['total_additions'].sum() if not contributor_stats.empty else 0
                total_contrib_deletions = contributor_stats['total_deletions'].sum() if not contributor_stats.empty else 0
                
                # 統計事件
                total_events = 0
                if not events_df.empty:
                    # 這裡根據 author_email 或 username 匹配
                    total_events = len(events_df)
                
                stats.append({
                    'author_name': author,
                    'author_email': author_email,
                    'total_commits': len(author_commits),
                    'total_additions': author_commits['additions'].sum(),
                    'total_deletions': author_commits['deletions'].sum(),
                    'total_changes': author_commits['total'].sum(),
                    'avg_changes_per_commit': author_commits['total'].mean(),
                    'total_merge_requests': len(author_mrs),
                    'merged_mrs': len(author_mrs[author_mrs['state'] == 'merged']) if not author_mrs.empty else 0,
                    'projects_contributed': author_commits['project_name'].nunique(),
                    'total_code_reviews': len(reviews_df[reviews_df['author'] == author]) if not reviews_df.empty else 0,
                    'total_files_changed': len(changes_df[changes_df['author_name'] == author]) if not changes_df.empty else 0,
                    # 新增授權統計
                    'total_projects_with_access': total_projects_with_access,
                    'owner_projects': owner_projects,
                    'maintainer_projects': maintainer_projects,
                    'developer_projects': developer_projects,
                    'reporter_projects': reporter_projects,
                    'guest_projects': guest_projects,
                    # 新增貢獻者統計（來自 repository_contributors API）
                    'contributor_total_commits': total_contrib_commits,
                    'contributor_total_additions': total_contrib_additions,
                    'contributor_total_deletions': total_contrib_deletions,
                    # 新增事件統計
                    'total_user_events': total_events,
                })
        
        return pd.DataFrame(stats)


class UserProjectsProcessor(IDataProcessor):
    """使用者專案資料處理器"""
    
    def process(self, data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """處理使用者專案資料"""
        result = {}
        
        if data['user_projects']:
            result['projects'] = pd.DataFrame(data['user_projects'])
        else:
            result['projects'] = pd.DataFrame()
        
        # 產生統計資料
        result['statistics'] = self._generate_statistics(result['projects'])
        
        return result
    
    def _generate_statistics(self, projects_df: pd.DataFrame) -> pd.DataFrame:
        """產生統計資料"""
        if projects_df.empty:
            return pd.DataFrame()
        
        stats = []
        
        # 按使用者統計
        for username in projects_df['username'].unique():
            user_projects = projects_df[projects_df['username'] == username]
            user_name = user_projects.iloc[0]['name']
            user_email = user_projects.iloc[0]['email']
            
            stats.append({
                'username': username,
                'name': user_name,
                'email': user_email,
                'total_projects': len(user_projects),
                'owner_projects': len(user_projects[user_projects['access_level'] == 50]),
                'maintainer_projects': len(user_projects[user_projects['access_level'] == 40]),
                'developer_projects': len(user_projects[user_projects['access_level'] == 30]),
                'reporter_projects': len(user_projects[user_projects['access_level'] == 20]),
                'guest_projects': len(user_projects[user_projects['access_level'] == 10]),
            })
        
        return pd.DataFrame(stats)


class GroupDataProcessor(IDataProcessor):
    """群組資料處理器"""
    
    def process(self, data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """
        處理群組資料
        
        Args:
            data: 包含 'groups', 'subgroups', 'projects', 'permissions' 的字典
        
        Returns:
            包含多個 DataFrame 的字典
        """
        result = {}
        
        # 處理群組資料
        groups_data = data.get('groups', [])
        if groups_data:
            result['groups'] = pd.DataFrame(groups_data)
        else:
            result['groups'] = pd.DataFrame()
        
        # 處理子群組資料
        subgroups_data = data.get('subgroups', [])
        if subgroups_data:
            result['subgroups'] = pd.DataFrame(subgroups_data)
        else:
            result['subgroups'] = pd.DataFrame()
        
        # 處理專案資料
        projects_data = data.get('projects', [])
        if projects_data:
            result['projects'] = pd.DataFrame(projects_data)
        else:
            result['projects'] = pd.DataFrame()
        
        # 處理授權資料
        permissions_data = data.get('permissions', [])
        if permissions_data:
            result['permissions'] = pd.DataFrame(permissions_data)
        else:
            result['permissions'] = pd.DataFrame()
        
        return result


# ==================== 資料匯出器 (單一職責原則) ====================

class DataExporter(IDataExporter):
    """資料匯出器 - 支援 CSV"""
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export(self, df: pd.DataFrame, filename: str, subdir: Optional[str] = None) -> None:
        """
        匯出資料到 CSV
        
        Args:
            df: 要匯出的 DataFrame
            filename: 檔案名稱（不含副檔名）
            subdir: 子目錄名稱（可選）
        """
        if df.empty:
            print(f"Warning: No data to export for {filename}")
            return
        
        # 決定輸出目錄
        if subdir:
            output_path = self.output_dir / subdir
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = self.output_dir
        
        # 匯出 CSV
        csv_path = export_dataframe_to_csv(df, str(output_path), filename)
        print(f"✓ CSV exported: {csv_path}")


# ==================== 服務層 (開放封閉原則) ====================

class BaseService(ABC):
    """基礎服務類別"""
    
    def __init__(self, fetcher: IDataFetcher, processor: IDataProcessor, exporter: IDataExporter):
        self.fetcher = fetcher
        self.processor = processor
        self.exporter = exporter
    
    @abstractmethod
    def execute(self, **kwargs) -> None:
        """執行服務"""
        pass


class ProjectStatsService(BaseService):
    """專案統計服務（包含授權資訊）"""
    
    def execute(self, project_name: Optional[str] = None, group_id: Optional[int] = None) -> None:
        """執行專案統計"""
        start_time = time.time()
        
        print("=" * 70)
        print("GitLab 專案資訊查詢（包含授權統計）")
        print("=" * 70)
        
        # 獲取資料（包含授權資訊）
        data = self.fetcher.fetch(project_name=project_name, group_id=group_id)
        
        if not data['projects']:
            print("No projects found.")
            return
        
        # 處理資料
        processed_data = self.processor.process(data)
        
        # 取得專案路徑作為子目錄名稱
        # 從第一筆專案資料中取得 path
        project_path = None
        if not processed_data['projects'].empty:
            project_path = processed_data['projects'].iloc[0].get('path', None)
        
        # 如果沒有 project_path，使用 project_name
        if not project_path and project_name:
            project_path = project_name
        
        # 建立兩層目錄結構：projects/{project_path}/
        subdir = f"projects/{project_path}" if project_path else "projects"
        
        # 匯出專案資料（包含授權統計）
        self.exporter.export(processed_data['projects'], 'project', subdir=subdir)
        
        # 匯出授權詳細資料
        if not processed_data['permissions'].empty:
            self.exporter.export(processed_data['permissions'], 'permissions', subdir=subdir)
            print(f"\n✓ Total permission records: {len(processed_data['permissions'])}")
        
        print(f"✓ Total projects: {len(processed_data['projects'])}")
        
        elapsed_time = time.time() - start_time
        print(f"✓ 執行時間: {elapsed_time:.2f} 秒")
        print("=" * 70)


class ProjectPermissionService(BaseService):
    """專案授權服務"""
    
    def execute(self, project_name: Optional[str] = None, group_id: Optional[int] = None) -> None:
        """執行專案授權查詢"""
        start_time = time.time()
        
        print("=" * 70)
        print("GitLab 專案授權資訊查詢")
        print("=" * 70)
        
        # 獲取資料
        permissions = self.fetcher.fetch(project_name=project_name, group_id=group_id)
        
        if not permissions:
            print("No permissions found.")
            return
        
        # 處理資料
        df = self.processor.process(permissions)
        
        # 取得專案路徑作為子目錄名稱
        # 從第一筆權限資料中取得 project_path
        project_path = None
        if not df.empty and 'project_path' in df.columns:
            project_path = df.iloc[0].get('project_path', None)
        
        # 如果沒有 project_path，使用 project_name
        if not project_path and project_name:
            project_path = project_name
        
        # 建立兩層目錄結構：projects/{project_path}/
        subdir = f"projects/{project_path}" if project_path else "projects"
        
        # 匯出資料
        self.exporter.export(df, 'permissions', subdir=subdir)
        
        print(f"\n✓ Total permission records: {len(df)}")
        
        elapsed_time = time.time() - start_time
        print(f"✓ 執行時間: {elapsed_time:.2f} 秒")
        print("=" * 70)


class UserStatsService(BaseService):
    """使用者統計服務"""
    
    def execute(self, username: Optional[str] = None,
                project_name: Optional[str] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                group_id: Optional[int] = None) -> None:
        """執行使用者統計"""
        start_time = time.time()
        
        print("=" * 70)
        print("GitLab 使用者資訊查詢")
        print("=" * 70)
        
        # 驗證使用者是否存在
        user_info = None
        if username:
            try:
                users = self.fetcher.client.gl.users.list(username=username)
                if not users:
                    print(f"\n❌ 錯誤：找不到使用者 '{username}'")
                    print("\n建議：")
                    print(f"  • 檢查使用者名稱是否正確")
                    print(f"  • 使用 GitLab username（不是顯示名稱）")
                    print(f"  • 執行不帶 --username 參數查看所有使用者")
                    print("\n" + "=" * 70)
                    return
                else:
                    user_info = users[0]
                    print(f"\n✓ 找到使用者：{user_info.name} (@{user_info.username})")
                    if hasattr(user_info, 'email'):
                        print(f"  Email: {user_info.email}")
            except Exception as e:
                print(f"\n⚠️  警告：無法驗證使用者 ({e})")
                print("  繼續執行查詢...")
        
        # 顯示查詢範圍
        if project_name:
            print(f"\n📂 查詢範圍：專案 '{project_name}'")
        
        # 獲取資料
        user_data = self.fetcher.fetch(
            username=username,
            project_name=project_name,
            start_date=start_date,
            end_date=end_date,
            group_id=group_id,
            user_info=user_info  # 傳遞使用者資訊以便精確匹配
        )
        
        # 處理資料
        processed_data = self.processor.process(user_data)
        
        # 按照開發者分組並匯出（不論有沒有指定 username）
        exported_count = self._export_by_developer(processed_data, username, project_name)
        
        # 產生索引檔案已移至 _export_by_developer 中
        
        # 顯示統計摘要
        if not processed_data['statistics'].empty:
            print("\n" + "=" * 70)
            print("統計摘要")
            print("=" * 70)
            print(processed_data['statistics'].to_string(index=False))
        
        print("\n" + "=" * 70)
        
        # 檢查是否有輸出資料
        if exported_count == 0:
            if username:
                print(f"⚠️  警告：沒有找到使用者 '{username}' 的任何資料")
                print("\n可能原因：")
                print(f"  • 使用者在指定時間範圍內沒有任何活動")
                print(f"  • 使用者的 Git 設定名稱與 GitLab username 不同")
                print(f"  • 使用者沒有權限存取的專案")
                print(f"\n建議：")
                print(f"  • 嘗試調整時間範圍（--start-date / --end-date）")
                print(f"  • 執行不帶 --username 參數查看所有開發者名稱")
            else:
                print("⚠️  警告：沒有找到任何使用者資料")
        else:
            print("✓ 查詢完成！")
            print(f"✓ 共匯出 {exported_count} 個資料檔案")
        
        elapsed_time = time.time() - start_time
        print(f"✓ 執行時間: {elapsed_time:.2f} 秒")
        print("=" * 70)
    
    def _export_by_developer(self, processed_data: Dict[str, pd.DataFrame], 
                            username: Optional[str] = None,
                            project_name: Optional[str] = None) -> int:
        """
        按照開發者分組並匯出資料
        
        Args:
            processed_data: 處理後的資料
            username: 指定的使用者名稱（可選）
            project_name: 指定的專案名稱（可選）
            
        Returns:
            匯出的檔案數量
        """
        total_exported_count = 0
        
        # 優先從 user_profile 取得 GitLab username
        user_profile_df = processed_data.get('user_profile', pd.DataFrame())
        
        if not user_profile_df.empty and 'username' in user_profile_df.columns:
            # 使用 GitLab username（最優先）
            gitlab_username = user_profile_df.iloc[0]['username']
            
            # 建立使用者專屬目錄：output/users/{username}/
            user_output_dir = Path(self.exporter.output_dir) / 'users' / gitlab_username
            user_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 建立使用者專屬的 exporter
            user_exporter = DataExporter(output_dir=str(user_output_dir))
            
            # 匯出所有資料（不需要過濾，因為已經是該使用者的資料）
            exported_files = []
            for data_type, df in processed_data.items():
                if not df.empty:
                    # 檔名直接使用資料類型（如 commits.csv, merge_requests.csv）
                    filename = data_type
                    user_exporter.export(df, filename)
                    exported_files.append((data_type, filename))
                    total_exported_count += 1
            
            # 產生該使用者的索引檔案
            if exported_files:
                self._generate_developer_index_file(user_exporter, gitlab_username, exported_files, gitlab_username)
            
            return total_exported_count
        
        # 如果沒有 user_profile，使用原有邏輯（按 author_name 分組）
        # 從 commits 中取得所有開發者的 author_name 和 author_email
        commits_df = processed_data.get('commits', pd.DataFrame())
        
        if commits_df.empty:
            # 如果沒有 commits，檢查其他資料來源
            statistics_df = processed_data.get('statistics', pd.DataFrame())
            if not statistics_df.empty and 'author_name' in statistics_df.columns:
                # 從統計資料中取得開發者列表
                developers = statistics_df[['author_name', 'author_email']].drop_duplicates()
            else:
                # 沒有開發者資料，使用原本的邏輯（單一匯出）
                print("⚠️  警告：沒有找到開發者資料，將使用預設匯出方式")
                return self._export_single(processed_data, username, project_name)
        else:
            # 從 commits 中取得開發者列表
            developers = commits_df[['author_name', 'author_email']].drop_duplicates()
        
        # 為每個開發者建立輸出目錄並匯出
        for _, dev_row in developers.iterrows():
            dev_name = dev_row['author_name']
            dev_email = dev_row['author_email']
            
            # 建立開發者專屬目錄：output/users/{author_name}/
            dev_output_dir = Path(self.exporter.output_dir) / 'users' / dev_name
            dev_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 建立開發者專屬的 exporter
            dev_exporter = DataExporter(output_dir=str(dev_output_dir))
            
            # 過濾該開發者的資料
            dev_data = self._filter_developer_data(processed_data, dev_name, dev_email)
            
            # 匯出該開發者的資料
            exported_files = []
            for data_type, df in dev_data.items():
                if not df.empty:
                    # 檔名直接使用資料類型
                    filename = data_type
                    dev_exporter.export(df, filename)
                    exported_files.append((data_type, filename))
                    total_exported_count += 1
            
            # 產生該開發者的索引檔案
            if exported_files:
                self._generate_developer_index_file(dev_exporter, dev_name, exported_files, dev_name)
        
        return total_exported_count
    
    def _export_single(self, processed_data: Dict[str, pd.DataFrame], 
                      username: Optional[str] = None,
                      project_name: Optional[str] = None) -> int:
        """
        單一匯出（當無法分組時使用）
        
        Args:
            processed_data: 處理後的資料
            username: 指定的使用者名稱（可選）
            project_name: 指定的專案名稱（可選）
            
        Returns:
            匯出的檔案數量
        """
        if username and project_name:
            base_filename = f"{username}-{project_name}-user"
        elif username:
            base_filename = f"{username}-user"
        elif project_name:
            base_filename = f"{project_name}-users"
        else:
            base_filename = "all-users"
        
        exported_count = 0
        exported_files = []
        for data_type, df in processed_data.items():
            if not df.empty:
                filename = f"{base_filename}-{data_type}"
                self.exporter.export(df, filename)
                exported_files.append((data_type, filename))
                exported_count += 1
        
        if exported_files:
            self._generate_index_file(base_filename, exported_files)
        
        return exported_count
    
    def _filter_developer_data(self, processed_data: Dict[str, pd.DataFrame],
                               dev_name: str, dev_email: str) -> Dict[str, pd.DataFrame]:
        """
        過濾出特定開發者的資料
        
        Args:
            processed_data: 處理後的資料
            dev_name: 開發者名稱
            dev_email: 開發者 Email
            
        Returns:
            該開發者的資料
        """
        result = {}
        
        # 過濾 commits
        commits_df = processed_data.get('commits', pd.DataFrame())
        if not commits_df.empty:
            result['commits'] = commits_df[
                (commits_df['author_name'] == dev_name) & 
                (commits_df['author_email'] == dev_email)
            ]
        else:
            result['commits'] = pd.DataFrame()
        
        # 過濾 code_changes
        code_changes_df = processed_data.get('code_changes', pd.DataFrame())
        if not code_changes_df.empty and 'author_name' in code_changes_df.columns:
            result['code_changes'] = code_changes_df[code_changes_df['author_name'] == dev_name]
        else:
            result['code_changes'] = pd.DataFrame()
        
        # 過濾 merge_requests
        merge_requests_df = processed_data.get('merge_requests', pd.DataFrame())
        if not merge_requests_df.empty and 'author' in merge_requests_df.columns:
            result['merge_requests'] = merge_requests_df[merge_requests_df['author'] == dev_name]
        else:
            result['merge_requests'] = pd.DataFrame()
        
        # 過濾 code_reviews
        code_reviews_df = processed_data.get('code_reviews', pd.DataFrame())
        if not code_reviews_df.empty and 'author' in code_reviews_df.columns:
            result['code_reviews'] = code_reviews_df[code_reviews_df['author'] == dev_name]
        else:
            result['code_reviews'] = pd.DataFrame()
        
        # 過濾 permissions
        permissions_df = processed_data.get('permissions', pd.DataFrame())
        if not permissions_df.empty:
            result['permissions'] = permissions_df[
                (permissions_df['member_email'] == dev_email) |
                (permissions_df['member_name'] == dev_name)
            ]
        else:
            result['permissions'] = pd.DataFrame()
        
        # 過濾 statistics
        statistics_df = processed_data.get('statistics', pd.DataFrame())
        if not statistics_df.empty and 'author_name' in statistics_df.columns:
            result['statistics'] = statistics_df[
                (statistics_df['author_name'] == dev_name) & 
                (statistics_df['author_email'] == dev_email)
            ]
        else:
            result['statistics'] = pd.DataFrame()
        
        # 過濾 contributors
        contributors_df = processed_data.get('contributors', pd.DataFrame())
        if not contributors_df.empty:
            result['contributors'] = contributors_df[
                (contributors_df['contributor_email'] == dev_email) |
                (contributors_df['contributor_name'] == dev_name)
            ]
        else:
            result['contributors'] = pd.DataFrame()
        
        # user_profile 和 user_events 通常是單一使用者的，直接使用
        result['user_profile'] = processed_data.get('user_profile', pd.DataFrame())
        result['user_events'] = processed_data.get('user_events', pd.DataFrame())
        
        return result
    
    def _generate_developer_index_file(self, exporter: DataExporter, 
                                       base_filename: str, 
                                       exported_files: List[tuple],
                                       dev_name: str) -> None:
        """
        產生開發者專屬的索引檔案
        
        Args:
            exporter: 資料匯出器
            base_filename: 基礎檔名
            exported_files: 已匯出的檔案列表 [(data_type, filename), ...]
            dev_name: 開發者名稱
        """
        index_filename = f"{base_filename}-index.md"
        index_path = exporter.output_dir / index_filename
        
        # 準備索引內容
        content = f"# 使用者分析報告索引\n\n"
        content += f"**開發者：** {dev_name}\n\n"
        content += f"**產生時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += f"## 匯出檔案清單\n\n"
        
        for data_type, filename in exported_files:
            content += f"- [{filename}]({filename}.csv)\n"
        
        # 寫入索引檔案
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Index file generated: {index_path}")
    
    def _generate_index_file(self, base_filename: str, exported_files: List[tuple]) -> None:
        """
        產生索引檔案，包含所有已匯出檔案的連結
        
        Args:
            base_filename: 基礎檔名
            exported_files: 已匯出的檔案列表 [(data_type, filename), ...]
        """
        index_filename = f"{base_filename}-index.md"
        index_path = self.exporter.output_dir / index_filename
        
        # 準備索引內容
        content = f"# 使用者分析報告索引\n\n"
        content += f"**產生時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += f"## 匯出檔案清單\n\n"
        
        # 資料類型中文對照
        type_names = {
            'user_profile': '使用者基本資訊',
            'user_events': '使用者事件',
            'commits': '提交記錄',
            'code_changes': '程式碼變更',
            'merge_requests': '合併請求',
            'code_reviews': '程式碼審查',
            'permissions': '專案權限',
            'statistics': '統計摘要',
            'contributors': '貢獻者統計'
        }
        
        for data_type, filename in exported_files:
            content += f"- [{filename}]({filename}.csv)\n"
        
        # 寫入索引檔案
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Index file generated: {index_path}")
    
    def execute_batch(self, usernames: List[str], 
                     project_name: Optional[str] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     group_id: Optional[int] = None) -> None:
        """
        批次執行使用者統計（共用專案清單）
        
        Args:
            usernames: 使用者名稱列表
            project_name: 專案名稱 (可選，篩選特定專案)
            start_date: 開始日期
            end_date: 結束日期
            group_id: 群組 ID (可選)
        """
        start_time = time.time()
        
        print("=" * 70)
        print(f"GitLab 使用者資訊批次查詢（{len(usernames)} 位使用者）")
        print("=" * 70)
        
        # 預先載入專案清單（只取一次）
        cache_key = (group_id, project_name)
        if cache_key not in self.fetcher._projects_cache:
            self.fetcher.progress.report_start("正在預載專案列表...")
            projects = self.fetcher.client.get_projects(group_id=group_id, search=project_name)
            self.fetcher._projects_cache[cache_key] = projects
            self.fetcher.progress.report_complete(f"找到 {len(projects)} 個專案（已快取供批次使用）")
        else:
            projects = self.fetcher._projects_cache[cache_key]
            print(f"\n✓ 使用現有快取（{len(projects)} 個專案）")
        
        # 分析每個使用者（使用快取的專案清單）
        for idx, username in enumerate(usernames, 1):
            print(f"\n{'='*70}")
            print(f"[{idx}/{len(usernames)}] 分析使用者: {username}")
            print(f"{'='*70}")
            
            self.execute(
                username=username,
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                group_id=group_id
            )
        
        elapsed_time = time.time() - start_time
        print(f"\n{'='*70}")
        print(f"✓ 批次執行完成！")
        print(f"✓ 處理使用者數量: {len(usernames)}")
        print(f"✓ 總執行時間: {elapsed_time:.2f} 秒")
        print(f"✓ 平均每位使用者: {elapsed_time/len(usernames):.2f} 秒")
        
        # 顯示快取統計
        cache_stats = self.fetcher.get_cache_stats()
        print(f"\n快取統計：")
        print(f"  • 快取查詢數: {cache_stats['cached_queries']}")
        print(f"  • 快取專案數: {cache_stats['total_cached_projects']}")
        print(f"{'='*70}")



class UserProjectsService(BaseService):
    """使用者專案服務"""
    
    def execute(self, username: Optional[str] = None, group_name: Optional[str] = None) -> None:
        """執行使用者專案查詢"""
        start_time = time.time()
        
        print("=" * 70)
        print("GitLab 使用者專案列表查詢")
        print("=" * 70)
        
        # 驗證使用者是否存在
        if username:
            try:
                users = self.fetcher.client.gl.users.list(username=username)
                if not users:
                    print(f"\n❌ 錯誤：找不到使用者 '{username}'")
                    print("\n建議：")
                    print(f"  • 檢查使用者名稱是否正確")
                    print(f"  • 使用 GitLab username（不是顯示名稱）")
                    print(f"  • 執行不帶 --username 參數查看所有使用者")
                    print("\n" + "=" * 70)
                    return
                else:
                    user_info = users[0]
                    print(f"\n✓ 找到使用者：{user_info.name} (@{user_info.username})")
                    if hasattr(user_info, 'email'):
                        print(f"  Email: {user_info.email}")
            except Exception as e:
                print(f"\n⚠️  警告：無法驗證使用者 ({e})")
                print("  繼續執行查詢...")
        
        # 獲取資料
        user_data = self.fetcher.fetch(username=username, group_name=group_name)
        
        # 處理資料
        processed_data = self.processor.process(user_data)
        
        # 匯出資料
        if username:
            base_filename = f"{username}-user_project"
        else:
            base_filename = "all-users_project"
        
        # 匯出各類資料並計數
        exported_count = 0
        for data_type, df in processed_data.items():
            if not df.empty:
                if data_type == 'projects':
                    filename = base_filename
                else:
                    filename = f"{base_filename}-{data_type}"
                self.exporter.export(df, filename)
                exported_count += 1
        
        # 顯示統計摘要
        if not processed_data['statistics'].empty:
            print("\n" + "=" * 70)
            print("統計摘要")
            print("=" * 70)
            print(processed_data['statistics'].to_string(index=False))
        
        print("\n" + "=" * 70)
        
        # 檢查是否有輸出資料
        if exported_count == 0:
            if username:
                print(f"⚠️  警告：沒有找到使用者 '{username}' 的任何專案")
            else:
                print("⚠️  警告：沒有找到任何使用者專案資料")
        else:
            print("✓ 查詢完成！")
            print(f"✓ 共匯出 {exported_count} 個資料檔案")
        
        elapsed_time = time.time() - start_time
        print(f"✓ 執行時間: {elapsed_time:.2f} 秒")
        print("=" * 70)


class GroupStatsService(BaseService):
    """群組統計服務"""
    
    def execute(self, group_name: Optional[str] = None) -> None:
        """執行群組統計"""
        start_time = time.time()
        
        print("=" * 70)
        print("GitLab 群組資訊查詢")
        print("=" * 70)
        
        # 獲取資料
        group_data = self.fetcher.fetch(group_name=group_name)
        
        if not group_data['groups']:
            print("No groups found.")
            return
        
        # 處理資料
        processed_data = self.processor.process(group_data)
        
        # 取得群組路徑作為子目錄名稱
        # 從第一筆群組資料中取得 group_path
        group_path = None
        if not processed_data['groups'].empty:
            group_path = processed_data['groups'].iloc[0].get('group_path', None)
        
        # 如果沒有 group_path，使用 group_name
        if not group_path and group_name:
            group_path = group_name
        
        # 建立兩層目錄結構：groups/{group_path}/
        subdir = f"groups/{group_path}" if group_path else "groups"
        
        # 匯出群組資料
        if not processed_data['groups'].empty:
            self.exporter.export(processed_data['groups'], 'groups', subdir=subdir)
            print(f"\n✓ Total groups: {len(processed_data['groups'])}")
        
        # 匯出子群組資料
        if not processed_data['subgroups'].empty:
            self.exporter.export(processed_data['subgroups'], 'subgroups', subdir=subdir)
            print(f"✓ Total subgroups: {len(processed_data['subgroups'])}")
        
        # 匯出專案資料
        if not processed_data['projects'].empty:
            self.exporter.export(processed_data['projects'], 'projects', subdir=subdir)
            print(f"✓ Total projects: {len(processed_data['projects'])}")
        
        # 匯出授權資料
        if not processed_data['permissions'].empty:
            self.exporter.export(processed_data['permissions'], 'permissions', subdir=subdir)
            print(f"✓ Total permission records: {len(processed_data['permissions'])}")
        
        elapsed_time = time.time() - start_time
        print(f"✓ 執行時間: {elapsed_time:.2f} 秒")
        print("=" * 70)


# ==================== CLI 介面 ====================

class GitLabCLI:
    """GitLab CLI 主程式"""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.client = create_default_client()
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.exporter = DataExporter(output_dir=self.output_dir)
        self.progress = ConsoleProgressReporter()
    
    def create_project_stats_service(self) -> ProjectStatsService:
        """創建專案統計服務"""
        fetcher = ProjectDataFetcher(self.client, self.progress)
        processor = ProjectDataProcessor()
        return ProjectStatsService(fetcher, processor, self.exporter)
    
    def create_project_permission_service(self) -> ProjectPermissionService:
        """創建專案授權服務"""
        fetcher = ProjectPermissionFetcher(self.client, self.progress)
        processor = ProjectPermissionProcessor()
        return ProjectPermissionService(fetcher, processor, self.exporter)
    
    def create_user_stats_service(self) -> UserStatsService:
        """創建使用者統計服務"""
        fetcher = UserDataFetcher(self.client, self.progress)
        processor = UserDataProcessor()
        return UserStatsService(fetcher, processor, self.exporter)
    
    def create_user_projects_service(self) -> UserProjectsService:
        """創建使用者專案服務"""
        fetcher = UserProjectsFetcher(self.client, self.progress)
        processor = UserProjectsProcessor()
        return UserProjectsService(fetcher, processor, self.exporter)
    
    def create_group_stats_service(self) -> GroupStatsService:
        """創建群組統計服務"""
        fetcher = GroupDataFetcher(self.client, self.progress)
        processor = GroupDataProcessor()
        return GroupStatsService(fetcher, processor, self.exporter)
    
    def run(self):
        """執行 CLI"""
        parser = self._create_parser()
        args = parser.parse_args()
        
        # 更新輸出目錄
        if hasattr(args, 'output') and args.output:
            self.output_dir = args.output
            self.exporter = DataExporter(output_dir=self.output_dir)
        
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit(0)
        except Exception as e:
            print(f"\n錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """創建參數解析器"""
        parser = argparse.ArgumentParser(
            description='GitLab 開發者程式碼品質與技術水平分析工具',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用範例:

  # 1. 取得所有專案資訊（包含授權統計）
  python gl-cli.py project-stats
  
  # 2. 取得特定專案資訊（包含授權統計）
  python gl-cli.py project-stats --project-name "my-project"
  
  # 3. 取得多個專案資訊 🆕
  python gl-cli.py project-stats --project-name "proj1" "proj2" "proj3"
  
  # 4. 取得所有專案授權資訊
  python gl-cli.py project-permission
  
  # 5. 取得特定專案授權資訊
  python gl-cli.py project-permission --project-name "my-project"
  
  # 6. 取得多個專案授權資訊 🆕
  python gl-cli.py project-permission --project-name "proj1" "proj2" "proj3"
  
  # 7. 取得所有使用者詳細資訊（commits, code changes, merge requests, code reviews）
  python gl-cli.py user-details --start-date 2024-01-01 --end-date 2024-12-31
  
  # 8. 取得特定使用者詳細資訊
  python gl-cli.py user-details --username alice --start-date 2024-01-01
  
  # 9. 取得多位使用者的詳細資訊 🆕
  python gl-cli.py user-details --username alice bob charlie --start-date 2024-01-01
  
  # 10. 取得特定專案的開發者活動
  python gl-cli.py user-details --project-name "web-api" --start-date 2024-01-01
  
  # 11. 取得多個專案的開發者活動 🆕
  python gl-cli.py user-details --project-name "web-api" "mobile-app" --start-date 2024-01-01
  
  # 12. 組合查詢：多位使用者在多個專案的活動 🆕
  python gl-cli.py user-details --username alice bob --project-name "web-api" "mobile-app" --start-date 2024-01-01
  
  # 13. 取得所有使用者的專案列表（包含授權資訊）
  python gl-cli.py user-projects
  
  # 14. 取得特定使用者的專案列表
  python gl-cli.py user-projects --username alice
  
  # 15. 取得多位使用者的專案列表 🆕
  python gl-cli.py user-projects --username alice bob charlie
  
  # 16. 取得特定群組的使用者專案列表
  python gl-cli.py user-projects --group-name "my-group"
  
  # 17. 取得多個群組的使用者專案列表 🆕
  python gl-cli.py user-projects --group-name "group1" "group2"
  
  # 18. 組合查詢：特定使用者在多個群組的專案 🆕
  python gl-cli.py user-projects --username alice --group-name "group1" "group2"
  
  # 19. 取得所有群組資訊
  python gl-cli.py group-stats
  
  # 20. 取得特定群組資訊
  python gl-cli.py group-stats --group-name "my-group"
  
  # 21. 取得多個群組的資訊 🆕
  python gl-cli.py group-stats --group-name "group1" "group2" "group3"
  """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='可用的命令')
        subparsers.required = True
        
        # 1. project-stats 命令
        project_stats_parser = subparsers.add_parser(
            'project-stats',
            help='取得專案所有資訊'
        )
        project_stats_parser.add_argument(
            '--project-name',
            type=str,
            nargs='*',
            help='專案名稱 (可選，不填則取得全部；可指定多個，例如: --project-name proj1 proj2)'
        )
        project_stats_parser.add_argument(
            '--group-id',
            type=int,
            help=f'群組 ID (預設: {config.TARGET_GROUP_ID})'
        )
        project_stats_parser.add_argument(
            '--output',
            type=str,
            default=os.path.join(os.getcwd(), 'output'),
            help='輸出目錄路徑 (預設: ./output)'
        )
        project_stats_parser.set_defaults(func=self._cmd_project_stats)
        
        # 2. project-permission 命令
        project_perm_parser = subparsers.add_parser(
            'project-permission',
            help='取得專案授權資訊'
        )
        project_perm_parser.add_argument(
            '--project-name',
            type=str,
            nargs='*',
            help='專案名稱 (可選，不填則取得全部；可指定多個，例如: --project-name proj1 proj2)'
        )
        project_perm_parser.add_argument(
            '--group-id',
            type=int,
            help=f'群組 ID (預設: {config.TARGET_GROUP_ID})'
        )
        project_perm_parser.add_argument(
            '--output',
            type=str,
            default=os.path.join(os.getcwd(), 'output'),
            help='輸出目錄路徑 (預設: ./output)'
        )
        project_perm_parser.set_defaults(func=self._cmd_project_permission)
        
        # 3. user-details 命令
        user_stats_parser = subparsers.add_parser(
            'user-details',
            help='取得使用者資訊'
        )
        user_stats_parser.add_argument(
            '--username',
            type=str,
            nargs='*',
            help='使用者名稱 (可選，不填則取得全部；可指定多個，例如: --username alice bob)'
        )
        user_stats_parser.add_argument(
            '--project-name',
            type=str,
            nargs='*',
            help='專案名稱 (可選，不填則取得全部；可指定多個，例如: --project-name web-api mobile-app)'
        )
        user_stats_parser.add_argument(
            '--start-date',
            type=str,
            help=f'開始日期 (格式: YYYY-MM-DD，預設: {config.START_DATE})'
        )
        user_stats_parser.add_argument(
            '--end-date',
            type=str,
            help=f'結束日期 (格式: YYYY-MM-DD，預設: {config.END_DATE})'
        )
        user_stats_parser.add_argument(
            '--group-id',
            type=int,
            help=f'群組 ID (預設: {config.TARGET_GROUP_ID})'
        )
        user_stats_parser.add_argument(
            '--output',
            type=str,
            default=os.path.join(os.getcwd(), 'output'),
            help='輸出目錄路徑 (預設: ./output)'
        )
        user_stats_parser.set_defaults(func=self._cmd_user_stats)
        
        # 4. user-projects 命令
        user_projects_parser = subparsers.add_parser(
            'user-projects',
            help='取得使用者專案列表'
        )
        user_projects_parser.add_argument(
            '--username',
            type=str,
            nargs='*',
            help='使用者名稱 (可選，不填則取得全部；可指定多個，例如: --username alice bob)'
        )
        user_projects_parser.add_argument(
            '--group-name',
            type=str,
            nargs='*',
            help='群組名稱 (可選，不填則取得全部；可指定多個，例如: --group-name group1 group2)'
        )
        user_projects_parser.add_argument(
            '--output',
            type=str,
            default=os.path.join(os.getcwd(), 'output'),
            help='輸出目錄路徑 (預設: ./output)'
        )
        user_projects_parser.set_defaults(func=self._cmd_user_projects)
        
        # 5. group-stats 命令
        group_stats_parser = subparsers.add_parser(
            'group-stats',
            help='取得群組所有資訊'
        )
        group_stats_parser.add_argument(
            '--group-name',
            type=str,
            nargs='*',
            help='群組名稱 (可選，不填則取得全部；可指定多個，例如: --group-name group1 group2)'
        )
        group_stats_parser.add_argument(
            '--output',
            type=str,
            default=os.path.join(os.getcwd(), 'output'),
            help='輸出目錄路徑 (預設: ./output)'
        )
        group_stats_parser.set_defaults(func=self._cmd_group_stats)
        
        return parser
    
    def _cmd_project_stats(self, args):
        """執行專案統計命令（支援多筆專案）"""
        service = self.create_project_stats_service()
        
        # 處理多筆專案名稱
        project_names = args.project_name if args.project_name else [None]
        
        # 如果是空列表，設為 [None] 表示查詢全部
        if not project_names:
            project_names = [None]
        
        total_queries = len(project_names)
        current = 0
        
        for project_name in project_names:
            current += 1
            if total_queries > 1:
                print(f"\n{'='*70}")
                print(f"查詢 {current}/{total_queries}: ", end="")
                if project_name:
                    print(f"專案={project_name}")
                else:
                    print("所有專案")
                print(f"{'='*70}")
            
            service.execute(
                project_name=project_name,
                group_id=args.group_id or config.TARGET_GROUP_ID
            )
    
    def _cmd_project_permission(self, args):
        """執行專案授權命令（支援多筆專案）"""
        service = self.create_project_permission_service()
        
        # 處理多筆專案名稱
        project_names = args.project_name if args.project_name else [None]
        
        # 如果是空列表，設為 [None] 表示查詢全部
        if not project_names:
            project_names = [None]
        
        total_queries = len(project_names)
        current = 0
        
        for project_name in project_names:
            current += 1
            if total_queries > 1:
                print(f"\n{'='*70}")
                print(f"查詢 {current}/{total_queries}: ", end="")
                if project_name:
                    print(f"專案={project_name}")
                else:
                    print("所有專案")
                print(f"{'='*70}")
            
            service.execute(
                project_name=project_name,
                group_id=args.group_id or config.TARGET_GROUP_ID
            )
    
    def _cmd_user_stats(self, args):
        """執行使用者統計命令（支援多筆使用者和專案，自動使用批次模式優化）"""
        service = self.create_user_stats_service()
        
        # 處理多筆使用者名稱
        usernames = args.username if args.username else [None]
        # 處理多筆專案名稱
        project_names = args.project_name if args.project_name else [None]
        
        # 如果兩者都是空列表，設為 [None] 表示查詢全部
        if not usernames:
            usernames = [None]
        if not project_names:
            project_names = [None]
        
        # 判斷是否可以使用批次模式（多個使用者 + 單一專案範圍）
        # 批次模式的條件：
        # 1. 多於 1 個使用者
        # 2. 只有 1 個專案範圍（或全部專案）
        # 3. 所有使用者都不是 None
        can_use_batch = (
            len(usernames) > 1 and 
            len(project_names) == 1 and 
            all(u is not None for u in usernames)
        )
        
        if can_use_batch:
            # 使用批次模式（預先載入專案清單，共用快取）
            service.execute_batch(
                usernames=usernames,
                project_name=project_names[0],
                start_date=args.start_date or config.START_DATE,
                end_date=args.end_date or config.END_DATE,
                group_id=args.group_id or config.TARGET_GROUP_ID
            )
        else:
            # 使用原有邏輯（笛卡爾積模式）
            total_queries = len(usernames) * len(project_names)
            current = 0
            
            for username in usernames:
                for project_name in project_names:
                    current += 1
                    if total_queries > 1:
                        print(f"\n{'='*70}")
                        print(f"查詢 {current}/{total_queries}: ", end="")
                        if username:
                            print(f"使用者={username}", end="")
                        if project_name:
                            print(f" 專案={project_name}", end="")
                        if not username and not project_name:
                            print("所有使用者和專案", end="")
                        print(f"\n{'='*70}")
                    
                    service.execute(
                        username=username,
                        project_name=project_name,
                        start_date=args.start_date or config.START_DATE,
                        end_date=args.end_date or config.END_DATE,
                        group_id=args.group_id or config.TARGET_GROUP_ID
                    )

    
    def _cmd_user_projects(self, args):
        """執行使用者專案命令（支援多筆使用者和群組）"""
        service = self.create_user_projects_service()
        
        # 處理多筆使用者名稱
        usernames = args.username if args.username else [None]
        
        # 如果是空列表，設為 [None] 表示查詢全部
        if not usernames:
            usernames = [None]
        
        # 處理多筆群組名稱
        group_names = args.group_name if args.group_name else [None]
        
        # 如果是空列表，設為 [None] 表示查詢全部
        if not group_names:
            group_names = [None]
        
        # 組合所有查詢（笛卡爾積）
        total_queries = len(usernames) * len(group_names)
        current = 0
        
        for username in usernames:
            for group_name in group_names:
                current += 1
                if total_queries > 1:
                    print(f"\n{'='*70}")
                    print(f"查詢 {current}/{total_queries}: ", end="")
                    if username:
                        print(f"使用者={username}", end="")
                    if group_name:
                        if username:
                            print(f" ", end="")
                        print(f"群組={group_name}", end="")
                    if not username and not group_name:
                        print("所有使用者和群組", end="")
                    print(f"\n{'='*70}")
                
                service.execute(
                    username=username,
                    group_name=group_name
                )
    
    def _cmd_group_stats(self, args):
        """執行群組統計命令（支援多筆群組）"""
        service = self.create_group_stats_service()
        
        # 處理多筆群組名稱
        group_names = args.group_name if args.group_name else [None]
        
        # 如果是空列表，設為 [None] 表示查詢全部
        if not group_names:
            group_names = [None]
        
        total_queries = len(group_names)
        current = 0
        
        for group_name in group_names:
            current += 1
            if total_queries > 1:
                print(f"\n{'='*70}")
                print(f"查詢 {current}/{total_queries}: ", end="")
                if group_name:
                    print(f"群組={group_name}")
                else:
                    print("所有群組")
                print(f"{'='*70}")
            
            service.execute(group_name=group_name)


def main():
    """主程式入口"""
    cli = GitLabCLI()
    cli.run()


if __name__ == "__main__":
    main()
