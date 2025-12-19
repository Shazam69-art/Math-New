from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import os
import base64
import json
from openai import OpenAI
from flask_session import Session

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session security
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# ============ NGROK FIX ============
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
# ===================================

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Math OCR Analysis</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
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
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            padding: 40px;
        }
        .login-title {
            text-align: center;
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 30px;
            color: #000000;
        }
        .input-group {
            position: relative;
            margin-bottom: 20px;
        }
        .input-group input {
            width: 100%;
            padding: 12px 40px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        .input-group input:focus {
            border-color: #3b82f6;
        }
        .input-icon {
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: #6b7280;
            font-size: 18px;
        }
        .auth-options {
            margin-top: 30px;
        }
        .auth-btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 10px;
            transition: background 0.3s;
        }
        .google-btn {
            background: #4285f4;
            color: #ffffff;
        }
        .google-btn:hover {
            background: #357ae8;
        }
        .apple-btn {
            background: #000000;
            color: #ffffff;
            display: none;
        }
        .apple-btn:hover {
            background: #333333;
        }
        .toggle-apple {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 10px;
        }
        .toggle-apple input {
            margin-right: 8px;
        }
        .toggle-apple label {
            color: #000000;
            font-size: 14px;
        }
        .login-btn {
            width: 100%;
            padding: 12px;
            background: #3b82f6;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
            margin-top: 20px;
        }
        .login-btn:hover {
            background: #2563eb;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1 class="login-title">Login to Math OCR Analysis</h1>
        <form action="/login" method="POST">
            <div class="input-group">
                <span class="input-icon">📧</span>
                <input type="email" name="email" placeholder="Email" required>
            </div>
            <div class="input-group">
                <span class="input-icon">🔒</span>
                <input type="password" name="password" placeholder="Password" required>
            </div>
            <button type="submit" class="login-btn">Login</button>
        </form>
        <div class="auth-options">
            <button class="auth-btn google-btn" onclick="alert('Google authentication not implemented in this demo')">Login with Google</button>
            <div class="toggle-apple">
                <input type="checkbox" id="apple-toggle" onclick="toggleApple()">
                <label for="apple-toggle">Show Apple Login</label>
            </div>
            <button class="auth-btn apple-btn" id="apple-btn" onclick="alert('Apple authentication not implemented in this demo')">Login with Apple</button>
        </div>
    </div>
    <script>
        function toggleApple() {
            const appleBtn = document.getElementById('apple-btn');
            appleBtn.style.display = document.getElementById('apple-toggle').checked ? 'block' : 'none';
        }
    </script>
</body>
</html>
'''

MAIN_HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Math OCR Analysis</title>
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
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
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            padding: 20px 30px;
            display: flex;
            justify-content: center;
            align-items: center;
            border-bottom: 1px solid #e5e7eb;
        }
        .header h1 { font-size: 24px; font-weight: 600; color: #000000; }
        .welcome-msg {
            text-align: center;
            padding: 20px;
            font-size: 18px;
            color: #000000;
        }
        .upload-area {
            display: flex;
            justify-content: center;
            gap: 20px;
            padding: 20px;
        }
        .upload-btn {
            background: #f3f4f6;
            color: #000000;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.3s;
            border: 1px solid #d1d5db;
        }
        .upload-btn:hover { background: #e5e7eb; }
        input[type="file"] { display: none; }
        .file-display {
            text-align: center;
            padding: 10px;
            color: #000000;
        }
        .start-btn {
            display: block;
            margin: 20px auto;
            background: #3b82f6;
            color: #ffffff;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 15px;
            cursor: pointer;
            transition: background 0.3s;
        }
        .start-btn:hover { background: #2563eb; }
        .start-btn:disabled {
            background: #d1d5db;
            cursor: not-allowed;
        }
        .analysis-container {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
            background: #ffffff;
            color: #000000;
        }
        .question-dropdown {
            background: #ffffff;
            margin: 15px 0;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            overflow: hidden;
        }
        .question-header {
            background: #f3f4f6;
            color: #000000;
            padding: 18px 25px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.3s;
        }
        .question-header:hover {
            background: #e5e7eb;
        }
        .question-header-title {
            font-size: 18px;
            font-weight: 700;
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
            background: #ffffff;
        }
        .question-content.open {
            max-height: 5000px;
            transition: max-height 0.5s ease-in;
        }
        .question-inner {
            padding: 25px;
            color: #000000;
            line-height: 1.6;
        }
        .section-title {
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            margin: 20px 0 12px 0;
            color: #000000;
        }
        .student-solution, .error-analysis, .correct-solution {
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            white-space: pre-wrap;
            line-height: 1.6;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            color: #000000;
        }
        .practice-section {
            margin-top: 30px;
            text-align: center;
        }
        .generate-btn {
            background: #3b82f6;
            color: #ffffff;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }
        .generate-btn:hover { background: #2563eb; }
        .practice-paper {
            background: #ffffff;
            padding: 30px;
            margin: 30px 0;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
        }
        .practice-title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 20px;
            color: #000000;
        }
        .practice-question {
            padding: 20px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .practice-question:last-child {
            border-bottom: none;
        }
        .practice-question-number {
            color: #000000;
            font-weight: 700;
            font-size: 18px;
            margin-bottom: 12px;
        }
        .practice-question-text {
            color: #000000;
            font-size: 16px;
            line-height: 1.6;
        }
        .download-btn {
            display: block;
            margin: 20px auto;
            background: #10b981;
            color: #ffffff;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }
        .download-btn:hover { background: #059669; }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f4f6;
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
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
            <h1>Math OCR Analysis</h1>
        </div>
        <div class="welcome-msg" id="welcomeMsg">{{ welcome_message }}</div>
        <div class="upload-area">
            <label class="upload-btn" for="questionsInput">Upload Questions File</label>
            <input type="file" id="questionsInput" accept="image/*,.pdf">
            <label class="upload-btn" for="answersInput">Upload Answers File</label>
            <input type="file" id="answersInput" accept="image/*,.pdf">
        </div>
        <div class="file-display" id="fileDisplay"></div>
        <button class="start-btn" id="startBtn" onclick="startAnalysis()" disabled>Start Analysis</button>
        <div class="analysis-container" id="analysisContainer"></div>
    </div>
    <script>
        let questionsFile = null;
        let answersFile = null;
        let analysisResult = null;

        document.getElementById('questionsInput').addEventListener('change', function(e) {
            questionsFile = e.target.files[0];
            updateFileDisplay();
        });

        document.getElementById('answersInput').addEventListener('change', function(e) {
            answersFile = e.target.files[0];
            updateFileDisplay();
        });

        function updateFileDisplay() {
            const display = document.getElementById('fileDisplay');
            display.innerHTML = '';
            if (questionsFile) {
                display.innerHTML += `<p>Questions: ${questionsFile.name}</p>`;
            }
            if (answersFile) {
                display.innerHTML += `<p>Answers: ${answersFile.name}</p>`;
            }
            document.getElementById('startBtn').disabled = !(questionsFile && answersFile);
        }

        function renderMath(element) {
            if (window.MathJax && window.MathJax.typesetPromise) {
                window.MathJax.typesetPromise([element]).catch((err) => console.log('MathJax render error:', err));
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
                        await new Promise(resolve => setTimeout(resolve, speed));
                    }
                }
            }
            renderMath(element);
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

        async function startAnalysis() {
            if (!questionsFile || !answersFile) return;
            const container = document.getElementById('analysisContainer');
            container.innerHTML = '<p class="loading">Analyzing...</p>';
            const formData = new FormData();
            formData.append('questions', questionsFile);
            formData.append('answers', answersFile);
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                container.innerHTML = '';
                if (result.error) {
                    container.innerHTML = `<p>Error: ${result.error}</p>`;
                } else {
                    analysisResult = result;
                    await displayAnalysisWithTyping(result);
                }
            } catch (error) {
                container.innerHTML = `<p>Error: ${error.message}</p>`;
            }
        }

        async function displayAnalysisWithTyping(result) {
            const container = document.getElementById('analysisContainer');
            for (let i = 0; i < result.questions.length; i++) {
                const q = result.questions[i];
                const qBlock = document.createElement('div');
                qBlock.className = 'question-dropdown';
                qBlock.innerHTML = `
                    <div class="question-header" onclick="toggleDropdown(${i})">
                        <div class="question-header-title">Question ${q.number}</div>
                        <span class="dropdown-arrow" id="arrow-${i}">▼</span>
                    </div>
                    <div class="question-content" id="question-content-${i}">
                        <div class="question-inner">
                            <div class="section-title">Question Text</div>
                            <div id="q-text-${i}"></div>
                            <div class="section-title">Student's Solution</div>
                            <div class="student-solution" id="q-student-${i}"></div>
                            <div class="section-title">Error Analysis</div>
                            <div class="error-analysis" id="q-error-${i}"></div>
                            <div class="section-title">Correct Solution</div>
                            <div class="correct-solution" id="q-correct-${i}"></div>
                        </div>
                    </div>
                `;
                container.appendChild(qBlock);
                // Open by default
                document.getElementById(`question-content-${i}`).classList.add('open');
                document.getElementById(`arrow-${i}`).classList.add('open');
                await typeText(document.getElementById(`q-text-${i}`), q.question);
                await typeText(document.getElementById(`q-student-${i}`), q.student_original);
                await typeText(document.getElementById(`q-error-${i}`), q.error);
                await typeText(document.getElementById(`q-correct-${i}`), q.correct_solution);
            }
            // Add generate practice prompt and button
            const practiceSection = document.createElement('div');
            practiceSection.className = 'practice-section';
            practiceSection.innerHTML = `
                <p>Would you like to generate a practice question paper?</p>
                <button class="generate-btn" onclick="generatePractice()">Generate Practice Paper</button>
            `;
            container.appendChild(practiceSection);
        }

        async function generatePractice() {
            const container = document.getElementById('analysisContainer');
            const practiceSection = document.querySelector('.practice-section');
            practiceSection.innerHTML = '<p class="loading">Generating practice paper...</p>';
            try {
                const response = await fetch('/generate_practice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ analysis: analysisResult })
                });
                const result = await response.json();
                practiceSection.remove();
                if (result.practice_questions && result.practice_questions.length > 0) {
                    const practiceBlock = document.createElement('div');
                    practiceBlock.className = 'practice-paper';
                    practiceBlock.id = 'practicePaper';
                    practiceBlock.innerHTML = `
                        <div class="practice-title">Practice Paper</div>
                        <div id="practice-questions-container"></div>
                    `;
                    container.appendChild(practiceBlock);
                    const pqContainer = document.getElementById('practice-questions-container');
                    for (const pq of result.practice_questions) {
                        const pqDiv = document.createElement('div');
                        pqDiv.className = 'practice-question';
                        pqDiv.innerHTML = `
                            <div class="practice-question-number">Question ${pq.number}</div>
                            <div class="practice-question-text" id="practice-q-${pq.number}"></div>
                        `;
                        pqContainer.appendChild(pqDiv);
                        await typeText(document.getElementById(`practice-q-${pq.number}`), pq.question);
                    }
                    // Add download button
                    const downloadBtn = document.createElement('button');
                    downloadBtn.className = 'download-btn';
                    downloadBtn.innerText = 'Download as PDF';
                    downloadBtn.onclick = downloadPDF;
                    container.appendChild(downloadBtn);
                } else {
                    container.innerHTML += '<p>No mistakes found, no practice paper needed.</p>';
                }
            } catch (error) {
                practiceSection.innerHTML = `<p>Error: ${error.message}</p>`;
            }
        }

        function downloadPDF() {
            const element = document.getElementById('practicePaper');
            const opt = {
                margin:       1,
                filename:     'practice_paper.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2 },
                jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
            };
            html2pdf().set(opt).from(element).save();
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('main'))
    return render_template_string(LOGIN_HTML)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    # Mock authentication - in real app, validate credentials
    if email and password:  # Simple check
        session['email'] = email
        return redirect(url_for('main'))
    return redirect(url_for('index'))

@app.route('/main')
def main():
    if 'email' not in session:
        return redirect(url_for('index'))
    email_prefix = session['email'].split('@')[0].capitalize()
    welcome_message = f'Welcome {email_prefix}'
    return render_template_string(MAIN_HTML_TEMPLATE, welcome_message=welcome_message)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        api_key = OPENAI_API_KEY
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.'})
        questions_file = request.files.get('questions')
        answers_file = request.files.get('answers')
        if not questions_file or not answers_file:
            return jsonify({'error': 'Both questions and answers files are required'})
        client = OpenAI(api_key=api_key)
        questions_content = []
        answers_content = []
        # Process questions file
        if questions_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            encoded = base64.b64encode(questions_file.read()).decode('utf-8')
            questions_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}
            })
        elif questions_file.filename.lower().endswith('.pdf'):
            questions_content.append({
                "type": "text",
                "text": f"[PDF file: {questions_file.filename} - Content extraction not implemented in this demo]"
            })
        # Process answers file
        if answers_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            encoded = base64.b64encode(answers_file.read()).decode('utf-8')
            answers_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}
            })
        elif answers_file.filename.lower().endswith('.pdf'):
            answers_content.append({
                "type": "text",
                "text": f"[PDF file: {answers_file.filename} - Content extraction not implemented in this demo]"
            })
        prompt = """Extract math questions from the questions file and student solutions from the answers file. Analyze them accordingly.
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
LaTeX Examples:
- Fractions: $\\frac{a}{b}$ or $\\dfrac{a}{b}$
- Integrals: $\\int f(x)\\,dx$ or $\\displaystyle\\int f(x)\\,dx$
- Square roots: $\\sqrt{x}$ or $\\sqrt[n]{x}$
- Exponents: $x^2$ or $x^{2n}$
- Trigonometry: $\\sin x$, $\\cos x$, $\\tan x$, $\\sec x$
- Greek letters: $\\pi$, $\\theta$, $\\alpha$
- Inverse trig: $\\sin^{-1} x$ or $\\arcsin x$
- Limits: $\\lim_{x\\to 0}$
Rules:
- Use EXACT question numbers from the images
- student_original must be VERBATIM
- Flag blank/partial/incorrect solutions as errors
- In correct_solution, use <br> between steps
- Each step should be complete
- Pair questions and answers by number"""
        response = client.chat.completions.create(
            model="gpt-4o",  # Updated to a valid model; gpt-5.1 doesn't exist yet
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + questions_content + answers_content
            }],
            max_tokens=4096,
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
4. Format ALL math using LaTeX: $x^2$, $\\frac{a}{b}$, $\\int$, etc.
Return a JSON array with this structure:
[{{"number": "exact_original_question_number", "question": "modified question with $LaTeX$ formatting targeting same concept"}}]
Rules:
- Use EXACT question numbers from originals (e.g., if original was "7", use "7")
- Questions should be DIFFERENT but test the SAME concept
- Use proper LaTeX formatting
- Target the specific error/weakness shown"""
        response = client.chat.completions.create(
            model="gpt-4o",  # Updated to a valid model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
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
    print("🚀 Math OCR Analysis Starting...")
    print("=" * 60)
    if not OPENAI_API_KEY:
        print("\n⚠️ WARNING: OpenAI API key not found!")
        print(" Please set the OPENAI_API_KEY environment variable.\n")
    else:
        print("\n✅ API Key configured")
    print("\n📱 Access the app at: http://localhost:5000")
    print("📱 ngrok URL will also work once you run ngrok!")
    print("=" * 60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
