#!/usr/bin/env node

/**
 * TestSprite Readiness Check
 * Verifies that the application is ready for TestSprite testing
 */

const http = require('http');
const https = require('https');

const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function makeRequest(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    
    const req = client.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          data: data
        });
      });
    });
    
    req.on('error', reject);
    req.setTimeout(5000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

async function checkEndpoint(name, url, expectedStatus = 200) {
  try {
    log(`\n🔍 Testing ${name}...`, 'blue');
    const response = await makeRequest(url);
    
    if (response.statusCode === expectedStatus) {
      log(`✅ ${name}: OK (${response.statusCode})`, 'green');
      return true;
    } else {
      log(`❌ ${name}: Unexpected status ${response.statusCode}`, 'red');
      return false;
    }
  } catch (error) {
    log(`❌ ${name}: ${error.message}`, 'red');
    return false;
  }
}

async function checkFrontendFeatures() {
  log(`\n🌐 Testing Frontend Features...`, 'blue');
  
  try {
    const response = await makeRequest('http://localhost:3001');
    
    // Check if it's the React app
    if (response.data.includes('root') && response.data.includes('bundle.js')) {
      log(`✅ Frontend: React app is serving`, 'green');
      return true;
    } else {
      log(`❌ Frontend: Not serving React app`, 'red');
      return false;
    }
  } catch (error) {
    log(`❌ Frontend: ${error.message}`, 'red');
    return false;
  }
}

async function checkBackendAPI() {
  log(`\n🔧 Testing Backend API...`, 'blue');
  
  try {
    const response = await makeRequest('http://localhost:8001');
    const data = JSON.parse(response.data);
    
    if (data.message && data.message.includes('Nutrition App API')) {
      log(`✅ Backend API: Responding correctly`, 'green');
      return true;
    } else {
      log(`❌ Backend API: Unexpected response`, 'red');
      return false;
    }
  } catch (error) {
    log(`❌ Backend API: ${error.message}`, 'red');
    return false;
  }
}

async function main() {
  log(`${colors.bold}🧪 TestSprite Readiness Check${colors.reset}`, 'blue');
  log('=====================================', 'blue');
  
  const results = [];
  
  // Check frontend
  results.push(await checkEndpoint('Frontend (Port 3001)', 'http://localhost:3001'));
  results.push(await checkFrontendFeatures());
  
  // Check backend
  results.push(await checkEndpoint('Backend API (Port 8001)', 'http://localhost:8001'));
  results.push(await checkBackendAPI());
  
  // Check API documentation
  results.push(await checkEndpoint('API Documentation', 'http://localhost:8001/docs'));
  
  // Summary
  log(`\n📊 Test Results Summary:`, 'blue');
  log('========================', 'blue');
  
  const passed = results.filter(r => r).length;
  const total = results.length;
  
  if (passed === total) {
    log(`\n🎉 All tests passed! (${passed}/${total})`, 'green');
    log(`\n✅ Your application is ready for TestSprite testing!`, 'green');
    log(`\n📋 Next Steps:`, 'blue');
    log(`1. Visit https://www.testsprite.com/`, 'yellow');
    log(`2. Create a new test project`, 'yellow');
    log(`3. Use these URLs:`, 'yellow');
    log(`   - Frontend: http://localhost:3001`, 'yellow');
    log(`   - Backend: http://localhost:8001`, 'yellow');
    log(`4. Use test credentials: chatbotuser / testpass123`, 'yellow');
    log(`5. Follow the test plan in TESTSPRITE_TEST_PLAN.md`, 'yellow');
  } else {
    log(`\n❌ Some tests failed (${passed}/${total})`, 'red');
    log(`\n🔧 Please fix the issues before running TestSprite tests`, 'red');
  }
  
  log(`\n📄 Configuration files created:`, 'blue');
  log(`- testsprite-config.json (TestSprite configuration)`, 'yellow');
  log(`- TESTSPRITE_TEST_PLAN.md (Detailed test plan)`, 'yellow');
}

// Run the check
main().catch(error => {
  log(`\n💥 Error running readiness check: ${error.message}`, 'red');
  process.exit(1);
});
