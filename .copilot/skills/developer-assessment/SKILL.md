---
name: developer-assessment
description: GitLab 開發者評估與分析技能，使用 gl-cli.py 工具分析開發者的程式碼品質、提交歷史、專案參與度與技術水平，並產生綜合評估報告。
globs: ['**/*.py', '**/*.md', '**/scripts/**']
---

# GitLab Developer Assessment Skill

GitLab 開發者評估與分析專家，透過 `gl-cli.py` 工具深度分析開發者在 GitLab 上的活動與貢獻，提供多維度的技術能力評估。

## 核心職責

1. **互動式需求確認**
   - 詢問分析目標（特定開發者 vs 團隊整體）
   - 確認分析範圍（時間區間、專案範圍）
   - 選擇評估維度（程式碼品質、活躍度、協作能力等）

2. **資料收集與分析** (詳見 [gl-cli.py 完整操作手冊](../../../scripts/README.md))
   - 使用 `gl-cli.py user-details` 取得開發者詳細資訊（commits, code changes, MRs, reviews）
   - 使用 `gl-cli.py user-projects` 取得開發者專案列表
   - 使用 `gl-cli.py project-stats` 取得專案詳細資訊
   - 使用 `gl-cli.py group-stats` 取得群組資訊（團隊分析）

3. **多維度評估** (詳見 [程式碼品質評估規範](./references/code-quality-analysis-spec.md))
   - **提交品質**：分析 commit 頻率、commit message 規範、程式碼變更量
   - **活躍度**：評估提交頻率、MR 參與度、issue 回應速度
   - **協作能力**：分析 code review 參與、跨專案協作、知識分享
   - **技術深度**：識別技術棧使用、程式語言熟練度、架構設計能力
   - **專案貢獻**：統計專案參與數量、核心專案貢獻度
   - **Code Review 品質**：Review 參與度、深度、時效性、問題發現能力

4. **報告產生**
   - 產生結構化評估報告（markdown 格式）
   - 提供視覺化圖表建議（若需要）
   - 給予改善建議與學習方向

## 工具整合

> 📚 **完整操作手冊**: [gl-cli.py 使用指南](../../../scripts/README.md) - 包含所有命令、參數說明與範例

### gl-cli.py 核心命令（v2.0.0+）

```bash
# 環境設定
cd /mnt/d/lab/gitlab-developer-assessment/scripts

# ⭐ 主要命令：取得開發者詳細資訊（推薦使用）
python3 gl-cli.py user-details \
  --username <開發者名稱> \
  --project-name <專案名稱> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  --output <輸出目錄>  # 選填，預設為 ./output

# 輸出檔案結構：
# output/                             # 預設輸出目錄（可透過 --output 參數自訂）
# ├── users/                          # 開發者資料目錄
# │   └── <username>/                 # 每位開發者獨立目錄
# │       ├── <username>-index.md     # 索引檔案（資料摘要與檔案清單）
# │       ├── user_profile.csv        # 使用者基本資料 (30+ 欄位)
# │       ├── user_events.csv         # 活動事件追蹤
# │       ├── commits.csv             # Commit 詳細記錄
# │       ├── code_changes.csv        # 程式碼異動詳情（file-level diffs）
# │       ├── merge_requests.csv      # MR 記錄
# │       ├── code_reviews.csv        # Code Review 評論
# │       ├── contributors.csv        # 專案貢獻者統計
# │       ├── permissions.csv         # 專案授權資訊
# │       └── statistics.csv          # 統計摘要 (多項指標)
# ├── groups/                         # 群組資料目錄
# │   └── <groupname>/
# │       ├── groups.csv              # 群組資訊
# │       ├── subgroups.csv           # 子群組列表
# │       ├── projects.csv            # 專案列表
# │       ├── permissions.csv         # 成員權限
# │       └── summary.csv             # 群組摘要
# └── projects/                       # 專案資料目錄
#     └── <projectname>/
#         ├── project.csv             # 專案資訊
#         └── permissions.csv         # 專案權限
# 
# 📌 CSV 檔案編碼：UTF-8 with BOM (utf-8-sig)，Excel 可直接開啟
# 
# 範例：分析開發者 G2023018 在 "新求才WebVue" 專案
# → 輸出路徑：output/users/G2023018/commits.csv

# 取得使用者專案列表
python3 gl-cli.py user-projects \
  --username <開發者名稱> \
  --group-name <群組名稱> \
  --output <輸出目錄>  # 選填

# 取得專案詳細資訊
python3 gl-cli.py project-stats \
  --project-name <專案名稱> \
  --output <輸出目錄>  # 選填

# 取得群組資訊
python3 gl-cli.py group-stats \
  --group-name <群組名稱> \
  --output <輸出目錄>  # 選填
```

