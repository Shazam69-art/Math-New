\from flask import Flask, render_template_string, request, jsonify, make_response, session, redirect
import os
import base64
import json
from openai import OpenAI
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import threading


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Enable sessions for login persistence
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
from flask_session import Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/flask_sessions'
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
Session(app)

# Define log file path - will be created automatically
LOG_FILE = '/tmp/login_logs.json'

# ============ NGROK FIX ============
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ============ HTML TEMPLATES ============
LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Math OCR Analyzer - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
        }
        body {
            background: #ffffff;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .login-container {
            width: 100%;
            max-width: 400px;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
            padding: 40px;
            text-align: center;
        }
        .login-header {
            margin-bottom: 30px;
        }
        .login-header h1 {
            font-size: 24px;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 8px;
        }
        .login-header p {
            color: #6b7280;
            font-size: 14px;
        }
        .login-form {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-bottom: 24px;
        }
        .input-group {
            position: relative;
            text-align: left;
        }
        .input-group label {
            display: block;
            margin-bottom: 6px;
            color: #374151;
            font-size: 14px;
            font-weight: 500;
        }
        .input-group input {
            width: 100%;
            padding: 12px 16px 12px 40px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-size: 14px;
            transition: border 0.2s;
        }
        .input-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .input-group i {
            position: absolute;
            left: 12px;
            top: 36px;
            color: #9ca3af;
            font-size: 16px;
        }
        .login-buttons {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .btn {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn-google {
            background: #ffffff;
            color: #374151;
            border: 1px solid #d1d5db;
        }
        .btn-google:hover {
            background: #f9fafb;
        }
        .btn-apple {
            background: #000000;
            color: #ffffff;
        }
        .btn-apple:hover {
            background: #1f2937;
        }
        .login-submit {
            background: #667eea;
            color: white;
            margin-top: 10px;
        }
        .login-submit:hover {
            background: #5a6cd4;
        }
        .toggle-container {
            margin-top: 20px;
            text-align: center;
        }
        .toggle {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: #6b7280;
            font-size: 14px;
        }
        .toggle-switch {
            width: 40px;
            height: 20px;
            background: #e5e7eb;
            border-radius: 10px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        }
        .toggle-switch.active {
            background: #10b981;
        }
        .toggle-switch::after {
            content: '';
            width: 16px;
            height: 16px;
            background: #ffffff;
            border-radius: 50%;
            position: absolute;
            top: 2px;
            left: 2px;
            transition: transform 0.2s;
        }
        .toggle-switch.active::after {
            transform: translateX(20px);
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>📐 Math OCR Analyzer</h1>
            <p>Log in to analyze your math problems</p>
        </div>
        <form class="login-form" onsubmit="event.preventDefault(); loginWithCredentials();">
            <div class="input-group">
                <label for="username">Username</label>
                <i>👤</i>
                <input type="text" id="username" placeholder="Enter your username" required>
            </div>
            <div class="input-group">
                <label for="password">Password</label>
                <i>🔒</i>
                <input type="password" id="password" placeholder="Enter your password" required>
            </div>
            <button type="submit" class="btn login-submit">Login</button>
        </form>
        <div style="margin: 15px 0; text-align: center; color: #6b7280; font-size: 14px;">OR</div>
        <div class="login-buttons">
            <button class="btn btn-google" onclick="loginWithGoogle()">
                <span>G</span>
                Continue with Google
            </button>
            <button class="btn btn-apple" onclick="loginWithApple()" id="appleBtn" style="display: none;">
                <span>🍎</span>
                Continue with Apple
            </button>
        </div>
        <div class="toggle-container">
            <span class="toggle">
                Enable Apple Login
                <div class="toggle-switch" id="appleToggle"></div>
            </span>
        </div>
    </div>
    <script>
        const appleToggle = document.getElementById('appleToggle');
        const appleBtn = document.getElementById('appleBtn');

        appleToggle.addEventListener('click', () => {
            appleToggle.classList.toggle('active');
            appleBtn.style.display = appleToggle.classList.contains('active') ? 'flex' : 'none';
        });

        function loginWithCredentials() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    if (!username) {
        alert('Please enter a username');
        return;
    }
    
    fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            username: username,
            password: password
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const emailPrefix = username.split('@')[0] || 'User';
            localStorage.setItem('userEmailPrefix', emailPrefix);
            window.location.href = '/main';
        } else {
            alert('Login failed: ' + data.message);
        }
    });
}

