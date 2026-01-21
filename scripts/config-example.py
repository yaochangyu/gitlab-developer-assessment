"""
GitLab 分析工具配置檔案範本

使用方式：
1. 複製此檔案為 config.py
   cp config-example.py config.py

2. 編輯 config.py，填入您的實際配置
   - GITLAB_URL: 您的 GitLab 伺服器網址
   - GITLAB_TOKEN: 您的 Personal Access Token

3. 確保 config.py 已加入 .gitignore，避免 Token 洩漏
"""

# ==================== 必要配置 ====================

# GitLab 伺服器網址
GITLAB_URL = "https://gitlab.com/"  # 公開 GitLab
# GITLAB_URL = "https://gitlab.yourcompany.com/"  # 私有 GitLab 範例

# GitLab Personal Access Token
# 如何取得：Settings → Access Tokens → 新增 Token（需要 read_api, read_repository, read_user 權限）
GITLAB_TOKEN = "your_token_here"  # ⚠️ 請替換為您的實際 Token

# ==================== 分析時間範圍 ====================

# 開始日期 (YYYY-MM-DD 格式)
START_DATE = "2024-01-01"

# 結束日期 (YYYY-MM-DD 格式)
END_DATE = "2026-12-31"

# ==================== 可選配置 ====================

# 指定要分析的 Group ID（留空則分析所有可存取的群組）
# 範例：TARGET_GROUP_ID = 123
TARGET_GROUP_ID = None

# 指定要分析的 Project IDs（留空則分析所有可存取的專案）
# 範例：TARGET_PROJECT_IDS = [456, 789, 101]
TARGET_PROJECT_IDS = []

# ==================== 輸出設定 ====================

# 預設輸出目錄（可透過 --output 參數覆寫）
OUTPUT_DIR = "./output"

# ==================== GitHub Models API 設定 ====================

# GitHub Models API Key（用於開發者技術水平 AI 分析）
# 如何取得：https://github.com/settings/tokens → Generate new token (classic)
GITHUB_MODELS_API_KEY = ""  # ⚠️ 請替換為您的 GitHub Models API Key

# GitHub Models API 端點
GITHUB_MODELS_API_URL = "https://models.github.com/v1/chat/completions"

# 使用的模型（可選：gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo）
GITHUB_MODELS_MODEL = "gpt-4o"

# ==================== 配置範例 ====================

# 範例 1：公司內部 GitLab
# GITLAB_URL = "https://gitlab.mycompany.com/"
# GITLAB_TOKEN = "glpat-1234567890abcdef"
# START_DATE = "2024-01-01"
# END_DATE = "2024-12-31"
# TARGET_GROUP_ID = 42
# OUTPUT_DIR = "./reports"

# 範例 2：GitLab.com 開源專案
# GITLAB_URL = "https://gitlab.com/"
# GITLAB_TOKEN = "glpat-abcdef1234567890"
# TARGET_PROJECT_IDS = [123, 456]
# OUTPUT_DIR = "./output"

# 範例 3：快速測試
# GITLAB_URL = "https://192.168.1.158/"
# GITLAB_TOKEN = "test_token_here"
# START_DATE = "2024-06-01"
# END_DATE = "2024-06-30"

# ==================== 安全提醒 ====================
# ⚠️ 請勿將含有真實 Token 的 config.py 提交到版本控制！
# ✅ 確保 config.py 已加入 .gitignore
# ✅ 定期輪換您的 GitLab Token
# ✅ 使用最小權限原則（只授予必要的權限）
