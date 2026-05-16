#!/bin/bash

# Fashion Image Analyzer - Render Deployment Script
# This script helps you set up and deploy to Render

set -e

echo "================================"
echo "Render Deployment Setup Script"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}Git repository not found. Initializing...${NC}"
    git init
    git add .
    git commit -m "Initial commit for Render deployment"
fi

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "Python version: ${GREEN}${python_version}${NC}"

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: requirements.txt not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ requirements.txt found${NC}"

# Check if Procfile exists
if [ ! -f "Procfile" ]; then
    echo -e "${RED}Error: Procfile not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Procfile found${NC}"

# Check if runtime.txt exists
if [ ! -f "runtime.txt" ]; then
    echo -e "${RED}Error: runtime.txt not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ runtime.txt found${NC}"

# Verify app structure
if [ ! -d "app" ] || [ ! -f "app/main.py" ]; then
    echo -e "${RED}Error: app/main.py not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ app/main.py found${NC}"

echo ""
echo -e "${YELLOW}Deployment files verification completed!${NC}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Push to GitHub/GitLab:"
echo "   git push origin main"
echo ""
echo "2. Visit https://dashboard.render.com"
echo "3. Click 'New +' and select 'Web Service'"
echo "4. Connect your repository"
echo "5. Render will auto-detect render.yaml"
echo ""
echo "6. Once deployed, test with:"
echo "   curl https://fashion-image-analyzer.onrender.com/health"
echo ""
echo -e "${YELLOW}For detailed instructions, see DEPLOYMENT_GUIDE.md${NC}"