function loginWithGoogle() {
    const username = document.getElementById('username').value || 'google_user';
    fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, provider: 'google'})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            localStorage.setItem('userEmailPrefix', username);
            window.location.href = '/main';
        }
    });
}

function loginWithApple() {
    const username = document.getElementById('username').value || 'apple_user';
    fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, provider: 'apple'})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            localStorage.setItem('userEmailPrefix', username);
            window.location.href = '/main';
        }
    });
}
        
    </script>
</body>
</html>
'''

MAIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Math OCR Analyzer</title>
    <script>
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                processEscapes: true,
                processEnvironments: true
            },
            options: {
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
            },
            startup: {
                pageReady: () => {
                    return MathJax.startup.defaultPageReady();
                }
            }
        };
    </script>
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
        }
        body {
            background: #ffffff;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            width: 95%;
            max-width: 1200px;
            min-height: 95vh;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #e5e7eb;
        }
        .header h1 {
            font-size: 20px;
            font-weight: 700;
            color: #1f2937;
        }
        .welcome-message {
            font-size: 16px;
            color: #6b7280;
            margin-left: 10px;
        }
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
            background: #ffffff;
        }
        .message {
            margin-bottom: 20px;
            animation: fadeIn 0.3s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.system {
            background: #f3f4f6;
            padding: 15px 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .file-upload {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 10px 0;
        }
        .file-tag {
            background: #f3f4f6;
            color: #374151;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .file-tag .remove {
            cursor: pointer;
            font-weight: bold;
            color: #ef4444;
        }
        .input-area {
            padding: 20px 30px;
            background: #ffffff;
            border-top: 1px solid #e5e7eb;
            display: flex;
            gap: 10px;
            align-items: center;
            justify-content: center;
        }
        .input-wrapper {
            flex: 1;
            display: flex;
            gap: 10px;
            justify-content: center;
        }
        input[type="file"] {
            display: none;
        }
        .upload-btn {
            background: #f3f4f6;
            color: #374151;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
            border: 1px solid #d1d5db;
        }
        .upload-btn:hover {
            background: #e5e7eb;
        }
        .start-btn {
            background: #667eea;
            color: white;
            padding: 12px 30px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 15px;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }
        .start-btn:hover {
            background: #5a6cd4;
        }
        .start-btn:disabled {
            background: #cbd5e1;
            cursor: not-allowed;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f4f6;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .question-dropdown {
            background: #ffffff;
            margin: 15px 0;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }
        .question-header {
            background: #f9fafb;
            color: #1f2937;
            padding: 15px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
            user-select: none;
            font-weight: 600;
        }
        .question-header:hover {
            background: #f3f4f6;
        }
        .dropdown-arrow {
            font-size: 18px;
            transition: transform 0.2s;
        }
        .dropdown-arrow.open {
            transform: rotate(180deg);
        }
        .question-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }
        .question-content.open {
            max-height: 5000px;
            transition: max-height 0.5s ease-in;
        }
        .question-inner {
            padding: 25px;
            background: #ffffff;
        }
        .question-text {
            color: #1f2937;
            font-size: 17px;
            margin-bottom: 20px;
            line-height: 1.8;
            padding: 15px;
            background: #f9fafb;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }
        .section-title {
            color: #6b7280;
            font-size: 15px;
            font-weight: 600;
            text-transform: uppercase;
            margin: 20px 0 15px 0;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .section-title::before {
            content: '';
            width: 3px;
            height: 16px;
            background: #667eea;
            border-radius: 2px;
        }
        .student-solution {
            background: #fef3c7;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            white-space: pre-wrap;
            line-height: 1.9;
            font-size: 16px;
            border: 1px solid #fde68a;
        }
        .error-analysis {
            background: #fee2e2;
            padding: 20px;
            border-radius: 8px;
            color: #991b1b;
            margin-bottom: 20px;
            font-weight: 500;
            line-height: 1.9;
            font-size: 16px;
            border: 1px solid #fecaca;
        }
        .correct-solution {
            background: #d1fae5;
            padding: 20px;
            border-radius: 8px;
            line-height: 1.9;
            font-size: 16px;
            border: 1px solid #a7f3d0;
            margin-bottom: 20px;
        }
        .correct-solution p {
            margin-bottom: 10px;
        }
        .practice-paper {
            background: #ffffff;
            padding: 25px;
            margin: 25px 0;
            border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
            border: 1px solid #e5e7eb;
        }
        .practice-header {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #e5e7eb;
        }
        .practice-title {
            font-size: 18px;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 5px;
        }
        .practice-subtitle {
            color: #6b7280;
            font-size: 14px;
        }
        .practice-question {
            padding: 15px 0;
            border-bottom: 1px solid #f3f4f6;
            margin-bottom: 15px;
        }
        .practice-question:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        .practice-question-number {
            color: #667eea;
            font-weight: 700;
            font-size: 16px;
            margin-bottom: 10px;
            display: inline-block;
        }
        .practice-question-text {
            color: #1f2937;
            font-size: 16px;
            line-height: 1.8;
            padding-left: 5px;
            margin-bottom: 15px;
        }
        .practice-footer {
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            color: #6b7280;
            font-size: 13px;
            font-weight: 500;
        }
        .confirm-prompt {
            background: #fef3c7;
            padding: 18px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #f59e0b;
        }
        .confirm-buttons {
            display: flex;
            gap: 10px;
            margin-top: 12px;
        }
        .btn-yes {
            background: #10b981;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            border: none;
            cursor: pointer;
        }
        .btn-yes:hover {
            background: #059669;
        }
        .btn-no {
            background: #ef4444;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            border: none;
            cursor: pointer;
        }
        .btn-no:hover {
            background: #dc2626;
        }
        .typing-cursor {
            display: inline-block;
            width: 2px;
            height: 1em;
            background: #667eea;
            margin-left: 2px;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }
        .MathJax {
            font-size: 1.2em !important;
        }
        mjx-container {
            display: inline-block;
            margin: 0 2px;
        }
        .download-btn {
            background: #3b82f6;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            margin-top: 20px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .download-btn:hover {
            background: #2563eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📐 Math OCR Analysis</h1>
            <div class="welcome-message" id="welcomeMessage"></div>
        </div>
        <div class="chat-area" id="chatArea">
            <div class="message system">
                <strong>Welcome to Math OCR Analyzer!</strong><br>
                Upload your question and answer files, then click "Start Analysis" to begin.
            </div>
        </div>
        <div class="input-area">
            <div class="input-wrapper">
                <label class="upload-btn">
                    📎 Upload Files
                    <input type="file" id="fileInput" multiple accept="image/*,.pdf">
                </label>
                <button class="btn start-btn" id="startBtn" onclick="startAnalysis()" disabled>
                    Start Analysis
                </button>
            </div>
        </div>
    </div>
    <script>
        // Global variables
        let uploadedFiles = [];
        let isAnalyzing = false;
        let analysisResult = null;

        // Set welcome message from localStorage
        const emailPrefix = localStorage.getItem('userEmailPrefix') || 'User';
        document.getElementById('welcomeMessage').textContent = `Welcome, ${emailPrefix}!`;

        // File upload handling
        document.getElementById('fileInput').addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            files.forEach(file => {
                if (!uploadedFiles.find(f => f.name === file.name)) {
                    uploadedFiles.push(file);
                }
            });
            updateFileDisplay();
            document.getElementById('startBtn').disabled = uploadedFiles.length === 0;
            e.target.value = '';
        });

        function updateFileDisplay() {
            const chatArea = document.getElementById('chatArea');
            const existingFileMsg = document.getElementById('fileMessage');
            if (existingFileMsg) existingFileMsg.remove();

            if (uploadedFiles.length > 0) {
                const fileMsg = document.createElement('div');
                fileMsg.id = 'fileMessage';
                fileMsg.className = 'message user';
                fileMsg.innerHTML = '<strong>Uploaded Files:</strong><div class="file-upload">' +
                    uploadedFiles.map((f, i) => `
                        <div class="file-tag">
                            ${f.name}
                            <span class="remove" onclick="removeFile(${i})">✕</span>
                        </div>
                    `).join('') + '</div>';
                chatArea.appendChild(fileMsg);
                chatArea.scrollTop = chatArea.scrollHeight;
            }
        }

        function removeFile(index) {
            uploadedFiles.splice(index, 1);
            updateFileDisplay();
            document.getElementById('startBtn').disabled = uploadedFiles.length === 0;
        }

        function renderMath(element) {
            if (window.MathJax && window.MathJax.typesetPromise) {
                window.MathJax.typesetPromise([element]).catch((err) => console.log('MathJax render error:', err));
            }
        }

        function toggleDropdown(index) {
            const content = document.getElementById(`question-content-${index}`);
            const arrow = document.getElementById(`arrow-${index}`);

            if (content.classList.contains('open')) {
                content.classList.remove('open');
                arrow.classList.remove('open');
            } else {
                content.classList.add('open');
                arrow.classList.add('open');
            }
        }

        async function typeText(element, text, speed = 5) {
            let i = 0;
            const chunks = text.split(/(\$\$[\s\S]*?\$\$|\$[^\$]+?\$|<br>)/);

            for (const chunk of chunks) {
                if (chunk.startsWith('$$') || chunk.startsWith('$')) {
                    element.innerHTML += chunk;
                    renderMath(element);
                } else if (chunk === '<br>') {
                    element.innerHTML += chunk;
                } else {
                    for (const char of chunk) {
                        element.innerHTML += char;
                        element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        await new Promise(resolve => setTimeout(resolve, speed));
                    }
                }
            }
        }

        async function startAnalysis() {
            if (uploadedFiles.length === 0 || isAnalyzing) return;

            isAnalyzing = true;
            const chatArea = document.getElementById('chatArea');
            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'message system';
            loadingMsg.innerHTML = '<div class="loading"></div> Analyzing your files...';
            chatArea.appendChild(loadingMsg);
            chatArea.scrollTop = chatArea.scrollHeight;

            document.getElementById('startBtn').disabled = true;

            const formData = new FormData();
            uploadedFiles.forEach(file => formData.append('files', file));

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const result = await response.json();
                loadingMsg.remove();

                if (result.error) {
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'message system';
                    errorMsg.innerHTML = `<strong>Error:</strong> ${result.error}`;
                    chatArea.appendChild(errorMsg);
                } else {
                    analysisResult = result; // Store the result globally
                    await displayAnalysisWithTyping(result);
                }
            } catch (error) {
                loadingMsg.remove();
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message system';
                errorMsg.innerHTML = `<strong>Error:</strong> ${error.message}`;
                chatArea.appendChild(errorMsg);
                console.error('Analysis error:', error);
            }

            chatArea.scrollTop = chatArea.scrollHeight;
            document.getElementById('startBtn').disabled = false;
            isAnalyzing = false;
        }

        async function displayAnalysisWithTyping(result) {
            const chatArea = document.getElementById('chatArea');

            for (let i = 0; i < result.questions.length; i++) {
                const q = result.questions[i];

                const qBlock = document.createElement('div');
                qBlock.className = 'question-dropdown';
                qBlock.innerHTML = `
                    <div class="question-header" onclick="toggleDropdown(${i})">
                        <div>
                            <span>📝 Question ${q.number}</span>
                        </div>
                        <span class="dropdown-arrow" id="arrow-${i}">▼</span>
                    </div>
                    <div class="question-content" id="question-content-${i}">
                        <div class="question-inner">
                            <div class="question-text" id="q-text-${i}"></div>
                            <div class="section-title">Student's Solution</div>
                            <div class="student-solution" id="q-student-${i}"></div>
                            <div class="section-title">Error Analysis</div>
                            <div class="error-analysis" id="q-error-${i}"></div>
                            <div class="section-title">Correct Solution</div>
                            <div class="correct-solution" id="q-correct-${i}"></div>
                        </div>
                    </div>
                `;
                chatArea.appendChild(qBlock);

                // Open dropdown automatically
                document.getElementById(`question-content-${i}`).classList.add('open');
                document.getElementById(`arrow-${i}`).classList.add('open');

                // Type each section with improved formatting
                await typeText(document.getElementById(`q-text-${i}`), q.question, 3);
                await typeText(document.getElementById(`q-student-${i}`), q.student_original, 3);
                await typeText(document.getElementById(`q-error-${i}`), q.error, 3);

                // Format correct solution with line breaks
                const correctSolutionElement = document.getElementById(`q-correct-${i}`);
                const steps = q.correct_solution.split('<br>').filter(step => step.trim() !== '');
                for (const step of steps) {
                    const p = document.createElement('p');
                    correctSolutionElement.appendChild(p);
                    await typeText(p, step, 3);
                }
            }

            // Show confirmation prompt
            const confirmMsg = document.createElement('div');
            confirmMsg.className = 'confirm-prompt';
            confirmMsg.innerHTML = `
                <strong>Analysis Complete!</strong><br>
                Would you like to generate a practice paper for the questions with mistakes?
                <div class="confirm-buttons">
                    <button class="btn-yes" onclick="generatePractice()">Yes, Generate</button>
                    <button class="btn btn-no" onclick="skipPractice()">No, Thanks</button>
                </div>
            `;
            chatArea.appendChild(confirmMsg);
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        async function generatePractice() {
            if (!analysisResult) {
                const chatArea = document.getElementById('chatArea');
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message system';
                errorMsg.innerHTML = '<strong>Error:</strong> No analysis result found. Please run the analysis first.';
                chatArea.appendChild(errorMsg);
                return;
            }

            const chatArea = document.getElementById('chatArea');
            const confirmPrompt = document.querySelector('.confirm-prompt');
            if (confirmPrompt) confirmPrompt.remove();

            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'message system';
            loadingMsg.innerHTML = '<div class="loading"></div> Generating practice paper...';
            chatArea.appendChild(loadingMsg);

            try {
                console.log('Sending to /generate_practice:', analysisResult); // Debug log

                const response = await fetch('/generate_practice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ analysis: analysisResult })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(`Server error: ${response.status}. ${errorData.error || ''}`);
                }

                const result = await response.json();
                loadingMsg.remove();

                if (result.error) {
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'message system';
                    errorMsg.innerHTML = `<strong>Error:</strong> ${result.error}`;
                    chatArea.appendChild(errorMsg);
                } else if (result.practice_questions && result.practice_questions.length > 0) {
                    const practiceBlock = document.createElement('div');
                    practiceBlock.className = 'practice-paper';
                    practiceBlock.id = 'practice-paper';
                    practiceBlock.innerHTML = `
                        <div class="practice-header">
                            <div class="practice-title">📝 Practice Paper</div>
                            <div class="practice-subtitle">Practice questions based on areas needing improvement</div>
                        </div>
                        <div id="practice-questions-container"></div>
                        <div class="practice-footer">
                            <button class="download-btn" onclick="downloadPracticePaper()">
                                📥 Download as PDF
                            </button>
                        </div>
                    `;
                    chatArea.appendChild(practiceBlock);

                    const container = document.getElementById('practice-questions-container');

                    for (const pq of result.practice_questions) {
                        const pqDiv = document.createElement('div');
                        pqDiv.className = 'practice-question';
                        pqDiv.innerHTML = `
                            <div class="practice-question-number">Question ${pq.number}</div>
                            <div class="practice-question-text" id="practice-q-${pq.number}"></div>
                        `;
                        container.appendChild(pqDiv);

                        await typeText(document.getElementById(`practice-q-${pq.number}`), pq.question, 3);
                    }
                } else {
                    const noMistakes = document.createElement('div');
                    noMistakes.className = 'message system';
                    noMistakes.innerHTML = '<strong>Great job!</strong> No mistakes found, so no practice paper needed.';
                    chatArea.appendChild(noMistakes);
                }

                chatArea.scrollTop = chatArea.scrollHeight;
            } catch (error) {
                loadingMsg.remove();
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message system';
                errorMsg.innerHTML = `<strong>Error:</strong> ${error.message}`;
                chatArea.appendChild(errorMsg);
                console.error('Generate practice error:', error);
            }
        }

        function skipPractice() {
            const confirmPrompt = document.querySelector('.confirm-prompt');
            if (confirmPrompt) confirmPrompt.remove();
        }

        async function downloadPracticePaper() {
            const practicePaper = document.getElementById('practice-paper');
            const pdf = new jsPDF('p', 'mm', 'a4');
            const imgData = await html2canvas(practicePaper, { scale: 2 });
            const imgWidth = pdf.internal.pageSize.getWidth();
            const imgHeight = (imgData.height * imgWidth) / imgData.width;

            pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight);
            pdf.save('practice-paper.pdf');
        }
    </script>
</body>
</html>
'''

