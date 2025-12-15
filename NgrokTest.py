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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        .container {
            width: 95%;
            max-width: 1200px;
            height: 95vh;
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
        .header-buttons { display: flex; gap: 10px; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .btn-questions { background: white; color: #667eea; }
        .btn-questions:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .btn-answers { background: #fbbf24; color: #78350f; }
        .btn-answers:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(251,191,36,0.4); }
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
            background: #f8fafc;
        }
        .message { margin-bottom: 20px; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
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
        .accordion {
            background: white;
            color: #667eea;
            cursor: pointer;
            padding: 18px;
            width: 100%;
            text-align: left;
            border: none;
            outline: none;
            transition: 0.4s;
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 10px;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }
        .accordion.active, .accordion:hover {
            background: #667eea;
            color: white;
        }
        .panel {
            padding: 20px;
            display: none;
            background: white;
            overflow: hidden;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }
        .question-text {
            color: #1e293b;
            font-size: 16px;
            margin-bottom: 15px;
            line-height: 1.8;
        }
        .section-title {
            color: #64748b;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            margin: 15px 0 10px 0;
            letter-spacing: 0.5px;
        }
        .student-solution {
            background: #fef3c7;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            white-space: pre-wrap;
            line-height: 2;
        }
        .error-analysis {
            background: #fee2e2;
            padding: 15px;
            border-radius: 8px;
            color: #991b1b;
            margin-bottom: 15px;
            font-weight: 500;
            line-height: 1.8;
        }
        .correct-solution {
            background: #d1fae5;
            padding: 15px;
            border-radius: 8px;
            line-height: 2.2;
            font-size: 15px;
        }
        .practice-paper {
            background: white;
            padding: 50px;
            margin: 30px 0;
            border: 2px solid #7c3aed;
            border-radius: 12px;
        }
        .practice-title {
            color: #7c3aed;
            font-size: 28px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 50px;
        }
        .practice-question {
            margin-bottom: 70px;
        }
        .question-number {
            color: #667eea;
            font-weight: 700;
            font-size: 20px;
            margin-bottom: 15px;
        }
        .practice-footer {
            text-align: center;
            margin-top: 60px;
            color: #64748b;
            font-style: italic;
            font-size: 14px;
        }
        .download-btn {
            background: #7c3aed;
            color: white;
            padding: 12px 30px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            margin: 40px auto 0;
            display: block;
        }
        .download-btn:hover { background: #6d28d9; }
        .file-upload { display: flex; gap: 10px; flex-wrap: wrap; margin: 10px 0; }
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
        .input-wrapper { flex: 1; display: flex; gap: 10px; }
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
        .start-btn:disabled { background: #cbd5e1; cursor: not-allowed; }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f4f6;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .confirm-prompt {
            background: #fef3c7;
            padding: 20px;
            border-radius: 12px;
            margin: 20px 0;
            border-left: 5px solid #f59e0b;
        }
        .confirm-buttons { display: flex; gap: 10px; margin-top: 15px; }
        .btn-yes { background: #10b981; color: white; }
        .btn-yes:hover { background: #059669; }
        .btn-no { background: #ef4444; color: white; }
        .btn-no:hover { background: #dc2626; }
        .MathJax { font-size: 1.1em !important; }
        mjx-container { display: inline-block; margin: 0 2px; }
        @media print {
            body * { visibility: hidden; }
            .practice-paper, .practice-paper * { visibility: visible; }
            .practice-paper { position: absolute; left: 0; top: 0; width: 100%; padding: 50px; border: none; box-shadow: none; background: white; }
            .download-btn { display: none; }
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
        let practiceBlock = null;

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

        function renderMath(el = document) {
            if (window.MathJax && window.MathJax.typesetPromise) {
                window.MathJax.typesetPromise([el]).catch(err => console.log('MathJax error:', err));
            }
        }

        function typeWriter(el, text, speed = 10, callback) {
            let i = 0;
            el.innerHTML = '';
            const interval = setInterval(() => {
                if (i < text.length) {
                    el.innerHTML += text.charAt(i);
                    i++;
                } else {
                    clearInterval(interval);
                    renderMath(el);
                    if (callback) callback();
                }
            }, speed);
        }

        async function startAnalysis() {
            if (uploadedFiles.length === 0) return;
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
                const response = await fetch('/analyze', { method: 'POST', body: formData });
                const result = await response.json();
                loadingMsg.remove();
                if (result.error) {
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'message system';
                    errorMsg.innerHTML = `<strong>Error:</strong> ${result.error}`;
                    chatArea.appendChild(errorMsg);
                } else {
                    analysisResult = result;
                    displayAnalysis(result);
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
        }

        function displayAnalysis(result) {
            const chatArea = document.getElementById('chatArea');
            result.questions.forEach(q => {
                const accordion = document.createElement('button');
                accordion.className = 'accordion';
                accordion.textContent = `Question ${q.number}`;
                const panel = document.createElement('div');
                panel.className = 'panel';

                chatArea.appendChild(accordion);
                chatArea.appendChild(panel);

                accordion.addEventListener('click', function() {
                    this.classList.toggle('active');
                    if (panel.style.display === 'block') {
                        panel.style.display = 'none';
                    } else {
                        panel.style.display = 'block';
                        if (panel.innerHTML === '') {
                            const questionDiv = document.createElement('div');
                            questionDiv.className = 'question-text';

                            const studentTitle = document.createElement('div');
                            studentTitle.className = 'section-title';
                            studentTitle.textContent = "Student's Solution (Original)";
                            const studentDiv = document.createElement('div');
                            studentDiv.className = 'student-solution';

                            const errorTitle = document.createElement('div');
                            errorTitle.className = 'section-title';
                            errorTitle.textContent = "Error Analysis";
                            const errorDiv = document.createElement('div');
                            errorDiv.className = 'error-analysis';

                            const correctTitle = document.createElement('div');
                            correctTitle.className = 'section-title';
                            correctTitle.textContent = "Correct Solution";
                            const correctDiv = document.createElement('div');
                            correctDiv.className = 'correct-solution';

                            panel.appendChild(questionDiv);
                            panel.appendChild(studentTitle);
                            panel.appendChild(studentDiv);
                            panel.appendChild(errorTitle);
                            panel.appendChild(errorDiv);
                            panel.appendChild(correctTitle);
                            panel.appendChild(correctDiv);

                            typeWriter(questionDiv, q.question, 10, () => {
                                renderMath(panel);
                                typeWriter(studentDiv, q.student_original, 10, () => {
                                    renderMath(panel);
                                    typeWriter(errorDiv, q.error, 10, () => {
                                        renderMath(panel);
                                        typeWriter(correctDiv, q.correct_solution, 10, () => {
                                            renderMath(panel);
                                        });
                                    });
                                });
                            });
                        }
                    }
                });
            });

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
                    practiceBlock = document.createElement('div');
                    practiceBlock.className = 'practice-paper';

                    const titleDiv = document.createElement('div');
                    titleDiv.className = 'practice-title';
                    titleDiv.textContent = '📝 Practice Paper';
                    practiceBlock.appendChild(titleDiv);

                    const textDivs = [];
                    result.practice_questions.forEach(pq => {
                        const qBlock = document.createElement('div');
                        qBlock.className = 'practice-question';

                        const numDiv = document.createElement('div');
                        numDiv.className = 'question-number';
                        numDiv.textContent = `Question ${pq.number}`;

                        const textDiv = document.createElement('div');
                        textDiv.className = 'question-text';

                        qBlock.appendChild(numDiv);
                        qBlock.appendChild(textDiv);
                        practiceBlock.appendChild(qBlock);
                        textDivs.push(textDiv);
                    });

                    const footerDiv = document.createElement('div');
                    footerDiv.className = 'practice-footer';
                    footerDiv.textContent = 'Generated by CAS Educations';
                    practiceBlock.appendChild(footerDiv);

                    const downloadBtn = document.createElement('button');
                    downloadBtn.className = 'download-btn';
                    downloadBtn.textContent = '📥 Download Practice Paper as PDF';
                    downloadBtn.onclick = downloadPracticePDF;
                    practiceBlock.appendChild(downloadBtn);

                    chatArea.appendChild(practiceBlock);

                    let index = 0;
                    function typeNext() {
                        if (index < textDivs.length) {
                            typeWriter(textDivs[index], result.practice_questions[index].question, 10, typeNext);
                            index++;
                        } else {
                            setTimeout(() => renderMath(practiceBlock), 1000);
                        }
                    }
                    typeNext();
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

        async function downloadPracticePDF() {
            if (!practiceBlock) return;

            await MathJax.typesetPromise([practiceBlock]);

            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            const margin = 15;
            const pdfWidth = pageWidth - 2 * margin;
            const pdfHeight = pageHeight - 2 * margin;

            const canvas = await html2canvas(practiceBlock, {
                scale: 2,
                useCORS: true,
                backgroundColor: '#ffffff'
            });

            const canvasWidth = canvas.width;
            const canvasHeight = canvas.height;
            const ratio = pdfWidth / canvasWidth;
            const totalPdfHeight = canvasHeight * ratio;

            let printedHeight = 0;

            while (printedHeight < totalPdfHeight) {
                pdf.addPage();
                const remainingPdfHeight = totalPdfHeight - printedHeight;
                const currentPdfHeight = Math.min(remainingPdfHeight, pdfHeight);

                const sourceY = printedHeight / ratio;
                const sourceHeight = currentPdfHeight / ratio;

                pdf.addImage(canvas, 'PNG', margin, margin, pdfWidth, currentPdfHeight, undefined, 'FAST', 0, sourceY, canvasWidth, sourceHeight);
                printedHeight += currentPdfHeight;
            }

            pdf.save('Practice_Paper.pdf');
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
                    "text": f"[PDF file: {file.filename} - Content extraction not implemented]"
                })

        prompt = f"""Extract and analyze math problems from the uploaded {"questions" if view == "questions" else "answers"}.

IMPORTANT: Preserve the EXACT original question number format (e.g., 1, 2(a), Q.5, 3b, etc.). Do NOT normalize to plain numbers.

CRITICAL FORMATTING RULES:
- Use $ for inline LaTeX, $$ for display.
- student_original: Transcribe exactly but wrap math in LaTeX.
- error: Short description or 'No error - solution is correct'.
- correct_solution: Step-by-step with <br> between steps.

Return JSON array:
[
  {{
    "number": "EXACT original number string",
    "question": "question with LaTeX",
    "student_original": "student work with LaTeX",
    "error": "...",
    "correct_solution": "..."
  }}
]
"""

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + file_contents}],
            max_tokens=9000,
            temperature=0.2
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith('```json'): result_text = result_text[7:]
        if result_text.endswith('```'): result_text = result_text[:-3]
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
            return jsonify({'error': 'OpenAI API key not configured.'})

        data = request.json
        analysis = data.get('analysis', {})
        questions = analysis.get('questions', [])
        error_questions = [q for q in questions if 'no error' not in q.get('error', '').lower()]

        if not error_questions:
            return jsonify({'practice_questions': []})

        client = OpenAI(api_key=api_key)

        prompt = f"""Generate clean practice questions (NO hints, NO solutions, NO answers - only the question) for these mistaken problems:
{json.dumps(error_questions, indent=2)}

Return JSON array:
[
  {{
    "number": "USE THE EXACT SAME ORIGINAL NUMBER STRING",
    "question": "new similar question with full LaTeX formatting"
  }}
]

Rules:
- Preserve exact original number format.
- Create different but similar questions targeting the error.
- Pure question paper style - only the question text.
"""

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.7
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith('```json'): result_text = result_text[7:]
        if result_text.endswith('```'): result_text = result_text[:-3]
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
        print("\n⚠️ WARNING: OpenAI API key not found!")
        print(" Please set the OPENAI_API_KEY environment variable.\n")
    else:
        print("\n✅ API Key configured")
    print("\n📱 Access the app at: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