### 🆕 支援多參數查詢與批次模式優化

```bash
# 多位使用者同時查詢（自動啟用批次模式優化）
# 批次模式：預先載入專案清單，共用快取，顯著提升效能
python3 gl-cli.py user-details \
  --username alice bob charlie \
  --start-date 2024-01-01

# 多個專案同時查詢（笛卡爾積模式）
python3 gl-cli.py user-details \
  --project-name "web-api" "mobile-app" "admin-panel" \
  --start-date 2024-01-01

# 組合查詢：多位使用者在多個專案的活動
# 注意：多使用者 + 多專案 → 使用笛卡爾積模式（較慢）
python3 gl-cli.py user-details \
  --username alice bob \
  --project-name "web-api" "mobile-app" \
  --start-date 2024-01-01

# 💡 效能建議：
# ✅ 推薦：多使用者 + 單一專案範圍（或不指定專案）→ 批次模式
# ⚠️  較慢：多使用者 + 多專案 → 笛卡爾積模式
```

### 相依套件與環境設定

執行前需確保已安裝：
- pandas
- openpyxl
- urllib3
- python-gitlab >= 4.4.0 (透過 gitlab_client.py)

若缺少套件，引導使用者安裝：
```bash
cd /mnt/d/lab/gitlab-developer-assessment
source .venv/bin/activate  # 如果有虛擬環境
pip install pandas openpyxl urllib3 python-gitlab

# 或使用 uv（推薦）
cd scripts && uv sync
```

### 設定檔配置

首次使用需設定 GitLab 連線資訊：
```bash
# 複製範本
cp scripts/config-example.py scripts/config.py

# 編輯 config.py，設定以下參數：
# - GITLAB_URL: GitLab 伺服器位址
# - GITLAB_TOKEN: Personal Access Token（需要 read_api, read_repository, read_user 權限）
# - START_DATE / END_DATE: 預設分析時間範圍
# - TARGET_GROUP_ID: 預設群組 ID（可選）
```

## 互動式工作流程

### 第 1 步：需求確認

詢問使用者：

1. **分析對象**
   - 特定開發者（請提供 GitLab username）
   - 整個團隊/群組（請提供群組名稱或 ID）

2. **時間範圍**
   - 最近 1 個月
   - 最近 3 個月
   - 最近 6 個月
   - 自訂時間區間（請提供開始與結束日期）

3. **專案範圍**
   - 所有專案
   - 特定專案（請提供專案名稱列表）
   - 特定群組下的專案（請提供群組 ID 或名稱）

4. **評估維度**（多選）
   - [ ] 提交活躍度與頻率
   - [ ] 程式碼變更量分析
   - [ ] Commit message 品質
   - [ ] 專案參與廣度
   - [ ] 技術棧識別
   - [ ] 完整評估（包含所有維度）

### 第 2 步：執行資料收集

根據使用者選擇，依序執行：

1. **檢查環境**
   ```bash
   # 確認 gl-cli.py 可用
   test -f /mnt/d/lab/gitlab-developer-assessment/scripts/gl-cli.py
   
   # 檢查相依套件
   cd /mnt/d/lab/gitlab-developer-assessment/scripts
   python3 -c "import pandas, openpyxl, urllib3, gitlab" 2>&1
   
   # 檢查設定檔
   test -f /mnt/d/lab/gitlab-developer-assessment/scripts/config.py
   ```

2. **收集開發者資料**
   ```bash
   cd /mnt/d/lab/gitlab-developer-assessment/scripts
   
   # 單一使用者
   python3 gl-cli.py user-details \
     --username <username> \
     --start-date <YYYY-MM-DD> \
     --end-date <YYYY-MM-DD> \
     --output ./output  # 可選，預設為 ./output
   
   # 多位使用者（批次模式優化）
   python3 gl-cli.py user-details \
     --username alice bob charlie \
     --start-date <YYYY-MM-DD>
   ```

3. **收集專案參與資料**
   ```bash
   python3 gl-cli.py user-projects \
     --username <username> \
     --output ./output  # 可選
   ```

4. **讀取並解析輸出檔案**
   - 所有 CSV 檔案輸出到 `scripts/output/users/<username>/` 目錄
   - CSV 使用 UTF-8 BOM 編碼 (utf-8-sig)，Excel 可直接開啟
   - 使用 bash + pandas 工具讀取並分析 CSV 檔案
   - 參考自動產生的 `output/users/<username>/<username>-index.md` 檔案了解檔案清單與資料摘要

### 第 3 步：資料分析

根據收集的資料，分析以下指標（完整評估標準請參考 [code-quality-analysis-spec.md](./references/code-quality-analysis-spec.md)）：