# ============ ROUTES ============
@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/main')
def main():
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect('/')  # Send back to login if not logged in
    return render_template_string(MAIN_HTML)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured.'}), 500

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files uploaded'}), 400

        client = OpenAI(api_key=api_key)
        file_contents = []

        for file in files:
            if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                file.seek(0)
                encoded = base64.b64encode(file.read()).decode('utf-8')
                file_contents.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}
                })
            elif file.filename.lower().endswith('.pdf'):
                file_contents.append({
                    "type": "text",
                    "text": f"[PDF file: {file.filename} - Content extraction not implemented in this demo]"
                })

        prompt = """
        Extract and analyze math problems from the uploaded files.

        CRITICAL INSTRUCTIONS:
        1. Use the EXACT question numbers from the images (e.g., if image shows "Q.7", use "7" as the number)
        2. Format ALL mathematical expressions using LaTeX with $ for inline math and $$ for display math
        3. For student_original: Extract VERBATIM what the student wrote, but format math with LaTeX
        4. Only flag REAL errors - mistakes include:
           - Questions left blank/unanswered
           - Partially correct solutions
           - Completely incorrect solutions
           - Mathematical errors in calculations or reasoning
        5. If solution is fully correct, set error to "No error - solution is correct"

        Return a JSON array with this exact structure:
        [{
          "number": "exact_question_number_from_image",
          "question": "question text with $LaTeX$ formatting",
          "student_original": "Student's work VERBATIM with ALL math wrapped in $LaTeX$",
          "error": "Detailed error description with $LaTeX$ if needed, or 'No error - solution is correct'",
          "correct_solution": "Complete step-by-step solution with $LaTeX$ formatting. Each step on a new line separated by <br>"
        }]
        """

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + file_contents
            }],
            max_completion_tokens=9000,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()
        if result_text.startswith('```json'):
            result_text = result_text[7:]
        if result_text.endswith('```'):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        try:
            questions = json.loads(result_text)
            return jsonify({'questions': questions})
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Problematic text: {result_text}")
            return jsonify({'error': f'Failed to parse OpenAI response: {str(e)}'}), 500

    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# ============ LOGIN API ============
