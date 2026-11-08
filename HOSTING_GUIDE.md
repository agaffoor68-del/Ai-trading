=============================================================================
  Options Trading Platform - Local Hosting Setup Guide
=============================================================================

PREREQUISITES:
- Windows OS
- Python 3.12+ installed
- Node.js & npm installed
- PostgreSQL database (optional for basic functionality)

STEP 1: Install Python Dependencies
-----------------------------------
1. Open PowerShell or Command Prompt
2. Run: cd C:\app
3. Run: pip install -r requirements.txt
4. Installation will include:
   - fastapi==0.104.1
   - uvicorn[standard]==0.30.4
   - sqlalchemy==2.0.23
   - psycopg2-binary==2.9.9
   - python-dotenv==1.0.1
   - websockets==8.1.0 (critical for Render compatibility)
   - wsproto==0.24.0 (critical - avoids WebSocket crash)
   - aiohttp==3.9.1
   - pandas==2.2.1
   - pandas_ta==0.3.14 (100+ technical indicators)
   - python-dateutil==2.9.0.post0

STEP 2: Configure Environment Variables
----------------------------------------
1. Copy .env.example to .env: copy C:\app\.env.example C:\app\.env
2. Edit C:\app\.env with your credentials:
   - DATABASE_URL: PostgreSQL connection string
     Example: postgresql://postgres:password@localhost/trading_platform
   - FYERS_CLIENT_ID: Your Fyers app client ID
   - FYERS_CLIENT_SECRET: Your Fyers app client secret
   - FYERS_REDIRECT_URI: http://localhost:8000/api/v1/fyers/auth/callback
   - KOTAK_CLIENT_ID/KOTAK_CLIENT_SECRET: (optional)
   - TOTAL_TRADING_CAPITAL: e.g., 1000000
   - RISK_PER_TRADE: e.g., 0.01 (1%)
   - CORS_ORIGINS: http://localhost:3000,http://127.0.0.1:3000

STEP 3: Install Node.js Dependencies (Frontend)
------------------------------------------------
1. Navigate to frontend: cd C:\app\frontend
2. Install: npm install
3. This will install: next@14, react@18, tailwindcss, etc.

STEP 4: Start the Application
------------------------------
OPTION A: Start separately (recommended for development)

Step 4a: Start Backend
1. Run: C:\app\start_backend.bat
2. Backend URL: http://localhost:8000
3. API Docs: http://localhost:8000/docs

Step 4b: Start Frontend (new terminal)
1. Run: cd C:\app\frontend
2. Run: npm run dev
3. Web URL: http://localhost:3000

OPTION B: Start both with one command
- Manual setup required as they need different environments

STEP 5: Verify Application is Running
--------------------------------------
Backend (http://localhost:8000):
- "/" - Root endpoint: API status, version, modules
- "/health" - Health check with database connectivity
- "/info" - Application configuration
- "/docs" - Swagger UI API documentation

Frontend (http://localhost:3000):
- Dashboard with live charts
- Options chain table
- Execution ticket
- AI signal display
- Market breadth widgets

STEP 6: Test Basic Functionality
---------------------------------
1. Open browser to http://localhost:8000/docs
2. Try the /health endpoint - should return database status
3. Try the / endpoint - should return API info
4. Open http://localhost:3000 to see the trading interface
5. The frontend will automatically proxy API calls to localhost:8000

TROUBLESHOOTING
---------------
• If backend fails: Check .env file and PostgreSQL status
• If frontend fails: Run "npm run build" first, check node version
• WebSocket issues: wsproto==0.24.0 is critical - ensure it's installed
• CORS errors: Verify CORS_ORIGINS in .env includes http://localhost:3000
• Database errors: Ensure PostgreSQL is running or comment out DB dependency

FILES CREATED:
- C:\app\start_backend.bat  - Backend startup script
- C:\app\start_frontend.bat - Frontend startup script
- C\app\.env.example        - Environment variable template

ENJOY YOUR TRADING PLATFORM!
=============================================================================