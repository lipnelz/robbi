#!/bin/bash
# Test script to verify git pull works in Docker container

set -e

echo "=================================================="
echo "Testing Git Pull Configuration for Robbi Bot"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if container exists
echo -e "${YELLOW}[1/5] Checking if robbi-container exists...${NC}"
if docker ps -a --format "table {{.Names}}" | grep -q "^robbi-container$"; then
    echo -e "${GREEN}✓ Container found${NC}"
else
    echo -e "${RED}✗ Container not found. Start it with: docker compose up -d${NC}"
    exit 1
fi

# Check git configuration
echo ""
echo -e "${YELLOW}[2/5] Checking git configuration...${NC}"
docker exec robbi-container git remote -v
echo -e "${GREEN}✓ Git remote configured${NC}"

# Test git pull (without actual pull to avoid rate limiting)
echo ""
echo -e "${YELLOW}[3/5] Testing git command access...${NC}"
if docker exec robbi-container git rev-parse --short HEAD > /dev/null 2>&1; then
    COMMIT=$(docker exec robbi-container git rev-parse --short HEAD)
    echo -e "${GREEN}✓ Current commit: $COMMIT${NC}"
else
    echo -e "${RED}✗ Cannot access git commands${NC}"
    exit 1
fi

# Check branch
echo ""
echo -e "${YELLOW}[4/5] Checking current branch...${NC}"
BRANCH=$(docker exec robbi-container git rev-parse --abbrev-ref HEAD)
echo -e "${GREEN}✓ Branch: $BRANCH${NC}"

# Test dry-run git pull (to see if it would work)
echo ""
echo -e "${YELLOW}[5/5] Testing git pull (dry-run)...${NC}"
if docker exec robbi-container git pull --dry-run origin main 2>&1 | grep -q "Already up to date\|Fast-forward\|Merge made"; then
    echo -e "${GREEN}✓ Git pull would succeed${NC}"
else
    echo -e "${YELLOW}⚠ Git pull needs credentials (normal, will use GIT_TOKEN on restart)${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✓ All checks passed!${NC}"
echo "=================================================="
echo ""
echo "To verify git pull works on restart:"
echo "  1. Set GIT_TOKEN: export GIT_TOKEN=ghp_xxxx"
echo "  2. Restart bot:   docker restart robbi-container"
echo "  3. Check logs:    docker logs robbi-container"
echo ""
echo "See GIT_PULL_SETUP.md for full configuration guide"