@app.route('/api/login', methods=['POST'])
def handle_login():
    """Save login to file and create session"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        
        if not username:
            return jsonify({'success': False, 'message': 'Username required'}), 400
        
        # 1. Create user session (persists on Render)
        session['user'] = username
        session['logged_in'] = True
        session['login_time'] = datetime.utcnow().isoformat()
        
        # 2. CAPTURE REQUEST DATA HERE (before starting thread)
        ip_address = request.remote_addr or 'Unknown'
        user_agent = request.headers.get('User-Agent', 'Unknown')[:100]
        current_time = datetime.utcnow().isoformat()
        
        # 3. Save to JSON file (in background thread)
        def save_login(username, ip_address, user_agent, current_time):
            try:
                login_data = {
                    'username': username,
                    'timestamp': current_time,
                    'ip': ip_address,
                    'user_agent': user_agent
                }
                
                # Load existing logins or create new file
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'r') as f:
                        try:
                            logins = json.load(f)
                        except:
                            logins = []
                else:
                    logins = []
                
                # Add new login
                logins.append(login_data)
                
                # Save back to file
                with open(LOG_FILE, 'w') as f:
                    json.dump(logins, f, indent=2)
                
                print(f"✅ Login saved to {LOG_FILE}: {username}")
            except Exception as e:
                print(f"⚠️ File save failed: {e}")
        
        # Run in background thread with captured data
        threading.Thread(
            target=save_login, 
            args=(username, ip_address, user_agent, current_time),
            daemon=True
        ).start()
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': username
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
        
        # Run in background thread
        threading.Thread(target=save_login, daemon=True).start()
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': username
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============ VIEW LOGS ============
@app.route('/view-logs')
def view_logs():
    """View all saved logins"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logins = json.load(f)
        
        # Create HTML table
        html = '''
        <!DOCTYPE html>
        <html>
        <head><title>Login Logs</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #667eea; color: white; }
            tr:nth-child(even) { background-color: #f2f2f2; }
        </style>
        </head>
        <body>
            <h1>🔐 Login Logs (Total: ''' + str(len(logins)) + ''')</h1>
            <table>
                <tr><th>#</th><th>Username</th><th>Timestamp</th><th>IP Address</th><th>User Agent</th></tr>
        '''
        
        for i, login in enumerate(reversed(logins), 1):
            html += f'''
                <tr>
                    <td>{i}</td>
                    <td><strong>{login['username']}</strong></td>
                    <td>{login['timestamp']}</td>
                    <td>{login['ip']}</td>
                    <td>{login['user_agent'][:50]}...</td>
                </tr>
            '''
        
        html += '''
            </table>
            <p style="margin-top: 20px;">
                <a href="/download-logs">📥 Download JSON</a> | 
                <a href="/">🏠 Back to Login</a>
            </p>
        </body>
        </html>
        '''
        return html
    return "<h1>No logins yet</h1>"

