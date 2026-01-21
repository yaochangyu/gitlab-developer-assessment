#!/usr/bin/env python3
"""
開發者技術水平分析模組

提供兩種分析方式：
1. CodeBasedAnalyzer: 基於程式碼計算的評分系統
2. AIModelAnalyzer: 基於 GitHub Models API 的 AI 分析
"""

import os
import re
import json
import requests
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path
import pandas as pd
from datetime import datetime
from collections import Counter, defaultdict

import config
from progress_reporter import IProgressReporter, SilentProgressReporter


# ==================== 抽象介面 ====================

class IUserAnalyzer(ABC):
    """開發者分析介面"""
    
    @abstractmethod
    def analyze(self, user_data_dir: Path, spec_file: Optional[Path] = None) -> str:
        """
        分析開發者技術水平
        
        Args:
            user_data_dir: 使用者資料目錄（包含 CSV 檔案）
            spec_file: 分析規格檔案路徑
            
        Returns:
            分析報告（Markdown 格式）
        """
        pass


# ==================== 資料讀取器 ====================

class UserDataLoader:
    """使用者資料載入器"""
    
    def __init__(self, user_data_dir: Path):
        self.user_data_dir = user_data_dir
        self.data: Dict[str, pd.DataFrame] = {}
    
    def load_all(self) -> Dict[str, pd.DataFrame]:
        """載入所有 CSV 檔案"""
        csv_files = {
            'commits': 'commits.csv',
            'statistics': 'statistics.csv',
            'code_reviews': 'code_reviews.csv',
            'code_changes': 'code_changes.csv',
            'user_events': 'user_events.csv',
            'merge_requests': 'merge_requests.csv',
            'user_profile': 'user_profile.csv'
        }
        
        for key, filename in csv_files.items():
            file_path = self.user_data_dir / filename
            if file_path.exists():
                try:
                    # 使用 utf-8-sig 處理 BOM
                    df = pd.read_csv(file_path, encoding='utf-8-sig')
                    self.data[key] = df
                except Exception as e:
                    print(f"⚠️ 警告：無法讀取 {filename}: {e}")
                    self.data[key] = pd.DataFrame()
            else:
                self.data[key] = pd.DataFrame()
        
        return self.data
    
    def get_username(self) -> str:
        """從目錄名稱或 user_profile 取得使用者名稱"""
        # 優先從 user_profile 取得
        if not self.data.get('user_profile', pd.DataFrame()).empty:
            profile = self.data['user_profile'].iloc[0]
            return profile.get('username', self.user_data_dir.name)
        
        # 否則使用目錄名稱
        return self.user_data_dir.name


# ==================== 方案 B: 程式碼計算分析器 ====================

