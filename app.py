from flask import Flask, render_template, request, jsonify
import html
import parser        # your dispatcher (Python + auto-detect)
import java_parser   # ✅ added for Java support

app = Flask(__name__, static_folder='static', template_folder='templates')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate_mermaid', methods=['POST'])
def generate_mermaid():
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        payload = request.get_json(force=True)
        code = payload.get('code', '')

        if not code.strip():
            return jsonify({"error": "No code provided"}), 400

        # Auto-detect language and generate flowchart
        mermaid = parser.flowchart_from_input(code)
        return jsonify({'mermaid_syntax': mermaid})

    except Exception as e:
        error = html.escape(str(e))
        fallback = f'graph TD\nError["Server Error"] --> Msg["{error}"]'
        return jsonify({'error': str(e), 'mermaid_syntax': fallback}), 500


if __name__ == '__main__':
    app.run(debug=True)