#### 3.1 提交活躍度
- 總 commit 數量
- 平均每週/每月 commit 數
- 提交時間分布（識別工作習慣）
- 活躍天數佔比

#### 3.2 程式碼品質指標
- 平均每次 commit 的程式碼變更量（Lines of Code）
- 新增 vs 刪除 vs 修改的比例
- 檔案類型分布（識別專長領域）
- Commit message 規範性（長度、格式、描述性）

#### 3.3 專案貢獻度
- 參與專案數量
- 每個專案的貢獻量分布
- 核心專案識別（貢獻量 > 30% 的專案）
- 跨專案協作指標

#### 3.4 技術棧分析
- 使用的程式語言分布
- 框架與工具識別（從檔案類型推斷）
- 技術廣度 vs 深度評估

### 第 4 步：產生評估報告

產生結構化的 Markdown 報告：

```markdown
# GitLab Developer Assessment Report

## 📊 基本資訊
- **開發者**: <username>
- **分析期間**: <start_date> ~ <end_date>
- **分析專案**: <project_count> 個專案
- **報告生成時間**: <timestamp>

---

## 🎯 綜合評分

| 評估維度 | 評分 | 說明 |
|---------|------|------|
| 提交活躍度 | ⭐⭐⭐⭐☆ (4/5) | 平均每週 X 次提交，表現良好 |
| 程式碼品質 | ⭐⭐⭐⭐⭐ (5/5) | Commit message 規範，變更量合理 |
| 專案貢獻度 | ⭐⭐⭐☆☆ (3/5) | 主要集中在 2 個核心專案 |
| 技術廣度 | ⭐⭐⭐⭐☆ (4/5) | 熟悉多種技術棧 |

**總體評價**: ⭐⭐⭐⭐☆ (4/5)

---

## 📈 活躍度分析

- **總 Commit 數**: X 次
- **平均每週提交**: X 次
- **活躍天數**: X 天 (佔比 X%)
- **最活躍時段**: 週一至週五 9:00-18:00

### 趨勢圖建議
\`\`\`
[建議使用 Excel 開啟輸出檔案，查看詳細統計圖表]
\`\`\`

---

## 💻 程式碼貢獻分析

- **總變更行數**: +X / -Y 行
- **平均每次 Commit**: ~Z 行
- **主要變更類型**: 
  - 新增功能: X%
  - Bug 修復: Y%
  - 重構: Z%

### Commit Message 品質
- ✅ 規範性: 良好
- ✅ 描述性: 詳細
- ⚠️ 改善建議: 建議增加 ticket ID 引用

---

## 🚀 專案參與度

| 專案名稱 | Commit 數 | 貢獻度 | 角色 |
|---------|----------|--------|------|
| Project A | X | High | Core Developer |
| Project B | Y | Medium | Contributor |
| Project C | Z | Low | Occasional |

**核心專案**: Project A (貢獻度 X%)

---

## 🔧 技術棧分析

### 程式語言分布
- Python: X%
- JavaScript: Y%
- SQL: Z%
- Others: W%

### 專長領域
- ✅ 後端開發 (Python, API)
- ✅ 資料庫設計 (SQL)
- 🔄 前端開發 (JavaScript) - 持續學習中

---

## 💡 改善建議

1. **提升專案參與廣度**
   - 建議參與更多跨團隊協作專案
   - 嘗試不同領域的技術挑戰

2. **深化技術深度**
   - 在核心專案中承擔更多架構設計工作
   - 增加 code review 參與度

3. **知識分享**
   - 建議撰寫技術文件或 README
   - 參與 issue 討論，分享經驗

---

## 📌 數據來源

本報告資料來源於 GitLab，透過 `gl-cli.py` 工具收集：
- 使用者統計: `user-stats`
- 專案列表: `user-projects`
- 時間範圍: <start_date> ~ <end_date>

---

**報告結束**
\`\`\`

### 第 5 步：後續行動建議

詢問使用者是否需要：

1. **匯出詳細資料**
   - Excel 檔案已儲存在: `output/<username>/dev_stats.xlsx`
   - 是否需要轉換為 CSV 或其他格式？

2. **進階分析**
   - 與團隊平均值比較
   - 時間序列趨勢分析
   - 特定專案深度分析

3. **持續追蹤**
   - 設定定期評估機制
   - 建立績效追蹤儀表板

## 錯誤處理

### 常見問題處理

1. **缺少相依套件**
   ```bash
   # 引導安裝
   cd /mnt/d/lab/gitlab-developer-assessment
   source .venv/bin/activate  # 如果有虛擬環境
   pip install pandas openpyxl urllib3 python-gitlab
   
   # 或使用 uv（推薦）
   cd scripts && uv sync
   ```

2. **GitLab 連線失敗**
   - 檢查 `scripts/config.py` 設定（GITLAB_URL, GITLAB_TOKEN）
   - 確認 GitLab Token 有效性與權限（需要 read_api, read_repository, read_user）
   - 驗證網路連線與 SSL 憑證
   - SSL 憑證問題：gl-cli.py 預設已停用 SSL 驗證（ssl_verify=False）

3. **無資料返回**
   - 確認使用者名稱正確
   - 檢查時間範圍是否合理
   - 驗證使用者在指定專案中有活動

4. **權限不足**
   - 確認 GitLab Token 有足夠權限（read_api, read_repository）
   - 檢查使用者是否為專案成員

## 最佳實踐

1. **資料保護**
   - 輸出檔案預設儲存在 `scripts/output/`，可透過 `--output` 自訂
   - 不在報告中包含敏感資訊（email、token）
   - 分析完成後詢問是否刪除暫存檔案

2. **效能優化**
   - ✅ **批次模式**：多位使用者 + 單一專案範圍（或不指定專案）→ 自動啟用批次模式，預先載入專案清單，共用快取
   - ⚠️ **笛卡爾積模式**：多位使用者 + 多個專案 → 效能較慢，建議拆分查詢
   - 大型團隊分析時，建議分批處理（利用批次模式優化）
   - 使用 `--group-id` 限縮查詢範圍
   - 避免過長的時間區間（建議 ≤ 6 個月）
   - gl-cli.py 使用多執行緒（ThreadPoolExecutor）加速專案分析，最多 10 個並行執行緒

3. **報告品質**
   - 提供具體數據支持評分
   - 避免主觀判斷，基於客觀指標
   - 給予建設性改善建議
   - 善用自動產生的 `<username>-index.md` 檔案快速了解資料概況

4. **使用者體驗**
   - 清晰的互動提示
   - 進度即時反饋（多查詢時自動顯示進度：查詢 X/Y）
   - 結果易於理解的視覺化呈現
   - CSV 使用 UTF-8 BOM 編碼，Excel 可直接開啟無亂碼

## 範例對話流程

```
使用者: 幫我分析開發者 john.doe 的表現

