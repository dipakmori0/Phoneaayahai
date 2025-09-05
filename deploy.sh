#!/bin/bash
# Automated deployment script for Telegram Bot

echo "🚀 Starting deployment process..."
echo "📦 Adding files to git..."

# Add all changes to git
git add .

# Check if there are any changes to commit
if git diff-index --quiet HEAD --; then
    echo "✅ No changes to deploy"
else
    # Commit with timestamp
    commit_message="Deploy: $(date '+%Y-%m-%d %H:%M:%S')"
    git commit -m "$commit_message"
    
    # Push to GitHub
    echo "📤 Pushing to GitHub..."
    git push origin main
    
    echo "✅ Deployment completed successfully!"
    echo "🎉 Files pushed to GitHub repository: https://github.com/dipakmori0/Phoneaayahai"
fi

echo "📊 Current status:"
git status
