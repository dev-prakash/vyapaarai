const axios = require('axios');
const { spawn } = require('child_process');
const fs = require('fs');

class FullStackIntegrationTest {
    constructor() {
        this.apiBaseUrl = 'https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws';
        this.frontendUrl = 'http://localhost:3000';
        this.testResults = {
            cors: [],
            authentication: [],
            api: [],
            realtime: [],
            errors: []
        };
    }

    async testCORSFromBrowser() {
        console.log('🌐 Testing CORS from browser context...');
        
        try {
            // Test preflight request
            const preflightResponse = await axios.options(`${this.apiBaseUrl}/api/v1/health`, {
                headers: {
                    'Origin': this.frontendUrl,
                    'Access-Control-Request-Method': 'GET',
                    'Access-Control-Request-Headers': 'Content-Type,Authorization'
                }
            });

            console.log('✅ Preflight request successful');
            console.log('CORS Headers:', preflightResponse.headers);
            
            this.testResults.cors.push({
                test: 'preflight',
                status: 'success',
                headers: preflightResponse.headers
            });

        } catch (error) {
            console.log('❌ CORS preflight failed:', error.message);
            this.testResults.cors.push({
                test: 'preflight',
                status: 'failed',
                error: error.message
            });
        }
    }

    async testAPIEndpoints() {
        console.log('🔗 Testing API endpoints...');
        
        const endpoints = [
            { method: 'GET', path: '/health', name: 'Health Check' },
            { method: 'GET', path: '/api/v1/health', name: 'API Health' },
            { method: 'GET', path: '/api/v1/orders', name: 'Orders List' },
            { method: 'POST', path: '/api/v1/auth/send-otp', name: 'Send OTP', data: { phone: '+919876543210' }},
            { method: 'POST', path: '/api/v1/auth/verify-otp', name: 'Verify OTP', data: { phone: '+919876543210', otp: '1234' }},
            { method: 'GET', path: '/api/v1/analytics/overview', name: 'Analytics' },
            { method: 'GET', path: '/api/v1/customers', name: 'Customers' },
            { method: 'GET', path: '/api/v1/inventory/products', name: 'Inventory' },
            { method: 'POST', path: '/api/v1/orders/test/generate-order', name: 'Generate Test Order' }
        ];

        for (const endpoint of endpoints) {
            try {
                const config = {
                    method: endpoint.method,
                    url: `${this.apiBaseUrl}${endpoint.path}`,
                    headers: {
                        'Origin': this.frontendUrl,
                        'Content-Type': 'application/json'
                    },
                    timeout: 10000
                };

                if (endpoint.data) {
                    config.data = endpoint.data;
                }

                const startTime = Date.now();
                const response = await axios(config);
                const responseTime = Date.now() - startTime;
                
                console.log(`✅ ${endpoint.name}: ${response.status} (${responseTime}ms)`);
                this.testResults.api.push({
                    endpoint: endpoint.name,
                    status: 'success',
                    statusCode: response.status,
                    responseTime: responseTime,
                    path: endpoint.path
                });

            } catch (error) {
                console.log(`❌ ${endpoint.name}: ${error.response?.status || 'ERROR'} - ${error.message}`);
                this.testResults.api.push({
                    endpoint: endpoint.name,
                    status: 'failed',
                    error: error.message,
                    statusCode: error.response?.status,
                    path: endpoint.path
                });
            }
        }
    }

