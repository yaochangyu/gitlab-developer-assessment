# GitLab Developer Assessment - AI Agent Instructions

## Project Overview

This is a **Python CLI toolset** for analyzing GitLab developer code quality and technical proficiency. It extracts comprehensive metrics from GitLab API including commits, merge requests, code reviews, permissions, and generates CSV/Markdown reports for developer assessment.

**Key Components:**
- `gitlab_client.py` - Unified GitLab API wrapper (projects, commits, MRs, users, groups)
- `gl-cli.py` - Main SOLID-designed CLI (v1.x) with threading support
- `gl-cli-2.py` - Simplified CLI (v2.x) for user-centric analysis
- `export_all_*.py` - Batch export scripts (users, projects, groups)

## Architecture Patterns

### Client-Wrapper Pattern
All GitLab API interactions go through `GitLabClient` class - never call `python-gitlab` directly in CLI scripts. This centralizes error handling, SSL verification, and pagination logic.

```python
# ✅ Correct
client = GitLabClient(config.GITLAB_URL, config.GITLAB_TOKEN)
projects = client.get_projects(group_id=123)

# ❌ Wrong
gl = gitlab.Gitlab(url, token)
projects = gl.projects.list()
```

### Multi-CLI Design Philosophy
- **gl-cli.py**: Feature-rich, SOLID-based, supports project/group/user statistics with threading
- **gl-cli-2.py**: Simplified user-details focused tool with 8 CSV output types per user
- **export_all_*.py**: Quick batch exports with timestamped output files

Choose the right tool based on use case - don't try to unify them.

### Output Organization
```
output/           # gl-cli.py default
output-2/         # gl-cli-2.py default  
  {username}-user-{type}.csv    # 8 types: profile, commits, code_changes, merge_requests, code_reviews, contributors, permissions, statistics
```

All commands support `--output` parameter to customize directory.

## Critical Developer Workflows

### First-Time Setup
```powershell
# 1. Install uv (Python package manager)
# 2. Copy config template
cp scripts/config-example.py scripts/config.py

# 3. Edit config.py with your GitLab URL and token (requires read_api, read_repository, read_user scopes)
# 4. Install dependencies
cd scripts && uv sync
```

### Running Analysis Commands
```bash
# Use uv run prefix (NOT python directly)
uv run python gl-cli.py project-stats --output ./reports
uv run python gl-cli-2.py user-details --username alice bob --start-date 2024-01-01

# Or use convenience wrapper
.\run-gl-cli.ps1 project-stats  # PowerShell on Windows
./run-gl-cli.sh project-stats   # Bash on Linux/Mac
```

### Common Analysis Patterns
```bash
# Single user deep dive (8 CSV files)
uv run python gl-cli-2.py user-details --username alice

# Multi-user comparison
uv run python gl-cli-2.py user-details --username alice bob charlie --start-date 2024-01-01

# Specific projects only
uv run python gl-cli.py project-stats --project-name web-api mobile-app

# Export all groups with hierarchy
python export_all_groups.py --output ./org-structure
```

## Project-Specific Conventions

### Date Handling
- Always use ISO format: `YYYY-MM-DD` (e.g., `2024-01-01`)
- Date filters apply via GitLab API's `since`/`until` parameters
- Default range defined in `config.py`: START_DATE to END_DATE

### CSV Field Naming
- Snake_case for all CSV columns: `user_id`, `merge_requests_count`, `total_additions`
- Timestamp fields use GitLab's ISO format: `created_at`, `merged_at`
- Consistent prefixes: `total_*` for aggregates, `*_count` for quantities

### Error Handling Strategy
```python
# Use getattr() for GitLab API objects (fields may not exist)
email = getattr(user, 'email', '')  # Returns '' if field missing

# Try-except for API calls with user-friendly messages
try:
    contributors = project.repository_contributors()
except Exception as e:
    print(f"  ⚠️  無法取得專案 {project.name} 的貢獻者: {e}")
```

### Threading Guidelines (gl-cli.py only)
- Max 10 concurrent threads for project analysis
- 60-second timeout per project to prevent hanging
- SIGINT handler for graceful shutdown
- Progress indicators with `[idx/total]` format

## Key Integration Points

### GitLab API Dependencies
- **python-gitlab >= 4.4.0** - Primary API client
- API endpoints used: projects, commits, merge_requests, users, groups, repository_contributors
- SSL verification disabled (`ssl_verify=False`) for self-signed certs - configure in config.py

### Data Export Pipeline
1. **GitLabClient** fetches raw data from API
2. **Analyzer classes** transform into structured dicts
3. **pandas** DataFrames for CSV generation
4. UTF-8 BOM encoding (`utf-8-sig`) for Excel compatibility

### CSV Output Types (gl-cli-2.py)
Each user generates 8 CSV files:
1. `user_profile` - 30+ fields (email, job_title, organization, followers, 2FA status)
2. `commits` - All commits with stats (additions, deletions, changed_files_count)
3. `code_changes` - File-level diffs for each commit
4. `merge_requests` - MR metadata (title, state, comments_count, merged_at)
5. `code_reviews` - Discussion threads and review comments
6. `contributors` - Per-project contribution statistics
7. `permissions` - Access levels across all projects (Guest/Reporter/Developer/Maintainer/Owner)
8. `statistics` - Aggregated summary metrics

## Testing & Debugging

### SSL Certificate Issues
```python
# All scripts disable SSL warnings via urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# GitLabClient initialized with ssl_verify=False
```

### Rate Limiting
- No explicit rate limit handling - GitLab CE/EE typically no limits for authenticated users
- Use `time.sleep()` if encountering 429 errors (not currently implemented)

### Output Validation
```bash
# Check CSV encoding (should be UTF-8 with BOM)
file -i output/*.csv

# Verify column counts
head -n 1 output-2/alice-user-commits.csv | awk -F',' '{print NF}'
```

## Code Generation Guidelines

When generating new analyzers or export scripts:
1. Extend `GitLabClient` for new API endpoints (don't call gitlab directly)
2. Use `getattr(obj, 'field', default)` for all GitLab API object fields
3. Output CSV with UTF-8 BOM encoding: `encoding='utf-8-sig'`
4. Add progress indicators: `print(f"[{idx}/{total}] Processing...")`
5. Include `--output` parameter for custom output directory
6. Document new CSV field names in README.md
7. Use pandas for CSV generation (consistent with existing scripts)
