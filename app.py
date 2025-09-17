from flask import Flask, render_template, request, redirect, url_for, jsonify
import csv
import os
import qrcode
import io
import base64
from datetime import datetime
# Removed pandas and plotly for simpler Vercel deployment
import sqlite3
import tempfile

app = Flask(__name__)

# Survey questions configuration
SURVEY_QUESTIONS = {
    'mcq': [
        {
            'id': 'ai_adoption',
            'question': 'What is your organization\'s current level of AI adoption in finance operations?',
            'options': [
                'No AI adoption yet',
                'Pilot projects/early exploration',
                'Limited implementation in specific areas',
                'Widespread adoption across multiple functions',
                'Fully integrated AI-driven operations'
            ]
        },
        {
            'id': 'ai_impact',
            'question': 'How do you expect AI to impact the finance industry in the next 3-5 years?',
            'options': [
                'Minimal impact - traditional methods will remain dominant',
                'Moderate impact - AI will supplement existing processes',
                'Significant impact - AI will transform many finance functions',
                'Revolutionary impact - AI will fundamentally reshape the industry',
                'Uncertain/Too early to tell'
            ]
        },
        {
            'id': 'biggest_concern',
            'question': 'What is your biggest concern regarding AI implementation in finance?',
            'options': [
                'Data security and privacy risks',
                'Regulatory compliance and governance',
                'Job displacement and workforce impact',
                'Accuracy and reliability of AI decisions',
                'Cost of implementation and ROI uncertainty',
                'Lack of technical expertise/skills gap'
            ]
        }
    ],
    'free_response': [
        {
            'id': 'ai_opportunities',
            'question': 'What specific opportunities do you see for AI in your finance operations? (Please describe in detail)'
        },
        {
            'id': 'implementation_barriers',
            'question': 'What are the main barriers preventing or slowing down AI adoption in your organization? (Please explain)'
        }
    ]
}

# Database setup
DB_FILE = os.path.join(tempfile.gettempdir(), 'survey.db')

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ai_adoption TEXT NOT NULL,
            ai_impact TEXT NOT NULL,
            biggest_concern TEXT NOT NULL,
            ai_opportunities TEXT NOT NULL,
            implementation_barriers TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def save_response(data):
    """Save survey response to database"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO responses (timestamp, ai_adoption, ai_impact, biggest_concern, ai_opportunities, implementation_barriers)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        timestamp,
        data.get('ai_adoption', ''),
        data.get('ai_impact', ''),
        data.get('biggest_concern', ''),
        data.get('ai_opportunities', ''),
        data.get('implementation_barriers', '')
    ))
    
    conn.commit()
    conn.close()

def get_responses():
    """Get all survey responses from database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM responses ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    
    columns = ['id', 'timestamp', 'ai_adoption', 'ai_impact', 'biggest_concern', 'ai_opportunities', 'implementation_barriers']
    responses = [dict(zip(columns, row)) for row in rows]
    
    conn.close()
    return responses

def generate_qr_code():
    """Generate QR code for the survey URL"""
    # For Vercel deployment, use the request host
    try:
        from flask import request
        if request and request.host:
            if 'vercel.app' in request.host:
                survey_url = f"https://{request.host}/"
            else:
                survey_url = f"http://{request.host}/"
        else:
            survey_url = "https://your-survey.vercel.app/"
    except:
        # Fallback for local development
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            survey_url = f"http://{local_ip}:8080/"
        except:
            survey_url = "http://localhost:8080/"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(survey_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding in HTML
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

@app.route('/')
def survey():
    """Main survey page"""
    qr_code = generate_qr_code()
    return render_template('survey.html', questions=SURVEY_QUESTIONS, qr_code=qr_code)

@app.route('/submit', methods=['POST'])
def submit_survey():
    """Handle survey submission"""
    try:
        # Validate required fields
        required_fields = ['ai_adoption', 'ai_impact', 'biggest_concern', 'ai_opportunities', 'implementation_barriers']
        for field in required_fields:
            if not request.form.get(field):
                return render_template('error.html', message=f"Please fill in all required fields. Missing: {field.replace('_', ' ').title()}")
        
        # Save response
        save_response(request.form.to_dict())
        return render_template('thank_you.html')
    except Exception as e:
        return render_template('error.html', message=f"An error occurred: {str(e)}")

@app.route('/dashboard')
def dashboard():
    """Survey results dashboard"""
    try:
        responses = get_responses()
        
        if not responses:
            return render_template('dashboard.html', message="No survey responses yet.", stats=None)
        
        # Calculate statistics manually without pandas
        total_responses = len(responses)
        latest_response = responses[0]['timestamp'] if responses else "No responses yet"
        
        # Count responses for each category
        adoption_counts = {}
        impact_counts = {}
        concern_counts = {}
        
        # Collect free responses for highlights
        opportunities = []
        barriers = []
        
        for response in responses:
            # AI Adoption counts
            adoption = response['ai_adoption']
            adoption_counts[adoption] = adoption_counts.get(adoption, 0) + 1
            
            # AI Impact counts  
            impact = response['ai_impact']
            impact_counts[impact] = impact_counts.get(impact, 0) + 1
            
            # Concern counts
            concern = response['biggest_concern']
            concern_counts[concern] = concern_counts.get(concern, 0) + 1
            
            # Collect free responses
            if response['ai_opportunities'].strip():
                opportunities.append(response['ai_opportunities'].strip())
            if response['implementation_barriers'].strip():
                barriers.append(response['implementation_barriers'].strip())
        
        # Get top/featured responses (you can modify this logic)
        featured_opportunities = opportunities[:3] if opportunities else []
        featured_barriers = barriers[:3] if barriers else []
        
        stats = {
            'total_responses': total_responses,
            'latest_response': latest_response,
            'adoption_counts': adoption_counts,
            'impact_counts': impact_counts,
            'concern_counts': concern_counts,
            'featured_opportunities': featured_opportunities,
            'featured_barriers': featured_barriers
        }
        
        return render_template('dashboard.html', stats=stats, message="")
        
    except Exception as e:
        return render_template('dashboard.html', message=f"Error loading dashboard: {str(e)}", stats=None)

@app.route('/responses')
def view_responses():
    """View raw survey responses"""
    try:
        responses = get_responses()
        return render_template('responses.html', responses=responses)
    except Exception as e:
        return jsonify({"error": str(e)})

# Initialize database on startup
init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)