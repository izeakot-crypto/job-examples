#!/bin/bash
# Deploy Python article pipeline to server
# Usage: bash deploy.sh

SERVER="root@157.180.42.152"
DEPLOY_DIR="/var/www/seo-articles/python-pipeline"

echo "=== Deploying Python Pipeline ==="

# 1. Create directory on server
ssh $SERVER "mkdir -p $DEPLOY_DIR"

# 2. Upload Python files
echo "Uploading files..."
scp -r config.py main.py requirements.txt $SERVER:$DEPLOY_DIR/
scp -r pipeline/ $SERVER:$DEPLOY_DIR/
scp -r services/ $SERVER:$DEPLOY_DIR/
scp -r utils/ $SERVER:$DEPLOY_DIR/

# 3. Create .env on server (copy from existing or prompt)
echo "Setting up .env..."
ssh $SERVER "if [ ! -f $DEPLOY_DIR/.env ]; then
  echo 'WARNING: No .env found. Creating template — fill in the values!'
  cp $DEPLOY_DIR/.env.example $DEPLOY_DIR/.env 2>/dev/null || cat > $DEPLOY_DIR/.env << 'ENVEOF'
ANTHROPIC_API_KEY=REPLACE_ME
ANTHROPIC_BASE_URL=http://127.0.0.1:5003
GEMINI_API_KEY=REPLACE_ME
SUPABASE_URL=REPLACE_ME
SUPABASE_KEY=REPLACE_ME
GOOGLE_CSE_KEY=
GOOGLE_CSE_ID=
FRONTEND_BASE_URL=http://127.0.0.1:3000
HOST=0.0.0.0
PORT=8000
ENVEOF
else
  echo '.env already exists, keeping current values'
fi"

# 4. Install Python dependencies (venv required on Debian 12+)
echo "Installing dependencies..."
ssh $SERVER "cd $DEPLOY_DIR && python3 -m venv venv 2>/dev/null; source venv/bin/activate && pip install -r requirements.txt"

# 5. Create PM2 ecosystem file
echo "Creating PM2 config..."
ssh $SERVER "cat > $DEPLOY_DIR/ecosystem.config.js << 'PM2EOF'
module.exports = {
  apps: [{
    name: 'article-pipeline',
    script: 'main.py',
    interpreter: 'python3',
    args: '',
    cwd: '/var/www/seo-articles/python-pipeline',
    env: {
      PATH: process.env.PATH
    },
    max_restarts: 10,
    restart_delay: 5000,
    watch: false,
    log_date_format: 'YYYY-MM-DD HH:mm:ss'
  }]
};
PM2EOF"

# 6. Start with PM2
echo "Starting pipeline..."
ssh $SERVER "cd $DEPLOY_DIR && pm2 start ecosystem.config.js && pm2 save"

echo ""
echo "=== Deployment complete ==="
echo "Pipeline running at http://157.180.42.152:8000"
echo ""
echo "IMPORTANT: Don't forget to:"
echo "  1. Set ANTHROPIC_API_KEY in $DEPLOY_DIR/.env"
echo "  2. Add PYTHON_PIPELINE_URL=http://127.0.0.1:8000 to /var/www/seo-articles/api/.env"
echo "  3. Update ideasController.js to call Python instead of n8n"