# ============ DOWNLOAD LOGS ============
@app.route('/download-logs')
def download_logs():
    """Download logs as JSON file"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            data = f.read()
        response = make_response(data)
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = 'attachment; filename=math_ocr_logins.json'
        return response
    return "No logins yet", 404

# ============ TEST LOGIN ============
@app.route('/test-login-page')
def test_login_page():
    """Simple page to test login"""
    return '''
    <html><body style="padding: 40px;">
    <h2>Test Login System</h2>
    <input id="username" placeholder="Enter username" value="test_user">
    <button onclick="login()">Test Login</button>
    <div id="result" style="margin-top: 20px;"></div>
    <script>
    async function login() {
        const username = document.getElementById('username').value;
        const result = document.getElementById('result');
        result.innerHTML = 'Logging in...';
        
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: username})
        });
        
        const data = await response.json();
        if (data.success) {
            result.innerHTML = `✅ Login successful!<br>
                                User: ${data.user}<br>
                                <a href="/view-logs">View All Logs</a>`;
        } else {
            result.innerHTML = `❌ Failed: ${data.message}`;
        }
    }
    </script>
    </body></html>
    '''

@app.route('/generate_practice', methods=['POST'])
def generate_practice():
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured.'}), 500

        data = request.json
        if not data or 'analysis' not in data:
            return jsonify({'error': 'No analysis data provided.'}), 400

        analysis = data.get('analysis', {})
        questions = analysis.get('questions', [])

        if not questions:
            return jsonify({'error': 'No questions found in analysis data.'}), 400

        error_questions = [q for q in questions if 'no error' not in q.get('error', '').lower()]

        if not error_questions:
            return jsonify({'practice_questions': []})

        client = OpenAI(api_key=api_key)

        prompt = f"""
        Generate practice questions for these problems where students made mistakes:

        {json.dumps(error_questions, indent=2)}

        CRITICAL INSTRUCTIONS:
        1. Use the EXACT SAME question numbers as the original questions
        2. Create MODIFIED versions of the questions (not identical, but similar concept)
        3. Target the specific errors or concepts the student struggled with
        4. Format ALL math using LaTeX: $x^2$, $\\frac{{a}}{{b}}$, $\\int$, etc.

        Return a JSON array with this structure:
        [{{"number": "exact_original_question_number", "question": "modified question with $LaTeX$ formatting targeting same concept"}}]
        """

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000,
            temperature=0.7
        )

        result_text = response.choices[0].message.content.strip()

        if result_text.startswith('```json'):
            result_text = result_text[7:]
        if result_text.endswith('```'):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        try:
            practice_questions = json.loads(result_text)
            return jsonify({'practice_questions': practice_questions})
        except json.JSONDecodeError as e:
            print(f"JSON decode error in generate_practice: {e}")
            print(f"Problematic text: {result_text}")
            return jsonify({'error': f'Failed to parse practice questions: {str(e)}'}), 500

    except Exception as e:
        print(f"Generate practice error: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 Math OCR Analyzer Starting...")
    print("=" * 60)
    if not os.getenv('OPENAI_API_KEY'):
        print("\n⚠️  WARNING: OpenAI API key not found!")
        print("   Please set the OPENAI_API_KEY environment variable.\n")
    else:
        print("\n✅ API Key configured")
    print("\n📱 Access the app at: http://localhost:5000")
    print("📱 ngrok URL will also work once you run ngrok!")
    print("=" * 60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