class CodeBasedAnalyzer(IUserAnalyzer):
    """基於程式碼計算的評分系統"""
    
    def __init__(self, progress_reporter: Optional[IProgressReporter] = None):
        self.progress = progress_reporter or SilentProgressReporter()
        self.data_loader: Optional[UserDataLoader] = None
        self.data: Dict[str, pd.DataFrame] = {}
        self.scores: Dict[str, float] = {}
        self.total_score: float = 0.0
        self.level: str = ""
    
    def analyze(self, user_data_dir: Path, spec_file: Optional[Path] = None) -> str:
        """執行分析"""
        self.progress.report_start(f"正在分析 {user_data_dir.name}...")
        
        # 載入資料
        self.data_loader = UserDataLoader(user_data_dir)
        self.data = self.data_loader.load_all()
        
        if self.data.get('commits', pd.DataFrame()).empty:
            return f"# {user_data_dir.name} 技術水平分析報告\n\n⚠️ 錯誤：找不到 commits.csv 或資料為空"
        
        # 計算各維度評分
        self.scores = {
            'contribution': self._calculate_contribution_score(),
            'commit_quality': self._calculate_commit_quality_score(),
            'tech_breadth': self._calculate_tech_breadth_score(),
            'collaboration': self._calculate_collaboration_score(),
            'code_review': self._calculate_code_review_score(),
            'work_pattern': self._calculate_work_pattern_score(),
            'progress_trend': self._calculate_progress_trend_score()
        }
        
        # 計算總分
        total_score = self._calculate_total_score()
        level = self._determine_level(total_score)
        
        # 儲存總分和等級（供彙總報告使用）
        self.total_score = total_score
        self.level = level
        
        # 產生報告
        report = self._generate_markdown_report(total_score, level)
        
        self.progress.report_complete(f"分析完成：{level}（{total_score:.2f}/10）")
        
        return report
    
    # ========== 維度 1: 程式碼貢獻量 (12%) ==========
    
    def _calculate_contribution_score(self) -> float:
        """計算程式碼貢獻量評分"""
        if self.data['statistics'].empty:
            return 5.0
        
        stats = self.data['statistics'].iloc[0]
        total_commits = int(stats.get('total_commits', 0))
        
        # 根據提交次數評分
        if total_commits >= 200:
            return 10.0
        elif total_commits >= 100:
            return 8.0
        elif total_commits >= 50:
            return 6.0
        else:
            return 4.0
    
    # ========== 維度 2: Commit 品質 (23%) ==========
    
    def _calculate_commit_quality_score(self) -> float:
        """計算 Commit 品質評分"""
        if self.data['commits'].empty:
            return 5.0
        
        commits_df = self.data['commits']
        
        # A. Message 規範性 (40%)
        message_score = self._calculate_message_quality(commits_df)
        
        # B. 變更粒度 (40%)
        granularity_score = self._calculate_change_granularity(commits_df)
        
        # C. 修復性提交比例 (20%)
        fix_ratio_score = self._calculate_fix_ratio(commits_df)
        
        # 加權平均
        quality_score = (message_score * 0.4 + 
                        granularity_score * 0.4 + 
                        fix_ratio_score * 0.2)
        
        return quality_score
    
    def _calculate_message_quality(self, commits_df: pd.DataFrame) -> float:
        """計算 Commit Message 品質"""
        # Conventional Commits 規範
        conventional_pattern = r'^(feat|fix|docs|refactor|test|chore|style|perf)(\(.+\))?:'
        
        total = len(commits_df)
        if total == 0:
            return 5.0
        
        # 計算符合規範的比例
        conventional_count = commits_df['title'].str.contains(
            conventional_pattern, 
            case=False, 
            regex=True,
            na=False
        ).sum()
        
        conventional_ratio = conventional_count / total
        
        # 評分
        if conventional_ratio >= 0.8:
            return 10.0
        elif conventional_ratio >= 0.6:
            return 8.0
        elif conventional_ratio >= 0.4:
            return 6.0
        else:
            return 4.0
    
    def _calculate_change_granularity(self, commits_df: pd.DataFrame) -> float:
        """計算變更粒度評分"""
        # 小型變更：≤100 行
        # 中型變更：100-500 行
        # 大型變更：>500 行
        
        total = len(commits_df)
        if total == 0:
            return 5.0
        
        commits_df['total_changes'] = commits_df['additions'] + commits_df['deletions']
        
        small_count = (commits_df['total_changes'] <= 100).sum()
        medium_count = ((commits_df['total_changes'] > 100) & 
                       (commits_df['total_changes'] <= 500)).sum()
        large_count = (commits_df['total_changes'] > 500).sum()
        
        small_ratio = small_count / total
        
        # 評分：小型變更佔比越高越好
        if small_ratio >= 0.6:
            return 10.0
        elif small_ratio >= 0.4:
            return 7.0
        else:
            return 5.0
    
    def _calculate_fix_ratio(self, commits_df: pd.DataFrame) -> float:
        """計算修復性提交比例"""
        total = len(commits_df)
        if total == 0:
            return 5.0
        
        # 統計包含修復關鍵字的提交
        fix_pattern = r'(fix|bug|hotfix|revert)'
        fix_count = commits_df['title'].str.contains(
            fix_pattern,
            case=False,
            regex=True,
            na=False
        ).sum()
        
        fix_ratio = fix_count / total
        
        # 評分：修復率越低越好
        if fix_ratio < 0.15:
            return 10.0
        elif fix_ratio < 0.30:
            return 7.0
        else:
            return 4.0
    
    # ========== 維度 3: 技術廣度 (18%) ==========
    
    def _calculate_tech_breadth_score(self) -> float:
        """計算技術廣度評分"""
        if self.data['code_changes'].empty:
            return 5.0
        
        changes_df = self.data['code_changes']
        
        # 提取檔案副檔名
        file_extensions = changes_df['file_path'].apply(
            lambda x: os.path.splitext(str(x))[1].lower() if pd.notna(x) else ''
        )
        
        # 過濾掉空字串和常見非程式碼檔案
        ignore_extensions = {'', '.md', '.txt', '.json', '.yml', '.yaml', '.xml'}
        file_extensions = file_extensions[~file_extensions.isin(ignore_extensions)]
        
        # 統計不同副檔名數量
        unique_extensions = file_extensions.nunique()
        
        # 評分
        if unique_extensions >= 5:
            return 10.0
        elif unique_extensions >= 3:
            return 8.0
        elif unique_extensions >= 1:
            return 6.0
        else:
            return 4.0
    
    # ========== 維度 4: 協作能力 (12%) ==========
    
    def _calculate_collaboration_score(self) -> float:
        """計算協作能力評分"""
        if self.data['commits'].empty:
            return 5.0
        
        commits_df = self.data['commits']
        
        # A. Merge Commits 參與度
        merge_pattern = r'merge'
        merge_count = commits_df['title'].str.contains(
            merge_pattern,
            case=False,
            regex=True,
            na=False
        ).sum()
        
        total_commits = len(commits_df)
        merge_ratio = merge_count / total_commits if total_commits > 0 else 0
        
        # B. Revert 率（越低越好）
        revert_pattern = r'revert'
        revert_count = commits_df['title'].str.contains(
            revert_pattern,
            case=False,
            regex=True,
            na=False
        ).sum()
        
        revert_ratio = revert_count / total_commits if total_commits > 0 else 0
        
        # 評分
        score = 7.0  # 基礎分
        
        # Merge 參與度加分
        if merge_ratio > 0.1:
            score += 2.0
        elif merge_ratio > 0.05:
            score += 1.0
        
        # Revert 率扣分
        if revert_ratio > 0.05:
            score -= 3.0
        elif revert_ratio > 0.02:
            score -= 1.0
        
        return max(1.0, min(10.0, score))
    
    # ========== 維度 5: Code Review 品質 (10%) ==========
    
    def _calculate_code_review_score(self) -> float:
        """計算 Code Review 品質評分"""
        if self.data['code_reviews'].empty:
            return 5.0
        
        reviews_df = self.data['code_reviews']
        total_reviews = len(reviews_df)
        
        # 簡單評分：基於參與度
        if total_reviews >= 20:
            return 9.0
        elif total_reviews >= 10:
            return 7.0
        elif total_reviews >= 5:
            return 6.0
        else:
            return 5.0
    
    # ========== 維度 6: 工作模式 (10%) ==========
    
    def _calculate_work_pattern_score(self) -> float:
        """計算工作模式評分"""
        if self.data['user_events'].empty:
            return 5.0
        
        events_df = self.data['user_events']
        
        # 嘗試解析時間
        try:
            events_df['created_at'] = pd.to_datetime(events_df['created_at'])
            events_df['hour'] = events_df['created_at'].dt.hour
            events_df['weekday'] = events_df['created_at'].dt.weekday
            
            # 工作時段 (9-18點) 活動比例
            work_hours = events_df['hour'].between(9, 18).sum()
            total_events = len(events_df)
            work_hours_ratio = work_hours / total_events if total_events > 0 else 0
            
            # 工作日（週一到週五）活動比例
            work_days = events_df['weekday'].between(0, 4).sum()
            work_days_ratio = work_days / total_events if total_events > 0 else 0
            
            # 評分
            score = 5.0
            if work_hours_ratio >= 0.6:
                score += 2.5
            if work_days_ratio >= 0.7:
                score += 2.5
            
            return min(10.0, score)
        except:
            return 5.0
    
    # ========== 維度 7: 進步趨勢 (15%) ==========
    
    def _calculate_progress_trend_score(self) -> float:
        """計算進步趨勢評分"""
        if self.data['commits'].empty:
            return 5.0
        
        commits_df = self.data['commits']
        
        try:
            # 解析提交日期
            commits_df['committed_date'] = pd.to_datetime(commits_df['committed_date'])
            commits_df = commits_df.sort_values('committed_date')
            
            # 計算中位數日期，分為前後兩期
            median_date = commits_df['committed_date'].median()
            
            early_commits = commits_df[commits_df['committed_date'] <= median_date]
            recent_commits = commits_df[commits_df['committed_date'] > median_date]
            
            if len(early_commits) == 0 or len(recent_commits) == 0:
                return 7.0  # 資料不足，給予中等分數
            
            # 比較前後期的 Commit Message 品質
            early_quality = self._calculate_message_quality(early_commits)
            recent_quality = self._calculate_message_quality(recent_commits)
            
            # 進步幅度
            improvement = recent_quality - early_quality
            
            # 評分
            if improvement >= 2.0:
                return 10.0
            elif improvement >= 1.0:
                return 8.5
            elif improvement >= 0:
                return 7.0
            else:
                return 5.0
        except:
            return 7.0
    
    # ========== 總分計算 ==========
    
    def _calculate_total_score(self) -> float:
        """計算總分（加權平均）"""
        weights = {
            'contribution': 0.12,
            'commit_quality': 0.23,
            'tech_breadth': 0.18,
            'collaboration': 0.12,
            'code_review': 0.10,
            'work_pattern': 0.10,
            'progress_trend': 0.15
        }
        
        total = sum(self.scores[key] * weights[key] for key in weights.keys())
        return round(total, 2)
    
    def _determine_level(self, total_score: float) -> str:
        """判定等級"""
        if total_score >= 8.0:
            return "🏆 高級工程師"
        elif total_score >= 5.0:
            return "⭐ 中級工程師"
        else:
            return "🌱 初級工程師"
    
    # ========== 報告產生 ==========
    
    def _generate_markdown_report(self, total_score: float, level: str) -> str:
        """產生 Markdown 格式報告"""
        username = self.data_loader.get_username() if self.data_loader else "Unknown"
        
        # 取得基本統計
        stats = self.data['statistics'].iloc[0] if not self.data['statistics'].empty else {}
        total_commits = int(stats.get('total_commits', 0))
        total_additions = int(stats.get('total_additions', 0))
        total_deletions = int(stats.get('total_deletions', 0))
        
        report = f"""# {username} 技術水平分析報告

**生成時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**分析方式：** 程式碼計算（Code-Based Analysis）

---

## 📊 總體評估

| 項目 | 數值 |
|------|------|
| **總分** | **{total_score:.2f} / 10** |
| **等級** | **{level}** |
| 總提交數 | {total_commits} |
| 總新增行數 | {total_additions:,} |
| 總刪除行數 | {total_deletions:,} |

---

## 🎯 各維度評分

| 維度 | 分數 | 權重 | 加權分數 |
|------|------|------|----------|
| 程式碼貢獻量 | {self.scores['contribution']:.2f} / 10 | 12% | {self.scores['contribution'] * 0.12:.2f} |
| **Commit 品質** | **{self.scores['commit_quality']:.2f} / 10** | **23%** | **{self.scores['commit_quality'] * 0.23:.2f}** |
| 技術廣度 | {self.scores['tech_breadth']:.2f} / 10 | 18% | {self.scores['tech_breadth'] * 0.18:.2f} |
| 協作能力 | {self.scores['collaboration']:.2f} / 10 | 12% | {self.scores['collaboration'] * 0.12:.2f} |
| Code Review 品質 | {self.scores['code_review']:.2f} / 10 | 10% | {self.scores['code_review'] * 0.10:.2f} |
| 工作模式 | {self.scores['work_pattern']:.2f} / 10 | 10% | {self.scores['work_pattern'] * 0.10:.2f} |
| 進步趨勢 | {self.scores['progress_trend']:.2f} / 10 | 15% | {self.scores['progress_trend'] * 0.15:.2f} |

---

## 📝 詳細分析

### 1️⃣ 程式碼貢獻量 ({self.scores['contribution']:.2f}/10)

{self._generate_contribution_details()}

### 2️⃣ Commit 品質 ({self.scores['commit_quality']:.2f}/10) ⭐ 最重要

{self._generate_commit_quality_details()}

### 3️⃣ 技術廣度 ({self.scores['tech_breadth']:.2f}/10)

{self._generate_tech_breadth_details()}

### 4️⃣ 協作能力 ({self.scores['collaboration']:.2f}/10)

{self._generate_collaboration_details()}

### 5️⃣ Code Review 品質 ({self.scores['code_review']:.2f}/10)

{self._generate_code_review_details()}

### 6️⃣ 工作模式 ({self.scores['work_pattern']:.2f}/10)

{self._generate_work_pattern_details()}

### 7️⃣ 進步趨勢 ({self.scores['progress_trend']:.2f}/10)

{self._generate_progress_trend_details()}

---

## 💡 改進建議

{self._generate_improvement_suggestions(total_score)}

---

**分析工具版本：** v1.0  
**評分標準：** 基於 code-quality-analysis-spec.md
"""
        
        return report
    
    def _generate_contribution_details(self) -> str:
        """產生貢獻量詳細說明"""
        if self.data['statistics'].empty:
            return "⚠️ 無統計資料"
        
        stats = self.data['statistics'].iloc[0]
        total_commits = int(stats.get('total_commits', 0))
        
        if total_commits >= 200:
            level = "✅ 高活躍度"
        elif total_commits >= 100:
            level = "⭐ 穩定貢獻"
        elif total_commits >= 50:
            level = "📚 中等參與"
        else:
            level = "🌱 參與度低"
        
        return f"""- 總提交數：**{total_commits}** ({level})
- 評估：{'活躍開發者，持續穩定貢獻' if total_commits >= 100 else '建議增加程式碼貢獻頻率'}"""
    
    def _generate_commit_quality_details(self) -> str:
        """產生 Commit 品質詳細說明"""
        if self.data['commits'].empty:
            return "⚠️ 無 Commit 資料"
        
        commits_df = self.data['commits']
        
        # Message 規範性
        conventional_pattern = r'^(feat|fix|docs|refactor|test|chore|style|perf)(\(.+\))?:'
        conventional_count = commits_df['title'].str.contains(
            conventional_pattern, case=False, regex=True, na=False
        ).sum()
        conventional_ratio = conventional_count / len(commits_df)
        
        # 變更粒度
        commits_df['total_changes'] = commits_df['additions'] + commits_df['deletions']
        small_count = (commits_df['total_changes'] <= 100).sum()
        small_ratio = small_count / len(commits_df)
        
        # 修復率
        fix_count = commits_df['title'].str.contains(
            r'(fix|bug|hotfix|revert)', case=False, regex=True, na=False
        ).sum()
        fix_ratio = fix_count / len(commits_df)
        
        return f"""#### A. Message 規範性
- 符合 Conventional Commits：**{conventional_ratio*100:.1f}%** ({conventional_count}/{len(commits_df)})
- 評估：{'✅ 優秀' if conventional_ratio >= 0.8 else '⚠️ 需改進'}

#### B. 變更粒度
- 小型變更（≤100行）：**{small_ratio*100:.1f}%** ({small_count}/{len(commits_df)})
- 評估：{'✅ 模組化思維好' if small_ratio >= 0.6 else '⚠️ 建議拆分大型變更'}

#### C. 修復性提交比例
- 修復率：**{fix_ratio*100:.1f}%** ({fix_count}/{len(commits_df)})
- 評估：{'✅ 程式碼品質高' if fix_ratio < 0.15 else '⚠️ 建議加強測試'}"""
    
    def _generate_tech_breadth_details(self) -> str:
        """產生技術廣度詳細說明"""
        if self.data['code_changes'].empty:
            return "⚠️ 無程式碼變更資料"
        
        changes_df = self.data['code_changes']
        file_extensions = changes_df['file_path'].apply(
            lambda x: os.path.splitext(str(x))[1].lower() if pd.notna(x) else ''
        )
        
        ignore_extensions = {'', '.md', '.txt', '.json', '.yml', '.yaml', '.xml'}
        file_extensions = file_extensions[~file_extensions.isin(ignore_extensions)]
        
        extension_counts = file_extensions.value_counts().head(10)
        unique_count = file_extensions.nunique()
        
        details = f"- 涉及檔案類型：**{unique_count}** 種\n\n"
        details += "**主要技術棧：**\n"
        for ext, count in extension_counts.items():
            details += f"  - `{ext}`: {count} 個檔案\n"
        
        return details
    
    def _generate_collaboration_details(self) -> str:
        """產生協作能力詳細說明"""
        if self.data['commits'].empty:
            return "⚠️ 無 Commit 資料"
        
        commits_df = self.data['commits']
        total = len(commits_df)
        
        merge_count = commits_df['title'].str.contains(
            r'merge', case=False, regex=True, na=False
        ).sum()
        merge_ratio = merge_count / total
        
        revert_count = commits_df['title'].str.contains(
            r'revert', case=False, regex=True, na=False
        ).sum()
        revert_ratio = revert_count / total
        
        return f"""- Merge Commits：**{merge_count}** ({merge_ratio*100:.1f}%)
- Revert 率：**{revert_ratio*100:.1f}%**
- 評估：{'✅ 良好的協作參與' if merge_ratio > 0.05 and revert_ratio < 0.02 else '建議增加分支協作'}"""
    
    def _generate_code_review_details(self) -> str:
        """產生 Code Review 品質詳細說明"""
        if self.data['code_reviews'].empty:
            return "⚠️ 無 Code Review 資料\n\n建議：積極參與 Code Review，提升團隊程式碼品質"
        
        reviews_df = self.data['code_reviews']
        total_reviews = len(reviews_df)
        
        return f"""- Review 參與次數：**{total_reviews}**
- 評估：{'✅ 積極參與' if total_reviews >= 20 else '⚠️ 建議增加 Review 參與度'}"""
    
    def _generate_work_pattern_details(self) -> str:
        """產生工作模式詳細說明"""
        if self.data['user_events'].empty:
            return "⚠️ 無活動資料"
        
        try:
            events_df = self.data['user_events'].copy()
            events_df['created_at'] = pd.to_datetime(events_df['created_at'])
            events_df['hour'] = events_df['created_at'].dt.hour
            events_df['weekday'] = events_df['created_at'].dt.weekday
            
            work_hours = events_df['hour'].between(9, 18).sum()
            work_hours_ratio = work_hours / len(events_df)
            
            work_days = events_df['weekday'].between(0, 4).sum()
            work_days_ratio = work_days / len(events_df)
            
            return f"""- 工作時段活動：**{work_hours_ratio*100:.1f}%**
- 工作日活動：**{work_days_ratio*100:.1f}%**
- 評估：{'✅ 規律的工作模式' if work_hours_ratio >= 0.6 and work_days_ratio >= 0.7 else '⚠️ 建議調整工作時間分配'}"""
        except:
            return "⚠️ 無法解析時間資料"
    
    def _generate_progress_trend_details(self) -> str:
        """產生進步趨勢詳細說明"""
        return "- 基於時間序列分析開發者的成長趨勢\n- 比較前後期的 Commit 品質變化"
    
    def _generate_improvement_suggestions(self, total_score: float) -> str:
        """產生改進建議"""
        suggestions = []
        
        # 根據各維度評分提供建議
        if self.scores['commit_quality'] < 7.0:
            suggestions.append("🎯 **提升 Commit 品質**：採用 Conventional Commits 格式，拆分大型變更")
        
        if self.scores['tech_breadth'] < 6.0:
            suggestions.append("🎯 **擴展技術廣度**：嘗試學習新的技術棧，參與不同類型的專案")
        
        if self.scores['code_review'] < 7.0:
            suggestions.append("🎯 **加強 Code Review 參與**：積極審查他人程式碼，提升團隊整體品質")
        
        if self.scores['collaboration'] < 6.0:
            suggestions.append("🎯 **增強協作能力**：多使用分支開發，減少直接提交到主分支")
        
        if not suggestions:
            suggestions.append("✅ **保持優秀表現**：繼續保持高品質的程式碼貢獻")
        
        return "\n".join(suggestions)