Skill: 好的！我將協助您分析 john.doe 的開發表現。請回答以下問題：

1. 分析時間範圍？
   a) 最近 1 個月
   b) 最近 3 個月
   c) 最近 6 個月
   d) 自訂（請提供起迄日期）

使用者: b

Skill: 2. 專案範圍？
   a) 所有專案
   b) 特定專案（請列出專案名稱）
   c) 特定群組（請提供群組 ID）

使用者: a

Skill: 3. 評估維度？（可多選）
   a) 提交活躍度
   b) 程式碼品質
   c) 專案參與度
   d) 技術棧分析
   e) 完整評估（全部）

使用者: e

Skill: 收到！開始執行完整評估...

[執行 gl-cli.py 命令]
[分析資料]
[產生報告]

完成！以下是 john.doe 的評估報告：

[顯示 Markdown 報告]

是否需要：
- 查看詳細 Excel 報告？
- 與團隊平均值比較？
- 匯出報告為檔案？
```

## 整合其他工具

若需要進階分析，可整合：

1. **Git 本地分析** (若有 clone repository)
   - 使用 `git log` 分析 commit 歷史
   - 使用 `git blame` 分析程式碼擁有權
   - 使用 `git diff` 分析變更品質

2. **程式碼品質工具**
   - pylint / flake8 (Python)
   - eslint (JavaScript)
   - SonarQube

3. **視覺化工具**
   - matplotlib / seaborn (Python 圖表)
   - Excel 樞紐分析表
   - Grafana (若有 metrics)

## 限制與注意事項

1. **資料準確性**
   - 依賴 GitLab API 回傳資料
   - 可能受網路延遲影響
   - 歷史資料可能不完整（取決於 GitLab 設定）

2. **評估侷限**
   - 無法評估程式碼實際品質（需 code review）
   - 無法評估軟技能（溝通、領導力）
   - 量化指標不代表全部價值

3. **隱私考量**
   - 需取得開發者同意
   - 不應作為唯一績效評估依據
   - 報告應妥善保管，避免外洩

---

## 參考文檔

- 📚 **[gl-cli.py 完整操作手冊](../../../scripts/README.md)** - 工具使用指南、所有命令參數、範例與故障排除
- 📊 **[程式碼品質分析規範](./references/code-quality-analysis-spec.md)** - 詳細的評估維度、權重配置與評分標準

---

**使用此 Skill 時，請確保已設定好 GitLab 環境並擁有適當權限。**
