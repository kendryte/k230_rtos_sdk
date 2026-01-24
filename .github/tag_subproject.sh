#!/bin/bash

TAG_NAME="$1"

if [ -z "$TAG_NAME" ]; then
  echo "Error: No tag name provided."
  echo "Usage: $0 <tag-name>"
  exit 1
fi

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 获取脚本所在目录 (.github/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 切换到repo根目录（.github/的父目录）
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
echo -e "${BOLD}Script directory: $SCRIPT_DIR${NC}"
echo -e "${BOLD}Repo root: $REPO_ROOT${NC}"

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo -e "${RED}Error: Not in a Git repository root (.git directory not found)${NC}"
  echo "Current directory: $REPO_ROOT"
  exit 1
fi

cd "$REPO_ROOT" || {
  echo -e "${RED}Error: Cannot change to repo root directory: $REPO_ROOT${NC}"
  exit 1
}

echo -e "${BOLD}Working directory: $(pwd)${NC}"

# Python脚本在.github/目录下
PYTHON_SCRIPT="$SCRIPT_DIR/tag_repo.py"
if [ ! -f "$PYTHON_SCRIPT" ]; then
  echo -e "${RED}Error: Cannot find tag_repo.py script${NC}"
  echo "Expected location: $PYTHON_SCRIPT"
  exit 1
fi

echo -e "${BOLD}Applying tag: $TAG_NAME to all subprojects...${NC}"
echo -e "${BOLD}Using Python script: $PYTHON_SCRIPT${NC}"

# 检查Python脚本是否可执行
if [ ! -x "$PYTHON_SCRIPT" ]; then
  chmod +x "$PYTHON_SCRIPT" 2>/dev/null || echo -e "${YELLOW}Warning: Cannot make Python script executable${NC}"
fi

# 检查repo命令是否可用
REPO_CMD=""
if [ -f ~/.bin/repo ] && [ -x ~/.bin/repo ]; then
  REPO_CMD="$HOME/.bin/repo"
elif command -v repo &> /dev/null; then
  REPO_CMD="repo"
else
  echo -e "${RED}Error: repo command not found${NC}"
  echo "Please ensure ~/.bin/repo exists or repo is in PATH"
  exit 1
fi

echo -e "${BOLD}Using repo command: $REPO_CMD${NC}"

# 获取项目列表
echo -e "\n${BOLD}Fetching project list from repo command...${NC}"
PROJECTS=$($REPO_CMD list --group sdk -p 2>&1)
REPO_EXIT_CODE=$?

if [ $REPO_EXIT_CODE -ne 0 ]; then
  echo -e "${RED}Error: Failed to get project list${NC}"
  echo "Command: $REPO_CMD list --group sdk -p"
  echo "Exit code: $REPO_EXIT_CODE"
  echo "Output:"
  echo "$PROJECTS"
  exit 1
fi

# 检查项目列表是否为空
PROJECT_COUNT=$(echo "$PROJECTS" | grep -c "^")
if [ "$PROJECT_COUNT" -eq 0 ]; then
  echo -e "${YELLOW}Warning: No projects found in SDK group${NC}"
  echo "Project list output:"
  echo "$PROJECTS"
  echo ""
  echo "Would you like to continue anyway? [y/N]"
  read -r response
  if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 0
  fi
fi

echo -e "${GREEN}Found $PROJECT_COUNT project(s) in SDK group${NC}"

# 统计变量
TOTAL=0
SUCCESS=0
FAILED=0
SKIPPED=0
ERROR_PROJECTS=()

# 显示项目列表预览
if [ "$PROJECT_COUNT" -gt 0 ]; then
  echo -e "\n${BOLD}Projects to be tagged:${NC}"
  echo "$PROJECTS" | while IFS= read -r project; do
    [ -z "$project" ] && continue
    echo "  • $(basename "$project")"
  done
  echo ""
fi

# 执行主循环
while IFS= read -r project; do
  # 跳过空行
  [ -z "$project" ] && continue
  
  TOTAL=$((TOTAL + 1))
  PROJECT_NAME=$(basename "$project")
  
  echo "════════════════════════════════════════════════════════════════"
  echo -e "${BOLD}Processing project [$TOTAL/$PROJECT_COUNT]: $PROJECT_NAME${NC}"
  echo "════════════════════════════════════════════════════════════════"
  
  # 检查项目路径是否存在（相对于repo根目录）
  if [ ! -d "$project" ]; then
    echo -e "${YELLOW}⚠️  Skipping: Project directory not found${NC}"
    echo "  Expected path: $project"
    echo "  Absolute path: $(pwd)/$project"
    SKIPPED=$((SKIPPED + 1))
    ERROR_PROJECTS+=("$PROJECT_NAME: Directory not found at '$project'")
    continue
  fi
  
  # 检查是否为Git仓库
  if [ ! -d "$project/.git" ]; then
    echo -e "${YELLOW}⚠️  Skipping: Not a Git repository${NC}"
    echo "  Path: $project"
    SKIPPED=$((SKIPPED + 1))
    ERROR_PROJECTS+=("$PROJECT_NAME: Not a Git repository")
    continue
  fi
  
  echo "  Path: $project"
  echo "  Tag: $TAG_NAME"
  
  # 显示远程信息（如果有）
  if [ -d "$project/.git" ]; then
    (
      cd "$project" && \
      REMOTE=$(git remote 2>/dev/null | head -n1) && \
      if [ -n "$REMOTE" ]; then
        REMOTE_URL=$(git remote get-url "$REMOTE" 2>/dev/null || echo "")
        echo "  Remote: $REMOTE ($REMOTE_URL)"
      fi
    )
  fi
  
  # 调用Python脚本处理
  echo -e "\n  ${BOLD}Executing:${NC} python3 \"$PYTHON_SCRIPT\" \"$project\" \"$TAG_NAME\""
  echo ""
  
  if python3 "$PYTHON_SCRIPT" "$project" "$TAG_NAME"; then
    echo -e "\n  ${GREEN}✅ Successfully tagged $PROJECT_NAME${NC}"
    SUCCESS=$((SUCCESS + 1))
  else
    PYTHON_EXIT_CODE=$?
    echo -e "\n  ${RED}❌ Failed to tag $PROJECT_NAME (exit code: $PYTHON_EXIT_CODE)${NC}"
    FAILED=$((FAILED + 1))
    ERROR_PROJECTS+=("$PROJECT_NAME: Python script failed with code $PYTHON_EXIT_CODE")
  fi
  
done <<< "$PROJECTS"

# 打印总结报告
echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${BOLD}TAGGING COMPLETED - SUMMARY REPORT${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo -e "${BOLD}Statistics:${NC}"
echo "  Total projects in SDK group: $PROJECT_COUNT"
echo "  Attempted to process:        $TOTAL"
echo "  Successfully tagged:         ${GREEN}$SUCCESS${NC}"
echo "  Failed:                      ${RED}$FAILED${NC}"
echo "  Skipped:                     ${YELLOW}$SKIPPED${NC}"
echo ""

if [ ${#ERROR_PROJECTS[@]} -gt 0 ]; then
  echo -e "${BOLD}Issues encountered:${NC}"
  for error in "${ERROR_PROJECTS[@]}"; do
    echo "  • $error"
  done
  echo ""
fi

if [ $TOTAL -eq 0 ]; then
  echo -e "${YELLOW}⚠️  No projects were processed. Check if SDK group contains projects.${NC}"
  exit 0
elif [ $FAILED -eq 0 ] && [ $SKIPPED -eq 0 ]; then
  echo -e "${GREEN}🎉 SUCCESS: All $SUCCESS projects tagged successfully!${NC}"
  exit 0
elif [ $FAILED -eq 0 ]; then
  echo -e "${YELLOW}⚠️  PARTIAL SUCCESS: $SUCCESS projects tagged, $SKIPPED skipped.${NC}"
  exit 0
else
  echo -e "${RED}💥 FAILURE: $FAILED out of $TOTAL projects failed.${NC}"
  exit 1
fi