# ==================== 方案 A: AI 模型分析器 ====================

class AIModelAnalyzer(IUserAnalyzer):
    """基於 GitHub Models API 的 AI 分析"""
    
    def __init__(self, progress_reporter: Optional[IProgressReporter] = None):
        self.progress = progress_reporter or SilentProgressReporter()
        self.api_key = config.GITHUB_MODELS_API_KEY
        self.api_url = config.GITHUB_MODELS_API_URL
        self.model = config.GITHUB_MODELS_MODEL
    
    def analyze(self, user_data_dir: Path, spec_file: Optional[Path] = None) -> str:
        """執行 AI 分析"""
        self.progress.report_start(f"正在使用 AI 分析 {user_data_dir.name}...")
        
        # 檢查 API Key
        if not self.api_key:
            return self._generate_error_report(
                user_data_dir.name,
                "❌ 錯誤：未設定 GITHUB_MODELS_API_KEY\n\n請在 config.py 中設定您的 GitHub Models API Key"
            )
        
        # 載入資料
        data_loader = UserDataLoader(user_data_dir)
        data = data_loader.load_all()
        
        if data.get('commits', pd.DataFrame()).empty:
            return self._generate_error_report(
                user_data_dir.name,
                "⚠️ 錯誤：找不到 commits.csv 或資料為空"
            )
        
        # 讀取 spec 檔案
        spec_content = self._load_spec_file(spec_file)
        
        # 組裝 prompt
        prompt = self._build_prompt(data_loader.get_username(), data, spec_content)
        
        # 調用 API
        try:
            report = self._call_api(prompt)
            self.progress.report_complete("AI 分析完成")
            return report
        except Exception as e:
            return self._generate_error_report(
                user_data_dir.name,
                f"❌ API 調用失敗：{str(e)}"
            )
    
    def _load_spec_file(self, spec_file: Optional[Path]) -> str:
        """載入分析規格檔案"""
        if spec_file and spec_file.exists():
            with open(spec_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        # 尋找預設 spec 檔案
        default_paths = [
            Path(__file__).parent.parent / '.copilot/skills/developer-assessment/references/code-quality-analysis-spec.md',
            Path('code-quality-analysis-spec.md'),
            Path('../.copilot/skills/developer-assessment/references/code-quality-analysis-spec.md')
        ]
        
        for path in default_paths:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        
        return "請根據開發者的 Git 版控資料，評估其技術水平。"
    
    def _build_prompt(self, username: str, data: Dict[str, pd.DataFrame], spec_content: str) -> str:
        """組裝 AI prompt"""
        # 準備 CSV 資料摘要
        csv_summary = self._summarize_csv_data(data)
        
        prompt = f"""請根據以下評分標準和開發者資料，分析開發者 {username} 的技術水平。

# 評分標準

{spec_content}

---

# 開發者資料

{csv_summary}

---

# 要求

請產生一份完整的 Markdown 格式分析報告，包含：

1. **總體評估**：總分（0-10）、等級（高級/中級/初級工程師）
2. **各維度評分**：7 個維度的詳細評分和分析
3. **詳細分析**：每個維度的具體數據和評估
4. **改進建議**：針對性的建議

請使用繁體中文，格式清晰專業。
"""
        return prompt
    
    def _summarize_csv_data(self, data: Dict[str, pd.DataFrame]) -> str:
        """摘要 CSV 資料"""
        summary = []
        
        # Statistics
        if not data['statistics'].empty:
            stats = data['statistics'].iloc[0]
            summary.append(f"""## 統計資料
- 總提交數：{stats.get('total_commits', 0)}
- 總新增行數：{stats.get('total_additions', 0)}
- 總刪除行數：{stats.get('total_deletions', 0)}
- 平均每次變更：{stats.get('avg_changes_per_commit', 0):.2f} 行
- Merge Requests：{stats.get('total_merge_requests', 0)}
- Code Reviews：{stats.get('total_code_reviews', 0)}
""")
        
        # Commits 樣本
        if not data['commits'].empty:
            commits_sample = data['commits'].head(20)
            summary.append(f"""## Commits 樣本（前 20 筆）
| Commit Message | 新增 | 刪除 | 總計 |
|----------------|------|------|------|
""")
            for _, row in commits_sample.iterrows():
                title = str(row.get('title', ''))[:50]
                summary.append(f"| {title} | {row.get('additions', 0)} | {row.get('deletions', 0)} | {row.get('total', 0)} |")
        
        # Code Reviews
        if not data['code_reviews'].empty:
            summary.append(f"\n## Code Reviews\n- 總參與次數：{len(data['code_reviews'])}")
        
        # File Types
        if not data['code_changes'].empty:
            file_extensions = data['code_changes']['file_path'].apply(
                lambda x: os.path.splitext(str(x))[1].lower() if pd.notna(x) else ''
            )
            extension_counts = file_extensions.value_counts().head(10)
            summary.append("\n## 檔案類型分佈")
            for ext, count in extension_counts.items():
                if ext:
                    summary.append(f"- {ext}: {count} 個檔案")
        
        return "\n".join(summary)
    
    def _call_api(self, prompt: str) -> str:
        """調用 GitHub Models API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位資深的程式碼品質評估專家，精通從 Git 版控資料評估開發者技術水平。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"API 錯誤 {response.status_code}: {response.text}")
        
        result = response.json()
        
        # 提取 AI 生成的內容
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            raise Exception("API 回應格式錯誤")
    
    def _generate_error_report(self, username: str, error_message: str) -> str:
        """產生錯誤報告"""
        return f"""# {username} 技術水平分析報告

**生成時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**分析方式：** AI 模型分析（GitHub Models API）

---

{error_message}
"""


# ==================== 分析服務 ====================

class UserAnalysisService:
    """開發者分析服務"""
    
    def __init__(
        self,
        analyzer: IUserAnalyzer,
        data_source: Path,
        output_dir: Path,
        progress_reporter: Optional[IProgressReporter] = None
    ):
        self.analyzer = analyzer
        self.data_source = data_source
        self.output_dir = output_dir
        self.progress = progress_reporter or SilentProgressReporter()
        self.analysis_results: List[Dict[str, Any]] = []  # 收集分析結果
    
    def execute(
        self,
        username: Optional[str] = None,
        spec_file: Optional[Path] = None
    ) -> None:
        """執行分析"""
        # 找到要分析的使用者目錄
        user_dirs = self._find_user_directories(username)
        
        if not user_dirs:
            print(f"⚠️ 找不到使用者資料：{username or '全部'}")
            return
        
        total = len(user_dirs)
        self.progress.report_start(f"開始分析 {total} 位使用者...")
        
        # 清空之前的結果
        self.analysis_results = []
        
        for i, user_dir in enumerate(user_dirs, 1):
            print(f"\n{'='*70}")
            print(f"[{i}/{total}] 分析：{user_dir.name}")
            print(f"{'='*70}")
            
            # 執行分析
            report = self.analyzer.analyze(user_dir, spec_file)
            
            # 儲存報告
            output_path = self.output_dir / 'users' / user_dir.name / 'analysis-result.md'
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"✅ 報告已儲存：{output_path}")
            
            # 收集評分資料（僅 CodeBasedAnalyzer 有 scores 屬性）
            if isinstance(self.analyzer, CodeBasedAnalyzer):
                self.analysis_results.append({
                    'username': user_dir.name,
                    'total_score': self.analyzer.total_score,
                    'level': self.analyzer.level,
                    'scores': self.analyzer.scores.copy()
                })
        
        self.progress.report_complete(f"完成 {total} 位使用者分析")
        
        # 產生彙總報告
        if len(self.analysis_results) > 0:
            self._generate_summary_report()
    
    def _generate_summary_report(self) -> None:
        """產生所有使用者的彙總報告"""
        print(f"\n{'='*70}")
        print("正在產生彙總報告...")
        print(f"{'='*70}")
        
        # 產生 Markdown 表格
        report_lines = [
            "# 開發者技術水平分析彙總報告",
            "",
            f"**生成時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**分析人數：** {len(self.analysis_results)} 位開發者  ",
            f"**分析方式：** 程式碼計算（Code-Based Analysis）",
            "",
            "---",
            "",
            "## 📊 整體評分總覽",
            "",
            "| username | 程式碼貢獻量 | 技術廣度 | 協作能力 | Code Review 品質 | 工作模式 | 進步趨勢 |",
            "|----------|-------------|---------|---------|-----------------|---------|---------|"
        ]
        
        # 排序：按總分降序
        sorted_results = sorted(
            self.analysis_results, 
            key=lambda x: x['total_score'], 
            reverse=True
        )
        
        for result in sorted_results:
            username = result['username']
            scores = result['scores']
            
            # 建立表格行（僅包含需要的欄位）
            row = (
                f"| {username} "
                f"| {scores['contribution']:.2f} "
                f"| {scores['tech_breadth']:.2f} "
                f"| {scores['collaboration']:.2f} "
                f"| {scores['code_review']:.2f} "
                f"| {scores['work_pattern']:.2f} "
                f"| {scores['progress_trend']:.2f} |"
            )
            report_lines.append(row)
        
        # 新增統計資訊
        report_lines.extend([
            "",
            "---",
            "",
            "## 📈 統計資訊",
            ""
        ])
        
        # 計算各等級人數
        level_counts = {}
        total_scores = []
        for result in self.analysis_results:
            level = result['level']
            level_counts[level] = level_counts.get(level, 0) + 1
            total_scores.append(result['total_score'])
        
        # 等級分佈
        report_lines.append("### 等級分佈")
        report_lines.append("")
        for level, count in sorted(level_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(self.analysis_results) * 100
            report_lines.append(f"- **{level}**：{count} 位 ({percentage:.1f}%)")
        
        # 分數統計
        if total_scores:
            avg_score = sum(total_scores) / len(total_scores)
            max_score = max(total_scores)
            min_score = min(total_scores)
            
            report_lines.extend([
                "",
                "### 分數統計",
                "",
                f"- **平均分：** {avg_score:.2f}",
                f"- **最高分：** {max_score:.2f}",
                f"- **最低分：** {min_score:.2f}",
            ])
        
        # 各維度平均分
        dimension_names = {
            'contribution': '程式碼貢獻量',
            'commit_quality': 'Commit 品質',
            'tech_breadth': '技術廣度',
            'collaboration': '協作能力',
            'code_review': 'Code Review 品質',
            'work_pattern': '工作模式',
            'progress_trend': '進步趨勢'
        }
        
        dimension_avgs = {}
        for dim_key in dimension_names.keys():
            scores = [r['scores'][dim_key] for r in self.analysis_results]
            dimension_avgs[dim_key] = sum(scores) / len(scores)
        
        report_lines.extend([
            "",
            "### 各維度平均分",
            ""
        ])
        
        for dim_key, dim_name in dimension_names.items():
            avg = dimension_avgs[dim_key]
            report_lines.append(f"- **{dim_name}**：{avg:.2f}")
        
        # 新增說明
        report_lines.extend([
            "",
            "---",
            "",
            "## 📝 評分說明",
            "",
            "**等級標準：**",
            "- 🏆 **高級工程師** (8-10分)：Message 規範率 90%+、小型變更佔比 80%+、涉及 3+ 技術棧",
            "- ⭐ **中級工程師** (5-7分)：Message 規範率 60-90%、變更粒度合理、2-3 種技術棧",
            "- 🌱 **初級工程師** (1-4分)：Message 不規範、大量修復性提交、單一技術棧",
            "",
            "**維度權重：**",
            "- Commit 品質：23% ⭐ 最重要",
            "- 技術廣度：18%",
            "- 進步趨勢：15%",
            "- 程式碼貢獻量：12%",
            "- 協作能力：12%",
            "- Code Review 品質：10%",
            "- 工作模式：10%",
            "",
            "---",
            "",
            "**分析工具版本：** v1.0  ",
            "**評分標準：** 基於 code-quality-analysis-spec.md"
        ])
        
        # 儲存彙總報告
        summary_path = self.output_dir / 'users' / 'all-user-analysis-result.md'
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"✅ 彙總報告已儲存：{summary_path}")
        print(f"   共分析 {len(self.analysis_results)} 位開發者")
    
    def _find_user_directories(self, username: Optional[str]) -> List[Path]:
        """尋找使用者資料目錄"""
        if not self.data_source.exists():
            return []
        
        if username:
            # 指定使用者
            user_dir = self.data_source / username
            if user_dir.exists() and user_dir.is_dir():
                return [user_dir]
            return []
        else:
            # 全部使用者
            return [d for d in self.data_source.iterdir() if d.is_dir()]
