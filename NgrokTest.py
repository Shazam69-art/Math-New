from flask import Flask, render_template_string, request, jsonify
import os
import base64
import json
from openai import OpenAI

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# ============ NGROK FIX ============
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
# ===================================

HTML_TEMPLATE = '''
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
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; font-weight: 600; }
        .header-buttons {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .btn-questions {
            background: white;
            color: #667eea;
        }
        .btn-questions:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .btn-answers {
            background: #fbbf24;
            color: #78350f;
        }
        .btn-answers:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(251,191,36,0.4); }
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
            background: #f8fafc;
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
            background: #e0e7ff;
            padding: 15px 20px;
            border-radius: 12px;
            border-left: 4px solid #667eea;
        }
        .message.user {
            background: white;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        /* Dropdown Question Styles */
        .question-dropdown {
            background: white;
            margin: 15px 0;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
            border: 2px solid #e2e8f0;
        }
        .question-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 18px 25px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s;
            user-select: none;
        }
        .question-header:hover {
            background: linear-gradient(135deg, #5568d3 0%, #6a3f91 100%);
        }
        .question-header-title {
            font-size: 18px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .dropdown-arrow {
            font-size: 20px;
            transition: transform 0.3s;
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
        }
        
        .question-text {
            color: #1e293b;
            font-size: 16px;
            margin-bottom: 20px;
            line-height: 1.8;
            padding: 15px;
            background: #f1f5f9;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .section-title {
            color: #64748b;
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            margin: 20px 0 12px 0;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title::before {
            content: '';
            width: 4px;
            height: 20px;
            background: #667eea;
            border-radius: 2px;
        }
        .student-solution {
            background: #fef3c7;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            white-space: pre-wrap;
            line-height: 2;
            border: 2px solid #fde68a;
        }
        .error-analysis {
            background: #fee2e2;
            padding: 20px;
            border-radius: 8px;
            color: #991b1b;
            margin-bottom: 20px;
            font-weight: 500;
            line-height: 1.8;
            border: 2px solid #fecaca;
        }
        .correct-solution {
            background: #d1fae5;
            padding: 20px;
            border-radius: 8px;
            line-height: 2.2;
            font-size: 15px;
            border: 2px solid #a7f3d0;
        }
        
        /* Practice Paper Styles */
        .practice-paper {
            background: white;
            padding: 30px;
            margin: 30px 0;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            border: 3px solid #7c3aed;
        }
        .practice-header {
            background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
            color: white;
            padding: 20px 30px;
            margin: -30px -30px 25px -30px;
            border-radius: 9px 9px 0 0;
        }
        .practice-title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        .practice-subtitle {
            font-size: 14px;
            opacity: 0.9;
        }
        .practice-question {
            padding: 20px 0;
            border-bottom: 2px solid #f3f4f6;
        }
        .practice-question:last-child {
            border-bottom: none;
        }
        .practice-question-number {
            color: #7c3aed;
            font-weight: 700;
            font-size: 18px;
            margin-bottom: 12px;
            display: inline-block;
            background: #ede9fe;
            padding: 5px 15px;
            border-radius: 20px;
        }
        .practice-question-text {
            color: #1e293b;
            font-size: 16px;
            line-height: 2;
            padding-left: 10px;
        }
        .practice-footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e2e8f0;
            text-align: center;
            color: #64748b;
            font-size: 14px;
            font-weight: 600;
        }
        
        .file-upload {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 10px 0;
        }
        .file-tag {
            background: #667eea;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .file-tag .remove { cursor: pointer; font-weight: bold; }
        .input-area {
            padding: 20px 30px;
            background: white;
            border-top: 2px solid #e2e8f0;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .input-wrapper {
            flex: 1;
            display: flex;
            gap: 10px;
        }
        input[type="file"] { display: none; }
        .upload-btn {
            background: #f1f5f9;
            color: #475569;
            padding: 12px 20px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            border: 2px solid #e2e8f0;
        }
        .upload-btn:hover { background: #e2e8f0; }
        .start-btn {
            background: #10b981;
            color: white;
            padding: 12px 30px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 15px;
        }
        .start-btn:hover { background: #059669; }
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
        .confirm-prompt {
            background: #fef3c7;
            padding: 20px;
            border-radius: 12px;
            margin: 20px 0;
            border-left: 5px solid #f59e0b;
        }
        .confirm-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .btn-yes {
            background: #10b981;
            color: white;
        }
        .btn-yes:hover { background: #059669; }
        .btn-no {
            background: #ef4444;
            color: white;
        }
        .btn-no:hover { background: #dc2626; }
        
        /* Typing cursor */
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
            font-size: 1.1em !important;
        }
        mjx-container {
            display: inline-block;
            margin: 0 2px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📐 Math OCR Analyzer</h1>
            <div class="header-buttons">
                <button class="btn btn-questions" onclick="showQuestions()">Questions</button>
                <button class="btn btn-answers" onclick="showAnswers()">Answers</button>
            </div>
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
        let uploadedFiles = [];
        let currentView = 'questions';
        let analysisResult = null;
        let isAnalyzing = false;

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
            formData.append('view', currentView);

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                loadingMsg.remove();

                if (result.error) {
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'message system';
                    errorMsg.innerHTML = `<strong>Error:</strong> ${result.error}`;
                    chatArea.appendChild(errorMsg);
                } else {
                    analysisResult = result;
                    await displayAnalysisWithTyping(result);
                }
            } catch (error) {
                loadingMsg.remove();
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message system';
                errorMsg.innerHTML = `<strong>Error:</strong> ${error.message}`;
                chatArea.appendChild(errorMsg);
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
                        <div class="question-header-title">
                            <span>📝</span>
                            <span>Question ${q.number}</span>
                        </div>
                        <span class="dropdown-arrow" id="arrow-${i}">▼</span>
                    </div>
                    <div class="question-content" id="question-content-${i}">
                        <div class="question-inner">
                            <div class="question-text" id="q-text-${i}"></div>
                            <div class="section-title">Student's Solution (Original)</div>
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

                // Type each section
                await typeText(document.getElementById(`q-text-${i}`), q.question, 3);
                await typeText(document.getElementById(`q-student-${i}`), q.student_original, 3);
                await typeText(document.getElementById(`q-error-${i}`), q.error, 3);
                await typeText(document.getElementById(`q-correct-${i}`), q.correct_solution, 3);
            }

            // Show confirmation prompt
            const confirmMsg = document.createElement('div');
            confirmMsg.className = 'confirm-prompt';
            confirmMsg.innerHTML = `
                <strong>Analysis Complete!</strong><br>
                Would you like to generate a practice paper for the questions with mistakes?
                <div class="confirm-buttons">
                    <button class="btn btn-yes" onclick="generatePractice()">Yes, Generate</button>
                    <button class="btn btn-no" onclick="skipPractice()">No, Thanks</button>
                </div>
            `;
            chatArea.appendChild(confirmMsg);
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        async function generatePractice() {
            const chatArea = document.getElementById('chatArea');
            const confirmPrompt = document.querySelector('.confirm-prompt');
            if (confirmPrompt) confirmPrompt.remove();

            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'message system';
            loadingMsg.innerHTML = '<div class="loading"></div> Generating practice paper...';
            chatArea.appendChild(loadingMsg);

            try {
                const response = await fetch('/generate_practice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ analysis: analysisResult })
                });

                const result = await response.json();
                loadingMsg.remove();

                if (result.practice_questions && result.practice_questions.length > 0) {
                    const practiceBlock = document.createElement('div');
                    practiceBlock.className = 'practice-paper';
                    practiceBlock.innerHTML = `
                        <div class="practice-header">
                            <div class="practice-title">📝 Practice Paper</div>
                            <div class="practice-subtitle">Practice questions based on areas needing improvement</div>
                        </div>
                        <div id="practice-questions-container"></div>
                        <div class="practice-footer">Generated by CAS Educations</div>
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
            }
        }

        function skipPractice() {
            const confirmPrompt = document.querySelector('.confirm-prompt');
            if (confirmPrompt) confirmPrompt.remove();
        }

        function showQuestions() {
            currentView = 'questions';
            document.querySelector('.btn-questions').style.opacity = '1';
            document.querySelector('.btn-answers').style.opacity = '0.7';
        }

        function showAnswers() {
            currentView = 'answers';
            document.querySelector('.btn-answers').style.opacity = '1';
            document.querySelector('.btn-questions').style.opacity = '0.7';
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        api_key = OPENAI_API_KEY
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.'})

        files = request.files.getlist('files')
        view = request.form.get('view', 'questions')

        if not files:
            return jsonify({'error': 'No files uploaded'})

        client = OpenAI(api_key=api_key)

        file_contents = []
        for file in files:
            if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
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

        prompt = f"""Extract and analyze math problems from the uploaded {"questions" if view == "questions" else "answers"}.

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
[{{
  "number": "exact_question_number_from_image",
  "question": "question text with $LaTeX$ formatting",
  "student_original": "Student's work VERBATIM with ALL math wrapped in $LaTeX$",
  "error": "Detailed error description with $LaTeX$ if needed, or 'No error - solution is correct'",
  "correct_solution": "Complete step-by-step solution with $LaTeX$ formatting. Each step on a new line separated by <br>"
}}]

LaTeX Examples:
- Fractions: $\\frac{{a}}{{b}}$ or $\\dfrac{{a}}{{b}}$
- Integrals: $\\int f(x)\\,dx$ or $\\displaystyle\\int f(x)\\,dx$
- Square roots: $\\sqrt{{x}}$ or $\\sqrt[n]{{x}}$
- Exponents: $x^2$ or $x^{{2n}}$
- Trigonometry: $\\sin x$, $\\cos x$, $\\tan x$, $\\sec x$
- Greek letters: $\\pi$, $\\theta$, $\\alpha$
- Inverse trig: $\\sin^{{-1}} x$ or $\\arcsin x$
- Limits: $\\lim_{{x\\to 0}}$

Rules:
- Use EXACT question numbers from the images
- student_original must be VERBATIM
- Flag blank/partial/incorrect solutions as errors
- In correct_solution, use <br> between steps
- Each step should be complete"""

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

        questions = json.loads(result_text)

        return jsonify({'questions': questions})

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/generate_practice', methods=['POST'])
def generate_practice():
    try:
        api_key = OPENAI_API_KEY
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.'})

        data = request.json
        analysis = data.get('analysis', {})
        questions = analysis.get('questions', [])

        # Filter questions with real errors (blank, partial, or incorrect)
        error_questions = [q for q in questions if 'no error' not in q.get('error', '').lower()]

        if not error_questions:
            return jsonify({'practice_questions': []})

        client = OpenAI(api_key=api_key)

        prompt = f"""Generate practice questions for these problems where students made mistakes:

{json.dumps(error_questions, indent=2)}

CRITICAL INSTRUCTIONS:
1. Use the EXACT SAME question numbers as the original questions
2. Create MODIFIED versions of the questions (not identical, but similar concept)
3. Target the specific errors or concepts the student struggled with
4. Format ALL math using LaTeX: $x^2$, $\\frac{{a}}{{b}}$, $\\int$, etc.

Return a JSON array with this structure:
[{{"number": "exact_original_question_number", "question": "modified question with $LaTeX$ formatting targeting same concept"}}]

Rules:
- Use EXACT question numbers from originals (e.g., if original was "7", use "7")
- Questions should be DIFFERENT but test the SAME concept
- Use proper LaTeX formatting
- Target the specific error/weakness shown"""

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

        practice_questions = json.loads(result_text)

        return jsonify({'practice_questions': practice_questions})

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 Math OCR Analyzer Starting...")
    print("=" * 60)
    if not OPENAI_API_KEY:
        print("\n⚠️  WARNING: OpenAI API key not found!")
        print("   Please set the OPENAI_API_KEY environment variable.\n")
    else:
        print("\n✅ API Key configured")
    print("\n📱 Access the app at: http://localhost:5000")
    print("📱 ngrok URL will also work once you run ngrok!")
    print("=" * 60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