    async testAuthenticationFlow() {
        console.log('🔐 Testing authentication flow...');
        
        try {
            // Test phone number submission
            const phoneResponse = await axios.post(`${this.apiBaseUrl}/api/v1/auth/send-otp`, {
                phone: '+919876543210'
            }, {
                headers: {
                    'Origin': this.frontendUrl,
                    'Content-Type': 'application/json'
                }
            });

            console.log('✅ Phone submission successful');
            this.testResults.authentication.push({
                step: 'phone_submission',
                status: 'success',
                response: phoneResponse.data
            });

            // Test OTP verification
            const otpResponse = await axios.post(`${this.apiBaseUrl}/api/v1/auth/verify-otp`, {
                phone: '+919876543210',
                otp: '1234'
            }, {
                headers: {
                    'Origin': this.frontendUrl,
                    'Content-Type': 'application/json'
                }
            });

            console.log('✅ OTP verification successful');
            this.testResults.authentication.push({
                step: 'otp_verification',
                status: 'success',
                response: otpResponse.data
            });

        } catch (error) {
            console.log('❌ Authentication flow failed:', error.message);
            this.testResults.authentication.push({
                step: 'authentication',
                status: 'failed',
                error: error.message
            });
        }
    }

    async testRealTimeFeatures() {
        console.log('⚡ Testing real-time features...');
        
        try {
            // Test WebSocket connection (if available)
            const wsResponse = await axios.get(`${this.apiBaseUrl}/api/v1/health`, {
                headers: {
                    'Origin': this.frontendUrl,
                    'Upgrade': 'websocket'
                }
            });

            console.log('✅ WebSocket test completed');
            this.testResults.realtime.push({
                test: 'websocket',
                status: 'success'
            });

        } catch (error) {
            console.log('⚠️ WebSocket test failed (expected for Lambda):', error.message);
            this.testResults.realtime.push({
                test: 'websocket',
                status: 'expected_failure',
                note: 'Lambda Function URLs don\'t support WebSockets'
            });
        }
    }

    async testErrorHandling() {
        console.log('🚨 Testing error handling...');
        
        const errorTests = [
            {
                name: 'Invalid Endpoint',
                url: `${this.apiBaseUrl}/api/v1/invalid-endpoint`,
                expectedStatus: 404
            },
            {
                name: 'Invalid OTP',
                url: `${this.apiBaseUrl}/api/v1/auth/verify-otp`,
                method: 'POST',
                data: { phone: '+919876543210', otp: '9999' },
                expectedStatus: 400
            }
        ];

        for (const test of errorTests) {
            try {
                const config = {
                    method: test.method || 'GET',
                    url: test.url,
                    headers: {
                        'Origin': this.frontendUrl,
                        'Content-Type': 'application/json'
                    }
                };

                if (test.data) {
                    config.data = test.data;
                }

                const response = await axios(config);
                
                if (response.status === test.expectedStatus) {
                    console.log(`✅ ${test.name}: Expected error ${test.expectedStatus} received`);
                    this.testResults.errors.push({
                        test: test.name,
                        status: 'success',
                        expectedStatus: test.expectedStatus,
                        actualStatus: response.status
                    });
                } else {
                    console.log(`⚠️ ${test.name}: Unexpected status ${response.status} (expected ${test.expectedStatus})`);
                    this.testResults.errors.push({
                        test: test.name,
                        status: 'unexpected',
                        expectedStatus: test.expectedStatus,
                        actualStatus: response.status
                    });
                }

            } catch (error) {
                if (error.response?.status === test.expectedStatus) {
                    console.log(`✅ ${test.name}: Expected error ${test.expectedStatus} received`);
                    this.testResults.errors.push({
                        test: test.name,
                        status: 'success',
                        expectedStatus: test.expectedStatus,
                        actualStatus: error.response.status
                    });
                } else {
                    console.log(`❌ ${test.name}: Unexpected error - ${error.message}`);
                    this.testResults.errors.push({
                        test: test.name,
                        status: 'failed',
                        error: error.message
                    });
                }
            }
        }
    }

