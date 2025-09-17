from flask import Flask, render_template, request, redirect, url_for, jsonify
import csv
import os
import qrcode
import io
import base64
from datetime import datetime
import pandas as pd
import plotly.graph_objs as go
import plotly.utils
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

# Database setup for Vercel
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
    # For Vercel deployment, use the deployed URL
    if os.getenv('VERCEL_URL'):
        survey_url = f"https://{os.getenv('VERCEL_URL')}/"
    else:
        # Local development - use network IP
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
            return render_template('dashboard.html', message="No survey responses yet.", charts=[])
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(responses)
        
        charts = []
        
        # Chart 1: AI Adoption Levels
        adoption_counts = df['ai_adoption'].value_counts()
        fig1 = go.Figure(data=[go.Bar(x=adoption_counts.index, y=adoption_counts.values)])
        fig1.update_layout(
            title='Current AI Adoption Levels',
            xaxis_title='Adoption Level',
            yaxis_title='Number of Responses',
            template='plotly_white'
        )
        charts.append({
            'title': 'AI Adoption Levels',
            'chart': plotly.utils.PlotlyJSONEncoder().encode(fig1)
        })
        
        # Chart 2: Expected AI Impact
        impact_counts = df['ai_impact'].value_counts()
        fig2 = go.Figure(data=[go.Pie(labels=impact_counts.index, values=impact_counts.values)])
        fig2.update_layout(
            title='Expected AI Impact in Next 3-5 Years',
            template='plotly_white'
        )
        charts.append({
            'title': 'Expected AI Impact',
            'chart': plotly.utils.PlotlyJSONEncoder().encode(fig2)
        })
        
        # Chart 3: Biggest Concerns
        concern_counts = df['biggest_concern'].value_counts()
        fig3 = go.Figure(data=[go.Bar(x=concern_counts.values, y=concern_counts.index, orientation='h')])
        fig3.update_layout(
            title='Biggest Concerns About AI Implementation',
            xaxis_title='Number of Responses',
            yaxis_title='Concerns',
            template='plotly_white',
            height=400
        )
        charts.append({
            'title': 'Biggest Concerns',
            'chart': plotly.utils.PlotlyJSONEncoder().encode(fig3)
        })
        
        # Summary statistics
        total_responses = len(df)
        latest_response = df['timestamp'].max() if not df.empty else "No responses yet"
        
        return render_template('dashboard.html', 
                             charts=charts, 
                             total_responses=total_responses,
                             latest_response=latest_response,
                             message="")
        
    except Exception as e:
        return render_template('dashboard.html', message=f"Error loading dashboard: {str(e)}", charts=[])

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