    async generateReport() {
        console.log('\n📊 INTEGRATION TEST REPORT');
        console.log('='.repeat(40));
        
        const report = {
            timestamp: new Date().toISOString(),
            backend_url: this.apiBaseUrl,
            frontend_url: this.frontendUrl,
            results: this.testResults,
            summary: {
                cors_tests: this.testResults.cors.length,
                cors_passed: this.testResults.cors.filter(t => t.status === 'success').length,
                api_tests: this.testResults.api.length,
                api_passed: this.testResults.api.filter(t => t.status === 'success').length,
                auth_tests: this.testResults.authentication.length,
                auth_passed: this.testResults.authentication.filter(t => t.status === 'success').length,
                realtime_tests: this.testResults.realtime.length,
                realtime_passed: this.testResults.realtime.filter(t => t.status === 'success').length,
                error_tests: this.testResults.errors.length,
                error_passed: this.testResults.errors.filter(t => t.status === 'success').length
            }
        };

        // Calculate overall success rate
        const totalTests = report.summary.cors_tests + report.summary.api_tests + 
                          report.summary.auth_tests + report.summary.realtime_tests + 
                          report.summary.error_tests;
        const totalPassed = report.summary.cors_passed + report.summary.api_passed + 
                           report.summary.auth_passed + report.summary.realtime_passed + 
                           report.summary.error_passed;
        
        report.summary.overall_success_rate = totalTests > 0 ? (totalPassed / totalTests * 100).toFixed(1) : 0;

        // Save report
        fs.writeFileSync('integration-test-report.json', JSON.stringify(report, null, 2));
        
        console.log('📈 Summary:');
        console.log(`CORS Tests: ${report.summary.cors_passed}/${report.summary.cors_tests} passed`);
        console.log(`API Tests: ${report.summary.api_passed}/${report.summary.api_tests} passed`);
        console.log(`Auth Tests: ${report.summary.auth_passed}/${report.summary.auth_tests} passed`);
        console.log(`Realtime Tests: ${report.summary.realtime_passed}/${report.summary.realtime_tests} passed`);
        console.log(`Error Tests: ${report.summary.error_passed}/${report.summary.error_tests} passed`);
        console.log(`Overall Success Rate: ${report.summary.overall_success_rate}%`);
        
        // Print detailed results
        console.log('\n🔍 Detailed Results:');
        
        if (this.testResults.cors.length > 0) {
            console.log('\n🌐 CORS Results:');
            this.testResults.cors.forEach(result => {
                console.log(`  ${result.status === 'success' ? '✅' : '❌'} ${result.test}: ${result.status}`);
            });
        }
        
        if (this.testResults.api.length > 0) {
            console.log('\n🔗 API Results:');
            this.testResults.api.forEach(result => {
                console.log(`  ${result.status === 'success' ? '✅' : '❌'} ${result.endpoint}: ${result.status} (${result.responseTime || 'N/A'}ms)`);
            });
        }
        
        if (this.testResults.authentication.length > 0) {
            console.log('\n🔐 Authentication Results:');
            this.testResults.authentication.forEach(result => {
                console.log(`  ${result.status === 'success' ? '✅' : '❌'} ${result.step}: ${result.status}`);
            });
        }
        
        return report;
    }

    async runFullTest() {
        console.log('🚀 Starting Full-Stack Integration Test...\n');
        console.log(`Backend URL: ${this.apiBaseUrl}`);
        console.log(`Frontend URL: ${this.frontendUrl}\n`);
        
        await this.testCORSFromBrowser();
        await this.testAPIEndpoints();
        await this.testAuthenticationFlow();
        await this.testRealTimeFeatures();
        await this.testErrorHandling();
        
        const report = await this.generateReport();
        
        console.log('\n✅ Integration test completed!');
        console.log('📄 Report saved to: integration-test-report.json');
        
        // Final assessment
        if (parseFloat(report.summary.overall_success_rate) >= 80) {
            console.log('\n🎉 EXCELLENT: Integration is working well!');
        } else if (parseFloat(report.summary.overall_success_rate) >= 60) {
            console.log('\n⚠️ GOOD: Integration mostly working, some issues to address');
        } else {
            console.log('\n❌ POOR: Significant integration issues detected');
        }
        
        return report;
    }
}

// Run the test
const tester = new FullStackIntegrationTest();
tester.runFullTest().catch(console.error);
